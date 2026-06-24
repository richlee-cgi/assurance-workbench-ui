from app.evidence import EvidenceForm, build_evidence_command, evidence_form_from_data, shell_command
from app.settings import AppSettings


def test_build_evidence_command_with_selected_sources() -> None:
    command = build_evidence_command(
        EvidenceForm(
            topic="booking allocation",
            preset="architecture",
            sources=("confluence", "azure"),
            confluence_space="SPACE",
            jira_project="ABC",
            azure_resource_group="rg",
            include_comments=True,
            refresh=True,
        )
    )

    assert command == [
        "assurance",
        "report",
        "evidence-pack",
        "booking allocation",
        "--preset",
        "architecture",
        "--confluence-space",
        "SPACE",
        "--skip-jira",
        "--include-azure",
        "--azure-resource-group",
        "rg",
        "--limit",
        "10",
        "--include-comments",
        "--refresh",
    ]


def test_evidence_form_uses_defaults() -> None:
    form = evidence_form_from_data(
        {"sources": ["confluence", "jira"], "limit": "20"},
        AppSettings(confluence_space="SPACE", jira_project="ABC", azure_resource_group="rg"),
    )

    assert form.confluence_space == "SPACE"
    assert form.jira_project == "ABC"
    assert form.limit == 20


def test_shell_command_quotes_topic() -> None:
    command = shell_command(["assurance", "report", "evidence-pack", "booking allocation"])

    assert command == "assurance report evidence-pack 'booking allocation'"
