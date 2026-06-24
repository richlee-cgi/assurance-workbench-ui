from fastapi.testclient import TestClient

from app.cli import CliCheckResult
from app.evidence import EvidenceRunResult
from app.main import app
from app.settings import SETTINGS_PATH_ENV


client = TestClient(app)


def test_home_page() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Assurance Workbench" in response.text
    assert "Evidence pack runner" in response.text
    assert "hx-post=\"/preview-command\"" in response.text


def test_settings_page() -> None:
    response = client.get("/settings")

    assert response.status_code == 200
    assert "Assurance executable" in response.text
    assert "Workbench evidence root" in response.text
    assert "hx-post=\"/settings\"" in response.text


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_htmx_asset_is_served() -> None:
    response = client.get("/static/vendor/htmx.min.js")

    assert response.status_code == 200
    assert "var htmx" in response.text
    assert len(response.text) > 10_000


def test_save_settings_route(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(SETTINGS_PATH_ENV, str(tmp_path / "settings.json"))

    response = client.post(
        "/settings",
        data={
            "assurance_path": "/tmp/assurance",
            "workbench_root": "/tmp/workbench",
            "confluence_space": "SPACE",
            "jira_project": "ABC",
            "azure_resource_group": "rg",
        },
    )

    assert response.status_code == 200
    assert "Settings saved locally" in response.text
    assert (tmp_path / "settings.json").exists()


def test_check_assurance_route_reports_missing_path() -> None:
    response = client.post("/settings/check-assurance", data={"assurance_path": "/definitely/missing/assurance"})

    assert response.status_code == 200
    assert "Unable to run assurance" in response.text


def test_check_azure_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.check_azure",
        lambda path: CliCheckResult(ok=True, command=[path, "azure", "check"], message="Azure check completed."),
    )

    response = client.post("/settings/check-azure", data={"assurance_path": "/tmp/assurance"})

    assert response.status_code == 200
    assert "Azure check completed" in response.text


def test_check_dataverse_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.check_dataverse",
        lambda path: CliCheckResult(ok=True, command=[path, "dataverse", "check"], message="Dataverse check completed."),
    )

    response = client.post("/settings/check-dataverse", data={"assurance_path": "/tmp/assurance"})

    assert response.status_code == 200
    assert "Dataverse check completed" in response.text


def test_preview_command_route() -> None:
    response = client.post(
        "/preview-command",
        data={
            "topic": "booking allocation",
            "preset": "architecture",
            "sources": ["confluence", "azure"],
            "confluence_space": "SPACE",
            "azure_resource_group": "rg",
            "limit": "15",
            "refresh": "on",
        },
    )

    assert response.status_code == 200
    assert "Command preview" in response.text
    assert "booking allocation" in response.text
    assert "--preset architecture" in response.text
    assert "--skip-jira" in response.text
    assert "--include-azure" in response.text
    assert "--azure-resource-group rg" in response.text
    assert "--refresh" in response.text


def test_run_evidence_pack_route(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "run"
    evidence_path = run_dir / "evidence-pack.md"
    run_dir.mkdir(parents=True)
    evidence_path.write_text("# Evidence\n", encoding="utf-8")

    def fake_run(form, settings):
        return EvidenceRunResult(
            run_dir=run_dir,
            command=["/tmp/assurance", "report", "evidence-pack", "booking", "--out", str(evidence_path)],
            exit_code=0,
            stdout="done",
            stderr="",
            evidence_path=evidence_path,
        )

    monkeypatch.setattr("app.main.run_evidence_pack", fake_run)

    response = client.post("/run-evidence-pack", data={"topic": "booking", "sources": ["confluence"]})

    assert response.status_code == 200
    assert "Run completed" in response.text
    assert str(evidence_path) in response.text
