from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from app.cli import resolve_assurance_path
from app.settings import AppSettings


PRESETS = ("architecture", "delivery", "operations", "dataverse", "performance", "risk")
SOURCES = ("confluence", "jira", "azure", "dataverse", "code")
RUN_FILES = {
    "request.json",
    "command.txt",
    "stdout.log",
    "stderr.log",
    "exit-code.txt",
    "evidence-pack.md",
    "gaps-and-warnings.md",
    "gaps-and-warnings.json",
    "assurance-checks.md",
    "analyst-brief.md",
}
EVIDENCE_PREVIEW_MAX_CHARS = 18_000
EVIDENCE_PREVIEW_MAX_SECTIONS = 4


@dataclass(frozen=True)
class EvidenceForm:
    topic: str = ""
    queries: tuple[str, ...] = ()
    preset: str = ""
    sources: tuple[str, ...] = ("confluence", "jira")
    confluence_space: str = ""
    jira_project: str = ""
    azure_resource_group: str = ""
    repo_roots: tuple[str, ...] = ()
    repos: tuple[str, ...] = ()
    exclude_confluence_parents: tuple[str, ...] = ()
    jira_team_field: str = "Team"
    exclude_jira_teams: tuple[str, ...] = ()
    limit: int = 10
    include_prs: bool = False
    include_diffs: bool = False
    github_fallback: bool = False
    max_diff_lines: int = 500
    include_comments: bool = False
    refresh: bool = False
    no_cache: bool = False
    no_preset_expansion: bool = True


@dataclass(frozen=True)
class EvidenceRunResult:
    run_dir: Path
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    evidence_path: Path
    timed_out: bool = False


@dataclass(frozen=True)
class EvidenceRunSummary:
    id: str
    run_dir: Path
    topic: str
    preset: str
    sources: tuple[str, ...]
    exit_code: int | None
    command: str
    evidence_path: Path
    has_evidence: bool


@dataclass(frozen=True)
class EvidenceRunDetail:
    summary: EvidenceRunSummary
    request: dict[str, Any]
    stdout: str
    stderr: str
    evidence_markdown: str
    evidence_html: str
    warnings: tuple[str, ...]
    warning_items: tuple[GapWarningItem, ...]
    evidence_preview_html: str = ""
    evidence_preview_truncated: bool = False
    evidence_line_count: int = 0
    evidence_char_count: int = 0


@dataclass(frozen=True)
class GapWarningItem:
    kind: str
    text: str
    criteria: tuple[str, ...]
    locations: tuple[str, ...]


@dataclass(frozen=True)
class AssuranceCheck:
    status: str
    title: str
    detail: str
    follow_up: str = ""


@dataclass(frozen=True)
class FileActionResult:
    ok: bool
    message: str
    command: list[str]


def evidence_form_from_data(data: Any, defaults: AppSettings | None = None) -> EvidenceForm:
    default_sources = ("confluence", "jira")
    sources_present = bool(data.get("sources_present"))
    if hasattr(data, "getlist"):
        raw_sources = data.getlist("sources")
    else:
        raw_sources = data.get("sources", () if sources_present else default_sources)
    if isinstance(raw_sources, str):
        raw_sources = (raw_sources,)
    sources = tuple(source for source in raw_sources if source in SOURCES)
    if not sources and not sources_present:
        sources = default_sources
    defaults = defaults or AppSettings()
    return EvidenceForm(
        topic=str(data.get("topic", "")).strip(),
        queries=_split_lines_or_commas(data.get("queries") or ""),
        preset=_valid_preset(str(data.get("preset", "")).strip()),
        sources=sources,
        confluence_space=str(data.get("confluence_space") or defaults.confluence_space).strip(),
        jira_project=str(data.get("jira_project") or defaults.jira_project).strip(),
        azure_resource_group=str(data.get("azure_resource_group") or defaults.azure_resource_group).strip(),
        repo_roots=_split_lines_or_commas(data.get("repo_roots") or defaults.repo_roots),
        repos=_split_lines_or_commas(data.get("repos") or defaults.repos),
        exclude_confluence_parents=_split_lines_or_commas(data.get("exclude_confluence_parents") or defaults.exclude_confluence_parents),
        jira_team_field=str(data.get("jira_team_field") or defaults.jira_team_field or "Team").strip(),
        exclude_jira_teams=_split_lines_or_commas(data.get("exclude_jira_teams") or defaults.exclude_jira_teams),
        limit=_positive_int(data.get("limit"), default=10),
        include_prs=_as_bool(data.get("include_prs")),
        include_diffs=_as_bool(data.get("include_diffs")),
        github_fallback=_as_bool(data.get("github_fallback")),
        max_diff_lines=_positive_int(data.get("max_diff_lines"), default=500),
        include_comments=_as_bool(data.get("include_comments")),
        refresh=_as_bool(data.get("refresh")),
        no_cache=_as_bool(data.get("no_cache")),
        no_preset_expansion=_as_bool(data.get("no_preset_expansion", "1")),
    )


