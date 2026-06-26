import subprocess

from app.cli import check_assurance_cli, check_azure, check_dataverse, discover_code_repos, resolve_assurance_path


def test_resolve_assurance_path_prefers_configured_path(monkeypatch) -> None:
    monkeypatch.setattr("app.cli._venv_assurance_executable", lambda: "/tmp/from-venv")

    assert resolve_assurance_path("/tmp/configured") == "/tmp/configured"


def test_resolve_assurance_path_uses_installed_venv_script(monkeypatch) -> None:
    monkeypatch.setattr("app.cli._venv_assurance_executable", lambda: "/tmp/from-venv")

    assert resolve_assurance_path("") == "/tmp/from-venv"


def test_check_assurance_cli_reports_missing_path() -> None:
    result = check_assurance_cli("/definitely/missing/assurance")

    assert result.ok is False
    assert "Unable to run assurance" in result.message


def test_check_azure_reports_missing_path() -> None:
    result = check_azure("/definitely/missing/assurance")

    assert result.ok is False
    assert result.command == ["/definitely/missing/assurance", "azure", "check"]


def test_check_dataverse_reports_missing_path() -> None:
    result = check_dataverse("/definitely/missing/assurance")

    assert result.ok is False
    assert result.command == ["/definitely/missing/assurance", "dataverse", "check"]


def test_discover_code_repos_parses_json(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"repositories": [{"name": "booking-service", "path": "/tmp/dev/booking-service"}]}',
            stderr="",
        )

    monkeypatch.setattr("app.cli.subprocess.run", fake_run)

    result = discover_code_repos("/tmp/assurance", ("/tmp/dev",))

    assert result.ok is True
    assert result.repositories[0]["name"] == "booking-service"
    assert result.command == ["/tmp/assurance", "code", "repos", "--raw", "--repo-root", "/tmp/dev"]
