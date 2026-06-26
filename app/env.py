from __future__ import annotations

import os
from pathlib import Path


ASSURANCE_ENV_FILE_ENV = "ASSURANCE_ENV_FILE"


def subprocess_env(env_file: str = "") -> dict[str, str]:
    env = dict(os.environ)
    selected = env_file.strip() or env.get(ASSURANCE_ENV_FILE_ENV, "").strip()
    if selected:
        env.update(read_env_file(Path(selected).expanduser()))
    return env


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _clean_value(value.strip())
    return values


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