def build_evidence_command(form: EvidenceForm) -> list[str]:
    command = ["assurance", "report", "evidence-pack"]
    if form.topic:
        command.append(form.topic)
    for query in form.queries:
        command.extend(["--query", query])
    if form.preset:
        command.extend(["--preset", form.preset])
    if form.no_preset_expansion:
        command.append("--no-preset-expansion")
    if "confluence" not in form.sources:
        command.append("--skip-confluence")
    elif form.confluence_space:
        command.extend(["--confluence-space", form.confluence_space])
    if "jira" not in form.sources:
        command.append("--skip-jira")
    elif form.jira_project:
        command.extend(["--jira-project", form.jira_project])
    if "azure" in form.sources:
        command.append("--include-azure")
        if form.azure_resource_group:
            command.extend(["--azure-resource-group", form.azure_resource_group])
    if "dataverse" in form.sources:
        command.append("--include-dataverse")
    for parent in form.exclude_confluence_parents:
        command.extend(["--exclude-confluence-parent", parent])
    if form.exclude_jira_teams or (form.jira_team_field and form.jira_team_field != "Team"):
        command.extend(["--jira-team-field", form.jira_team_field])
    for team in form.exclude_jira_teams:
        command.extend(["--exclude-jira-team", team])
    if "code" in form.sources:
        command.append("--include-code")
        for root in form.repo_roots:
            command.extend(["--repo-root", root])
        for repo in form.repos:
            command.extend(["--repo", repo])
        if form.include_prs:
            command.append("--include-prs")
        if form.include_diffs:
            command.append("--include-diffs")
        if form.github_fallback:
            command.append("--github-fallback")
        command.extend(["--max-diff-lines", str(form.max_diff_lines)])
    command.extend(["--limit", str(form.limit)])
    if form.include_comments:
        command.append("--include-comments")
    if form.refresh:
        command.append("--refresh")
    if form.no_cache:
        command.append("--no-cache")
    return command


def build_run_command(form: EvidenceForm, *, assurance_path: str, evidence_path: Path) -> list[str]:
    command = build_evidence_command(form)
    command[0] = resolve_assurance_path(assurance_path) or command[0]
    command.extend(["--out", str(evidence_path)])
    return command


def output_folder_preview(workbench_root: str, form: EvidenceForm) -> Path:
    root = Path(workbench_root).expanduser() if workbench_root else Path("runs")
    slug = _slug(form.topic or form.preset or "evidence-pack")
    return root / "runs" / f"<timestamp>-{slug}"


def create_run_dir(workbench_root: str, form: EvidenceForm, *, now: datetime | None = None) -> Path:
    root = Path(workbench_root).expanduser() if workbench_root else Path("runs")
    timestamp = (now or datetime.now().astimezone()).strftime("%Y-%m-%d-%H%M%S")
    slug = _slug(form.topic or form.preset or "evidence-pack")
    return root / "runs" / f"{timestamp}-{slug}"


