from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.env import subprocess_env


@dataclass(frozen=True)
class CliCheckResult:
    ok: bool
    command: list[str]
    message: str
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CodeRepoDiscoveryResult:
    ok: bool
    command: list[str]
    repositories: list[dict]
    message: str
    stderr: str = ""


def resolve_assurance_path(configured_path: str) -> str | None:
    if configured_path:
        return configured_path
    return _venv_assurance_executable() or shutil.which("assurance")


def _venv_assurance_executable() -> str | None:
    scripts_dir = Path(sys.executable).parent
    names = ("assurance.exe", "assurance") if os.name == "nt" else ("assurance", "assurance.exe")
    for name in names:
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def check_assurance_cli(configured_path: str, env_file: str = "") -> CliCheckResult:
    return run_assurance_check(configured_path, ["--help"], "assurance CLI is available.", "assurance --help", env_file=env_file)


def check_azure(configured_path: str, env_file: str = "") -> CliCheckResult:
    return run_assurance_check(configured_path, ["azure", "check"], "Azure check completed.", "assurance azure check", timeout=20, env_file=env_file)


def check_dataverse(configured_path: str, env_file: str = "") -> CliCheckResult:
    return run_assurance_check(configured_path, ["dataverse", "check"], "Dataverse check completed.", "assurance dataverse check", timeout=20, env_file=env_file)


def discover_code_repos(configured_path: str, repo_roots: tuple[str, ...], env_file: str = "") -> CodeRepoDiscoveryResult:
    executable = resolve_assurance_path(configured_path)
    fallback = ["assurance", "code", "repos", "--raw"]
    if not executable:
        return CodeRepoDiscoveryResult(False, fallback, [], "assurance executable not configured or found on PATH.")
    command = [executable, "code", "repos", "--raw"]
    for root in repo_roots:
        command.extend(["--repo-root", root])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20, env=subprocess_env(env_file))
    except OSError as exc:
        return CodeRepoDiscoveryResult(False, command, [], f"Unable to run assurance: {exc}")
    except subprocess.TimeoutExpired:
        return CodeRepoDiscoveryResult(False, command, [], "assurance code repos timed out.")
    if completed.returncode != 0:
        return CodeRepoDiscoveryResult(False, command, [], f"assurance exited with {completed.returncode}.", completed.stderr.strip())
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return CodeRepoDiscoveryResult(False, command, [], "assurance code repos returned invalid JSON.", completed.stderr.strip())
    repositories = payload.get("repositories", [])
    if not isinstance(repositories, list):
        repositories = []
    return CodeRepoDiscoveryResult(True, command, repositories, f"Discovered {len(repositories)} repositories.")


def run_assurance_check(
    configured_path: str,
    args: list[str],
    success_message: str,
    fallback_command: str,
    *,
    timeout: int = 10,
    env_file: str = "",
) -> CliCheckResult:
    executable = resolve_assurance_path(configured_path)
    if not executable:
        return CliCheckResult(ok=False, command=fallback_command.split(), message="assurance executable not configured or found on PATH.")
    command = [executable, *args]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout, env=subprocess_env(env_file))
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
