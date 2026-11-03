"""ASN.1 (TAP3 TD.57 subset) module parser.

Parses the textual ASN.1 modules shipped in ``schema/*.asn`` into a small
type model that the BER layer uses to annotate a raw TLV tree with field
names, type names and human readable values.

Supported constructs (everything TD.57 uses):
    [APPLICATION n] SEQUENCE { name Type OPTIONAL, ... }
    [APPLICATION n] SEQUENCE OF Type
    [APPLICATION n] CHOICE { name Type, ... }
    [APPLICATION n] INTEGER | OCTET STRING
    Name ::= OtherName                 (alias)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

UNIVERSAL = "UNIVERSAL"
APPLICATION = "APPLICATION"
CONTEXT = "CONTEXT"

_TAG_UNIVERSAL = {"SEQUENCE": 16, "SEQUENCE_OF": 16, "CHOICE": None,
                  "INTEGER": 2, "OCTET STRING": 4, "BOOLEAN": 1}


@dataclass
class Type:
    """Base type node."""

    kind: str                                  # sequence|sequence_of|choice|primitive|alias|tagged
    name: str = ""                             # alias target / reference name
    def_name: str = ""                         # name of the ::= definition
    tag_class: Optional[str] = None
    tag_num: Optional[int] = None
    fields: List[Tuple[str, "Type", bool]] = field(default_factory=list)
    alternatives: List[Tuple[str, "Type"]] = field(default_factory=list)
    item: Optional["Type"] = None
    inner: Optional["Type"] = None
    primitive: Optional[str] = None

    # ---- tag resolution -------------------------------------------------
    def effective_tag(self, module: "Module") -> Optional[Tuple[str, int]]:
        t = self
        seen = 0
        while t is not None and seen < 32:
            seen += 1
            if t.tag_class is not None and t.tag_num is not None:
                return (t.tag_class, t.tag_num)
            if t.kind == "alias":
                t = self._alias_target(module)
                continue
            if t.kind == "sequence":
                return (UNIVERSAL, 16)
            if t.kind == "sequence_of":
                return (UNIVERSAL, 16)
            if t.kind == "choice":
                return None
            if t.kind == "primitive":
                return (UNIVERSAL, _TAG_UNIVERSAL.get(t.primitive or "", None))
            return None
        return None

    def _alias_target(self, module: "Module") -> Optional["Type"]:
        return module.types.get(self.name)

    def resolved(self, module: "Module") -> "Type":
        t = self
        seen = 0
        while t is not None and t.kind == "alias" and seen < 32:
            nxt = module.types.get(t.name)
            if nxt is None:
                return t
            t = nxt
            seen += 1
        return t

    def describe(self) -> str:
        if self.kind == "alias":
            return self.name
        if self.kind == "sequence":
            return "SEQUENCE"
        if self.kind == "sequence_of":
            return "SEQUENCE OF " + (self.item.describe() if self.item else "?")
        if self.kind == "choice":
            return "CHOICE"
        if self.kind == "primitive":
            return self.primitive or "?"
        return self.kind


@dataclass
class Module:
    name: str
    types: Dict[str, Type]

    def root_type(self, name: str) -> Optional[Type]:
        return self.types.get(name)


_RE_TAG = re.compile(r"^\[APPLICATION\s+(\d+)\]\s*", re.I)
_RE_DEF_START = re.compile(r"\b([A-Z][A-Za-z0-9]*)\s*::=")


def _strip_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


def _split_top_level(body: str) -> List[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _parse_fields(body: str, is_choice: bool) -> List[Tuple[str, Type, bool]]:
    out: List[Tuple[str, Type, bool]] = []
    for raw in _split_top_level(body):
        item = raw.strip().strip(",").strip()
        if not item:
            continue
        optional = bool(re.search(r"\bOPTIONAL\b", item))
        item = re.sub(r"\bOPTIONAL\b", "", item).strip()
        m = re.match(r"^([A-Za-z][A-Za-z0-9]*)\s+(.+)$", item, re.S)
        if m:
            fname, ftype = m.group(1), m.group(2).strip()
        else:                                   # anonymous / bare type
            fname, ftype = "", item.strip()
        out.append((fname, _parse_type(ftype), optional))
    return out


def _parse_type(body: str) -> Type:
    body = " ".join(body.split())
    m = _RE_TAG.match(body)
    tag_class = tag_num = None
    if m:
        tag_class, tag_num = APPLICATION, int(m.group(1))
        body = body[m.end():].strip()
    inner: Type
    if body.upper().startswith("SEQUENCE OF"):
        item = _parse_type(body[len("SEQUENCE OF"):])
        inner = Type(kind="sequence_of", item=item)
    elif body.upper().startswith("SEQUENCE"):
        brace = body.find("{")
        fields = _parse_fields(body[brace + 1:body.rfind("}")], False) if brace >= 0 else []
        inner = Type(kind="sequence", fields=fields)
    elif body.upper().startswith("CHOICE"):
        brace = body.find("{")
        alts = _parse_fields(body[brace + 1:body.rfind("}")], True) if brace >= 0 else []
        inner = Type(kind="choice", alternatives=[(n, t) for n, t, _ in alts])
    elif body.upper().startswith("INTEGER"):
        inner = Type(kind="primitive", primitive="INTEGER")
    elif body.upper().startswith("OCTET STRING"):
        inner = Type(kind="primitive", primitive="OCTET STRING")
    elif body.upper().startswith("BOOLEAN"):
        inner = Type(kind="primitive", primitive="BOOLEAN")
    else:
        name = re.match(r"^[A-Za-z][A-Za-z0-9]*", body)
        inner = Type(kind="alias", name=name.group(0) if name else body)
    if tag_class is not None:
        return Type(kind="tagged", tag_class=tag_class, tag_num=tag_num, inner=inner)
    return inner


def parse_module(text: str, name: str = "TAP3") -> Module:
    text = _strip_comments(text)
    # drop the module header (X DEFINITIONS ... BEGIN) when it is present;
    # some published modules comment the BEGIN/END markers out
    match = re.search(r"BEGIN", text)
    if match:
        text = text[match.end():]
    text = text.strip()
    if re.search(r"END\s*$", text):
        text = re.sub(r"END\s*$", "", text)
    starts = list(_RE_DEF_START.finditer(text))
    types: Dict[str, Type] = {}
    for i, m in enumerate(starts):
        def_name = m.group(1)
        body_start = m.end()
        body_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[body_start:body_end].strip().rstrip(",").strip()
        if not body:
            continue
        try:
            t = _parse_type(body)
            t.def_name = def_name
            types[def_name] = t
        except Exception:
            continue
    return Module(name=name, types=types)
