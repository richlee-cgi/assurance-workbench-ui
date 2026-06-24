# assurance-workbench-ui

Local HTMX web UI wrapper for `assurance-cli`.

The CLI remains the evidence engine. This app is a local browser interface for configuring evidence runs, previewing commands, and eventually saving results into a Workbench evidence folder.

## Install

```bash
cd assurance-workbench-ui
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

## Current Scope

Implemented first slice:

- FastAPI app shell.
- Jinja templates.
- HTMX-ready static layout.
- Home page.
- Settings page shell.
- Health endpoint.
- Route tests.

Not implemented yet:

- Running `assurance-cli`.
- Persisting Workbench runs.
- Evidence pack form.
- Results viewer.
- Deterministic analysis.

## HTMX Asset Strategy

The template references `/static/vendor/htmx.min.js` so the app can work offline on corporate machines. The checked-in file is a placeholder until the real HTMX distribution file is vendored.

Before relying on HTMX interactions, replace `app/static/vendor/htmx.min.js` with an official `htmx.min.js` release.
