"""FastAPI backend for TAP3 Studio (local, single-user desktop service)."""
from __future__ import annotations

import os
import threading
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import dictionary as dictionary_mod
from . import batch as batch_mod
from . import generator, ops, rap as rap_mod, resources, rules, tapfile, validate
from .tapfile import _int_value

WEB_DIR = resources.resource_path("web")

app = FastAPI(title="TAP3 Studio", version="1.0")
_lock = threading.Lock()
STATE = {"doc": None, "path": None}


# ------------------------------------------------------------------ models
class OpenReq(BaseModel):
    path: Optional[str] = None
    events: int = 6
    seed: int = 7


class TreeReq(BaseModel):
    id: int
    depth: int = 1


class ValueReq(BaseModel):
    id: int
    value: str
    mode: str = "auto"


class NodeReq(BaseModel):
    id: int


class SaveReq(BaseModel):
    path: str


class ReplaceReq(BaseModel):
    pattern: str
    repl: str = ""
    path: str = ""
    limit: int = 0


class GenReq(BaseModel):
    path: str
    events: int = 100
    seed: int = 7
    sender: str = "26201"
    recipient: str = "22801"
    currency: str = "EUR"


class MergeReq(BaseModel):
    paths: List[str]
    out: str


class ListingImportReq(BaseModel):
    path: str
    out: str


class BatchReq(BaseModel):
    paths: List[str]
    pattern: str = "*"
    profile: Optional[dict] = None


class BatchExportReq(BatchReq):
    out: str
    fmt: str = "xlsx"


class RapReq(BaseModel):
    out: Optional[str] = None
    profile: Optional[dict] = None
    include_warnings: bool = True


class ValidateReq(BaseModel):
    profile: Optional[dict] = None


class InsertReq(BaseModel):
    target_id: int
    mode: str = "child"
    field: str
    alt: str = ""
    value: str = ""


class SplitReq(BaseModel):
    out_prefix: str
    chunk: int = 1000
    start_seq: Optional[int] = None


# ------------------------------------------------------------------ helpers
def _doc() -> tapfile.Tap3Document:
    if STATE["doc"] is None:
        raise HTTPException(status_code=409, detail="no file open")
    return STATE["doc"]


def _summary(doc: tapfile.Tap3Document) -> dict:
    return {
        "header": doc.header(),
        "stats": doc.statistics(),
        "path": STATE["path"],
        "dirty": doc.dirty,
    }


def _open_path(path: str):
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    try:
        doc = tapfile.open_document(path)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    STATE["doc"] = doc
    STATE["path"] = os.path.abspath(path)
    return doc


# --------------------------------------------------------------------- API
@app.get("/api/state")
def state():
    if STATE["doc"] is None:
        return {"open": False}
    doc = STATE["doc"]
    return {"open": True, **_summary(doc),
            "root": doc.root.to_dict(shallow=True)}


@app.post("/api/open")
def open_file(req: OpenReq):
    with _lock:
        if req.path:
            doc = _open_path(req.path)
        else:
            doc = generator.make_document(req.events, req.seed)
            STATE["doc"] = doc
            STATE["path"] = None
        return {"open": True, **_summary(doc), "root": doc.root.to_dict(shallow=True)}


@app.post("/api/tree")
def tree(req: TreeReq):
    doc = _doc()
    node = doc.node(req.id)
    depth = max(1, min(8, req.depth))
    budget = {"n": 0, "max": 20000, "truncated": False}

    def conv(n, d):
        item = n.to_dict(shallow=True)
        item["modified"] = doc.is_modified(n)
        budget["n"] += 1
        if d > 0 and n.children and budget["n"] < budget["max"]:
            kids = []
            for c in n.children:
                if budget["n"] >= budget["max"]:
                    budget["truncated"] = True
                    break
                kids.append(conv(c, d - 1))
            item["children"] = kids
        else:
            item["children"] = None
            if n.children:
                budget["truncated"] = True
        return item

    payload = conv(node, depth)
    return {"node": payload, "truncated": budget["truncated"],
            "nodes": budget["n"], "limit": budget["max"]}


@app.get("/api/node/{node_id}")
def node_detail(node_id: int, deep: bool = False):
    doc = _doc()
    if deep:
        n = doc.node(node_id)
        d = n.to_dict(shallow=False)
        d["parent"] = n.parent_path
        d["childrenIds"] = [c.node_id for c in n.children]
        d["span"] = [n.id_start, n.id_end]
        d["rawHex"] = doc.raw[n.id_start:n.id_end][:128].hex(" ").upper()
        return d
    return doc.node_detail(node_id)


