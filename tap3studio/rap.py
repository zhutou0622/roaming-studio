"""Generate a RAP1 return file from TAP3 validation findings.

The returned batch mirrors the input TAP file:

* every invalid call-event record becomes a ``SevereReturn`` containing the
  original record plus the error details,
* file level findings become one ``FatalReturn`` with a ``BatchControlError``,
* ``RapAuditControlInfo`` counts the returned records and sums their charges.

Only the RAP1.05 schema shipped with the application is used.
"""
from __future__ import annotations

import copy
import datetime as _dt
from typing import Dict, Iterable, List, Optional

from . import ber, builder, tapfile

RAP_MODULE = "RAP0105.asn"
RAP_SPEC_VERSION = 4
RAP_RELEASE = 5

# TAP3 Studio rule code -> RAP/TADIG style error code
ERROR_CODES: Dict[str, int] = {
    "TAP-001": 30, "TAP-002": 30, "TAP-003": 10, "TAP-004": 50,
    "TAP-005": 50, "TAP-006": 30, "TAP-007": 50, "TAP-008": 10,
    "ACC-001": 30, "ACC-002": 30, "ACC-003": 20,
    "NET-001": 30, "NET-002": 10, "NET-003": 50,
    "EVT-001": 30, "EVT-002": 50, "EVT-003": 30, "EVT-004": 30,
    "EVT-005": 30, "EVT-006": 20, "EVT-007": 20, "EVT-008": 30,
    "EVT-009": 60,
    "TS-001": 30, "TS-002": 10, "TS-003": 10,
    "AUD-001": 30, "AUD-002": 30, "AUD-003": 20, "AUD-004": 20, "AUD-005": 20,
    "BCD-001": 10,
}


class RapError(ValueError):
    pass


def _module():
    module = tapfile.all_modules().get(RAP_MODULE)
    if module is None:
        raise RapError(f"schema {RAP_MODULE} is missing")
    return module


def _node(tag_class: str, tag_num: int, constructed: bool = True,
          payload: bytes = b"", name: str = "") -> ber.BerNode:
    node = ber.BerNode(tag_class=tag_class, tag_num=tag_num, constructed=constructed,
                       payload=payload)
    node.name = name
    return node


def _timestamp(ts: Optional[_dt.datetime] = None) -> Dict[str, str]:
    ts = ts or _dt.datetime.now()
    return {"localTimeStamp": ts.strftime("%Y%m%d%H%M%S"),
            "utcTimeOffset": ts.strftime("%z") or "+0000"}


def _error_detail(module, findings: Iterable[dict]) -> ber.BerNode:
    items = []
    for index, finding in enumerate(findings, start=1):
        items.append({
            "errorContext": [{"pathItemId": index, "itemLevel": 1}],
            "errorCode": ERROR_CODES.get(finding.get("code", ""), 10),
        })
    node = builder.build(module, "ErrorDetailList", items)
    if node is None:
        raise RapError("cannot build ErrorDetailList")
    return node


def _batch_control(module, doc, seq: str) -> ber.BerNode:
    header = doc.header()
    value = {
        "sender": header.get("recipient") or header.get("sender") or "00000",
        "recipient": header.get("sender") or header.get("recipient") or "00000",
        "rapFileSequenceNumber": seq,
        "rapFileCreationTimeStamp": _timestamp(),
        "rapFileAvailableTimeStamp": _timestamp(),
        "specificationVersionNumber": 3,
        "releaseVersionNumber": doc.release or 12,
        "rapSpecificationVersionNumber": RAP_SPEC_VERSION,
        "rapReleaseVersionNumber": RAP_RELEASE,
        "fileTypeIndicator": "R",
        "tapDecimalPlaces": header.get("tapDecimalPlaces") or 0,
    }
    if header.get("tapCurrency"):
        value["tapCurrency"] = header["tapCurrency"]
    node = builder.build(module, "RapBatchControlInfo", value)
    if node is None:
        raise RapError("cannot build RapBatchControlInfo")
    return node


def _first_named(root: ber.BerNode, name: str) -> Optional[ber.BerNode]:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.name == name:
            return node
        stack.extend(node.children)
    return None


def _severe_return(module, event: ber.BerNode, findings: List[dict], seq: str) -> ber.BerNode:
    node = _node("APPLICATION", 540, True, name="severeReturn")
    node.children.append(copy.deepcopy(event))
    node.children.append(_error_detail(module, findings))
    return node


def _fatal_return(module, doc, findings: List[dict], seq: str) -> ber.BerNode:
    batch = None
    for child in doc.root.children:
        if child.name == "batchControlInfo":
            batch = child
            break
    node = _node("APPLICATION", 539, True, name="fatalReturn")
    node.children.append(builder.build(module, "FileSequenceNumber", seq)
                         or _node("APPLICATION", 109, False, seq.encode()))
    if batch is not None:
        error = _node("APPLICATION", 517, True, name="batchControlError")
        error.children.append(copy.deepcopy(batch))
        error.children.append(_error_detail(module, findings))
        node.children.append(error)
    else:
        error = _node("APPLICATION", 542, True, name="transferBatchError")
        error.children.append(_error_detail(module, findings))
        node.children.append(error)
    return node


def build_rap(doc, findings: Iterable[dict], sequence: Optional[str] = None,
              now: Optional[_dt.datetime] = None) -> tapfile.Tap3Document:
    """Build a RAP1 return document from validation findings."""
    module = _module()
    findings = list(findings or [])
    if not findings:
        raise RapError("nothing to return: no validation findings supplied")

    events = doc.events()
    by_event: Dict[int, List[dict]] = {}
    file_level: List[dict] = []
    for finding in findings:
        idx = finding.get("event", -1)
        if isinstance(idx, int) and 0 <= idx < len(events):
            by_event.setdefault(idx, []).append(finding)
        else:
            file_level.append(finding)

    header = doc.header()
    seq = sequence or header.get("fileSequenceNumber") or "00001"
    seq = "".join(ch for ch in str(seq) if ch.isdigit())[-5:].rjust(5, "0")

    details = _node("APPLICATION", 536, True, name="returnDetails")
    for idx in sorted(by_event):
        details.children.append(_severe_return(module, events[idx], by_event[idx], seq))
    if file_level:
        details.children.append(_fatal_return(module, doc, file_level, seq))

    returned_charge = 0
    for idx in by_event:
        stack = [events[idx]]
        while stack:
            node = stack.pop()
            if node.name == "charge" and not node.constructed:
                try:
                    returned_charge += int(node.value_text or 0)
                except ValueError:
                    pass
            stack.extend(node.children)

    audit_value = {
        "totalSevereReturnValue": returned_charge,
        "returnDetailsCount": len(details.children),
    }
    if header.get("tapCurrency"):
        audit_value["totalSevereReturnTax"] = 0
    audit = builder.build(module, "RapAuditControlInfo", audit_value)
    if audit is None:
        raise RapError("cannot build RapAuditControlInfo")

    batch = _node("APPLICATION", 534, True, name="returnBatch")
    batch.children.append(_batch_control(module, doc, seq))
    batch.children.append(details)
    batch.children.append(audit)

    data = ber.encode_file(batch)
    result = tapfile.Tap3Document(data, f"{doc.filename}_RAP.rap")
    result.modified_paths.clear()
    return result


def rap_filename(source_path: str) -> str:
    base = source_path.rsplit(".", 1)[0] if "." in source_path else source_path
    return base + "_RAP.rap"
