"""Command line interface for TAP3 Studio.

    python -m tap3studio.cli info file.tap3
    python -m tap3studio.cli validate file.tap3 --json
    python -m tap3studio.cli events file.tap3 --limit 20
    python -m tap3studio.cli generate out.tap3 --events 100
    python -m tap3studio.cli merge a.tap3 b.tap3 --out merged.tap3
    python -m tap3studio.cli split file.tap3 --prefix part_ --chunk 100
    python -m tap3studio.cli export file.tap3 --fmt csv
    python -m tap3studio.cli dump file.tap3 --limit 40
    python -m tap3studio.cli search file.tap3 26201
    python -m tap3studio.cli set file.tap3 123 26201999 --out edited.tap3
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import batch, generator, ops, rap, rules, tapfile, validate


def cmd_info(args):
    doc = tapfile.open_document(args.file)
    h = doc.header()
    st = doc.statistics()
    print(f"file         : {h['file']} ({h['size']} bytes)")
    print(f"release      : {h['releaseLabel']}   schema: {h['schema']}")
    print(f"sender       : {h['sender']}   recipient: {h['recipient']}")
    print(f"sequence     : {h['fileSequenceNumber']}   available: {h['fileAvailableTimeStamp']}")
    print(f"currency     : {h['localCurrency']} -> {h['tapCurrency']} (dp={h['tapDecimalPlaces']})")
    print(f"records      : {st['events']}  auditCount={st['auditCount']}")
    dp = h["tapDecimalPlaces"] or 0
    print(f"total charge : {st['chargeSum'] / (10 ** dp):.{dp}f}")
    for k, v in sorted(st["byType"].items()):
        print(f"  {k:<26} {v['count']:>6} records  {v['charge']:>10} units  {v['duration']:>8}s")
    return 0


def cmd_validate(args):
    doc = tapfile.open_document(args.file)
    profile = rules.normalize(path=args.profile) if args.profile else None
    r = validate.validate(doc, profile)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"{r['file']}: {r['release']}  records={r['records']}  "
              f"errors={r['errors']} warnings={r['warnings']}")
        for f in r["findings"]:
            print(f"  [{f['severity']:<7}] {f['code']}  {f['message']}")
    return 1 if r["errors"] else 0


def cmd_events(args):
    doc = tapfile.open_document(args.file)
    rows = doc.events_json()
    for i, r in enumerate(rows[: args.limit]):
        print(f"{i:>4} {r['type']:<22} {str(r.get('subscriber') or ''):<18} "
              f"{str(r.get('called') or ''):<16} {r.get('duration') or 0:>6}s "
              f"charge={r.get('charge')}")
    print(f"-- {len(rows)} records")
    return 0


def cmd_rap(args):
    doc = tapfile.open_document(args.file)
    profile = rules.normalize(path=args.profile) if args.profile else None
    result = validate.validate(doc, profile)
    findings = [f for f in result["findings"] if f["severity"] == "error" or not args.errors_only]
    if not findings:
        print("no findings to return")
        return 1
    rapdoc = rap.build_rap(doc, findings)
    out = args.out or rap.rap_filename(args.file)
    rapdoc.save(out)
    details = sum(1 for n in rapdoc.nodes.values()
                  if n.name in ("severeReturn", "fatalReturn", "stopReturn", "missingReturn"))
    print(f"{out}: {rapdoc.release_label}, {details} return detail(s), "
          f"{len(findings)} finding(s) from {args.file}")
    return 0


def cmd_batch(args):
    profile = rules.normalize(path=args.profile) if args.profile else None
    rows = batch.scan(args.paths, profile, args.pattern)
    head = f"{'File':<44}{'Release':<9}{'Recs':>6}{'Err':>5}{'Warn':>6}{'Status':>8}"
    print(head)
    print("-" * len(head))
    for row in rows:
        print(f"{row['file'][:42]:<44}{row['release']:<9}{row['records']:>6}"
              f"{row['errors']:>5}{row['warnings']:>6}{row['status']:>8}")
    total = batch.summary(rows)
    print("-" * len(head))
    print(f"files={total['files']} ok={total['ok']} errors={total['with_errors']} "
          f"failed={total['failed']} skipped={total.get('skipped', 0)} "
          f"records={total['records']} findings={total['errors']}E/{total['warnings']}W")
    if args.csv:
        print("csv:", batch.write_csv(rows, args.csv))
    if args.xlsx:
        print("xlsx:", batch.write_xlsx(rows, args.xlsx))
    return 1 if (total["with_errors"] or total["failed"]) else 0


def cmd_import_listing(args):
    try:
        doc = ops.import_listing(args.file)
    except ops.OpsError as exc:
        print(f"import failed: {exc}")
        return 2
    doc.save(args.out)
    print(f"{args.out}: {len(doc.events())} event(s) rebuilt from {args.file}")
    return 0


def cmd_export(args):
    doc = tapfile.open_document(args.file)
    out = args.out
    if args.fmt == "csv":
        doc.export_csv(out)
    elif args.fmt == "json":
        doc.export_json(out)
    elif args.fmt == "xml":
        doc.export_xml(out)
    elif args.fmt == "listing":
        doc.export_listing(out)
    elif args.fmt == "stat":
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(doc.statistic_report())
    else:
        raise SystemExit(f"unknown fmt {args.fmt}")
    print(out)
    return 0


def cmd_generate(args):
    doc = generator.make_document(args.events, args.seed, args.sender, args.recipient, args.currency)
    doc.save(args.out)
    print(f"{args.out}: {os.path.getsize(args.out)} bytes, {len(doc.events())} records")
    return 0


def cmd_merge(args):
    docs = [tapfile.open_document(p) for p in args.files]
    merged = ops.merge_documents(docs)
    merged.save(args.out)
    print(f"{args.out}: {len(merged.events())} records")
    return 0


def cmd_split(args):
    doc = tapfile.open_document(args.file)
    outs = ops.split_document(doc, args.prefix, args.chunk, args.start_seq)
    for o in outs:
        print(o)
    return 0


def cmd_dump(args):
    doc = tapfile.open_document(args.file)
    count = 0
    for n in doc.nodes.values():
        print(f"{n.node_id:>6} {'  ' * min(n.path().count('.'), 12)}{n.path().split('.')[-1]:<34}"
              f"{n.tag_label():<9}{n.type_name:<26}{n.value_text[:40]}")
        count += 1
        if args.limit and count >= args.limit:
            break
    return 0


def cmd_search(args):
    doc = tapfile.open_document(args.file)
    q = args.query.lower()
    hits = 0
    for n in doc.nodes.values():
        if q in f"{n.name} {n.type_name} {n.value_text} {n.path()}".lower():
            print(f"{n.node_id:>6} {n.path()}  = {n.value_text[:60]}")
            hits += 1
    print(f"-- {hits} hits")
    return 0


def cmd_set(args):
    doc = tapfile.open_document(args.file)
    node = doc.node(int(args.id))
    doc.set_value(node.node_id, args.value)
    out = args.out or args.file
    doc.save(out)
    print(f"{out}: node {args.id} ({node.path()}) = {args.value}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tap3studio", description="TAP3 Studio CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="file summary"); p.add_argument("file"); p.set_defaults(func=cmd_info)

    p = sub.add_parser("validate", help="run validation rules"); p.add_argument("file")
    p.add_argument("--json", action="store_true")
    p.add_argument("--profile", default="", help="validation profile JSON")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("events", help="list call events"); p.add_argument("file")
    p.add_argument("--limit", type=int, default=50); p.set_defaults(func=cmd_events)

    p = sub.add_parser("import-listing", help="rebuild a TAP3 skeleton from a listing file")
    p.add_argument("file")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_import_listing)

    p = sub.add_parser("rap", help="generate a RAP1 return file from validation findings")
    p.add_argument("file")
    p.add_argument("--out", default="")
    p.add_argument("--profile", default="")
    p.add_argument("--errors-only", action="store_true")
    p.set_defaults(func=cmd_rap)

    p = sub.add_parser("batch", help="scan a folder of TAP files")
    p.add_argument("paths", nargs="+")
    p.add_argument("--pattern", default="*")
    p.add_argument("--profile", default="")
    p.add_argument("--csv", default="")
    p.add_argument("--xlsx", default="")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("export", help="export csv/json/xml/listing/stat"); p.add_argument("file")
    p.add_argument("--fmt", default="csv"); p.add_argument("--out", required=True); p.set_defaults(func=cmd_export)

    p = sub.add_parser("generate", help="create a synthetic TAP3 file"); p.add_argument("out")
    p.add_argument("--events", type=int, default=100); p.add_argument("--seed", type=int, default=7)
    p.add_argument("--sender", default="26201"); p.add_argument("--recipient", default="22801")
    p.add_argument("--currency", default="EUR"); p.set_defaults(func=cmd_generate)

    p = sub.add_parser("merge", help="merge TAP3 files"); p.add_argument("files", nargs="+")
    p.add_argument("--out", required=True); p.set_defaults(func=cmd_merge)

    p = sub.add_parser("split", help="split into chunks"); p.add_argument("file")
    p.add_argument("--prefix", required=True); p.add_argument("--chunk", type=int, default=1000)
    p.add_argument("--start-seq", type=int, default=None); p.set_defaults(func=cmd_split)

    p = sub.add_parser("dump", help="annotated tree dump"); p.add_argument("file")
    p.add_argument("--limit", type=int, default=80); p.set_defaults(func=cmd_dump)

    p = sub.add_parser("search", help="search names/values"); p.add_argument("file")
    p.add_argument("query"); p.set_defaults(func=cmd_search)

    p = sub.add_parser("set", help="edit one node value"); p.add_argument("file")
    p.add_argument("id"); p.add_argument("value"); p.add_argument("--out", default="")
    p.set_defaults(func=cmd_set)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