@app.post("/api/value")
def set_value(req: ValueReq):
    doc = _doc()
    try:
        doc.set_value(req.id, req.value, req.mode)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "dirty": doc.dirty, "header": doc.header()}


@app.get("/api/insert/options")
def insert_options(id: int):
    doc = _doc()
    try:
        return doc.insert_options(id)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/insert")
def insert_node(req: InsertReq):
    doc = _doc()
    try:
        result = doc.insert_node(req.target_id, req.mode, req.field, req.alt, req.value)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "node": result, "modified": len(doc.modified_paths)}


@app.post("/api/delete")
def delete_node(req: NodeReq):
    doc = _doc()
    try:
        doc.delete_node(req.id)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "dirty": doc.dirty}


@app.post("/api/clone")
def clone_node(req: NodeReq):
    doc = _doc()
    try:
        doc.clone_node(req.id)
    except tapfile.Tap3Error as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "dirty": doc.dirty}


@app.post("/api/save")
def save(req: SaveReq):
    doc = _doc()
    path = req.path or STATE["path"]
    if not path:
        raise HTTPException(status_code=422, detail="save path required")
    # write exactly to the requested name: no extension is added and the
    # original file is overwritten in place
    doc.save(path)
    STATE["path"] = os.path.abspath(path)
    return {"ok": True, "path": STATE["path"], "size": os.path.getsize(path),
            "original": os.path.basename(path)}


def _run_validation(doc, profile=None):
    if getattr(doc, "kind", "tap3") != "tap3":
        return {"file": doc.filename, "release": doc.release_label, "records": 0,
                "errors": 0, "warnings": 0, "findings": [], "suppressed": 0,
                "profile": "n/a", "skipped": True,
                "reason": "validation rules currently apply to TAP3 files; "
                          "RAP1/NRTRDE are browsable/editable only"}
    result = validate.validate(doc, profile)
    by_path = {}
    for node in doc.nodes.values():
        by_path.setdefault(node.path(), node.node_id)
    for f in result["findings"]:
        f["id"] = by_path.get(f.get("path", ""), 0)
    return result


@app.get("/api/validate")
def do_validate():
    return _run_validation(_doc())


@app.post("/api/validate")
def do_validate_post(req: Optional[ValidateReq] = None):
    return _run_validation(_doc(), req.profile if req else None)


@app.post("/api/import-listing")
def import_listing(req: ListingImportReq):
    try:
        doc = ops.import_listing(req.path)
        doc.save(req.out)
    except (OSError, ops.OpsError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    STATE["doc"] = doc
    STATE["path"] = os.path.abspath(req.out)
    return {"ok": True, "path": STATE["path"], "events": len(doc.events()),
            "size": os.path.getsize(STATE["path"]),
            "header": doc.header(), "stats": doc.statistics(),
            "root": doc.root.to_dict(shallow=True)}


@app.post("/api/batch")
def batch_scan(req: BatchReq):
    profile = rules.normalize(req.profile) if req.profile else None
    rows = batch_mod.scan(req.paths, profile, req.pattern)
    return {"rows": rows, "summary": batch_mod.summary(rows)}


@app.post("/api/batch/export")
def batch_export(req: BatchExportReq):
    profile = rules.normalize(req.profile) if req.profile else None
    rows = batch_mod.scan(req.paths, profile, req.pattern)
    fmt = req.fmt.lower()
    try:
        if fmt == "csv":
            batch_mod.write_csv(rows, req.out)
        elif fmt in ("xlsx", "excel"):
            batch_mod.write_xlsx(rows, req.out)
        else:
            raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True, "path": os.path.abspath(req.out), "files": len(rows),
            "summary": batch_mod.summary(rows)}


@app.post("/api/rap")
def generate_rap(req: RapReq):
    doc = _doc()
    result = validate.validate(doc, req.profile)
    findings = [f for f in result["findings"]
                if req.include_warnings or f["severity"] == "error"]
    if not findings:
        raise HTTPException(status_code=422, detail="no findings to return")
    try:
        rapdoc = rap_mod.build_rap(doc, findings)
    except rap_mod.RapError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    out = req.out or rap_mod.rap_filename(STATE["path"] or doc.filename)
    rapdoc.save(out)
    details = sum(1 for n in rapdoc.nodes.values()
                  if n.name in ("severeReturn", "fatalReturn", "stopReturn", "missingReturn"))
    return {"ok": True, "path": os.path.abspath(out), "details": details,
            "returned": len(findings), "errors": result["errors"],
            "warnings": result["warnings"], "release": rapdoc.release_label}


@app.get("/api/rec-entities")
def rec_entities():
    return {"entities": _doc().rec_entities()}


@app.get("/api/rules")
def rule_catalog():
    return rules.catalog()


