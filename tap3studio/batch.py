"""Batch scanning: validate many TAP files and summarise the result.

Used by ``python -m tap3studio.cli batch <dir>`` and by automation that wants
a per-file status table instead of opening each file in the UI.
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

from . import tapfile, validate


def collect(paths: Iterable[str], pattern: str = "*") -> List[str]:
    import fnmatch

    files: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                if os.path.isfile(full) and fnmatch.fnmatch(name, pattern):
                    files.append(full)
        elif os.path.isfile(path):
            files.append(path)
        else:
            files.append(path)          # keep it: scan() reports it as missing
    return files


def scan(paths: Iterable[str], profile: Optional[dict] = None,
         pattern: str = "*") -> List[Dict]:
    rows: List[Dict] = []
    for path in collect(paths, pattern):
        row = {"file": os.path.basename(path), "path": os.path.abspath(path),
               "release": "", "sender": "", "recipient": "", "records": 0,
               "errors": 0, "warnings": 0, "charge": None, "currency": "",
               "status": "OK", "message": ""}
        try:
            doc = tapfile.open_document(path)
            if getattr(doc, "kind", "tap3") != "tap3":
                row.update({"release": doc.release_label, "status": "SKIPPED",
                            "message": "not a TAP3 file"})
                rows.append(row)
                continue
            result = validate.validate(doc, profile)
            header = doc.header()
            stats = doc.statistics()
            row.update({
                "release": header["releaseLabel"],
                "sender": header["sender"],
                "recipient": header["recipient"],
                "records": result["records"],
                "errors": result["errors"],
                "warnings": result["warnings"],
                "charge": result["chargeSumScaled"],
                "currency": header.get("tapCurrency") or header.get("localCurrency") or "",
                "status": "OK" if result["errors"] == 0 else "ERRORS",
            })
        except Exception as exc:  # unreadable / not a TAP file
            row["status"] = "FAILED"
            row["message"] = str(exc)[:200]
        rows.append(row)
    return rows


COLUMNS = ["file", "release", "sender", "recipient", "records",
           "errors", "warnings", "charge", "currency", "status", "message"]


def write_csv(rows: List[Dict], path: str) -> str:
    import csv

    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_xlsx(rows: List[Dict], path: str) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "TAP scan"
    ws.append(["File", "Release", "Sender", "Recipient", "Records",
               "Errors", "Warnings", "Charge", "Currency", "Status", "Message"])
    header_fill = PatternFill("solid", fgColor="DCE6F2")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    for row in rows:
        ws.append([row.get(col, "") for col in COLUMNS])
    widths = [38, 10, 10, 10, 10, 8, 9, 14, 9, 10, 50]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = width
    ws.freeze_panes = "A2"
    wb.save(path)
    return path


def summary(rows: List[Dict]) -> Dict:
    return {
        "files": len(rows),
        "ok": sum(1 for r in rows if r["status"] == "OK"),
        "with_errors": sum(1 for r in rows if r["status"] == "ERRORS"),
        "failed": sum(1 for r in rows if r["status"] == "FAILED"),
        "skipped": sum(1 for r in rows if r["status"] == "SKIPPED"),
        "records": sum(r.get("records") or 0 for r in rows),
        "errors": sum(r.get("errors") or 0 for r in rows),
        "warnings": sum(r.get("warnings") or 0 for r in rows),
    }
