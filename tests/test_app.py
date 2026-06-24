from fastapi.testclient import TestClient

from app.main import app


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


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_htmx_asset_is_served() -> None:
    response = client.get("/static/vendor/htmx.min.js")

    assert response.status_code == 200
    assert "var htmx" in response.text
    assert len(response.text) > 10_000
