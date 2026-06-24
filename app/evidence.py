from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.settings import AppSettings


PRESETS = ("architecture", "dataverse", "scaling")
SOURCES = ("confluence", "jira", "azure", "dataverse")


@dataclass(frozen=True)
class EvidenceForm:
    topic: str = ""
    preset: str = ""
    sources: tuple[str, ...] = ("confluence", "jira")
    confluence_space: str = ""
    jira_project: str = ""
    azure_resource_group: str = ""
    limit: int = 10
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
        limit=_positive_int(data.get("limit"), default=10),
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
    return EvidenceRunResult(
        run_dir=run_dir,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        evidence_path=evidence_path,
        timed_out=timed_out,
    )


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


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    slug = "".join(chars).strip("-")
    return slug[:60] or "evidence-pack"
