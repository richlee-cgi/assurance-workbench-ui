# assurance-workbench-ui

Local HTMX web UI wrapper for `assurance-cli`.

The CLI remains the evidence engine. This app is a local browser interface for configuring evidence runs, previewing commands, saving results into a Workbench evidence folder, and inspecting completed evidence packs.

The browser-facing name is **Assure-O-Matic 3000 Workbench**.

## New User Start Here

If you want the browser app, clone this repo first. Installing it also installs `assurance-cli` from GitHub as a Python dependency, so the install needs network access to GitHub.

Mac/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/richlee-cgi/assurance-workbench-ui/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/richlee-cgi/assurance-workbench-ui/main/install.ps1 | iex
```

The installer checks Python 3.11+ and Git, clones or updates the Workbench repo, creates `.venv`, installs the app and CLI dependency, and reports whether optional provider CLIs (`az`, `gh`, `pac`) are available. It does not install optional provider CLIs, change credentials, or change shell profiles.

Manual setup:

```bash
git clone https://github.com/richlee-cgi/assurance-workbench-ui.git
cd assurance-workbench-ui
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
./run.sh
```

Then open `http://127.0.0.1:8765`, go to Settings, set your Workbench output folder and source defaults, and run **Check assurance CLI**.

Before running Confluence or Jira evidence, make sure the terminal that starts Workbench has Atlassian environment variables set:

```powershell
$env:ATLASSIAN_BASE_URL = "https://example.atlassian.net"
$env:ATLASSIAN_EMAIL = "you@example.com"
$env:ATLASSIAN_API_TOKEN = "..."
```

For Mac/Linux shells, use `export ATLASSIAN_BASE_URL=...`, `export ATLASSIAN_EMAIL=...` and `export ATLASSIAN_API_TOKEN=...`.

Clone `assurance-cli` separately only if you want to develop the CLI itself or pin the UI to a local CLI checkout. The Settings page still supports an explicit `assurance` executable path as an override.

For local development across both repos, activate the Workbench virtualenv and install the CLI checkout in editable mode:

```bash
python -m pip install -e ../assurance-cli
```

## Install

```bash
cd assurance-workbench-ui
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

### Windows setup

Use PowerShell from the cloned repo:

```powershell
cd assurance-workbench-ui
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If PowerShell blocks virtual environment activation, allow locally-created scripts for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Workbench can use the `assurance-cli` dependency installed in the same virtualenv. Set the Assurance CLI path only when you want to override that default with a separate CLI checkout, for example:

```text
C:\path\to\assurance-cli\.venv\Scripts\assurance.exe
```

Use Windows paths for the Workbench root and repo roots, for example:

```text
C:\Users\name\Workbench
C:\Users\name\dev
```

## Run

Mac/Linux:

```bash
./run.sh
```

Windows:

```powershell
.\run.ps1
```

Then open:

```text
http://127.0.0.1:8765
```

You can still run Uvicorn directly if needed:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

## Restarting The Workbench

The installer does not create a background service or startup item. After a reboot, open a terminal and start the local server again from the cloned repo.

Mac/Linux:

```bash
cd ~/dev/assurance-workbench-ui
./run.sh
```

Windows:

```powershell
cd "$HOME\dev\assurance-workbench-ui"
.\run.ps1
```

Then open:

```text
http://127.0.0.1:8765
```

## Current Scope

Implemented:

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
- Local user guide.
- Mechanical gaps, warnings, checks and analyst brief artifacts generated from completed evidence packs.
- Health endpoint.
- Route tests.

Not implemented:

- Local LLM analysis.
- RAG or long-term indexed knowledge store.

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

Leave `assurance_path` blank to use the `assurance-cli` dependency installed with this app. Set it only when you want to use a separate local CLI executable.

## Evidence Form Options

Configured exclusions are applied to evidence runs automatically. `Exclude Confluence from parent` accepts page IDs or Confluence page URLs. `Excluded Jira teams` uses exact team names and the configured `Jira team exclusion field`, which can be `Team` or a Jira custom field ID such as `customfield_12345`.

`Code repositories` enables local Git repository evidence. The UI passes selected repo roots and repo names to `assurance report evidence-pack --include-code`, so the CLI can search local files, recent commits and repository metadata.

`GitHub fallback` is only useful with code or PR evidence. It allows the CLI to use the GitHub CLI (`gh`) for read-only PR lookup when a Jira-linked PR or other GitHub detail cannot be resolved from local repositories alone. It depends on local `gh` authentication.

`Refresh cache` tells `assurance-cli` to bypass existing Atlassian cache entries for this run and update the cache with fresh responses.

`No cache` disables cache reads and writes for this run. Use it for one-off live retrievals or when cached evidence may be misleading.

## Output Files

Each run is saved to a timestamped folder under the configured Workbench evidence root.

Common files:

- `evidence-pack.md`: the main Markdown evidence bundle from `assurance-cli`.
- `stdout.log` and `stderr.log`: raw command output streams.
- `command.txt`: the exact CLI command that was run.
- `request.json`: saved UI form settings, used for re-run.
- `exit-code.txt`: the CLI process exit code.
- `gaps-and-warnings.md`: browser-friendly Markdown summary of mechanical gaps and warnings.
- `gaps-and-warnings.json`: structured version of the same findings.
- `assurance-checks.md`: deterministic checks derived from the completed evidence pack.
- `analyst-brief.md`: a short, non-AI briefing file for a human analyst.

These files are intended to be readable directly in VS Code, Typora or the Workbench results view.

## HTMX Asset Strategy

The template references `/static/vendor/htmx.min.js` so the app can work offline on corporate machines.

Vendored asset:

- Package: `htmx.org`
- Version: `2.0.10`
- Source: `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js`

Update the vendored file manually when upgrading HTMX.
