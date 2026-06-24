from __future__ import annotations

import shlex
from dataclasses import dataclass
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


def evidence_form_from_data(data: Any, defaults: AppSettings | None = None) -> EvidenceForm:
    default_sources = ("confluence", "jira")
    raw_sources = data.getlist("sources") if hasattr(data, "getlist") else data.get("sources", default_sources)
    if isinstance(raw_sources, str):
        raw_sources = (raw_sources,)
    sources = tuple(source for source in raw_sources if source in SOURCES) or default_sources
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
