"""Validation engine for TAP3 Studio.

The rule set is our own, modelled on the checks that matter when a TAP file
is produced or accepted in a roaming settlement chain (TD.57 structural
rules + the TADIG-style cross checks the legacy editor exposed):

  * structural completeness (BatchControlInfo / AccountingInfo / AuditControlInfo)
  * count and amount reconciliation against AuditControlInfo
  * per-record mandatory groups for MO / MT / GPRS / SCU / content records
  * timestamp format and UTC offset references
  * BCD / numeric / hex field syntax
  * duplicate record detection

Every finding carries a stable code so the same rule can be overridden or
suppressed by an acceptance profile later on.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import ber
from .tapfile import AMOUNT_TYPES, Finding, Tap3Document, _int_value

REQUIRED_BCI = ["sender", "recipient", "fileSequenceNumber", "fileCreationTimeStamp",
                "transferCutOffTimeStamp", "fileAvailableTimeStamp",
                "specificationVersionNumber", "releaseVersionNumber", "fileTypeIndicator"]
REQUIRED_ACI = ["totalCharge", "totalTaxValue", "totalDiscountValue", "callEventDetailsCount"]
REQUIRED_ACC = ["localCurrency", "tapDecimalPlaces"]
VALID_TIME = re.compile(r"^\d{14}$")
VALID_OFFSET = re.compile(r"^[+-]\d{4}$")
VALID_BCD = re.compile(r"^[0-9a-fA-F]*f?$")
EVENT_REQUIRED = {
    "mobileOriginatedCall": ["basicCallInformation"],
    "mobileTerminatedCall": ["basicCallInformation"],
    "gprsCall": ["gprsBasicCallInformation", "gprsServiceUsed"],
    "serviceCentreUsage": ["basicInformation", "chargeInformation"],
    "supplServiceEvent": ["supplServiceUsed"],
    "contentTransaction": ["contentTransactionBasicInfo", "contentServiceUsed"],
    "valueAddedService": ["valueAddedServiceUsed"],
    "locationService": ["locationServiceUsage"],
}


def _nodes_named(scope: ber.BerNode, name: str) -> List[ber.BerNode]:
    out = []
    stack = [scope]
    while stack:
        n = stack.pop()
        if n.name == name:
            out.append(n)
        stack.extend(n.children)
    return out


def _child(node: ber.BerNode, name: str) -> Optional[ber.BerNode]:
    for c in node.children:
        if c.name == name:
            return c
    return None


def _timecheck(name: str, node: Optional[ber.BerNode], out: List[Finding], path: str):
    if node is None:
        return
    if node.constructed:
        local = _child(node, "localTimeStamp")
        offset = _child(node, "utcTimeOffset") or _child(node, "utcTimeOffsetCode")
        if local is None:
            out.append(Finding("error", "TS-001", f"{name}: localTimeStamp missing", path))
        elif not VALID_TIME.match(local.value_text or ""):
            out.append(Finding("error", "TS-002",
                               f"{name}: localTimeStamp '{local.value_text}' is not CCYYMMDDhhmmss",
                               path))
        if offset is not None and offset.name == "utcTimeOffset" and \
                not VALID_OFFSET.match(offset.value_text or ""):
            out.append(Finding("warning", "TS-003",
                               f"{name}: utcTimeOffset '{offset.value_text}' is not +/-hhmm", path))
    elif not VALID_TIME.match(node.value_text or ""):
        out.append(Finding("error", "TS-002", f"{name}: '{node.value_text}' is not CCYYMMDDhhmmss", path))


def _amount_scaled(v: Optional[int], dp: Optional[int]) -> str:
    if v is None:
        return "n/a"
    dp = dp or 0
    return f"{v / (10 ** dp):.{dp}f}"


def validate(doc: Tap3Document) -> dict:
    out: List[Finding] = []
    dp = doc.decimal_places
    batch = None
    for c in doc.root.children:
        if c.name == "batchControlInfo":
            batch = c
    if batch is None:
        out.append(Finding("error", "TAP-001", "batchControlInfo missing (first group in TransferBatch)",
                           doc.root.path()))
    else:
        for f in REQUIRED_BCI:
            if _child(batch, f) is None:
                out.append(Finding("error", "TAP-002", f"mandatory item '{f}' missing", batch.path()))
        _timecheck("fileCreationTimeStamp", _child(batch, "fileCreationTimeStamp"), out, batch.path())
        _timecheck("transferCutOffTimeStamp", _child(batch, "transferCutOffTimeStamp"), out, batch.path())
        _timecheck("fileAvailableTimeStamp", _child(batch, "fileAvailableTimeStamp"), out, batch.path())
        fsn = _child(batch, "fileSequenceNumber")
        if fsn is not None and not re.match(r"^\d{5}$", fsn.value_text or ""):
            out.append(Finding("error", "TAP-003",
                               f"fileSequenceNumber '{fsn.value_text}' must be 5 numeric digits", fsn.path()))
        spec = _child(batch, "specificationVersionNumber")
        if spec is not None and _int_value(spec) != 3:
            out.append(Finding("warning", "TAP-004",
                               f"specificationVersionNumber is {_int_value(spec)}, expected 3", spec.path()))
        fti = _child(batch, "fileTypeIndicator")
        if fti is not None and (fti.value_text or "") not in ("T", "N", "R", "A", "C"):
            out.append(Finding("warning", "TAP-005",
                               f"unknown fileTypeIndicator '{fti.value_text}'", fti.path()))
    if doc.release is None:
        out.append(Finding("error", "TAP-006", "releaseVersionNumber not found", doc.root.path()))
    elif doc.release not in (1, 2, 3, 4, 9, 10, 11, 12):
        out.append(Finding("warning", "TAP-007",
                           f"releaseVersionNumber {doc.release} is outside the supported set", doc.root.path()))
    if getattr(doc, "schema_mismatch", 0):
        out.append(Finding("warning", "TAP-008",
                           f"{doc.schema_mismatch} element(s) could not be mapped to the "
                           f"{doc.schema_name} schema", doc.root.path()))

    acc = None
    for c in doc.root.children:
        if c.name == "accountingInfo":
            acc = c
    if acc is None:
        out.append(Finding("error", "ACC-001", "accountingInfo missing", doc.root.path()))
    else:
        for f in REQUIRED_ACC:
            if _child(acc, f) is None:
                out.append(Finding("error", "ACC-002", f"mandatory item '{f}' missing", acc.path()))
        if dp is not None and not 0 <= dp <= 5:
            out.append(Finding("error", "ACC-003", f"tapDecimalPlaces {dp} outside 0..5", acc.path()))

    net = None
    for c in doc.root.children:
        if c.name == "networkInfo":
            net = c
    if net is None:
        out.append(Finding("warning", "NET-001", "networkInfo missing (no utcTimeOffsetInfo)", doc.root.path()))
    else:
        offsets = _child(net, "utcTimeOffsetInfo")
        codes = set()
        if offsets is not None:
            for item in offsets.children:
                code = _child(item, "utcTimeOffsetCode")
                val = _child(item, "utcTimeOffset")
                if code is not None:
                    codes.add(code.value_text)
                if val is not None and not VALID_OFFSET.match(val.value_text or ""):
                    out.append(Finding("error", "NET-002",
                                       f"utcTimeOffset '{val.value_text}' is not +/-hhmm", item.path()))
        for node in doc.nodes.values():
            if node.name == "utcTimeOffsetCode" and node.value_text not in codes and codes:
                out.append(Finding("warning", "NET-003",
                                   f"utcTimeOffsetCode '{node.value_text}' not declared in NetworkInfo",
                                   node.path()))

    events = doc.events()
    if not events:
        out.append(Finding("error", "EVT-001", "callEventDetails is empty or missing", doc.root.path()))
    seen = set()
    total_charge = 0
    for idx, ev in enumerate(events):
        et = ev.name or "unknown"
        if et not in EVENT_REQUIRED and not et.startswith("item"):
            out.append(Finding("warning", "EVT-002", f"unknown call event type '{et}'", ev.path(), idx))
        for req in EVENT_REQUIRED.get(et, []):
            if _child(ev, req) is None:
                out.append(Finding("error", "EVT-003", f"{et}: mandatory group '{req}' missing",
                                   ev.path(), idx))
        start = _nodes_named(ev, "callEventStartTimeStamp")
        if not start:
            out.append(Finding("error", "EVT-004", f"{et}: callEventStartTimeStamp missing", ev.path(), idx))
        for s in start:
            _timecheck("callEventStartTimeStamp", s, out, s.path())
        dur = _child(ev, "totalCallEventDuration") or None
        if dur is None:
            for n in _nodes_named(ev, "totalCallEventDuration"):
                dur = n
                break
        dv = _int_value(dur)
        if dv is None:
            out.append(Finding("warning", "EVT-005", f"{et}: totalCallEventDuration missing", ev.path(), idx))
        elif dv < 0 or dv > 86400 * 2:
            out.append(Finding("error", "EVT-006",
                               f"{et}: implausible totalCallEventDuration {dv}s", ev.path(), idx))
        charges = _nodes_named(ev, "charge")
        ev_charge = 0
        for c in charges:
            v = _int_value(c)
            if v is None:
                continue
            if v < 0:
                out.append(Finding("error", "EVT-007", f"{et}: negative charge {v}", c.path(), idx))
            ev_charge += v
        total_charge += ev_charge
        if not charges:
            out.append(Finding("warning", "EVT-008", f"{et}: no charge information", ev.path(), idx))
        # duplicate detection
        sub = {n.name: n.value_text for n in _nodes_named(ev, "imsi")[:1]}
        key = (et, start[0].children[0].value_text if start and start[0].children else "",
               _nodes_named(ev, "chargeableUnits")[0].value_text if _nodes_named(ev, "chargeableUnits") else "",
               str(ev_charge))
        if key in seen:
            out.append(Finding("warning", "EVT-009",
                               f"{et}: possible duplicate record (start/units/charge identical)",
                               ev.path(), idx))
        seen.add(key)
        # BCD sanity on subscriber identifiers
        for name in ("imsi", "msisdn", "imei"):
            for node in _nodes_named(ev, name)[:1]:
                if node.value_text and not VALID_BCD.match(node.value_text):
                    out.append(Finding("error", "BCD-001",
                                       f"{name} '{node.value_text}' is not valid BCD digits",
                                       node.path(), idx))

    audit = None
    for c in doc.root.children:
        if c.name == "auditControlInfo":
            audit = c
    if audit is None:
        out.append(Finding("error", "AUD-001", "auditControlInfo missing", doc.root.path()))
    else:
        for f in REQUIRED_ACI:
            if _child(audit, f) is None:
                out.append(Finding("error", "AUD-002", f"mandatory item '{f}' missing", audit.path()))
        _timecheck("earliestCallTimeStamp", _child(audit, "earliestCallTimeStamp"), out, audit.path())
        _timecheck("latestCallTimeStamp", _child(audit, "latestCallTimeStamp"), out, audit.path())
        cnt = _child(audit, "callEventDetailsCount")
        if cnt is not None and _int_value(cnt) != len(events):
            out.append(Finding("error", "AUD-003",
                               f"callEventDetailsCount {_int_value(cnt)} != {len(events)} records",
                               cnt.path()))
        tc = _child(audit, "totalCharge")
        if tc is not None:
            claimed = _int_value(tc)
            if claimed is not None and claimed != total_charge:
                out.append(Finding("error", "AUD-004",
                                   f"totalCharge {_amount_scaled(claimed, dp)} != sum of record charges "
                                   f"{_amount_scaled(total_charge, dp)} (difference "
                                   f"{_amount_scaled(claimed - total_charge, dp)})", tc.path()))
        earliest = _child(audit, "earliestCallTimeStamp")
        latest = _child(audit, "latestCallTimeStamp")
        if earliest is not None and latest is not None:
            e = _child(earliest, "localTimeStamp")
            l = _child(latest, "localTimeStamp")
            if e and l and e.value_text and l.value_text and e.value_text > l.value_text:
                out.append(Finding("error", "AUD-005",
                                   "earliestCallTimeStamp is later than latestCallTimeStamp",
                                   earliest.path()))

    errors = sum(1 for f in out if f.severity == "error")
    warnings = sum(1 for f in out if f.severity == "warning")
    return {
        "file": doc.filename,
        "release": doc.release_label,
        "records": len(events),
        "errors": errors,
        "warnings": warnings,
        "findings": [f.to_dict() for f in out],
        "chargeSum": total_charge,
        "chargeSumScaled": _amount_scaled(total_charge, dp),
        "decimalPlaces": dp,
    }
