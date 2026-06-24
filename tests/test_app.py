from fastapi.testclient import TestClient

from app.main import app
from app.settings import SETTINGS_PATH_ENV


client = TestClient(app)


def test_home_page() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Assurance Workbench" in response.text
    assert "Evidence pack runner" in response.text


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