def run_evidence_pack(
    form: EvidenceForm,
    settings: AppSettings,
    *,
    timeout: int = 300,
    runner=subprocess.run,
) -> EvidenceRunResult:
    run_dir = create_run_dir(settings.workbench_root, form)
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = run_dir / "evidence-pack.md"
    command = build_run_command(form, assurance_path=settings.assurance_path, evidence_path=evidence_path)
    (run_dir / "request.json").write_text(json.dumps(asdict(form), indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "command.txt").write_text(shell_command(command) + "\n", encoding="utf-8")
    try:
        completed = runner(command, capture_output=True, text=True, check=False, timeout=timeout)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = int(completed.returncode)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = 124
        timed_out = True
    (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    (run_dir / "exit-code.txt").write_text(str(exit_code) + "\n", encoding="utf-8")
    write_gaps_and_warnings(run_dir, stderr=stderr)
    return EvidenceRunResult(
        run_dir=run_dir,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        evidence_path=evidence_path,
        timed_out=timed_out,
    )


def evidence_runs_root(settings: AppSettings) -> Path:
    root = Path(settings.workbench_root).expanduser() if settings.workbench_root else Path("runs")
    return root / "runs"


def list_evidence_runs(settings: AppSettings) -> list[EvidenceRunSummary]:
    runs_root = evidence_runs_root(settings)
    if not runs_root.exists():
        return []
    summaries = []
    for run_dir in runs_root.iterdir():
        if run_dir.is_dir():
            summaries.append(_run_summary(run_dir))
    return sorted(summaries, key=lambda item: item.id, reverse=True)


def filter_evidence_runs(
    runs: list[EvidenceRunSummary],
    *,
    topic: str = "",
    preset: str = "",
    source: str = "",
) -> list[EvidenceRunSummary]:
    topic = topic.strip().lower()
    preset = preset.strip()
    source = source.strip()
    filtered = runs
    if topic:
        filtered = [run for run in filtered if topic in (run.topic or run.id).lower()]
    if preset:
        filtered = [run for run in filtered if run.preset == preset]
    if source:
        filtered = [run for run in filtered if source in run.sources]
    return filtered


def load_evidence_run(settings: AppSettings, run_id: str) -> EvidenceRunDetail | None:
    if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
        return None
    run_dir = evidence_runs_root(settings) / run_id
    if not run_dir.is_dir():
        return None
    summary = _run_summary(run_dir)
    request = _read_json(run_dir / "request.json")
    stdout = _read_text(run_dir / "stdout.log")
    stderr = _read_text(run_dir / "stderr.log")
    evidence_markdown = _read_text(summary.evidence_path)
    evidence_preview_markdown, evidence_preview_truncated = preview_markdown(evidence_markdown)
    warning_items = _extract_warning_items(evidence_markdown, stderr)
    return EvidenceRunDetail(
        summary=summary,
        request=request,
        stdout=stdout,
        stderr=stderr,
        evidence_markdown=evidence_markdown,
        evidence_html=render_markdown(evidence_markdown),
        warnings=tuple(item.text for item in warning_items),
        warning_items=warning_items,
        evidence_preview_html=render_markdown(evidence_preview_markdown),
        evidence_preview_truncated=evidence_preview_truncated,
        evidence_line_count=len(evidence_markdown.splitlines()),
        evidence_char_count=len(evidence_markdown),
    )


def form_from_saved_request(request: dict[str, Any], defaults: AppSettings | None = None) -> EvidenceForm:
    data = dict(request)
    data["sources_present"] = "1"
    return evidence_form_from_data(data, defaults)


def run_file_path(settings: AppSettings, run_id: str, filename: str) -> Path | None:
    if filename not in RUN_FILES:
        return None
    if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
        return None
    path = evidence_runs_root(settings) / run_id / filename
    return path if path.exists() and path.is_file() else None


def delete_evidence_run(settings: AppSettings, run_id: str) -> FileActionResult:
    if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
        return FileActionResult(False, "Run not found.", [])
    runs_root = evidence_runs_root(settings).resolve()
    run_dir = (runs_root / run_id).resolve()
    try:
        common = os.path.commonpath([str(runs_root), str(run_dir)])
    except ValueError:
        return FileActionResult(False, "Run path is outside the configured runs folder.", [])
    if common != str(runs_root):
        return FileActionResult(False, "Run path is outside the configured runs folder.", [])
    if not run_dir.exists() or not run_dir.is_dir():
        return FileActionResult(False, "Run not found.", [])
    shutil.rmtree(run_dir)
    return FileActionResult(True, "Deleted evidence run.", ["delete", str(run_dir)])


def write_gaps_and_warnings(run_dir: Path, *, evidence_markdown: str | None = None, stderr: str | None = None) -> tuple[str, ...]:
    evidence_markdown = _read_text(run_dir / "evidence-pack.md") if evidence_markdown is None else evidence_markdown
    stderr = _read_text(run_dir / "stderr.log") if stderr is None else stderr
    request = _read_json(run_dir / "request.json")
    structured_items = _extract_warning_items(evidence_markdown, stderr)
    checks = _assurance_checks(evidence_markdown, stderr, request, structured_items)
    payload = {
        "items": [
            {
                "kind": item.kind,
                "text": item.text,
                "criteria": list(item.criteria),
                "locations": list(item.locations),
            }
            for item in structured_items
        ]
    }
    (run_dir / "gaps-and-warnings.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "gaps-and-warnings.md").write_text(_gaps_and_warnings_markdown(structured_items), encoding="utf-8")
    (run_dir / "assurance-checks.md").write_text(_assurance_checks_markdown(checks), encoding="utf-8")
    (run_dir / "analyst-brief.md").write_text(_analyst_brief_markdown(evidence_markdown, request, structured_items, checks), encoding="utf-8")
    return tuple(item.text for item in structured_items)


def open_run_folder(settings: AppSettings, run_id: str, *, runner=subprocess.run) -> FileActionResult:
    detail = load_evidence_run(settings, run_id)
    if not detail:
        return FileActionResult(False, "Run not found.", [])
    command = ["open", str(detail.summary.run_dir)]
    return _run_file_action(command, "Opened run folder.", runner=runner)


def open_run_in_vscode(settings: AppSettings, run_id: str, *, runner=subprocess.run) -> FileActionResult:
    detail = load_evidence_run(settings, run_id)
    if not detail:
        return FileActionResult(False, "Run not found.", [])
    code_path = shutil.which("code")
    if not code_path:
        return FileActionResult(False, "VS Code command-line launcher 'code' was not found.", [])
    command = [code_path, str(detail.summary.run_dir)]
    return _run_file_action(command, "Opened run folder in VS Code.", runner=runner)


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    paragraph: list[str] = []
    table_rows: list[list[str]] = []
    table_has_separator = False
    in_code = False
    code_lines: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_table() -> None:
        nonlocal table_has_separator
        if not table_rows:
            return
        html.append("<table>")
        body_rows = table_rows
        if table_has_separator:
            header = table_rows[0]
            body_rows = table_rows[1:]
            html.append("<thead><tr>")
            for cell in header:
                html.append(f"<th>{escape(cell)}</th>")
            html.append("</tr></thead>")
        if body_rows:
            html.append("<tbody>")
            for row in body_rows:
                html.append("<tr>")
                for cell in row:
                    html.append(f"<td>{escape(cell)}</td>")
                html.append("</tr>")
            html.append("</tbody>")
        html.append("</table>")
        table_rows.clear()
        table_has_separator = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            close_table()
            if in_code:
                html.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            close_table()
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            close_list()
            close_table()
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            text = stripped[level:].strip()
            html.append(f"<h{level}>{escape(text)}</h{level}>")
            continue
        if _is_table_line(stripped):
            flush_paragraph()
            close_list()
            if _is_table_separator(stripped):
                table_has_separator = True
            else:
                table_rows.append(_table_cells(stripped))
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            close_table()
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{escape(stripped[2:].strip())}</li>")
            continue
        close_table()
        paragraph.append(stripped)

    if in_code:
        html.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
    flush_paragraph()
    close_list()
    close_table()
    return "\n".join(html)


def _is_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(cell and set(cell) <= {"-", ":", " "} for cell in cells)


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def preview_markdown(
    markdown: str,
    *,
    max_chars: int = EVIDENCE_PREVIEW_MAX_CHARS,
    max_sections: int = EVIDENCE_PREVIEW_MAX_SECTIONS,
) -> tuple[str, bool]:
    if len(markdown) <= max_chars and _section_count(markdown) <= max_sections:
        return markdown, False

    preview_lines: list[str] = []
    char_count = 0
    section_count = 0
    in_code = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
        if not in_code and stripped.startswith("## "):
            section_count += 1
            if section_count > max_sections:
                return "\n".join(preview_lines).rstrip(), True
        line_length = len(line) + 1
        if char_count + line_length > max_chars:
            return "\n".join(preview_lines).rstrip(), True
        preview_lines.append(line)
        char_count += line_length

    return "\n".join(preview_lines).rstrip(), False


def shell_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _section_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("## "))


def _valid_preset(value: str) -> str:
    return value if value in PRESETS else ""


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_bool(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def _split_lines_or_commas(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    value = str(value)
    normalized = value.replace(",", "\n")
    return tuple(item.strip() for item in normalized.splitlines() if item.strip())


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    slug = "".join(chars).strip("-")
    return slug[:60] or "evidence-pack"


def _run_summary(run_dir: Path) -> EvidenceRunSummary:
    request = _read_json(run_dir / "request.json")
    evidence_path = run_dir / "evidence-pack.md"
    return EvidenceRunSummary(
        id=run_dir.name,
        run_dir=run_dir,
        topic=str(request.get("topic", "")),
        preset=str(request.get("preset", "")),
        sources=tuple(str(source) for source in request.get("sources", ())),
        exit_code=_read_exit_code(run_dir / "exit-code.txt"),
        command=_read_text(run_dir / "command.txt").strip(),
        evidence_path=evidence_path,
        has_evidence=evidence_path.exists(),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_exit_code(path: Path) -> int | None:
    text = _read_text(path).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _extract_warnings(markdown: str, stderr: str) -> tuple[str, ...]:
    return tuple(item.text for item in _extract_warning_items(markdown, stderr))


def _assurance_checks(
    markdown: str,
    stderr: str,
    request: dict[str, Any],
    warning_items: tuple[GapWarningItem, ...],
) -> tuple[AssuranceCheck, ...]:
    selected_sources = tuple(str(source) for source in request.get("sources", ()) if str(source))
    lowered = markdown.lower()
    checks: list[AssuranceCheck] = []
    checks.append(_evidence_presence_check(markdown))
    checks.extend(_source_coverage_checks(markdown, selected_sources))
    checks.append(_mechanical_signal_check(warning_items))
    if stderr.strip():
        checks.append(
            AssuranceCheck(
                "review",
                "Tool stderr was captured",
                "The run produced stderr output.",
                "Check stderr.log to distinguish expected CLI warnings from retrieval failures.",
            )
        )
    checks.extend(_document_absence_checks(lowered))
    return tuple(checks)


def _evidence_presence_check(markdown: str) -> AssuranceCheck:
    if markdown.strip():
        return AssuranceCheck("pass", "Evidence pack exists", "evidence-pack.md contains retrieved evidence.")
    return AssuranceCheck(
        "warn",
        "Evidence pack is empty",
        "No evidence text was available for mechanical checks.",
        "Check command.txt, stdout.log and stderr.log before relying on this run.",
    )


def _source_coverage_checks(markdown: str, selected_sources: tuple[str, ...]) -> tuple[AssuranceCheck, ...]:
    if not selected_sources:
        return (
            AssuranceCheck(
                "review",
                "No sources selected",
                "The saved request did not select any evidence sources.",
                "Confirm whether this was intentional or re-run with Confluence, Jira, code, Azure or Dataverse enabled.",
            ),
        )
    checks = []
    for source in selected_sources:
        status = _source_status(markdown, source)
        if status in {"yes", ""}:
            checks.append(AssuranceCheck("pass", f"{source.title()} evidence selected", f"Source status: `{status or 'not recorded'}`."))
        else:
            checks.append(
                AssuranceCheck(
                    "review",
                    f"{source.title()} evidence incomplete",
                    f"Source status: `{status}`.",
                    f"Check whether missing {source} evidence affects the assurance conclusion.",
                )
            )
    return tuple(checks)


def _source_status(markdown: str, source: str) -> str:
    prefix = f"- {source.title()}: `"
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).split("`", 1)[0]
    return ""


def _mechanical_signal_check(warning_items: tuple[GapWarningItem, ...]) -> AssuranceCheck:
    if warning_items:
        return AssuranceCheck(
            "review",
            "Explicit gap or warning language found",
            f"{len(warning_items)} mechanical signal(s) were found in retrieved evidence.",
            "Review gaps-and-warnings.md before doing deeper analysis.",
        )
    return AssuranceCheck("pass", "No explicit gap or warning language found", "No configured mechanical signal terms were found.")


def _document_absence_checks(lowered_markdown: str) -> tuple[AssuranceCheck, ...]:
    checks = []
    lld_present = _contains_any(lowered_markdown, ("lld", "low level design", "low-level design"))
    if lld_present:
        checks.append(_absence_check(lowered_markdown, ("nfr", "non-functional", "non functional"), "LLD NFR coverage", "No obvious NFR/non-functional requirement language was found near this evidence set.", "Confirm whether the LLD covers performance, resilience, audit, security, monitoring and support needs."))
        checks.append(_absence_check(lowered_markdown, ("error handling", "error code", "http 4", "http 5", "status code"), "LLD error handling coverage", "No obvious error-handling or HTTP status-code language was found.", "Compare documented error behaviour with implementation and API contracts."))
    else:
        checks.append(
            AssuranceCheck(
                "info",
                "LLD absence checks not triggered",
                "No obvious LLD marker was found in the retrieved evidence.",
                "If this run is meant to assure a design, confirm the relevant LLD was retrieved.",
            )
        )
    if _contains_any(lowered_markdown, ("xml", "soap")):
        checks.append(_absence_check(lowered_markdown, ("schema", "xsd", ".xsd"), "XML schema coverage", "XML/SOAP language was found but no obvious schema/XSD language was found.", "Confirm whether XML payloads have a documented and tested schema."))
    if _contains_any(lowered_markdown, ("api", "endpoint", "http")):
        checks.append(_absence_check(lowered_markdown, ("400", "401", "403", "404", "409", "422", "429", "500", "5xx", "4xx"), "API error-code coverage", "API/HTTP language was found but common error-code terms were not obvious.", "Compare documented status codes against code, tests and client behaviour."))
    return tuple(checks)


def _absence_check(markdown: str, terms: tuple[str, ...], title: str, missing_detail: str, follow_up: str) -> AssuranceCheck:
    if _contains_any(markdown, terms):
        return AssuranceCheck("pass", title, "Expected language was found.")
    return AssuranceCheck("review", title, missing_detail, follow_up)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _extract_warning_items(markdown: str, stderr: str) -> tuple[GapWarningItem, ...]:
    items: dict[tuple[str, tuple[str, ...]], GapWarningItem] = {}
    current_section = ""
    pending_heading = ""
    current_location = "evidence-pack.md"
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = _clean_heading(stripped[3:])
            if heading in {"Confluence Evidence", "Jira Evidence", "Azure Evidence", "Dataverse Evidence", "Code Evidence"}:
                current_section = heading.removesuffix(" Evidence").lower()
                current_location = f"{current_section}: evidence-pack.md"
            elif heading not in {
                "Search Summary",
                "Status Summary",
                "Search Exclusions",
                "Sources Queried",
                "Scope",
                "Gaps / Follow-up Questions",
                "Appendix: Commands Run",
            }:
                pending_heading = heading
        elif stripped.startswith("- URL:"):
            url = stripped.removeprefix("- URL:").strip()
            title = pending_heading or current_section or "source"
            prefix = f"{current_section}: " if current_section else ""
            current_location = f"{prefix}{title} ({url})"
        _record_warning_item(items, stripped, current_location)
    for line in stderr.splitlines():
        _record_warning_item(items, line.strip(), "stderr.log")
    return tuple(items.values())[:20]


def _record_warning_item(items: dict[tuple[str, tuple[str, ...]], GapWarningItem], line: str, location: str) -> None:
    if not line:
        return
    lowered = line.lower()
    if "no mechanical gaps identified" in lowered:
        return
    if "identify gaps, inconsistencies, or missing behaviours" in lowered:
        return
    if line.startswith("#"):
        return
    criteria = _warning_criteria(line)
    if not criteria:
        return
    key = (line, criteria)
    existing = items.get(key)
    if existing:
        locations = existing.locations
        if location not in locations:
            locations = (*locations, location)
        items[key] = GapWarningItem(existing.kind, existing.text, existing.criteria, locations)
        return
    items[key] = GapWarningItem(_gap_or_warning(line), line, criteria, (location,))


def _warning_criteria(line: str) -> tuple[str, ...]:
    lowered = line.lower()
    criteria = []
    if "gap" in lowered:
        criteria.append('contains "gap"')
    if "warning" in lowered:
        criteria.append('contains "warning"')
    if "warn:" in lowered:
        criteria.append('contains "warn:"')
    return tuple(criteria)


def _clean_heading(value: str) -> str:
    return value.strip().strip("*`").strip()


def _gap_or_warning(item: str) -> str:
    lowered = item.lower()
    if "gap" in lowered:
        return "gap"
    return "warning"


def _gaps_and_warnings_markdown(items: tuple[GapWarningItem, ...]) -> str:
    lines = ["# Gaps and Warnings", ""]
    if not items:
        lines.append("_No gaps or warnings detected._")
    else:
        for index, item in enumerate(items, 1):
            lines.append(f"## {index}. {item.kind.title()}")
            lines.append("")
            lines.extend(_format_gap_or_warning_item(item.text))
            lines.append("")
            lines.extend(_format_metadata_lines("Source", item.locations))
            lines.extend(_format_metadata_lines("Criteria", item.criteria))
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _assurance_checks_markdown(checks: tuple[AssuranceCheck, ...]) -> str:
    lines = ["# Assurance Checks", ""]
    if not checks:
        lines.append("_No deterministic checks were run._")
    else:
        for check in checks:
            lines.append(f"## {_status_label(check.status)} {check.title}")
            lines.append("")
            lines.append(_escape_markdown_inline(check.detail))
            if check.follow_up:
                lines.append("")
                lines.append(f"- **Follow-up:** {_escape_markdown_inline(check.follow_up)}")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _analyst_brief_markdown(
    markdown: str,
    request: dict[str, Any],
    warning_items: tuple[GapWarningItem, ...],
    checks: tuple[AssuranceCheck, ...],
) -> str:
    topic = str(request.get("topic") or "unspecified")
    preset = str(request.get("preset") or "none")
    sources = tuple(str(source) for source in request.get("sources", ()) if str(source))
    review_checks = tuple(check for check in checks if check.status in {"warn", "review"})
    lines = [
        "# Analyst Brief",
        "",
        "This brief is generated mechanically from the retrieved evidence. It is intended to prepare human or agent review, not replace it.",
        "",
        "## Run Context",
        "",
        f"- **Topic:** {_escape_markdown_inline(topic)}",
        f"- **Preset:** {_escape_markdown_inline(preset)}",
        f"- **Sources selected:** {_escape_markdown_inline(', '.join(sources) if sources else 'none')}",
        f"- **Evidence length:** {len(markdown):,} characters",
        f"- **Mechanical signals:** {len(warning_items)}",
        f"- **Checks needing review:** {len(review_checks)}",
        "",
        "## Highest-Value Starting Points",
        "",
    ]
    if warning_items:
        for item in warning_items[:5]:
            location = item.locations[0] if item.locations else "unknown source"
            lines.append(f"- **{item.kind.title()}:** {_truncate(_plain_text(item.text), 220)}")
            lines.append(f"  Source: {_escape_markdown_inline(location)}")
    else:
        lines.append("- No explicit gap/warning language was detected. Review may need to focus on absence and consistency checks.")
    lines.extend(["", "## Deterministic Follow-Ups", ""])
    if review_checks:
        for check in review_checks:
            follow_up = check.follow_up or check.detail
            lines.append(f"- **{check.title}:** {_escape_markdown_inline(follow_up)}")
    else:
        lines.append("- No deterministic checks currently require review.")
    lines.extend(
        [
            "",
            "## Analyst Questions",
            "",
            "- Are the expected source documents present for this topic, especially LLDs, API contracts, implementation code and test evidence?",
            "- Are required schemas, payload contracts or interface definitions present where integrations are discussed?",
            "- Do documented HTTP/API error behaviours match code, tests and downstream expectations?",
            "- Are NFRs covered explicitly, including performance, resilience, audit, monitoring, support and security?",
            "- Are there contradictions between Confluence decisions, Jira stories and repository implementation evidence?",
            "",
            "## Related Files",
            "",
            "- evidence-pack.md",
            "- assurance-checks.md",
            "- gaps-and-warnings.md",
            "- gaps-and-warnings.json",
            "",
        ]
    )
    return "\n".join(lines)


def _status_label(status: str) -> str:
    labels = {"pass": "PASS", "info": "INFO", "review": "REVIEW", "warn": "WARN"}
    return labels.get(status, status.upper())


def _plain_text(value: str) -> str:
    return " ".join(value.replace("|", " ").split())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return _escape_markdown_inline(value)
    return _escape_markdown_inline(value[: limit - 3].rstrip() + "...")


def _format_metadata_lines(label: str, values: tuple[str, ...]) -> list[str]:
    if not values:
        return []
    if len(values) == 1:
        return [f"- **{label}:** {_escape_markdown_inline(values[0])}"]
    joined = "; ".join(_escape_markdown_inline(value) for value in values)
    return [f"- **{label}s:** {joined}"]


def _format_gap_or_warning_item(item: str) -> list[str]:
    table_cells = _markdown_table_cells(item)
    if table_cells:
        header = " | ".join(" " for _ in table_cells)
        separator = " | ".join("---" for _ in table_cells)
        row = " | ".join(_escape_markdown_table_cell(cell) for cell in table_cells)
        return [f"| {header} |", f"| {separator} |", f"| {row} |"]
    return [_escape_markdown_inline(item)]


def _markdown_table_cells(item: str) -> list[str]:
    stripped = item.strip()
    if not stripped.startswith("|") or "|" not in stripped[1:]:
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return [cell for cell in cells if cell]


def _escape_markdown_inline(value: str) -> str:
    return value.replace("|", r"\|")


def _escape_markdown_table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def _run_file_action(command: list[str], success_message: str, *, runner=subprocess.run) -> FileActionResult:
    try:
        completed = runner(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return FileActionResult(False, str(exc), command)
    if completed.returncode == 0:
        return FileActionResult(True, success_message, command)
    message = (completed.stderr or completed.stdout or "Command failed.").strip()
    return FileActionResult(False, message, command)
