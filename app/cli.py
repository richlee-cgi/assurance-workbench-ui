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
    return run_assurance_check(configured_path, ["--help"], "assurance CLI is available.", "assurance --help")


def check_azure(configured_path: str) -> CliCheckResult:
    return run_assurance_check(configured_path, ["azure", "check"], "Azure check completed.", "assurance azure check", timeout=20)


def check_dataverse(configured_path: str) -> CliCheckResult:
    return run_assurance_check(configured_path, ["dataverse", "check"], "Dataverse check completed.", "assurance dataverse check", timeout=20)


def run_assurance_check(
    configured_path: str,
    args: list[str],
    success_message: str,
    fallback_command: str,
    *,
    timeout: int = 10,
) -> CliCheckResult:
    executable = resolve_assurance_path(configured_path)
    if not executable:
        return CliCheckResult(ok=False, command=fallback_command.split(), message="assurance executable not configured or found on PATH.")
    command = [executable, *args]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except OSError as exc:
        return CliCheckResult(ok=False, command=command, message=f"Unable to run assurance: {exc}")
    except subprocess.TimeoutExpired:
        return CliCheckResult(ok=False, command=command, message=f"{fallback_command} timed out.")
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
        message=success_message,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