@app.get("/api/events")
def events(offset: int = 0, limit: int = 200, q: str = ""):
    doc = _doc()
    rows = doc.events_json()
    if q:
        ql = q.lower()
        rows = [r for r in rows if any(ql in str(v).lower() for v in r.values())]
    total = len(rows)
    page = rows[offset:offset + limit]
    dp = doc.decimal_places or 0
    for r in page:
        if r.get("charge") is not None:
            r["chargeScaled"] = f"{r['charge'] / (10 ** dp):.{dp}f}"
    return {"total": total, "offset": offset, "limit": limit, "rows": page}


@app.get("/api/hex")
def hexdump(offset: int = 0, length: int = 512):
    doc = _doc()
    offset = max(0, min(offset, len(doc.raw)))
    length = max(16, min(8192, length))
    chunk = doc.raw[offset:offset + length]
    lines = []
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append({"offset": offset + i, "hex": row.hex(" ").upper(), "ascii": ascii_part})
    return {"offset": offset, "length": len(doc.raw), "lines": lines}


@app.get("/api/search")
def search(q: str, limit: int = 200):
    doc = _doc()
    ql = q.lower()
    hits = []
    for n in doc.nodes.values():
        hay = f"{n.name} {n.type_name} {n.value_text} {n.path()}".lower()
        if ql in hay:
            hits.append({"id": n.node_id, "path": n.path(), "name": n.name,
                         "type": n.type_name, "value": n.value_text[:120],
                         "offset": n.offset})
            if len(hits) >= limit:
                break
    return {"q": q, "count": len(hits), "hits": hits}


@app.post("/api/replace")
def replace(req: ReplaceReq):
    doc = _doc()
    changed = doc.replace(req.pattern, req.repl, req.path, limit=req.limit)
    return {"ok": True, "changed": changed, "count": len(changed)}


@app.post("/api/generate")
def generate(req: GenReq):
    doc = generator.make_document(req.events, req.seed, req.sender, req.recipient, req.currency)
    doc.save(req.path)
    STATE["doc"] = doc
    STATE["path"] = os.path.abspath(req.path)
    return {"ok": True, "path": STATE["path"], "size": os.path.getsize(req.path),
            **_summary(doc), "root": doc.root.to_dict(shallow=True)}


@app.post("/api/merge")
def merge(req: MergeReq):
    docs = []
    for p in req.paths:
        if not os.path.exists(p):
            raise HTTPException(status_code=404, detail=f"file not found: {p}")
        docs.append(tapfile.open_document(p))
    try:
        merged = ops.merge_documents(docs)
    except ops.OpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    merged.save(req.out)
    STATE["doc"] = merged
    STATE["path"] = os.path.abspath(req.out)
    return {"ok": True, "path": STATE["path"], "events": len(merged.events()),
            **_summary(merged), "root": merged.root.to_dict(shallow=True)}


@app.post("/api/split")
def split(req: SplitReq):
    doc = _doc()
    try:
        outs = ops.split_document(doc, req.out_prefix, req.chunk, req.start_seq)
    except ops.OpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "files": outs}


@app.get("/api/export")
def export(fmt: str):
    doc = _doc()
    base = STATE["path"] or os.path.join(os.getcwd(), "export.tap3")
    stem = os.path.splitext(base)[0]
    fmt = fmt.lower()
    try:
        if fmt == "csv":
            path = stem + ".csv"; doc.export_csv(path)
        elif fmt == "json":
            path = stem + ".json"; doc.export_json(path)
        elif fmt == "xml":
            path = stem + ".xml"; doc.export_xml(path)
        elif fmt == "listing":
            path = stem + ".lis"; doc.export_listing(path)
        elif fmt == "stat":
            path = stem + ".stat.txt"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(doc.statistic_report())
        else:
            raise HTTPException(status_code=400, detail="fmt must be csv|json|xml|listing|stat")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True, "path": os.path.abspath(path)}


@app.get("/api/reveal")
def reveal(path: str):
    """Locate a node by its tree path after a re-render (used after edits)."""
    doc = _doc()
    node = doc.find_by_path(path)
    if node is None:
        raise HTTPException(status_code=404, detail="path not found")
    detail = doc.node_detail(node.node_id)
    return {"id": node.node_id, "path": path, "ancestors": detail.get("ancestors", []),
            "name": node.name, "type": node.type_name, "value": node.value_text,
            "modified": detail.get("modified", False)}


@app.post("/api/clear-marks")
def clear_marks():
    doc = _doc()
    doc.modified_paths.clear()
    return {"ok": True, "modified": 0}


@app.get("/api/modified")
def modified():
    doc = _doc()
    return {"count": len(doc.modified_paths),
            "paths": sorted(doc.modified_paths)[:500]}


