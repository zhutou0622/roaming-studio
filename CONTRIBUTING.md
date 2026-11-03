# Contributing

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for helping with Roaming Studio (TAP3 Studio). This is the minimal development loop.

## Environment

- Python **3.9+** (3.11 recommended)
- Node.js **20+** (desktop shell and frontend tests only)
- Windows 10/11 for packaging the desktop app; web/CLI run everywhere

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd desktop && npm install && cd ..
```

## Repository map

| Path | Contents |
| --- | --- |
| `tap3studio/` | parsing, editing, validation, dictionary, REST service, CLI |
| `web/` | classic Win32-style frontend (no build step) |
| `desktop/` | Electron shell, PyInstaller backend packaging, UI regression scripts |
| `tests/` | unit and performance regressions (large-file fixtures are skipped when absent) |
| `docs/` | screenshots, performance and fix notes |

## Development

```bash
python run.py --open samples/demo.tap3
cd desktop && npm start            # unset ELECTRON_RUN_AS_NODE first
```

## Before committing

```bash
python -m unittest discover -s tests -v
node --check web/app.js

cd desktop
npx electron uitest.js
# with a large TAP file:
npx electron uitest-large.js "<file>"
npx electron uitest-sections.js "<file>"
```

## Conventions

- Python: prefer the standard library; new parsing/validation logic needs unit tests; do not add
  full-table scans on hot paths (see `docs/performance.md`).
- Frontend: no framework, no build step; cap or chunk DOM row counts; every popup must close on
  outside click, `Esc` and scroll.
- When changing schemas or dictionary text, cite the TD.57 source and do not introduce
  non-public material.
- Never commit customer TAP data, `dist/`, `release/` or `node_modules/`.

## Pull request checklist

- [ ] New or changed behaviour has tests (Python or `desktop/uitest*.js`)
- [ ] `python -m unittest discover -s tests` passes
- [ ] `node --check` passes and the console shows no renderer errors
- [ ] Relevant docs updated (README / docs / desktop/README)
- [ ] No credentials, customer data or large files

Commit messages: `type(scope): summary`, e.g. `fix(ui): keep call view after edit`.
