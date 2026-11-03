# Roaming Studio · TAP3 Studio

> Open-source, cross-platform **TAP3 / RAP / NRTRDE** viewer, editor, validator and statistics tool.
> Schema-driven TAP3 tooling with a TD.57 data dictionary, byte-preserving edits and a classic desktop UI.

**English** | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](requirements.txt)
[![Electron](https://img.shields.io/badge/desktop-Electron%2031-47848F?logo=electron&logoColor=white)](desktop/)
[![Platform](https://img.shields.io/badge/desktop-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](desktop/)
[![CI](https://github.com/zhutou0622/roaming-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/zhutou0622/roaming-studio/actions/workflows/ci.yml)
![TAP3](https://img.shields.io/badge/TAP3-3.01%E2%80%933.12-success)

![Roaming Studio](docs/ui-packaged.png)

---

## Overview

Roaming Studio is an independent, open-source implementation of the daily TAP3 workflow used in
roaming settlement: browse the ASN.1 tree of a transfer batch, inspect TD.57 field semantics and
code lists, edit values in place, reconcile charges against `AuditControlInfo`, validate whole
folders of files and export the results.

Delivery options:

- **Electron desktop app** (Windows 10/11, bundled Python backend — no Python required on the target machine)
- **Browser mode** (local FastAPI + build-free frontend, `python run.py`)
- **CLI** (`python -m tap3studio.cli`, pipeline friendly)
- **REST API** (20+ endpoints, scriptable)

**Highlights**

- 15 bundled ASN.1 modules: TAP3.01–3.12, RAP1.01–1.05, NRTRDE 2.1; module chosen by release
- Byte-preserving saves: untouched files re-encode to the exact original bytes, including
  indefinite-length (`0x80 … 00 00`) elements
- TD.57 **Data Dictionary**: description, derivation, conditionality, code lists, validation
  tables, ASN.1 definition and parent types
- 30+ validation rules covering structure, accounting, audit reconciliation, timestamps, BCD and
  duplicates; configurable profiles (severity/off, thresholds)
- Interactive tree editing: schema-driven insertion of child/sibling elements, “modified”
  highlighting, the current call record stays in view
- Large files: 168,605 nodes / 3,883 call records open in ~1.2 s, navigation in milliseconds
- CSV / JSON / Tap3Info XML / listing / statistics export, merge, split, batch scan and RAP returns

---

## Features

| Area | Capability |
| --- | --- |
| Parsing | 15 bundled ASN.1 modules (TAP3.01–3.12, RAP1.01–1.05, NRTRDE 2.1); release-based selection; definite and indefinite BER lengths; CHOICE wire form; BCD / numeric / HexString / INTEGER semantics |
| Browsing | `DataInterChange → transferBatch → batchControlInfo / accountingInfo / networkInfo / messageDescriptionInfo / callEventDetails / auditControlInfo`; lazy tree, batch sections expand fully on click |
| Data Dictionary | Description / Derivation / Conditionality / Values / Validations / ASN.1 Definition / Parent Types; available for TAP, RAP and NRTRDE types |
| Editing | Value and HEX editing, clone, delete; schema-driven insertion of child/sibling elements (placed in SEQUENCE order, duplicate fields rejected); modified values highlighted; `Ctrl+S` overwrites the original file name in place |
| Validation | Structure, accounting, network, events, timestamps, audit reconciliation, BCD syntax and duplicates; findings are clickable; profiles allow per-rule severity/off, duration threshold, charge tolerance and duplicate detection toggle |
| Statistics | Per-event-type counts, charges and durations, reconciled with `AuditControlInfo.totalCharge` and `totalTaxValue` |
| File operations | Merge (release-safe), split, export CSV/JSON/XML/listing/statistics; listing import (own format); batch folder scan (CLI + UI, CSV/Excel); generate RAP1.05 return files (`SevereReturn` / `FatalReturn`) |
| Display | BCD alias fields such as `CallingNumber` and `CalledNumber` are decoded through their alias chain (no mojibake); `recEntityCode` is resolved against `NetworkInfo.recEntityInfo`, e.g. `2 (MSC 1, 12844440025)` |
| Navigation | `Ctrl+Home` / `Ctrl+End` jump to the first/last call; `Go to Call…` by index |
| Performance | 168,605 nodes / 3,883 records: open 1.2 s, switch call 8 ms, validate 0.27 s |
| Delivery | Electron desktop app, browser mode, CLI, REST API |

## Screenshots

| Large file (168k nodes) | File statistics and audit reconciliation |
| --- | --- |
| ![Large file](docs/ui-large-file.png) | ![Statistics](docs/ui-statistics.png) |

| Batch section fully expanded | Edit marks and last-call jump |
| --- | --- |
| ![Section](docs/ui-section-expanded.png) | ![Edit mark](docs/ui-edit-highlight.png) |

| Insert child / sibling wizard | Jump to the last call |
| --- | --- |
| ![Insert](docs/ui-insert-dialog.png) | ![Last call](docs/ui-last-call.png) |

---

## Quick start

### 1. Desktop app (recommended, Windows 10/11, no Python needed)

Download from [Releases](https://github.com/zhutou0622/roaming-studio/releases):

- `Roaming-Studio-<version>-portable.exe` — portable, double-click to run
- `Roaming-Studio-Setup-<version>.exe` — installer with Start menu and desktop shortcuts

Build locally:

```bat
pip install -r requirements.txt
pyinstaller --noconfirm --onedir --name tap3-server --distpath dist/onedir ^
  --add-data "tap3studio/schema;tap3studio/schema" --add-data "web;web" ^
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan.on ^
  --exclude-module numpy --exclude-module pandas --exclude-module PIL --exclude-module jedi ^
  --exclude-module matplotlib --exclude-module tkinter --exclude-module IPython ^
  --exclude-module Pythonwin --exclude-module win32com ^
  server_entry.py

cd desktop
npm install
npm run dist        :: release\Roaming-Studio-Setup-*.exe + portable
```

> If your shell sets `ELECTRON_RUN_AS_NODE=1` (some IDEs do), start with
> `env -u ELECTRON_RUN_AS_NODE npm start`.

### 2. Browser / development mode

```bat
pip install -r requirements.txt
python run.py                                 :: http://127.0.0.1:8765
python run.py --open samples\demo.tap3        :: load a file at startup
```

### 3. CLI

```bat
python -m tap3studio.cli generate samples\demo.tap3 --events 500
python -m tap3studio.cli info samples\demo.tap3
python -m tap3studio.cli validate samples\demo.tap3 --json
python -m tap3studio.cli events samples\demo.tap3 --limit 20
python -m tap3studio.cli search samples\demo.tap3 26201
python -m tap3studio.cli dump samples\demo.tap3 --limit 80
python -m tap3studio.cli merge a.tap3 b.tap3 --out merged.tap3
python -m tap3studio.cli split samples\demo.tap3 --prefix part_ --chunk 100
python -m tap3studio.cli export samples\demo.tap3 --fmt csv --out records.csv
python -m tap3studio.cli batch "D:\tap_in" --pattern "*.tap3" --csv scan.csv --xlsx scan.xlsx
python -m tap3studio.cli rap samples\demo.tap3 --out return_RAP.rap --errors-only
python -m tap3studio.cli import-listing records.lis --out imported.tap3
python -m tap3studio.cli validate file.tap3 --profile profiles/operator-a.json
```

`samples/demo.tap3` is produced by the built-in generator (mixed MO / MT / GPRS with a complete
audit group) and can be used for demos and tests.

---

## Supported formats

| Format | Status |
| --- | --- |
| TAP3 (releases 1–4, 9–12) | ✅ Structured browsing/editing/validation; TAP3.01–3.12 modules bundled and selected by release |
| RAP1 (releases 1–5) | ✅ Dedicated schema: browsing/editing/dictionary; field-level validation currently targets TAP3 (batch scan marks RAP files as SKIPPED) |
| NRTRDE 2.1 | ✅ Dedicated schema: browsing/editing/dictionary; no field-level validation yet |
| Listing (own format) | ✅ Export; import rebuilds a TAP3 skeleton from record attributes |
| Tap3Info XML / CSV / JSON | ✅ Export |

> Any BER file can still be opened as a generic TLV tree; fields outside the schema are annotated
> with warnings instead of failing the decode.

---

## Architecture

```
TapStudio/
├─ run.py                    # uvicorn launcher (optional pre-open file)
├─ server_entry.py           # PyInstaller entry point
├─ tap3studio/
│  ├─ asn1model.py           # TD.57 ASN.1 parser → type model
│  ├─ ber.py                 # BER codec (tag / offset / indefinite length preserved)
│  ├─ tapfile.py             # Tap3Document: annotation, events, editing, export, marks
│  ├─ builder.py             # schema + dict → valid TAP3 subtrees
│  ├─ generator.py           # synthetic TAP3.11 test files
│  ├─ dictionary.py          # TD.57 text / code lists / validation tables / ASN.1 rendering
│  ├─ validate.py            # validation rule engine
│  ├─ rap.py                 # validation findings → RAP1.05 return file
│  ├─ batch.py               # batch scanning and CSV/Excel summaries
│  ├─ ops.py                 # merge / split / listing import
│  ├─ server.py              # FastAPI REST + static frontend
│  └─ schema/                # TAP0301–0312, RAP0101–0105, NRT0201 (15 modules)
├─ web/                      # classic Win32-style frontend (no build step)
├─ desktop/                  # Electron shell (main / backend / preload / tests)
├─ tests/                    # 65 unit and performance regression tests
└─ docs/                     # screenshots, performance and fix notes
```

### Design principles

1. **Schema driven** — parse TD.57 ASN.1 text into a tag → field/type map; sniff
   `releaseVersionNumber` before selecting a module and only fall back when the mismatch is high.
2. **Byte fidelity** — every node keeps tag class/number, offset, payload and `indefinite` flag;
   editing replaces only the target payload, and untouched files re-encode to the original bytes.
3. **Wire form and value semantics** — CHOICE values carry the chosen alternative's tag; BCD,
   numeric and HexString values are resolved through the alias + tag chain
   (`CallingNumber → AddressStringDigits → BCDString`).
4. **Large-file first** — header name index + cache, shallow node details, `/api/tree` depth
   limits with a 20k node budget, chunked navigation with incremental loading.
5. **Stateless frontend + REST** — every operation can be scripted through HTTP.

---

## Performance (measured)

Sample: 1.08 MB TAP3.12, **168,605 ASN.1 nodes / 3,883 call records**.

| Operation | Before | After |
| --- | --- | --- |
| Open file | 2.0 s | **1.2 s** |
| header calculation (state/nav/save) | 4.3 s per call | **< 1 ms** |
| Open `callEventDetails` | 65.6 MB JSON, UI freeze | **0.34 s / 3,884 rows** |
| Node details (root) | 70.7 MB JSON | **0.7 KB** |
| Navigation tree (3,883 rows) | one-shot DOM | **400 rows per chunk + scroll loading** |
| Save untouched file | 1 byte larger | **byte-identical** |

Root causes, reproduction scripts and interaction fixes: [docs/performance.md](docs/performance.md)
(English summary + Chinese details).

---

## Validation rules

| Group | Codes | Examples |
| --- | --- | --- |
| Structure | `TAP-001..008` | missing batchControlInfo, missing mandatory items (`fileTypeIndicator` is optional per TD.57), bad fileSequenceNumber, unsupported release, unmapped schema elements |
| Accounting | `ACC-001..003` | missing accountingInfo / localCurrency / tapDecimalPlaces, dp out of range |
| Network | `NET-001..003` | missing utcTimeOffsetInfo, malformed offsets, undeclared utcTimeOffsetCode |
| Events | `EVT-001..009` | empty event list, unknown type, missing mandatory groups, implausible duration, negative charge, missing charge info, suspected duplicates |
| Timestamps | `TS-001..003` | local timestamp not `CCYYMMDDhhmmss`, UTC offset not `±hhmm` |
| Audit | `AUD-001..007` | missing auditControlInfo, `callEventDetailsCount` mismatch, `totalCharge` mismatch (de-duplicated ChargeDetail sum reported as AUD-006), `totalTaxValue` mismatch (AUD-007), earliest > latest |
| Syntax | `BCD-001` | IMSI / MSISDN / IMEI not valid BCD |

`tap3studio.cli validate` exits with code 1 when errors are present, so it can gate a pipeline.

---

## REST API (selection)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/state` | Current file summary + root node |
| POST | `/api/open` | Open `{path}`; empty generates a test file |
| POST | `/api/tree` | Lazy subtree `{id,depth}` (20k node budget) |
| GET | `/api/node/{id}` | Shallow node details + ancestor chain + raw bytes |
| POST | `/api/value` / `/api/delete` / `/api/clone` | Editing operations |
| GET | `/api/insert/options?id=` | Schema fields/alternatives insertable at a node |
| POST | `/api/insert` | Insert a child/sibling element |
| POST | `/api/save` | Overwrite the given path (no renaming, no extension added) |
| GET/POST | `/api/validate` | Full validation (POST accepts `profile`) |
| GET | `/api/rules` | Rule catalogue, default severities and thresholds |
| GET | `/api/rec-entities` | recEntityCode → entity mapping |
| POST | `/api/import-listing` | Rebuild a TAP3 skeleton from listing text |
| POST | `/api/batch` / `/api/batch/export` | Batch scan / export CSV or Excel |
| POST | `/api/rap` | Generate a RAP1.05 return file from findings |
| GET | `/api/statistics` | Per-type statistics + audit reconciliation |
| GET | `/api/dictionary?type=&field=` | TD.57 dictionary entry |
| GET | `/api/events` / `/api/hex` / `/api/search` | Record table / bytes / search |
| POST | `/api/replace` / `/api/merge` / `/api/split` | Replace / merge / split |
| GET | `/api/export?fmt=csv\|json\|xml\|listing\|stat` | Export |

See `tap3studio/server.py` for the complete endpoint list and request bodies.

---

## Testing

```bat
python -m unittest discover -s tests -v          :: 65 tests (performance/save/insert/profiles/batch/schemas/RAP/listing/display)
python -m tap3studio.cli validate samples\demo.tap3

cd desktop
npx electron uitest.js                            :: 14 basic UI checks
npx electron uitest-large.js "<large TAP file>"   :: 24+ checks (context menu/Find/edit/stats/last call/save/RAP/batch/display)
npx electron uitest-sections.js "<large TAP file>":: 10 checks (batch sections expand)
npx electron perf.js "<large TAP file>"           :: performance probe
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs Python tests, frontend syntax checks
and a backend launch smoke test on every push and pull request.

---

## Roadmap

- [x] Insert child/sibling wizard (SEQUENCE-ordered, duplicate fields rejected)
- [x] Dedicated schemas for TAP3.01–3.12, RAP1.01–1.05 and NRTRDE 2.1
- [x] Generate RAP return files from validation findings (`SevereReturn` / `FatalReturn` / audit)
- [x] Configurable validation profiles (JSON rules, severity/off, thresholds, error overrides)
- [x] Batch folder scan + CSV/Excel reports (CLI + UI)
- [x] Listing export/import round trip (own format)
- [x] Electron desktop packaging + frozen backend
- [x] Large-file performance work and interaction regressions
- [ ] **Native** operator `.lis` column parser (needs a real listing sample)

---

## Background and disclaimer

This project is an independent implementation. It is not affiliated with, endorsed by or licensed
by **Semantix**, **XINTEC**, **INFOBRAIN AG** or any commercial TAP3 editor vendor. The UI follows
the familiar desktop layout used in roaming settlement tools; the code, schema parser, validation
rules and frontend are all original work. No third-party program code or assets are copied,
decompiled or redistributed.

TAP3 / TD.57 / TADIG are GSMA specifications and trademarks. The bundled ASN.1 modules and
dictionary text come from public specifications and are used for interoperability. Always defer to
the official GSMA releases, and verify redistribution terms for the schema text before publishing.

⚠️ **Beta**: validate against your own test files before using it in production settlement.
The repository contains no operator customer data; files under `samples/` are synthetic.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
([中文](CONTRIBUTING.zh-CN.md)) for the development setup, test commands and code conventions.

## License

[MIT](LICENSE) © 2026 Roaming Studio contributors
