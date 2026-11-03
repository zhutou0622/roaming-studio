"""Validation profiles: rule catalogue, severities and thresholds.

A profile is a small JSON document:

    {
      "name": "operator-a",
      "thresholds": {"maxDurationSeconds": 172800, "chargeTolerance": 0,
                      "duplicateDetection": true},
      "rules": {"NET-003": "off", "EVT-005": "info"}
    }

Rule codes not mentioned keep their default severity.  "off" suppresses a
finding entirely, which mirrors the TADIG "error override" idea.
"""
from __future__ import annotations

import json
from typing import Dict, Iterable, List, Optional

SEVERITIES = ("error", "warning", "info", "off")

# (code, group, default severity, title)
CATALOG = [
    ("TAP-001", "structure", "error", "batchControlInfo missing"),
    ("TAP-002", "structure", "error", "mandatory batch item missing"),
    ("TAP-003", "structure", "error", "fileSequenceNumber is not 5 digits"),
    ("TAP-004", "structure", "warning", "specificationVersionNumber is not 3"),
    ("TAP-005", "structure", "warning", "unknown fileTypeIndicator"),
    ("TAP-006", "structure", "error", "releaseVersionNumber not found"),
    ("TAP-007", "structure", "warning", "unsupported releaseVersionNumber"),
    ("TAP-008", "structure", "warning", "element not mapped to the schema"),
    ("ACC-001", "accounting", "error", "accountingInfo missing"),
    ("ACC-002", "accounting", "error", "mandatory accounting item missing"),
    ("ACC-003", "accounting", "error", "tapDecimalPlaces outside 0..5"),
    ("NET-001", "network", "warning", "networkInfo missing"),
    ("NET-002", "network", "error", "malformed utcTimeOffset"),
    ("NET-003", "network", "warning", "undeclared utcTimeOffsetCode"),
    ("EVT-001", "events", "error", "no call event details"),
    ("EVT-002", "events", "warning", "unknown call event type"),
    ("EVT-003", "events", "error", "mandatory event group missing"),
    ("EVT-004", "events", "error", "callEventStartTimeStamp missing"),
    ("EVT-005", "events", "warning", "totalCallEventDuration missing"),
    ("EVT-006", "events", "error", "implausible totalCallEventDuration"),
    ("EVT-007", "events", "error", "negative charge"),
    ("EVT-008", "events", "warning", "no charge information"),
    ("EVT-009", "events", "warning", "possible duplicate record"),
    ("TS-001", "timestamps", "error", "timestamp component missing"),
    ("TS-002", "timestamps", "error", "timestamp is not CCYYMMDDhhmmss"),
    ("TS-003", "timestamps", "warning", "UTC offset is not +/-hhmm"),
    ("AUD-001", "audit", "error", "auditControlInfo missing"),
    ("AUD-002", "audit", "error", "mandatory audit item missing"),
    ("AUD-003", "audit", "error", "record count does not match"),
    ("AUD-004", "audit", "error", "totalCharge does not match the record sum"),
    ("AUD-005", "audit", "error", "earliestCallTimeStamp > latestCallTimeStamp"),
    ("BCD-001", "syntax", "error", "identifier is not valid BCD"),
]

DEFAULT_SEVERITY: Dict[str, str] = {c: s for c, _g, s, _t in CATALOG}
GROUPS = {c: g for c, g, _s, _t in CATALOG}
TITLES = {c: t for c, _g, _s, t in CATALOG}
GROUP_LABELS = {
    "structure": "Structure / BatchControlInfo",
    "accounting": "AccountingInfo",
    "network": "NetworkInfo",
    "events": "Call event details",
    "timestamps": "Timestamps",
    "audit": "AuditControlInfo",
    "syntax": "Value syntax",
}

DEFAULT_THRESHOLDS = {
    "maxDurationSeconds": 172800,
    "chargeTolerance": 0,
    "duplicateDetection": True,
}


class ProfileError(ValueError):
    pass


def catalog() -> dict:
    return {
        "rules": [{"code": c, "group": g, "severity": s, "title": t}
                  for c, g, s, t in CATALOG],
        "groups": GROUP_LABELS,
        "thresholds": DEFAULT_THRESHOLDS,
        "severities": list(SEVERITIES),
    }


def _coerce(value, default):
    if isinstance(default, bool):
        return bool(value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def normalize(profile: Optional[dict] = None, path: Optional[str] = None) -> dict:
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                profile = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"cannot read profile {path}: {exc}") from exc
    out = {
        "name": "default",
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "rules": {},
    }
    if not profile:
        return out
    if not isinstance(profile, dict):
        raise ProfileError("profile must be an object")
    out["name"] = str(profile.get("name") or "custom")[:60]
    thr = profile.get("thresholds") or {}
    if not isinstance(thr, dict):
        raise ProfileError("thresholds must be an object")
    for key, default in DEFAULT_THRESHOLDS.items():
        if key in thr:
            out["thresholds"][key] = _coerce(thr[key], default)
    rules = profile.get("rules") or {}
    if not isinstance(rules, dict):
        raise ProfileError("rules must be an object")
    for code, severity in rules.items():
        if code not in DEFAULT_SEVERITY:
            continue
        sev = str(severity).lower()
        if sev in SEVERITIES:
            out["rules"][code] = sev
    return out


def apply(findings: Iterable, profile: dict) -> List:
    rules = profile.get("rules", {})
    out = []
    for f in findings:
        severity = rules.get(f.code, f.severity)
        if severity == "off":
            continue
        f.severity = severity
        out.append(f)
    return out
