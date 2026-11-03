"""File level operations: merge, split, batch generation, listing import."""
from __future__ import annotations

import copy
import os
from typing import Iterable, List, Optional

from . import ber, builder, generator, tapfile
from .tapfile import Tap3Document, _int_bytes, _int_value


class OpsError(ValueError):
    pass


def _events_node(doc: Tap3Document) -> ber.BerNode:
    node = doc.event_list_node()
    if node is None:
        raise OpsError("file has no callEventDetails list")
    return node


def _recompute_audit(doc: Tap3Document) -> None:
    events = doc.events()
    total = 0
    for ev in events:
        stack = [ev]
        while stack:
            n = stack.pop()
            if n.name == "charge" and not n.constructed:
                v = _int_value(n)
                if v:
                    total += v
            stack.extend(n.children)
    audit = None
    for c in doc.root.children:
        if c.name == "auditControlInfo":
            audit = c
    if audit is None:
        return
    for c in audit.children:
        if c.name == "callEventDetailsCount":
            c.payload = _int_bytes(len(events))
        elif c.name == "totalCharge":
            c.payload = _int_bytes(total)
    doc._redecode_annotate()


def merge_documents(docs: List[Tap3Document]) -> Tap3Document:
    if not docs:
        raise OpsError("nothing to merge")
    base = docs[0]
    releases = {d.release for d in docs}
    if len(releases) > 1:
        raise OpsError(f"cannot merge different TAP3 releases: {sorted(releases)}")
    target = _events_node(base)
    for other in docs[1:]:
        for ev in other.events():
            target.children.append(copy.deepcopy(ev))
    _recompute_audit(base)
    base.dirty = True
    return base


def split_document(doc: Tap3Document, out_prefix: str, chunk: int = 1000,
                   start_seq: Optional[int] = None) -> List[str]:
    events = doc.events()
    if not events:
        raise OpsError("no events to split")
    chunk = max(1, chunk)
    src_list = _events_node(doc)
    outputs: List[str] = []
    seq = start_seq if start_seq is not None else 0
    for i in range(0, len(events), chunk):
        part = copy.deepcopy(doc.root)
        part_list = part
        # find event list inside the copied tree by tag (APPLICATION 3)
        stack = [part]
        lst = None
        while stack:
            n = stack.pop()
            if n.tag_class == "APPLICATION" and n.tag_num == 3:
                lst = n
                break
            stack.extend(n.children)
        if lst is None:
            raise OpsError("internal: event list not found in copy")
        keep = events[i:i + chunk]
        lst.children = [copy.deepcopy(e) for e in keep]
        newdoc = Tap3Document(ber.encode_file(part), filename=f"{out_prefix}{i // chunk + 1}.tap3")
        if start_seq is not None:
            for n in newdoc.nodes.values():
                if n.name == "fileSequenceNumber":
                    n.payload = str(seq).zfill(5).encode("ascii")
                    break
            seq += 1
        _recompute_audit(newdoc)
        out = f"{out_prefix}{i // chunk + 1}.tap3"
        newdoc.save(out)
        outputs.append(out)
    return outputs


LIS_COLS = ["id", "type", "subscriber", "called", "calling", "start", "duration",
            "charge", "dataVolume", "causeForTerm"]


def import_listing(path: str) -> Tap3Document:
    """Import the fixed-width/pipe listing written by ``export_listing``.

    Rows carry the extracted record attributes only, so the importer rebuilds
    a schema-valid TAP3.11 skeleton and fills the values it can map back.
    """
    rows = []
    header = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("FILE|"):
                parts = line.split("|")
                if len(parts) >= 6:
                    header = {"sender": parts[4], "recipient": parts[5], "release": parts[3]}
            elif line.startswith("EV|"):
                parts = line.split("|")
                rows.append(dict(zip(LIS_COLS, parts[1:])))
    if not rows:
        raise OpsError("listing contains no EV rows")
    events = []
    for r in rows:
        et = r.get("type") or "mobileOriginatedCall"
        if et not in tapfile.EVENT_TYPES:
            et = "mobileOriginatedCall"
        events.append({et: {"operatorSpecInformation": [
            "imported", f"start={r.get('start','')}", f"charge={r.get('charge','')}"]}})
    spec = generator.build_spec(n_events=1, seed=1,
                                sender=header.get("sender") or "26201",
                                recipient=header.get("recipient") or "22801")
    spec["transferBatch"]["callEventDetails"] = events
    spec["transferBatch"]["auditControlInfo"]["callEventDetailsCount"] = len(events)
    module = tapfile.all_modules()["TAP0311.asn"]
    root = builder.build(module, "DataInterChange", spec)
    doc = Tap3Document(ber.encode_file(root), filename=os.path.basename(path))
    _recompute_audit(doc)
    return doc
