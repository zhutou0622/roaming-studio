"""Schema-driven TAP3 builder.

Builds a BER tree from a plain dict using the ASN.1 module, which makes it
possible to create valid TAP3 test files without hard-coding tag numbers:

    builder.build(module, "DataInterChange", {"transferBatch": {...}})

The same engine powers the built-in sample generator and the "new file"
wizard in the UI.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import ber
from .asn1model import Module, Type
from .tapfile import (AMOUNT_TYPES, BCD_TYPES, HEX_TYPES, NUMERIC_TYPES,
                      digits_to_bcd, semantic_for_name, _int_bytes)

DEFAULT_TEXT = {
    "PlmnId": "26201",
    "Bid": "TADIG",
    "FileTypeIndicator": "T",
    "Currency": "EUR",
    "UtcTimeOffset": "+0100",
    "LocalTimeStamp": "20240101120000",
    "ChargeType": "10",
    "TaxType": "01",
    "TaxRate": "1900000",
    "ChargedItem": "1",
    "PartialTypeIndicator": "N",
    "ChargingPoint": "1",
    "ServingNetwork": "26201",
    "NetworkId": "26201",
    "AccessPointNameNI": "internet",
}


class BuildError(ValueError):
    pass


def _tag_of(t: Type, module: Module):
    return t.effective_tag(module)


def _primitive_bytes(prim: str, type_name: str, value, semantic: str = "") -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    s = str(value)
    if semantic == "bcd" or (not semantic and type_name in BCD_TYPES):
        return digits_to_bcd(s)
    if prim == "INTEGER":
        try:
            return _int_bytes(int(s or 0))
        except ValueError:
            raise BuildError(f"{type_name or 'INTEGER'}: expected integer, got {value!r}")
    return s.encode("ascii", "replace")


def build(module: Module, type_name: str, value, depth: int = 0) -> Optional[ber.BerNode]:
    if depth > 40:
        raise BuildError("type nesting too deep")
    t = module.types.get(type_name)
    if t is None:
        raise BuildError(f"unknown type {type_name}")
    return _build(module, t, value, type_name, depth)


def _build(module: Module, t: Type, value, display_name: str, depth: int) -> Optional[ber.BerNode]:
    if value is None:
        return None
    cls, num = (None, None)
    inner = t
    if t.kind == "tagged":
        cls, num = t.tag_class, t.tag_num
        inner = t.inner if t.inner is not None else t
    if inner.kind == "alias":
        target = module.types.get(inner.name)
        if target is None:
            raise BuildError(f"unknown alias {inner.name}")
        effective_name = display_name if (display_name and display_name[:1].isupper()) else inner.name
        node = _build(module, target, value, effective_name, depth + 1)
        if node is None:
            return None
        if cls is not None:
            node.tag_class, node.tag_num = cls, num
    elif inner.kind == "sequence":
        if not isinstance(value, dict):
            raise BuildError(f"{display_name}: SEQUENCE expects dict, got {type(value).__name__}")
        node = ber.BerNode(tag_class=cls or "UNIVERSAL", tag_num=num if num is not None else 16,
                           constructed=True)
        for fname, ftype, optional in inner.fields:
            if fname in value:
                child = _build(module, ftype, value[fname], fname, depth + 1)
                if child is not None:
                    child.name = fname
                    node.children.append(child)
        node.name = display_name
        return node
    elif inner.kind == "sequence_of":
        if not isinstance(value, list):
            value = [value]
        node = ber.BerNode(tag_class=cls or "UNIVERSAL", tag_num=num if num is not None else 16,
                           constructed=True)
        for i, item in enumerate(value):
            child = _build(module, inner.item, item, f"item[{i}]", depth + 1)
            if child is not None:
                node.children.append(child)
        node.name = display_name
        return node
    elif inner.kind == "choice":
        if not isinstance(value, dict) or len(value) != 1:
            raise BuildError(f"{display_name}: CHOICE expects {{alternative: value}}")
        alt_name, alt_val = next(iter(value.items()))
        for aname, atype in inner.alternatives:
            if aname == alt_name:
                child = _build(module, atype, alt_val, aname, depth + 1)
                if child is None:
                    raise BuildError(f"{display_name}: empty CHOICE value")
                child.name = aname
                return child
        raise BuildError(f"{display_name}: unknown CHOICE alternative {alt_name}")
    elif inner.kind == "primitive":
        node = ber.BerNode(tag_class=cls or "UNIVERSAL",
                           tag_num=num if num is not None else (2 if inner.primitive == "INTEGER" else 4),
                           constructed=False)
        node.payload = _primitive_bytes(
            inner.primitive or "OCTET STRING", display_name, value,
            semantic_for_name(module, display_name, inner.primitive or "OCTET STRING"))
    else:
        raise BuildError(f"{display_name}: unsupported type {inner.kind}")
    node.name = display_name
    return node


def default_value(module: Module, type_name: str):
    """A minimal sensible default for a leaf type (used by the insert dialog)."""
    t = module.types.get(type_name)
    if t is None:
        return ""
    r = t.resolved(module)
    tn = type_name
    if tn in DEFAULT_TEXT:
        return DEFAULT_TEXT[tn]
    if r.kind == "primitive":
        return 0 if r.primitive == "INTEGER" else DEFAULT_TEXT.get(type_name, "")
    return None
