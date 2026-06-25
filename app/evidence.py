from __future__ import annotations

import json
import shutil
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

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
}


@dataclass(frozen=True)
class EvidenceForm:
    topic: str = ""
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
        preset=_valid_preset(str(data.get("preset", "")).strip()),
        sources=sources,
        confluence_space=str(data.get("confluence_space") or defaults.confluence_space).strip(),
        jira_project=str(data.get("jira_project") or defaults.jira_project).strip(),
        azure_resource_group=str(data.get("azure_resource_group") or defaults.azure_resource_group).strip(),
        repo_roots=_split_lines_or_commas(str(data.get("repo_roots") or defaults.repo_roots)),
        repos=_split_lines_or_commas(str(data.get("repos") or defaults.repos)),
        exclude_confluence_parents=_split_lines_or_commas(str(data.get("exclude_confluence_parents") or defaults.exclude_confluence_parents)),
        jira_team_field=str(data.get("jira_team_field") or defaults.jira_team_field or "Team").strip(),
        exclude_jira_teams=_split_lines_or_commas(str(data.get("exclude_jira_teams") or defaults.exclude_jira_teams)),
        limit=_positive_int(data.get("limit"), default=10),
        include_prs=_as_bool(data.get("include_prs")),
        include_diffs=_as_bool(data.get("include_diffs")),
        github_fallback=_as_bool(data.get("github_fallback")),
        max_diff_lines=_positive_int(data.get("max_diff_lines"), default=500),
        include_comments=_as_bool(data.get("include_comments")),
        refresh=_as_bool(data.get("refresh")),
        no_cache=_as_bool(data.get("no_cache")),
    )


def build_evidence_command(form: EvidenceForm) -> list[str]:
    command = ["assurance", "report", "evidence-pack"]
    if form.topic:
        command.append(form.topic)
    if form.preset:
        command.extend(["--preset", form.preset])
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
    command[0] = assurance_path or command[0]
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
    return EvidenceRunDetail(
        summary=summary,
        request=request,
        stdout=stdout,
        stderr=stderr,
        evidence_markdown=evidence_markdown,
        evidence_html=render_markdown(evidence_markdown),
        warnings=_extract_warnings(evidence_markdown, stderr),
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


def write_gaps_and_warnings(run_dir: Path, *, evidence_markdown: str | None = None, stderr: str | None = None) -> tuple[str, ...]:
    evidence_markdown = _read_text(run_dir / "evidence-pack.md") if evidence_markdown is None else evidence_markdown
    stderr = _read_text(run_dir / "stderr.log") if stderr is None else stderr
    items = _extract_warnings(evidence_markdown, stderr)
    payload = {
        "items": [
            {
                "kind": _gap_or_warning(item),
                "text": item,
            }
            for item in items
        ]
    }
    (run_dir / "gaps-and-warnings.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "gaps-and-warnings.md").write_text(_gaps_and_warnings_markdown(items), encoding="utf-8")
    return items


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
    in_code = False
    code_lines: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{escape(' '.join(paragraph))}</p>")
            paragraph.clear()

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
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            text = stripped[level:].strip()
            html.append(f"<h{level}>{escape(text)}</h{level}>")
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{escape(stripped[2:].strip())}</li>")
            continue
        paragraph.append(stripped)

    if in_code:
        html.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
    flush_paragraph()
    close_list()
    return "\n".join(html)


def shell_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


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


def _split_lines_or_commas(value: str) -> tuple[str, ...]:
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
    warnings: list[str] = []
    for line in (markdown + "\n" + stderr).splitlines():
        lowered = line.lower()
        if "no mechanical gaps identified" in lowered:
            continue
        if "identify gaps, inconsistencies, or missing behaviours" in lowered:
            continue
        if "warning" in lowered or "warn:" in lowered or "gap" in lowered:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped:
                warnings.append(stripped)
    return tuple(warnings[:20])


def _gap_or_warning(item: str) -> str:
    lowered = item.lower()
    if "gap" in lowered:
        return "gap"
    return "warning"


def _gaps_and_warnings_markdown(items: tuple[str, ...]) -> str:
    lines = ["# Gaps and Warnings", ""]
    if not items:
        lines.append("_No gaps or warnings detected._")
    else:
        for index, item in enumerate(items, 1):
            lines.append(f"## {index}. {_gap_or_warning(item).title()}")
            lines.append("")
            lines.extend(_format_gap_or_warning_item(item))
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _format_gap_or_warning_item(item: str) -> list[str]:
    table_cells = _markdown_table_cells(item)
    if table_cells:
        lines = ["Extracted table row:", ""]
        for index, cell in enumerate(table_cells, 1):
            lines.append(f"- **Column {index}:** {_escape_markdown_inline(cell)}")
        return lines
    return [_escape_markdown_inline(item)]


def _markdown_table_cells(item: str) -> list[str]:
    stripped = item.strip()
    if not stripped.startswith("|") or "|" not in stripped[1:]:
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return [cell for cell in cells if cell]


def _escape_markdown_inline(value: str) -> str:
    return value.replace("|", r"\|")


def _run_file_action(command: list[str], success_message: str, *, runner=subprocess.run) -> FileActionResult:
    try:
        completed = runner(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return FileActionResult(False, str(exc), command)
    if completed.returncode == 0:
        return FileActionResult(True, success_message, command)
    message = (completed.stderr or completed.stdout or "Command failed.").strip()
    return FileActionResult(False, message, command)