@app.get("/api/statistics")
def statistics():
    doc = _doc()
    h = doc.header()
    st = doc.statistics()
    dp = h.get("tapDecimalPlaces") or 0
    currency = h.get("tapCurrency") or h.get("localCurrency") or ""

    def scaled(v):
        if v is None:
            return None
        return round(v / (10 ** dp), dp)

    rows = []
    for name, slot in sorted(st["byType"].items()):
        rows.append({"type": name, "count": slot["count"], "charge": slot["charge"],
                     "chargeScaled": scaled(slot["charge"]), "duration": slot["duration"]})
    audit = {}
    for c in doc.root.children:
        if c.name == "auditControlInfo":
            for item in c.children:
                if item.name in ("totalCharge", "totalTaxValue", "totalDiscountValue",
                                 "callEventDetailsCount", "totalTaxRefund",
                                 "totalDiscountRefund"):
                    audit[item.name] = _int_value(item)
    audit_charge = audit.get("totalCharge")
    return {
        "file": h["file"], "release": h["releaseLabel"],
        "records": st["events"], "auditCount": st["auditCount"],
        "countMatches": st["countMatches"],
        "currency": currency, "localCurrency": h.get("localCurrency"),
        "decimalPlaces": dp,
        "rows": rows,
        "chargeSum": st["chargeSum"], "chargeSumScaled": scaled(st["chargeSum"]),
        "durationSum": st["durationSum"],
        "auditTotalCharge": audit_charge, "auditTotalChargeScaled": scaled(audit_charge),
        "auditMatches": (audit_charge is None or audit_charge == st["chargeSum"]),
        "auditTotalTaxValue": audit.get("totalTaxValue"),
        "auditTotalTaxValueScaled": scaled(audit.get("totalTaxValue")),
        "auditTotalDiscountValue": audit.get("totalDiscountValue"),
        "auditTotalDiscountValueScaled": scaled(audit.get("totalDiscountValue")),
    }


@app.get("/api/dictionary")
def dictionary(type: str, field: str = ""):
    try:
        return dictionary_mod.dictionary(type, field)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/nav")
def nav():
    """Outline for the left navigation pane (batch sections + numbered CEDs)."""
    doc = _doc()
    children = []
    for c in doc.root.children:
        if c.tag_num == 3 and c.tag_class == "APPLICATION":
            items = []
            for i, ev in enumerate(c.children):
                items.append({"index": i + 1, "id": ev.node_id,
                              "label": f"[{i + 1}] CED({ev.type_name or ev.tag_label()})",
                              "type": ev.type_name or ""})
            children.append({"kind": "events", "id": c.node_id, "name": c.name or "callEventDetails",
                             "items": items})
        else:
            children.append({"kind": "section", "id": c.node_id, "name": c.name or c.tag_label(),
                             "type": c.type_name, "childCount": len(c.children)})
    return {"root": {"id": doc.root.node_id, "name": doc.root.name or "DataInterChange"},
            "children": children, "header": doc.header(), "stats": doc.statistics()}


@app.get("/api/types")
def types(q: str = ""):
    module = tapfile.all_modules().get("TAP0311.asn")
    if module is None:
        return {"types": []}
    names = sorted(module.types.keys())
    if q:
        ql = q.lower()
        names = [n for n in names if ql in n.lower()]
    return {"types": names[:500]}


@app.get("/api/schema/{name}")
def schema_type(name: str):
    module = tapfile.all_modules().get("TAP0311.asn")
    t = module.types.get(name) if module else None
    if t is None:
        raise HTTPException(status_code=404, detail="unknown type")
    fields = []
    if t.kind == "sequence":
        fields = [{"name": n, "type": f.describe(), "optional": o} for n, f, o in t.fields]
    elif t.kind == "choice":
        fields = [{"name": n, "type": f.describe(), "optional": False} for n, f in t.alternatives]
    return {"name": name, "kind": t.kind, "tag": t.effective_tag(module), "fields": fields}


# ------------------------------------------------------------------ static
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def serve(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main(argv=None):
    """Entry point used by the Electron shell and the frozen server build."""
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--host", default=os.environ.get("TAP3_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("TAP3_PORT", "8765")))
    ap.add_argument("--open", dest="open_path", default="")
    args, _unknown = ap.parse_known_args(argv)
    if args.open_path and os.path.exists(args.open_path):
        try:
            STATE["doc"] = tapfile.open_document(args.open_path)
            STATE["path"] = os.path.abspath(args.open_path)
        except Exception as exc:  # keep the server usable even with a bad file
            print(f"could not preload {args.open_path}: {exc}", flush=True)
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
