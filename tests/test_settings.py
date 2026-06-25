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
        exclude_confluence_parents="983238177",
        jira_team_field="customfield_12345",
        exclude_jira_teams="DSP Assurance",
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
            "exclude_confluence_parents": " 983238177 ",
            "jira_team_field": " customfield_12345 ",
            "exclude_jira_teams": " DSP Assurance ",
        }
    )

    assert settings.assurance_path == "/tmp/assurance"
    assert settings.workbench_root == "/tmp/workbench"
    assert settings.confluence_space == "SPACE"
    assert settings.jira_project == "ABC"
    assert settings.azure_resource_group == "rg"
    assert settings.repo_roots == "/tmp/dev"
    assert settings.repos == "service-a"
    assert settings.exclude_confluence_parents == "983238177"
    assert settings.jira_team_field == "customfield_12345"
    assert settings.exclude_jira_teams == "DSP Assurance"
