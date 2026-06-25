# assurance-workbench-ui

Local HTMX web UI wrapper for `assurance-cli`.

The CLI remains the evidence engine. This app is a local browser interface for configuring evidence runs, previewing commands, saving results into a Workbench evidence folder, and inspecting completed evidence packs.

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
- Evidence-pack form with HTMX command preview, including optional local code repository evidence, PR metadata and bounded diffs.
- Local repository discovery through `assurance code repos`.
- Output folder preview for the next evidence run.
- Evidence-pack execution with timestamped run folders, polling progress and cancellation.
- Results list for saved evidence runs.
- Result detail view with run metadata, source coverage, command, rendered evidence, warnings, logs, saved-file links and local open actions.
- Previous-run filters and re-run from saved request metadata.
- Health endpoint.
- Route tests.

Not implemented yet:

- Deterministic analysis.

## Settings

Settings are stored locally in `.assurance-workbench-ui.json`, which is ignored by Git.

Stored values:

- `assurance_path`
- `workbench_root`
- `confluence_space`
- `jira_project`
- `azure_resource_group`
- `repo_roots`
- `repos`
- `exclude_confluence_parents`
- `jira_team_field`
- `exclude_jira_teams`

The UI does not store API tokens or credentials.

## Evidence Form Options

Configured exclusions are applied to evidence runs automatically. `Exclude Confluence from parent` accepts page IDs or Confluence page URLs. `Exclude Jira from Team` uses exact team names and the configured `Jira team field`, which can be `Team` or a Jira custom field ID such as `customfield_12345`.

`Code repositories` enables local Git repository evidence. The UI passes selected repo roots and repo names to `assurance report evidence-pack --include-code`, so the CLI can search local files, recent commits and repository metadata.

`GitHub fallback` is only useful with code or PR evidence. It allows the CLI to use the GitHub CLI (`gh`) for read-only PR lookup when a Jira-linked PR or other GitHub detail cannot be resolved from local repositories alone. It depends on local `gh` authentication.

`Refresh cache` tells `assurance-cli` to bypass existing Atlassian cache entries for this run and update the cache with fresh responses.

`No cache` disables cache reads and writes for this run. Use it for one-off live retrievals or when cached evidence may be misleading.

## HTMX Asset Strategy

The template references `/static/vendor/htmx.min.js` so the app can work offline on corporate machines.

Vendored asset:

- Package: `htmx.org`
- Version: `2.0.10`
- Source: `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js`

Update the vendored file manually when upgrading HTMX.
