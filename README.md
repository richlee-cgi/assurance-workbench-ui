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

The template references `/static/vendor/htmx.min.js` so the app can work offline on corporate machines.

Vendored asset:

- Package: `htmx.org`
- Version: `2.0.10`
- Source: `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js`

Update the vendored file manually when upgrading HTMX.
