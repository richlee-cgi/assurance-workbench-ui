from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CliCheckResult:
    ok: bool
    command: list[str]
    message: str
    stdout: str = ""
    stderr: str = ""


def resolve_assurance_path(configured_path: str) -> str | None:
    if configured_path:
        return configured_path
    return shutil.which("assurance")


def check_assurance_cli(configured_path: str) -> CliCheckResult:
    executable = resolve_assurance_path(configured_path)
    if not executable:
        return CliCheckResult(ok=False, command=["assurance", "--help"], message="assurance executable not configured or found on PATH.")
    command = [executable, "--help"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    except OSError as exc:
        return CliCheckResult(ok=False, command=command, message=f"Unable to run assurance: {exc}")
    except subprocess.TimeoutExpired:
        return CliCheckResult(ok=False, command=command, message="assurance --help timed out.")
    if completed.returncode != 0:
        return CliCheckResult(
            ok=False,
            command=command,
            message=f"assurance exited with {completed.returncode}.",
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
    return CliCheckResult(
        ok=True,
        command=command,
        message="assurance CLI is available.",
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
