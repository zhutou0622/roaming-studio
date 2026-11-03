"""TAP3 document model: load, annotate, inspect, edit, export.

The class :class:`Tap3Document` is the heart of TAP3 Studio.  It keeps the
raw BER tree (byte-exact), an ASN.1 annotation layer derived from the TD.57
schema modules, and mutation helpers used by the web UI and CLI.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

from . import asn1model, ber, resources
from .asn1model import APPLICATION, UNIVERSAL, Module, Type

SCHEMA_DIR = resources.resource_path("tap3studio", "schema")

RELEASES = {1: "TAP3.01", 2: "TAP3.02", 3: "TAP3.03", 4: "TAP3.04", 9: "TAP3.09",
            10: "TAP3.10", 11: "TAP3.11", 12: "TAP3.12"}

BCD_TYPES = {"AddressStringDigits", "Imei", "Imsi", "Msisdn", "BcdString"}
NUMERIC_TYPES = {"NumberString", "LocalTimeStamp", "FileSequenceNumber", "RapFileSequenceNumber",
                 "ChargeType", "TaxRate", "Min", "Mdn", "Esn", "Bid", "PlmnId",
                 "NetworkId", "Iac", "CountryCode", "CalledCountryCode", "UtcTimeOffset",
                 "ServingNetwork", "AccessPointNameNI", "AccessPointNameOI", "ChargingPoint"}
HEX_TYPES = {"HexString", "TeleServiceCode", "BearerServiceCode", "SupplServiceCode",
             "DualTeleServiceCode", "DualBearerServiceCode", "CamelCallReferenceNumber"}
AMOUNT_TYPES = {"AbsoluteAmount", "Charge", "DiscountValue", "TaxValue", "TaxableAmount",
                "TotalCharge", "TotalChargeRefund", "TotalTaxValue", "TotalTaxRefund",
                "TotalDiscountValue", "TotalDiscountRefund", "Commission",
                "AdvisedCharge", "DiscountableAmount", "TotalAdvisedCharge"}

EVENT_TYPES = ["mobileOriginatedCall", "mobileTerminatedCall", "supplServiceEvent",
               "serviceCentreUsage", "valueAddedService", "gprsCall", "contentTransaction",
               "locationService"]


@lru_cache(maxsize=8)
def load_module(filename: str) -> Module:
    path = os.path.join(SCHEMA_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return asn1model.parse_module(text, filename)


@lru_cache(maxsize=1)
def all_modules() -> Dict[str, Module]:
    out = {}
    if not os.path.isdir(SCHEMA_DIR):
        return out
    for fn in sorted(os.listdir(SCHEMA_DIR)):
        if not fn.lower().endswith(".asn"):
            continue
        try:
            out[fn] = load_module(fn)
        except Exception:
            pass
    # RAP1 / NRTRDE modules IMPORT TAP types (Sender, Recipient, ...).
    # Merge the TAP3.11 definitions so those aliases resolve.
    base = out.get("TAP0311.asn")
    if base is not None:
        for fn, module in out.items():
            upper = fn.upper()
            if upper.startswith(("RAP", "NRT")):
                for name, tdef in base.types.items():
                    module.types.setdefault(name, tdef)
    return out


ROOT_TYPES = {"tap3": "DataInterChange", "rap": "RapDataInterChange", "nrtrde": "Nrtrde"}
KIND_LABELS = {"tap3": "TAP3", "rap": "RAP1", "nrtrde": "NRTRDE"}


def schema_specs() -> list:
    """Bundled schemas with kind, release number and root type."""
    specs = []
    for fn in all_modules():
        upper = fn.upper()
        if upper.startswith("TAP"):
            kind, rest = "tap3", upper[3:7]
        elif upper.startswith("RAP"):
            kind, rest = "rap", upper[3:7]
        elif upper.startswith("NRT"):
            kind, rest = "nrtrde", upper[3:7]
        else:
            continue
        try:
            release = int(rest[2:4])
        except ValueError:
            release = 0
        specs.append({"file": fn, "kind": kind, "release": release,
                      "root": ROOT_TYPES[kind]})
    specs.sort(key=lambda x: (x["kind"], x["release"]))
    return specs


def _alias_name(t: Optional[Type], module: Module) -> str:
    """Return the outermost type name for display (e.g. 'Charge')."""
    if t is None:
        return ""
    if t.def_name:
        return t.def_name
    if t.kind == "alias":
        return t.name
    return t.describe()


def bcd_to_digits(b: bytes) -> str:
    out = []
    for byte in b:
        hi, lo = byte >> 4, byte & 0x0F
        for nib in (hi, lo):
            if nib == 0xF:
                out.append("f")
            else:
                out.append("0123456789abcdef"[nib])
    s = "".join(out).rstrip("f")
    return s


def digits_to_bcd(s: str) -> bytes:
    s = s.strip().lower().rstrip("f")
    if len(s) % 2:
        s += "f"
    return bytes(int(s[i:i + 2], 16) for i in range(0, len(s), 2))


class Tap3Error(ValueError):
    pass


@dataclass
class Finding:
    severity: str          # error | warning | info
    code: str
    message: str
    path: str
    event: int = -1

    def to_dict(self):
        d = {"severity": self.severity, "code": self.code, "message": self.message, "path": self.path}
        if self.event >= 0:
            d["event"] = self.event
        return d


class Tap3Document:
    # ------------------------------------------------------------------ load
    def __init__(self, data: bytes, filename: str = "<memory>", layout: str = "auto"):
        self.filename = filename
        self.raw = data
        self.layout = layout
        self.dirty = False
        self.notes: List[str] = []
        self.module: Optional[Module] = None
        self.schema_name = ""
        self.root: ber.BerNode
        self.nodes: Dict[int, ber.BerNode] = {}
        self.release: Optional[int] = None
        self.decimal_places: Optional[int] = None
        self._counter = 0
        self._by_name: Dict[str, ber.BerNode] = {}
        self._header_base: Optional[dict] = None
        self.modified_paths: set = set()
        self._decode()

    # ------------------------------------------------------------- decoding
    def _decode(self):
        if not self.raw:
            raise Tap3Error("empty file")
        try:
            root, end = ber.decode_element(self.raw, 0)
        except ber.BerError as exc:
            raise Tap3Error(f"BER decode failed: {exc}") from exc
        if end != len(self.raw):
            self.notes.append(f"{len(self.raw) - end} trailing byte(s) after top level element ignored")
        self.root = root
        kind = self._guess_kind()
        self.kind = kind
        if kind in ("tap3", "rap", "nrtrde"):
            self._annotate_best()
        else:
            # unknown layout: keep a generic tree, still tag-labelled
            self.module = all_modules().get("TAP0311.asn")
            self.schema_name = "generic"
        self._reindex()
        self._detect_release()
        self._detect_decimal_places()
        self._reindex()

    def _guess_kind(self) -> str:
        r = self.root
        if r.tag_class != APPLICATION or not r.constructed:
            return "generic"
        if r.tag_num in (534, 535):
            return "rap"
        if r.tag_num == 2:
            return "tap3"
        if r.tag_num == 1:
            # A TransferBatch always starts with BatchControlInfo (APPLICATION 4);
            # everything else with this root tag is an NRTRDE file.
            for child in r.children:
                if child.tag_class == APPLICATION and child.tag_num == 4:
                    return "tap3"
            return "nrtrde"
        return "generic"

    def _sniff_release(self, kind: str) -> Optional[int]:
        """Read the release number from the raw tree without annotation."""
        wanted = {189}
        if kind == "rap":
            wanted = {543, 189}
        for child in self.root.children:
            if child.tag_class != "APPLICATION":
                continue
            for sub in child.children:
                if sub.tag_class == "APPLICATION" and sub.tag_num in wanted and not sub.constructed:
                    if sub.payload:
                        return int.from_bytes(sub.payload, "big")
        return None

    def _annotate_best(self):
        specs = schema_specs()
        if not specs:
            self.module = None
            return
        kind = getattr(self, "kind", "tap3") or "tap3"
        candidates = [sp for sp in specs if sp["kind"] == kind]
        if not candidates:
            candidates = [sp for sp in specs if sp["kind"] == "tap3"]
        rel = self._sniff_release(kind)
        exact = []
        if rel is not None:
            exact = [sp for sp in candidates if sp["release"] == rel]
        if exact:
            candidates = exact + [sp for sp in candidates if sp not in exact]
        else:
            # newest first when the release is unknown
            candidates = sorted(candidates, key=lambda sp: -sp["release"])
        node_count = max(1, self._count_nodes())
        best = None
        last = None
        for spec in candidates:
            module = all_modules().get(spec["file"])
            if module is None:
                continue
            root_type = module.types.get(spec["root"])
            if root_type is None:
                continue
            reset_annotation(self.root)
            mismatch = _annotate(self.root, root_type, module, 0)
            last = spec
            best = (mismatch, spec, module)
            if mismatch == 0:
                break
            if len(candidates) == 1 or mismatch <= max(1, node_count // 500):
                break
        if best is None:
            self.module = None
            return
        _, spec, module = best
        self.module = module
        self.schema_name = spec["file"]
        self.schema_kind = spec["kind"]
        self.schema_mismatch = best[0]
        if last is not spec:
            reset_annotation(self.root)
            _annotate(self.root, module.types.get(spec["root"]), module, 0)

    def _count_nodes(self) -> int:
        n, stack = 0, [self.root]
        while stack:
            cur = stack.pop()
            n += 1
            stack.extend(cur.children)
        return n

    # ------------------------------------------------------------- indexing
    def _walk_ids(self, node: ber.BerNode, parent_path: str):
        self._counter += 1
        node.node_id = self._counter
        self.nodes[node.node_id] = node
        node.parent_path = parent_path
        for i, child in enumerate(node.children):
            child.index = i
            child.parent_id = node.node_id
            self._walk_ids(child, node.path())

    def _reindex(self):
        self.nodes.clear()
        self._counter = 0
        self._walk_ids(self.root, "")
        self.root.node_id = 1
        by_name: Dict[str, ber.BerNode] = {}
        for n in self.nodes.values():
            if n.name and n.name not in by_name:
                by_name[n.name] = n
        self._by_name = by_name
        self._header_base = None

    # ------------------------------------------------------------- metadata
    def find(self, path_regex: str) -> List[ber.BerNode]:
        rx = re.compile(path_regex, re.I)
        return [n for n in self.nodes.values() if rx.search(n.path())]

    def first(self, path_regex: str) -> Optional[ber.BerNode]:
        hits = self.find(path_regex)
        return hits[0] if hits else None

    def _detect_release(self):
        if getattr(self, "kind", "") == "rap":
            n = self._by_name.get("rapReleaseVersionNumber")
            if n is not None:
                self.release = _int_value(n)
                return
        n = self._by_name.get("releaseVersionNumber")
        if n is not None:
            if n.tag_num == 189 and n.payload:
                self.release = int.from_bytes(n.payload, "big")
            else:
                self.release = _int_value(n)
            return
        for n in self.root.children:
            if n.tag_class != "APPLICATION":
                continue
            stack = [n]
            while stack:
                cur = stack.pop()
                if cur.name == "releaseVersionNumber":
                    self.release = _int_value(cur)
                    return
                stack.extend(cur.children)

    def _detect_decimal_places(self):
        n = self._by_name.get("tapDecimalPlaces")
        if n is not None:
            self.decimal_places = _int_value(n)

    @property
    def release_label(self) -> str:
        kind = getattr(self, "kind", "tap3")
        if self.release is None:
            return KIND_LABELS.get(kind, "unknown") + " (release unknown)"
        if kind == "tap3":
            return RELEASES.get(self.release, f"TAP3.{self.release:02d}")
        if kind == "rap":
            return f"RAP1.{self.release:02d}"
        if kind == "nrtrde":
            return f"NRTRDE release {self.release}"
        return f"release {self.release}"

    # ----------------------------------------------------------- annotation
    def header(self) -> dict:
        if self._header_base is None:
            def node_text(name):
                n = self._by_name.get(name)
                if n is None:
                    return ""
                if n.constructed:
                    return " ".join(c.value_text for c in n.children if c.value_text)
                return n.value_text

            dp_node = self._by_name.get("tapDecimalPlaces")
            self._header_base = {
                "file": self.filename,
                "size": len(self.raw),
                "release": self.release,
                "releaseLabel": self.release_label,
                "schema": self.schema_name,
                "sender": node_text("sender"),
                "recipient": node_text("recipient"),
                "fileSequenceNumber": node_text("fileSequenceNumber"),
                "fileCreationTimeStamp": node_text("fileCreationTimeStamp"),
                "fileAvailableTimeStamp": node_text("fileAvailableTimeStamp"),
                "transferCutOffTimeStamp": node_text("transferCutOffTimeStamp"),
                "localCurrency": node_text("localCurrency"),
                "tapCurrency": node_text("tapCurrency"),
                "tapDecimalPlaces": self.decimal_places,
                "topTag": self.root.tag_label(),
                "notes": list(self.notes),
            }
        out = dict(self._header_base)
        out["dirty"] = self.dirty
        return out

    def node_detail(self, node_id: int) -> dict:
        """Single-node inspector payload (never serializes the subtree)."""
        n = self.node(node_id)
        d = n.to_dict(shallow=True)
        d["parent"] = n.parent_path
        d["childrenIds"] = [c.node_id for c in n.children[:1000]]
        d["span"] = [n.id_start, n.id_end]
        d["rawHex"] = self.raw[n.id_start:n.id_end][:128].hex(" ").upper()
        d["modified"] = n.path() in self.modified_paths
        ancestors = []
        cur = n
        guard = 0
        while cur.parent_id and guard < 256:
            parent = self.nodes.get(cur.parent_id)
            if parent is None:
                break
            ancestors.append(parent.node_id)
            cur = parent
            guard += 1
        d["ancestors"] = list(reversed(ancestors))
        return d

    def is_modified(self, node: ber.BerNode) -> bool:
        return bool(self.modified_paths) and node.path() in self.modified_paths


    # ------------------------------------------------------------ insertion
    def _unwrap(self, t: Optional[Type]) -> Optional[Type]:
        """Follow aliases and APPLICATION tags down to the structural type."""
        seen = 0
        while t is not None and seen < 64:
            if t.kind == "tagged":
                t = t.inner
            elif t.kind == "alias":
                t = self.module.types.get(t.name) if self.module else None
            else:
                return t
            seen += 1
        return t

    def _resolved(self, name: str) -> Optional[Type]:
        if not self.module or not name:
            return None
        return self._unwrap(self.module.types.get(name))

    @staticmethod
    def _type_name_for(t: Type) -> str:
        if getattr(t, "def_name", ""):
            return t.def_name
        if t.kind == "alias":
            return t.name
        return t.describe()

    @staticmethod
    def _present_fields(node: ber.BerNode) -> set:
        return {c.field_name for c in node.children if c.field_name}

    def _candidates(self, t: Type, present: set) -> dict:
        out = []
        if t.kind == "sequence":
            for fname, ftype, optional in t.fields:
                base = self._unwrap(ftype)
                if base.kind == "choice":
                    for aname, atype in base.alternatives:
                        abase = self._unwrap(atype)
                        out.append({
                            "field": fname, "alt": aname,
                            "type": self._type_name_for(atype),
                            "kind": abase.kind,
                            "leaf": abase.kind in ("primitive", "alias"),
                            "present": fname in present,
                            "repeatable": False,
                            "label": f"{fname} → {aname} : {self._type_name_for(atype)}",
                        })
                else:
                    out.append({
                        "field": fname, "alt": "",
                        "type": self._type_name_for(ftype),
                        "kind": base.kind,
                        "leaf": base.kind in ("primitive", "alias"),
                        "present": fname in present,
                        "repeatable": False,
                        "label": f"{fname} : {self._type_name_for(ftype)}",
                    })
        elif t.kind == "sequence_of":
            item = t.item
            ibase = self._unwrap(item)
            out.append({
                "field": "item", "alt": "",
                "type": self._type_name_for(item),
                "kind": ibase.kind,
                "leaf": ibase.kind in ("primitive", "alias"),
                "present": False, "repeatable": True,
                "label": f"item : {self._type_name_for(item)}",
            })
        return {"kind": t.kind, "options": out}

    def insert_options(self, node_id: int) -> dict:
        node = self.node(node_id)
        child = {"kind": "", "options": []}
        t = self._resolved(node.type_name)
        if t is not None and t.kind in ("sequence", "sequence_of"):
            child = self._candidates(t, self._present_fields(node))
        sibling = {"kind": "", "options": []}
        parent = self.nodes.get(node.parent_id) if node.parent_id else None
        if parent is not None:
            pt = self._resolved(parent.type_name)
            if pt is not None and pt.kind in ("sequence", "sequence_of"):
                sibling = self._candidates(pt, self._present_fields(parent))
        return {
            "node": {"id": node.node_id, "path": node.path(), "type": node.type_name,
                     "name": node.name, "constructed": node.constructed},
            "child": child, "sibling": sibling,
        }

    def _default_for(self, t: Type, value):
        from . import builder
        base = self._unwrap(t)
        type_name = self._type_name_for(t)
        if base.kind == "sequence":
            return {}
        if base.kind == "sequence_of":
            return []
        if base.kind == "choice":
            return None
        if value not in (None, ""):
            return value
        try:
            v = builder.default_value(self.module, type_name)
        except Exception:
            v = ""
        return "" if v is None else v

    def insert_node(self, target_id: int, mode: str, field: str, alt: str = "",
                    value: str = "") -> dict:
        from . import builder
        if mode not in ("child", "sibling"):
            raise Tap3Error("mode must be child or sibling")
        target = self.node(target_id)
        if mode == "sibling":
            parent = self.nodes.get(target.parent_id)
            if parent is None:
                raise Tap3Error("the document root cannot have siblings")
        else:
            parent = target
        pt = self._resolved(parent.type_name)
        if pt is None or pt.kind not in ("sequence", "sequence_of"):
            raise Tap3Error(f"{parent.type_name or 'node'} cannot contain child elements")

        if pt.kind == "sequence_of":
            item = pt.item
            type_name = self._type_name_for(item)
            new = builder.build(self.module, type_name, self._default_for(item, None))
            if new is None:
                raise Tap3Error(f"cannot build {type_name}")
            new.field_name = ""
            new.name = type_name
            index = parent.children.index(target) + 1 if mode == "sibling" else len(parent.children)
        else:
            fdef = None
            for fname, ftype, optional in pt.fields:
                if fname == field:
                    fdef = (fname, ftype, optional)
                    break
            if fdef is None:
                raise Tap3Error(f"field '{field}' is not part of {parent.type_name}")
            fname, ftype, optional = fdef
            if any(c.field_name == fname for c in parent.children):
                raise Tap3Error(f"field '{fname}' is already present in {parent.type_name}")
            base = self._unwrap(ftype)
            if base.kind == "choice":
                atype = None
                for aname, candidate in base.alternatives:
                    if aname == alt:
                        atype = candidate
                        break
                if atype is None:
                    raise Tap3Error(f"alternative '{alt}' is not part of {fname}")
                chosen = atype
            else:
                chosen = ftype
            type_name = self._type_name_for(chosen)
            new = builder.build(self.module, type_name, self._default_for(chosen, value))
            if new is None:
                raise Tap3Error(f"cannot build {type_name}")
            new.field_name = fname
            new.name = alt or fname
            order = {f[0]: i for i, f in enumerate(pt.fields)}
            new_order = order[fname]
            index = len(parent.children)
            for i, child in enumerate(parent.children):
                if child.field_name in order and order[child.field_name] > new_order:
                    index = i
                    break

        parent.children.insert(index, new)
        self.dirty = True
        self._redecode_annotate()
        self.mark_modified(parent.path())
        return {"id": new.node_id, "path": new.path(), "name": new.name,
                "type": new.type_name, "modified": True}

    def find_by_path(self, path: str) -> Optional[ber.BerNode]:
        for n in self.nodes.values():
            if n.path() == path:
                return n
        return None

    def mark_modified(self, path: str) -> None:
        if path:
            self.modified_paths.add(path)

    # --------------------------------------------------------------- events
    def event_list_node(self) -> Optional[ber.BerNode]:
        for n in self.root.children:
            if n.tag_num == 3 and n.tag_class == APPLICATION:
                return n
        return None

    def events(self) -> List[ber.BerNode]:
        lst = self.event_list_node()
        if lst is None:
            return []
        return [c for c in lst.children if c.constructed]

    def event_index_map(self) -> Dict[int, int]:
        return {n.node_id: i for i, n in enumerate(self.events())}

    def event_summary(self, ev: ber.BerNode) -> dict:
        d = {"type": ev.name or ev.tag_label(), "typeName": ev.type_name}
        d["charge"] = self._sum_amount(ev)
        d["start"] = self._first_text(ev, "callEventStartTimeStamp")
        d["duration"] = _int_value(self._first_node(ev, "totalCallEventDuration")) or 0
        d["causeForTerm"] = _int_value(self._first_node(ev, "causeForTerm"))
        d["subscriber"] = self._first_text(ev, "imsi") or self._first_text(ev, "msisdn") \
            or self._first_text(ev, "min")
        d["called"] = self._first_text(ev, "calledNumber") or self._first_text(ev, "dialledDigits")
        d["calling"] = self._first_text(ev, "callingNumber")
        d["dataVolume"] = (_int_value(self._first_node(ev, "dataVolumeIncoming")) or 0) + \
                          (_int_value(self._first_node(ev, "dataVolumeOutgoing")) or 0)
        d["id"] = ev.node_id
        d["offset"] = ev.offset
        return d

    def statistics(self) -> dict:
        events = self.events()
        by_type: Dict[str, dict] = {}
        total_charge = 0
        duration = 0
        for i, ev in enumerate(events):
            key = ev.name or ev.tag_label()
            slot = by_type.setdefault(key, {"count": 0, "charge": 0, "duration": 0})
            slot["count"] += 1
            c = self._sum_amount(ev) or 0
            slot["charge"] += c
            total_charge += c
            ev_dur = _int_value(self._first_node(ev, "totalCallEventDuration")) or 0
            slot["duration"] += ev_dur
            duration += ev_dur
        audit_count = _int_value(self._first_node(self.root, "callEventDetailsCount"))
        return {
            "events": len(events),
            "auditCount": audit_count,
            "countMatches": audit_count in (None, len(events)),
            "byType": by_type,
            "chargeSum": total_charge,
            "durationSum": duration,
            "decimalPlaces": self.decimal_places,
            "release": self.release_label,
        }

    def _first_node(self, scope: ber.BerNode, name: str) -> Optional[ber.BerNode]:
        if scope.name == name:
            return scope
        for c in scope.children:
            r = self._first_node(c, name)
            if r is not None:
                return r
        return None

    def _first_text(self, scope: ber.BerNode, name: str) -> str:
        n = self._first_node(scope, name)
        if n is None:
            return ""
        if n.constructed:
            return " ".join(c.value_text for c in n.children if c.value_text)
        return n.value_text

    def _sum_amount(self, scope: ber.BerNode) -> Optional[int]:
        """Sum of chargeDetail.charge (TAP currency units) inside an event."""
        total, seen = 0, False
        stack = [scope]
        while stack:
            n = stack.pop()
            if n.name == "charge" and n.type_name in AMOUNT_TYPES | {"AbsoluteAmount"}:
                v = _int_value(n)
                if v is not None:
                    total += v
                    seen = True
            stack.extend(n.children)
        return total if seen else None

    # ------------------------------------------------------------- mutation
    def node(self, node_id: int) -> ber.BerNode:
        try:
            return self.nodes[int(node_id)]
        except KeyError:
            raise Tap3Error(f"no node {node_id}")

    def set_value(self, node_id: int, value: str, mode: str = "auto") -> ber.BerNode:
        node = self.node(node_id)
        if node.constructed:
            raise Tap3Error("cannot set a value on a constructed element")
        path = node.path()
        node.payload = encode_value(node, value, mode)
        self.dirty = True
        self._redecode_annotate()
        self.mark_modified(path)
        return self.node(node_id) if node_id in self.nodes else node

    def delete_node(self, node_id: int) -> None:
        node = self.node(node_id)
        parent = None
        for cand in self.nodes.values():
            if node in cand.children:
                parent = cand
                break
        if parent is None:
            raise Tap3Error("cannot delete the document root")
        parent_path = parent.path()
        parent.children.remove(node)
        self.dirty = True
        self._redecode_annotate()
        self.mark_modified(parent_path)

    def clone_node(self, node_id: int) -> None:
        node = self.node(node_id)
        parent = None
        for cand in self.nodes.values():
            if node in cand.children:
                parent = cand
                break
        if parent is None:
            raise Tap3Error("cannot clone the document root")
        import copy
        parent_path = parent.path()
        parent.children.insert(parent.children.index(node) + 1, copy.deepcopy(node))
        self.dirty = True
        self._redecode_annotate()
        self.mark_modified(parent_path)

    def _redecode_annotate(self):
        self._header_base = None
        reset_annotation(self.root)
        if self.module:
            _annotate(self.root, self.module.types.get("DataInterChange"), self.module, 0)
        self._reindex()

    def replace(self, pattern: str, repl: str, path_regex: str = "", case: bool = False,
                limit: int = 0) -> List[dict]:
        flags = 0 if case else re.I
        rx = re.compile(pattern, flags)
        scope = re.compile(path_regex, re.I) if path_regex else None
        changed = []
        for node in list(self.nodes.values()):
            if node.constructed:
                continue
            if scope and not scope.search(node.path()):
                continue
            if not node.value_text:
                continue
            new, n = rx.subn(repl, node.value_text)
            if n:
                try:
                    node.payload = encode_value(node, new, "auto")
                    changed.append({"id": node.node_id, "path": node.path(),
                                    "old": node.value_text, "new": new})
                except Tap3Error:
                    continue
            if limit and len(changed) >= limit:
                break
        if changed:
            self.dirty = True
            for item in changed:
                self.mark_modified(item.get("path", ""))
            self._redecode_annotate()
        return changed

    # ----------------------------------------------------------------- save
    def to_bytes(self) -> bytes:
        return ber.encode_file(self.root)

    def save(self, path: str) -> str:
        data = self.to_bytes()
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        self.dirty = False
        return path

    # -------------------------------------------------------------- exports
    def tree_json(self, max_nodes: int = 200000) -> dict:
        def conv(n: ber.BerNode, depth=0):
            d = n.to_dict(shallow=True)
            if depth < 400 and n.children:
                d["children"] = [conv(c, depth + 1) for c in n.children]
            return d
        return conv(self.root)

    def events_json(self) -> List[dict]:
        return [self.event_summary(ev) for ev in self.events()]

    def export_json(self, path: str):
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump({"header": self.header(), "tree": self.tree_json()}, fh, ensure_ascii=False, indent=1)

    def export_csv(self, path: str):
        import csv
        rows = self.events_json()
        cols = ["id", "type", "subscriber", "called", "calling", "start", "duration",
                "charge", "dataVolume", "causeForTerm", "offset"]
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)

    def export_xml(self, path: str):
        """Tap3Info-style XML export (structure + values, not a re-encoding)."""
        def esc(s: str) -> str:
            return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    .replace('"', "&quot;"))
        def emit(n: ber.BerNode, depth: int, out: List[str]):
            pad = "  " * depth
            name = n.name or f"item_{n.tag_num}"
            attrs = f'tag="{n.tag_label()}" type="{esc(n.type_name)}"'
            if n.constructed:
                out.append(f"{pad}<{name} {attrs}>")
                for c in n.children:
                    emit(c, depth + 1, out)
                out.append(f"{pad}</{name}>")
            else:
                out.append(f'{pad}<{name} {attrs} value="{esc(n.value_text)}" '
                           f'hex="{n.payload.hex().upper()}"/>')
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<Tap3Info>"]
        emit(self.root, 1, lines)
        lines.append("</Tap3Info>")
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    def export_listing(self, path: str):
        """Fixed-width listing (human readable, importable by TAP3 Studio)."""
        lines = []
        lines.append("TAP3 STUDIO LISTING 1.0")
        h = self.header()
        lines.append(f"FILE|{h['file']}|{h['size']}|{h['releaseLabel']}|{h['sender']}|{h['recipient']}")
        lines.append(f"SEQ|{h['fileSequenceNumber']}|{h['fileAvailableTimeStamp']}|{h['localCurrency']}"
                     f"|{h['tapCurrency']}|{h['tapDecimalPlaces']}")
        cols = ["id", "type", "subscriber", "called", "calling", "start", "duration",
                "charge", "dataVolume", "causeForTerm"]
        lines.append("EVENTS|" + "|".join(cols))
        for r in self.events_json():
            lines.append("EV|" + "|".join("" if r.get(c) is None else str(r.get(c)) for c in cols))
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    def statistic_report(self) -> str:
        st = self.statistics()
        h = self.header()
        out = ["", "=" * 78,
               f"File Statistics for '{self.filename}' on {_dt.datetime.now():%Y-%m-%d %H:%M:%S}",
               "=" * 78,
               f"Release            : {h['releaseLabel']}  (schema {h['schema']})",
               f"Sender / Recipient : {h['sender']} / {h['recipient']}",
               f"File sequence      : {h['fileSequenceNumber']}",
               f"File available     : {h['fileAvailableTimeStamp']}",
               f"Currency           : {h['localCurrency']} -> TAP {h['tapCurrency']} "
               f"(decimal places {h['tapDecimalPlaces']})",
               "-" * 78,
               f"{'Type':<28}{'NofValidRecs':>14}{'Charge':>18}{'Duration':>14}"]
        for k, v in sorted(st["byType"].items()):
            out.append(f"{k:<28}{v['count']:>14}{v['charge']:>18}{v['duration']:>14}")
        out.append("-" * 78)
        out.append(f"{'Total':<28}{st['events']:>14}{st['chargeSum']:>18}{st['durationSum']:>14}")
        out.append(f"Audit callEventDetailsCount: {st['auditCount']} "
                   f"({'OK' if st['countMatches'] else 'MISMATCH'})")
        out.append("----------- End statistic report ---------")
        return "\n".join(out)


# ---------------------------------------------------------------- helpers
def _int_value(node: Optional[ber.BerNode]) -> Optional[int]:
    if node is None or node.constructed or not node.payload:
        return None
    if node.type_name in ("INTEGER", "AbsoluteAmount", "Code"):
        return int.from_bytes(node.payload, "big")
    try:
        return int(node.value_text)
    except Exception:
        return None


def _primitive_semantic(type_name: str) -> str:
    if type_name in BCD_TYPES:
        return "bcd"
    if type_name in HEX_TYPES:
        return "hex"
    if type_name in NUMERIC_TYPES:
        return "num"
    return "text"


def _value_text(node: ber.BerNode) -> str:
    if node.constructed:
        return ""
    is_int = node.primitive == "INTEGER" or node.type_name in AMOUNT_TYPES
    if is_int:
        return str(int.from_bytes(node.payload, "big")) if node.payload else "0"
    if not node.payload:
        return ""
    sem = _primitive_semantic(node.type_name)
    try:
        if sem == "bcd":
            return bcd_to_digits(node.payload)
        return node.payload.decode("ascii", "replace")
    except Exception:
        return node.payload.hex(" ").upper()


def encode_value(node: ber.BerNode, value: str, mode: str = "auto") -> bytes:
    sem = _primitive_semantic(node.type_name)
    if mode == "hex":
        return bytes.fromhex(value.replace(" ", ""))
    numeric = node.primitive == "INTEGER" or node.type_name in ("INTEGER", "Code", "PercentageRate")         or node.type_name in AMOUNT_TYPES
    if sem == "bcd":
        return digits_to_bcd(value)
    if numeric:
        return int(value or 0).to_bytes(1, "big", signed=False) if False else _int_bytes(int(value or 0))
    data = value.encode("ascii", "strict")
    return data


def _int_bytes(v: int) -> bytes:
    if v == 0:
        return b"\x00"
    n = (v.bit_length() + 7) // 8
    return v.to_bytes(n, "big")


# ------------------------------------------------------------- annotation
def reset_annotation(node: ber.BerNode) -> None:
    stack = [node]
    while stack:
        n = stack.pop()
        n.name = ""
        n.field_name = ""
        n.type_name = ""
        n.primitive = ""
        n.value_text = ""
        n.warnings = []
        n.repeated = False
        stack.extend(n.children)


def _type_name(t: Optional[Type]) -> str:
    if t is None:
        return ""
    if t.def_name:
        return t.def_name
    if t.kind == "alias":
        return t.name
    return t.describe()


def _annotate(node: ber.BerNode, tdef: Optional[Type], module: Module, depth: int) -> int:
    """Annotate *node* (and children) from the declared type. Returns mismatch count."""
    if tdef is None or depth > 64:
        return _annotate_generic(node, module)
    declared = _type_name(tdef)
    t = tdef
    seen = 0
    while t is not None and t.kind == "alias" and seen < 32:
        nxt = module.types.get(t.name)
        if nxt is None or nxt is t:
            break
        t = nxt
        seen += 1
    if t is None:
        return _annotate_generic(node, module)
    if t.kind == "tagged":
        return _annotate_inner(node, t.inner, module, declared or _type_name(t), depth)
    return _annotate_inner(node, t, module, declared or _type_name(t), depth)


def _annotate_inner(node: ber.BerNode, inner: Optional[Type], module: Module,
                    declared: str, depth: int) -> int:
    if inner is None:
        return _annotate_generic(node, module)
    base = inner.resolved(module)
    inner_name = _type_name(inner)
    if base.kind == "primitive":
        node.type_name = declared or inner_name or base.primitive
        node.primitive = base.primitive
        if not node.constructed:
            node.value_text = _value_text(node)
        return 0
    if base.kind == "sequence":
        node.type_name = declared or inner_name or "SEQUENCE"
        if node.constructed:
            return _annotate_sequence(node, base, module, depth)
        node.warnings.append("constructed element expected but primitive found")
        return 1
    if base.kind == "sequence_of":
        node.type_name = declared or inner_name or "SEQUENCE OF"
        if node.constructed:
            return _annotate_seq_of(node, base.item, module, depth)
        node.warnings.append("SEQUENCE OF expected but primitive found")
        return 1
    if base.kind == "choice":
        node.type_name = declared or inner_name or "CHOICE"
        for aname, atype in base.alternatives:
            tag = atype.effective_tag(module)
            if tag is not None and (tag[0], tag[1]) == (node.tag_class, node.tag_num):
                # prefer the alternative name; the enclosing field name is kept
                # in field_name so the UI can show both levels
                node.name = aname
                return _annotate(node, atype, module, depth + 1)
        if node.constructed:
            return _annotate_choice(node, base, module, depth)
        node.warnings.append("CHOICE alternative not matched")
        return 1
    # unresolved alias: keep the tree readable
    node.type_name = declared or inner_name
    if not node.constructed and not node.value_text:
        node.value_text = _value_text(node)
    return 0


def _matches_field(ftype: Type, module: Module, child: ber.BerNode) -> bool:
    t = ftype
    seen = 0
    while t is not None and t.kind == "alias" and seen < 32:
        nxt = module.types.get(t.name)
        if nxt is None or nxt is t:
            break
        t = nxt
        seen += 1
    if t is not None and t.kind == "tagged":
        if (t.tag_class, t.tag_num) == (child.tag_class, child.tag_num):
            return True
        t = t.inner
        while t is not None and t.kind == "alias" and seen < 64:
            nxt = module.types.get(t.name)
            if nxt is None or nxt is t:
                break
            t = nxt
            seen += 1
    if t is not None and t.kind == "choice":
        for _aname, atype in t.alternatives:
            atag = atype.effective_tag(module)
            if atag is not None and (atag[0], atag[1]) == (child.tag_class, child.tag_num):
                return True
        return False
    tag = ftype.effective_tag(module)
    if tag is not None:
        return (tag[0], tag[1]) == (child.tag_class, child.tag_num)
    return False


def _annotate_sequence(node: ber.BerNode, seq: Type, module: Module, depth: int) -> int:
    mismatch = 0
    cursor = 0
    fields = seq.fields
    for child in node.children:
        chosen = -1
        for i in range(cursor, len(fields)):
            fname, ftype, optional = fields[i]
            if _matches_field(ftype, module, child):
                chosen = i
                break
        if chosen < 0:
            if cursor < len(fields):
                chosen = cursor
                mismatch += 1
                child.warnings.append("tag not in schema at this position")
            else:
                mismatch += 1
                child.warnings.append("extra element not in schema")
                child.name = ""
                _annotate(child, None, module, depth + 1)
                continue
        fname, ftype, optional = fields[chosen]
        cursor = chosen + 1
        child.field_name = fname
        child.name = fname
        _annotate(child, ftype, module, depth + 1)
    return mismatch


def _annotate_seq_of(node: ber.BerNode, item_type: Optional[Type], module: Module, depth: int) -> int:
    if item_type is None:
        return 0
    item_name = _type_name(item_type)
    mismatch = 0
    for i, child in enumerate(node.children):
        child.index = i
        child.repeated = True
        if not child.name:
            child.name = item_name
        mismatch += _annotate(child, item_type, module, depth + 1)
        if not child.type_name:
            child.type_name = item_name
    return mismatch


def _annotate_choice(node: ber.BerNode, choice: Type, module: Module, depth: int) -> int:
    mismatch = 0
    for child in node.children:
        picked = None
        for aname, atype in choice.alternatives:
            tag = atype.effective_tag(module)
            if tag is not None and (tag[0], tag[1]) == (child.tag_class, child.tag_num):
                picked = (aname, atype)
                break
        if picked is None:
            mismatch += 1
            child.warnings.append("CHOICE alternative not matched")
            _annotate(child, None, module, depth + 1)
            continue
        if not child.name:
            child.name = picked[0]
        _annotate(child, picked[1], module, depth + 1)
    return mismatch


def _annotate_generic(node: ber.BerNode, module: Module) -> int:
    for child in node.children:
        _annotate_generic(child, module)
    if not node.constructed and not node.value_text:
        node.value_text = node.payload.hex(" ").upper()
    return 0


# ---------------------------------------------------------------- factory
def open_document(path: str, layout: str = "auto") -> Tap3Document:
    with open(path, "rb") as fh:
        data = fh.read()
    return Tap3Document(data, filename=os.path.basename(path), layout=layout)


def detect_kind(path: str) -> str:
    with open(path, "rb") as fh:
        head = fh.read(8)
    if len(head) < 2:
        return "unknown"
    ident = head[0]
    if ident >> 6 == 1:                        # APPLICATION class
        num = ident & 0x1F
        if num == 1:
            return "TAP3"
        if num == 2:
            return "TAP3-notification"
    return "RAP1/NRTRDE/other"
