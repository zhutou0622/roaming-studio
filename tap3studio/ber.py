"""BER (Basic Encoding Rules) codec for TAP3 files.

TAP3/TD.57 uses ASN.1 with IMPLICIT tags, definite or indefinite lengths and
APPLICATION/UNIVERSAL tags only.  The decoder keeps the original tag numbers
and byte spans so a decoded document can be re-encoded byte-identically
unless a value was explicitly edited.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class BerError(ValueError):
    pass


@dataclass
class BerNode:
    tag_class: str                      # UNIVERSAL | APPLICATION | CONTEXT
    tag_num: int
    constructed: bool
    offset: int = 0                     # byte offset of the identifier octet
    header_len: int = 0
    length: int = 0
    indefinite: bool = False
    payload: bytes = b""                # primitive content
    children: List["BerNode"] = field(default_factory=list)
    # annotation (filled by tapfile.annotate)
    name: str = ""
    field_name: str = ""
    type_name: str = ""
    primitive: str = ""
    value_text: str = ""
    warnings: List[str] = field(default_factory=list)
    index: int = 0                      # position among siblings
    parent_path: str = ""
    parent_id: int = 0
    node_id: int = 0
    id_start: int = 0                   # byte span of whole element
    id_end: int = 0
    repeated: bool = False

    # ------------------------------------------------------------------
    def tag_label(self) -> str:
        cls = {"UNIVERSAL": "U", "APPLICATION": "A", "CONTEXT": "C"}.get(self.tag_class, "?")
        return f"[{cls}{self.tag_num}]"

    def path(self) -> str:
        base = self.parent_path
        label = self.name or "item"
        if self.repeated:
            label = f"{label}[{self.index}]"
        return f"{base}.{label}" if base else label

    def to_dict(self, shallow: bool = True) -> dict:
        d = {
            "id": self.node_id,
            "tag": self.tag_label(),
            "tagNum": self.tag_num,
            "name": self.name,
            "field": self.field_name,
            "repeated": self.repeated,
            "index": self.index,
            "type": self.type_name,
            "value": self.value_text,
            "constructed": self.constructed,
            "offset": self.offset,
            "len": self.length,
            "hex": self.payload[:24].hex(" ").upper() if not self.constructed else "",
            "warnings": list(self.warnings),
            "childCount": len(self.children),
            "path": self.path(),
        }
        if not shallow:
            d["children"] = [c.to_dict(False) for c in self.children]
        return d


def _read_length(data: bytes, pos: int):
    if pos >= len(data):
        raise BerError("truncated length")
    b = data[pos]
    if b == 0x80:
        return None, pos + 1, True            # indefinite
    if b & 0x80:
        n = b & 0x7F
        if n == 0 or n > 4:
            raise BerError(f"unsupported length of length {n} at {pos}")
        if pos + 1 + n > len(data):
            raise BerError("truncated long length")
        return int.from_bytes(data[pos + 1:pos + 1 + n], "big"), pos + 1 + n, False
    return b, pos + 1, False


def decode_element(data: bytes, pos: int, depth: int = 0) -> tuple:
    """Decode one TLV at *pos*.  Returns (node, next_pos)."""
    if depth > 60:
        raise BerError("nesting too deep")
    start = pos
    if pos >= len(data):
        raise BerError("offset past end of data")
    ident = data[pos]
    pos += 1
    tag_class = {0: "UNIVERSAL", 1: "APPLICATION", 2: "CONTEXT", 3: "PRIVATE"}[ident >> 6]
    constructed = bool(ident & 0x20)
    tag_num = ident & 0x1F
    if tag_num == 0x1F:                       # high tag number form
        tag_num = 0
        while True:
            if pos >= len(data):
                raise BerError("truncated high tag")
            b = data[pos]
            pos += 1
            tag_num = (tag_num << 7) | (b & 0x7F)
            if not b & 0x80:
                break
    length, pos, indefinite = _read_length(data, pos)
    node = BerNode(tag_class=tag_class, tag_num=tag_num, constructed=constructed,
                   offset=start, header_len=(pos - start), indefinite=indefinite)
    if indefinite:
        while True:
            if pos + 1 < len(data) and data[pos] == 0 and data[pos + 1] == 0:
                pos += 2
                break
            child, pos = decode_element(data, pos, depth + 1)
            node.children.append(child)
        node.length = pos - start - node.header_len - 2
    elif length is None:
        raise BerError("missing length")
    else:
        end = pos + length
        if end > len(data):
            raise BerError(f"element at {start} claims {length} bytes, only {len(data) - pos} left")
        node.length = length
        if constructed:
            while pos < end:
                child, pos = decode_element(data, pos, depth + 1)
                node.children.append(child)
            if pos != end:
                raise BerError("constructed element length mismatch")
        else:
            node.payload = data[pos:end]
            pos = end
    node.id_start = start
    node.id_end = pos
    return node, pos


def _encode_length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def encode_element(node: BerNode) -> bytes:
    """Re-encode a node (lengths always recalculated, definite form)."""
    ident_bytes = bytearray()
    cls_bits = {"UNIVERSAL": 0, "APPLICATION": 1, "CONTEXT": 2, "PRIVATE": 3}[node.tag_class]
    first = (cls_bits << 6) | (0x20 if node.constructed else 0)
    if node.tag_num < 0x1F:
        ident_bytes.append(first | node.tag_num)
    else:
        ident_bytes.append(first | 0x1F)
        num = node.tag_num
        chunks = [num & 0x7F]
        num >>= 7
        while num:
            chunks.append((num & 0x7F) | 0x80)
            num >>= 7
        ident_bytes.extend(reversed(chunks))
    if node.constructed:
        body = b"".join(encode_element(c) for c in node.children)
        if node.indefinite:
            # keep the original indefinite form so untouched files re-encode
            # byte for byte (TAP files from some mediators use 0x80 lengths)
            return bytes(ident_bytes) + bytes([0x80]) + body + bytes([0, 0])
    else:
        body = node.payload
    return bytes(ident_bytes) + _encode_length(len(body)) + body


def encode_file(root: BerNode) -> bytes:
    return encode_element(root)
