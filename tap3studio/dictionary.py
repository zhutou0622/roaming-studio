"""Data dictionary for the right-hand pane.

The original Roaming Studio shows a TD.57 "Data Dictionary" entry for every
field in the tree: description, derivation, conditionality, code list,
validation table, ASN.1 definition and parent types.  This module builds the
same content from the parsed ASN.1 schema plus curated TD.57 text.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional

from . import tapfile
from .asn1model import Module, Type

MODULE_NAME = "TAP0311.asn"

# --------------------------------------------------------------------- text
DESCRIPTIONS: Dict[str, List[str]] = {
    "TeleServiceCode": [
        "A code which uniquely defines a TeleService.",
        "Group TeleService Codes, identifiable by the description 'All', should only be used where "
        "details of the specific services affected are not available from the network.",
        "Note that compound TeleService group codes can only occur in call independent supplementary "
        "service operations.",
    ],
    "BearerServiceCode": [
        "A code which uniquely defines a Bearer Service.",
        "The code is derived from the GSM MAP encoding of the bearer capability, see TD.57 Annex C.",
    ],
    "SimChargeableSubscriber": [
        "The subscriber that is charged for the event, identified by SIM data (IMSI and/or MSISDN).",
        "Imsi must be present when the subscriber is a SIM subscriber and no other subscriber "
        "identification is available.",
    ],
    "Msisdn": [
        "The Mobile Station ISDN number of the subscriber, encoded as BCD digits with an 'f' filler "
        "when the number of digits is odd.",
    ],
    "Imsi": [
        "International Mobile Subscriber Identity, BCD encoded with an 'f' filler for an odd number "
        "of digits.",
    ],
    "Imei": [
        "International Mobile Equipment Identity (or ESN for ANSI networks), BCD encoded.",
    ],
    "CallEventStartTimeStamp": [
        "The local time at which the call or event started, together with a reference to the UTC "
        "time offset code defined in NetworkInfo.",
    ],
    "LocalTimeStamp": [
        "Local time stamp in the format CCYYMMDDhhmmss.",
    ],
    "TotalCallEventDuration": [
        "The duration of the call event in seconds.  A value of zero is used when the duration is "
        "not known, e.g. for unsuccessful call attempts.",
    ],
    "Charge": [
        "The charge for the event, expressed in TAP currency units.  The number of decimal places "
        "is defined once per file by TapDecimalPlaces in AccountingInfo.",
    ],
    "AbsoluteAmount": [
        "Absolute revenue amount.  Only values greater than or equal to zero are allowed; the "
        "decimal point is defined by TapDecimalPlaces.",
    ],
    "ChargeDetail": [
        "One chargeable component of a charge information group: charge type, amount, chargeable "
        "and charged units and optionally the time stamp of the charging.",
    ],
    "ChargeInformation": [
        "The charging information for a basic service usage or a supplementary service usage, "
        "including the charge detail list, taxes and discounts.",
    ],
    "TaxInformation": [
        "Tax applied to the charge: tax code, tax value and the taxable amount.",
    ],
    "CallTypeGroup": [
        "Call type classification used for rating: up to three levels plus the called country code.",
    ],
    "NetworkLocation": [
        "The network location of the served subscriber: recording entity, call reference, location "
        "area and cell id.",
    ],
    "FileSequenceNumber": [
        "A five digit sequential number identifying the file within the transfer cut-off period.",
    ],
    "FileTypeIndicator": [
        "A one character indicator of the file content, e.g. 'T' for TAP, 'N' for notification.",
    ],
    "TapDecimalPlaces": [
        "The number of decimal places used for all absolute amounts in the file (0..5).",
    ],
    "ReleaseVersionNumber": [
        "The TAP release version number of the file, e.g. 11 for TAP3.11.",
    ],
    "SpecificationVersionNumber": [
        "The TAP specification version, always 3 for TAP3 files.",
    ],
    "RecEntityCode": [
        "A code identifying a recording entity (MSC, SGSN, SMSC, ...) defined in NetworkInfo.",
    ],
    "MobileTerminatedCall": [
        "A mobile terminated call record: the served subscriber received a call.",
    ],
    "MobileOriginatedCall": [
        "A mobile originated call record: the served subscriber made a call.",
    ],
    "GprsCall": [
        "A GPRS / packet data record with data volumes, PDP context information and charging.",
    ],
    "BatchControlInfo": [
        "Batch control information: sender, recipient, file sequence number, timestamps and the "
        "release version of the transfer batch.",
    ],
    "AuditControlInfo": [
        "Audit information for the batch: earliest and latest call time stamp, total charge, total "
        "tax, total discount and the number of call event details.",
    ],
    "AccountingInfo": [
        "Accounting information for the batch: taxation, discounting, currencies and decimal places.",
    ],
    "NetworkInfo": [
        "Network information for the batch: UTC time offset definitions and recording entity data.",
    ],
}

DERIVATIONS: Dict[str, str] = {
    "TeleServiceCode": "GSM: from TeleServiceCode (See Annex C - CS Domain Charging)",
    "BearerServiceCode": "GSM: from BearerCapability (See Annex C - CS Domain Charging)",
    "CauseForTerm": "GSM: from Cause (See Annex C - CS Domain Charging)",
    "ChargeType": "Operator defined charge type, see the roaming agreement.",
    "CallTypeLevel1": "Operator defined call type level 1, see the roaming agreement.",
}

CONDITIONALITY: Dict[str, str] = {
    "TeleServiceCode": "Must be present within group Service Code where the type of service used was "
                       "a teleservice. Must not be present when the type of service used was a bearer "
                       "service.",
    "BearerServiceCode": "Must be present within group Service Code where the type of service used "
                         "was a bearer service.",
    "Imsi": "Must be present when the subscriber is identified by SIM data.",
    "Msisdn": "Must be present when available from the network; otherwise only the IMSI is sent.",
    "TotalCallEventDuration": "Must be present unless the call event is an unsuccessful call attempt.",
    "Charge": "Must be present within ChargeDetail.",
    "TapDecimalPlaces": "Must be present within AccountingInfo.",
}

VALUES: Dict[str, List[Dict[str, str]]] = {
    "TeleServiceCode": [
        ("00", "All teleservices"),
        ("10", "All Speech transmission services"),
        ("11", "Telephony"),
        ("12", "Emergency calls"),
        ("20", "All SMS Services"),
        ("21", "Short Message MT/PP"),
        ("22", "Short Message MO/PP"),
        ("60", "All Fax Services"),
        ("61", "Facsimile Group 3 & alternate speech"),
        ("62", "Automatic Facsimile Group 3"),
        ("63", "Automatic Facsimile Group 4"),
        ("70", "All data teleservices (compound)"),
        ("80", "All teleservices except SMS (compound)"),
        ("90", "All voice group call services"),
        ("91", "Voice group call"),
        ("92", "Voice broadcast call"),
    ],
    "BearerServiceCode": [
        ("20", "Asynchronous data"),
        ("30", "Synchronous data"),
        ("40", "PAD access"),
        ("50", "Reserved"),
        ("60", "Alternate speech/data"),
        ("70", "Speech followed by data"),
        ("80", "Reserved"),
    ],
    "CauseForTerm": [
        ("0", "Normal call clearing / normal event"),
        ("1", "Unallocated (unassigned) number"),
        ("16", "Normal call clearing"),
        ("17", "User busy"),
        ("18", "No user responding"),
        ("19", "No answer from user"),
        ("21", "Call rejected"),
        ("22", "Number changed"),
        ("31", "Normal, unspecified"),
        ("34", "No circuit/channel available"),
        ("38", "Network out of order"),
        ("41", "Temporary failure"),
        ("42", "Switching equipment congestion"),
        ("44", "Requested circuit/channel not available"),
        ("47", "Resource unavailable, unspecified"),
        ("49", "Quality of service not available"),
        ("57", "Bearer capability not authorized"),
        ("58", "Bearer capability not presently available"),
        ("63", "Service or option not available"),
        ("65", "Bearer service not implemented"),
        ("69", "Requested facility not implemented"),
        ("70", "Only restricted digital information bearer capability available"),
        ("79", "Service or option not implemented"),
        ("95", "Invalid transit network selection"),
        ("102", "Recovery on timer expiry"),
        ("111", "Protocol error, unspecified"),
        ("127", "Interworking, unspecified"),
    ],
    "ChargeType": [
        ("10", "Call / event charge"),
        ("20", "Data volume charge"),
        ("30", "Supplementary service charge"),
        ("40", "Content / value added service charge"),
    ],
    "FileTypeIndicator": [
        ("T", "TAP file"),
        ("N", "Notification"),
        ("R", "RAP file"),
        ("A", "Acknowledgement"),
        ("C", "Content transaction"),
    ],
    "RecEntityType": [
        ("1", "MSC (mobile switching centre)"),
        ("2", "SGSN"),
        ("3", "SMSC"),
        ("4", "GGSN"),
    ],
    "TaxType": [
        ("01", "VAT"),
        ("02", "Sales tax"),
        ("03", "Excise"),
    ],
}

VALIDATION_DEFAULT = [
    ("10", "MOC\nMTC", "Severe", "Syntax error."),
    ("20", "MOC\nMTC", "Severe",
     "Value out of range.\nNote: Value 21 is only allowed for MTC and value 22 is only allowed for MOC."),
    ("30", "ALL", "Severe", "Mandatory item missing."),
    ("40", "ALL", "Warning", "Invalid length for the data type."),
    ("50", "ALL", "Warning", "Value not within the set of allowed codes."),
    ("60", "ALL", "Warning", "Duplicate call event detail detected."),
]

VALIDATIONS: Dict[str, List[tuple]] = {
    "TeleServiceCode": [
        ("10", "MOC\nMTC", "Severe", "Syntax error."),
        ("11", "SS", "Warning", "Syntax error."),
        ("20", "MOC\nMTC", "Severe",
         "Value out of range.\nNote: Value 21 is only allowed for MTC and value 22 is only allowed for MOC."),
        ("21", "SS", "Warning", "Value out of range."),
    ],
    "CauseForTerm": [
        ("10", "MOC\nMTC", "Severe", "Syntax error."),
        ("20", "MOC\nMTC", "Warning", "Value not defined for TAP."),
        ("30", "GPRS", "Warning", "Cause for term not applicable to GPRS records."),
    ],
    "Charge": [
        ("10", "ALL", "Severe", "Syntax error."),
        ("20", "ALL", "Warning", "Negative charge is not allowed."),
        ("21", "ALL", "Warning", "Charge exceeds the value defined in the roaming agreement."),
    ],
    "Imsi": [
        ("10", "MOC\nMTC\nGPRS\nSS", "Severe", "Syntax error."),
        ("11", "ALL", "Warning", "Invalid BCD filler, only 'f' is allowed."),
        ("40", "ALL", "Severe", "IMSI length must be between 6 and 15 digits."),
    ],
}

FOOTER = "Text extracted from GSM TD57 standard"


# ------------------------------------------------------------- schema helpers
def _module() -> Optional[Module]:
    return tapfile.all_modules().get(MODULE_NAME)


def _module_for(type_name: str) -> Optional[Module]:
    """Find the bundled schema module that defines *type_name*."""
    modules = tapfile.all_modules()
    default = modules.get(MODULE_NAME)
    if default is not None and type_name in default.types:
        return default
    for module in modules.values():
        if type_name in module.types:
            return module
    return default


@lru_cache(maxsize=16)
def _reverse_index_for(module_name: str) -> Dict[str, List[str]]:
    module = tapfile.all_modules().get(module_name)
    out: Dict[str, List[str]] = {}
    if module is None:
        return out
    for name, t in module.types.items():
        refs = set()
        _collect_refs(t, refs)
        for ref in refs:
            out.setdefault(ref, []).append(name)
    for ref, parents in out.items():
        parents.sort()
    return out


def _reverse_index(module: Optional[Module] = None) -> Dict[str, List[str]]:
    if module is None:
        module = _module()
    if module is None:
        return {}
    return _reverse_index_for(module.name)


def _collect_refs(t: Type, refs: set, depth: int = 0):
    if t is None or depth > 8:
        return
    if t.kind == "alias" and t.name:
        refs.add(t.name)
    if t.kind == "tagged":
        _collect_refs(t.inner, refs, depth + 1)
    if t.kind == "sequence":
        for _n, ft, _o in t.fields:
            _collect_refs(ft, refs, depth + 1)
    if t.kind == "sequence_of":
        _collect_refs(t.item, refs, depth + 1)
    if t.kind == "choice":
        for _n, at in t.alternatives:
            _collect_refs(at, refs, depth + 1)


def _tag_prefix(t: Type) -> str:
    if t.kind == "tagged":
        return f"[APPLICATION {t.tag_num}] "
    return ""


def render_asn1(name: str, module: Optional[Module] = None) -> List[str]:
    """Pretty print one type definition as ASN.1 text lines."""
    module = module or _module()
    if module is None or name not in module.types:
        return []
    t = module.types[name]
    head = f"{name} ::= {_tag_prefix(t)}"
    body = t.inner if t.kind == "tagged" else t
    if body.kind == "sequence":
        lines = [head + "SEQUENCE", "{"]
        for fn, ft, opt in body.fields:
            suffix = " OPTIONAL," if opt else ","
            lines.append(f"    {fn:<26}{_type_ref(ft)}{suffix}")
        lines.append("}")
        return lines
    if body.kind == "sequence_of":
        return [head + "SEQUENCE OF " + _type_ref(body.item)]
    if body.kind == "choice":
        lines = [head + "CHOICE", "{"]
        for fn, ft in body.alternatives:
            lines.append(f"    {fn:<26}{_type_ref(ft)},")
        lines.append("}")
        return lines
    if body.kind == "primitive":
        return [head + body.primitive]
    if body.kind == "alias":
        return [head + body.name]
    return [head + body.describe()]


def _type_ref(t: Type) -> str:
    if t is None:
        return "?"
    if t.kind == "tagged":
        return t.inner.name if t.inner is not None and t.inner.kind == "alias" else _type_ref(t.inner)
    if t.kind == "alias":
        return t.name
    return t.describe()


def dictionary(type_name: str, field_name: str = "") -> dict:
    module = _module_for(type_name)
    if module is None or type_name not in module.types:
        raise KeyError(f"unknown type {type_name}")
    parent_names = [p for p in _reverse_index(module).get(type_name, [])][:4]
    # the definition shown is the containing type (as in Roaming Studio),
    # falling back to the field type itself
    shown = parent_names or [type_name]
    asn1 = []
    for n in shown[:2]:
        asn1.extend(render_asn1(n, module))
    desc = DESCRIPTIONS.get(type_name)
    if desc is None:
        kind = module.types[type_name].resolved(module).kind if module and type_name in module.types else "data item"
        desc = [
            f"TAP3 {kind} '{type_name}'.",
            "Definition taken from the TD.57 abstract syntax; semantics follow the TAP3 data "
            "dictionary of the parent group.",
        ]
    values = [{"code": c, "text": t} for c, t in VALUES.get(type_name, [])]
    validations = [
        {"code": c, "context": ctx, "severity": sev, "description": d}
        for c, ctx, sev, d in VALIDATIONS.get(type_name, VALIDATION_DEFAULT)
    ]
    return {
        "type": type_name,
        "field": field_name or (type_name[:1].lower() + type_name[1:]),
        "description": desc,
        "derivation": DERIVATIONS.get(type_name, ""),
        "conditionality": CONDITIONALITY.get(type_name, ""),
        "values": values,
        "validations": validations,
        "asn1": asn1,
        "asn1Title": "ASN.1 Definition (of containing types)" if parent_names else "ASN.1 Definition",
        "parents": parent_names,
        "footer": FOOTER,
    }
