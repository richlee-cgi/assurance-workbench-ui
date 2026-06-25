from pathlib import Path

from app.settings import AppSettings, load_settings, save_settings, settings_from_form


def test_save_and_load_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(
        assurance_path="/tmp/assurance",
        workbench_root="/tmp/workbench",
        confluence_space="SPACE",
        jira_project="ABC",
        azure_resource_group="rg",
        repo_roots="/tmp/dev",
        repos="service-a",
    )

    save_settings(settings, path)

    assert load_settings(path) == settings


def test_settings_from_form_strips_values() -> None:
    settings = settings_from_form(
        {
            "assurance_path": " /tmp/assurance ",
            "workbench_root": " /tmp/workbench ",
            "confluence_space": " SPACE ",
            "jira_project": " ABC ",
            "azure_resource_group": " rg ",
            "repo_roots": " /tmp/dev ",
            "repos": " service-a ",
        }
    )

    assert settings.assurance_path == "/tmp/assurance"
    assert settings.workbench_root == "/tmp/workbench"
    assert settings.confluence_space == "SPACE"
    assert settings.jira_project == "ABC"
    assert settings.azure_resource_group == "rg"
    assert settings.repo_roots == "/tmp/dev"
    assert settings.repos == "service-a"
