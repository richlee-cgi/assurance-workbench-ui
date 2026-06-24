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
- Settings page with local persistence.
- Assurance CLI health check.
- Azure and Dataverse CLI health checks through `assurance-cli`.
- Evidence-pack form with HTMX command preview.
- Evidence-pack execution with timestamped run folders.
- Health endpoint.
- Route tests.

Not implemented yet:

- Streaming long-running command progress.
- Results viewer.
- Deterministic analysis.

## Settings

Settings are stored locally in `.assurance-workbench-ui.json`, which is ignored by Git.

Stored values:

- `assurance_path`
- `workbench_root`
- `confluence_space`
- `jira_project`
- `azure_resource_group`

The UI does not store API tokens or credentials.

## HTMX Asset Strategy

The template references `/static/vendor/htmx.min.js` so the app can work offline on corporate machines.

Vendored asset:

- Package: `htmx.org`
- Version: `2.0.10`
- Source: `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js`

Update the vendored file manually when upgrading HTMX.
