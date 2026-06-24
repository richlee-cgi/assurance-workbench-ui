from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SETTINGS_PATH_ENV = "ASSURANCE_WORKBENCH_UI_SETTINGS"
DEFAULT_SETTINGS_PATH = Path(".assurance-workbench-ui.json")


@dataclass(frozen=True)
class AppSettings:
    assurance_path: str = ""
    workbench_root: str = ""
    confluence_space: str = ""
    jira_project: str = ""
    azure_resource_group: str = ""


def settings_path() -> Path:
    return Path(os.environ.get(SETTINGS_PATH_ENV, DEFAULT_SETTINGS_PATH)).expanduser()


def load_settings(path: Path | None = None) -> AppSettings:
    selected_path = path or settings_path()
    if not selected_path.exists():
        return AppSettings()
    with selected_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return AppSettings(**_known_settings(data))


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    selected_path = path or settings_path()
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    selected_path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")


def settings_from_form(data: Any) -> AppSettings:
    return AppSettings(
        assurance_path=str(data.get("assurance_path", "")).strip(),
        workbench_root=str(data.get("workbench_root", "")).strip(),
        confluence_space=str(data.get("confluence_space", "")).strip(),
        jira_project=str(data.get("jira_project", "")).strip(),
        azure_resource_group=str(data.get("azure_resource_group", "")).strip(),
    )


def _known_settings(data: dict[str, Any]) -> dict[str, str]:
    allowed = set(AppSettings.__dataclass_fields__)
    return {key: str(value) for key, value in data.items() if key in allowed}
