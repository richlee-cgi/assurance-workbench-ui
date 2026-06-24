import subprocess
from datetime import datetime

from app.evidence import (
    EvidenceForm,
    build_evidence_command,
    create_run_dir,
    evidence_form_from_data,
    run_evidence_pack,
    shell_command,
)
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


def test_evidence_form_allows_no_sources_from_ui() -> None:
    form = evidence_form_from_data({"sources_present": "1"})

    assert form.sources == ()


def test_shell_command_quotes_topic() -> None:
    command = shell_command(["assurance", "report", "evidence-pack", "booking allocation"])

    assert command == "assurance report evidence-pack 'booking allocation'"


def test_create_run_dir_uses_slug_and_timestamp(tmp_path) -> None:
    run_dir = create_run_dir(str(tmp_path), EvidenceForm(topic="Booking Allocation!"), now=datetime(2026, 6, 24, 9, 30, 0))

    assert run_dir == tmp_path / "runs" / "2026-06-24-093000-booking-allocation"


def test_run_evidence_pack_writes_metadata_and_logs(tmp_path) -> None:
    def fake_runner(command, **kwargs):
        out_path = command[command.index("--out") + 1]
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write("# Evidence\n")
        return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

    result = run_evidence_pack(
        EvidenceForm(topic="booking", sources=("confluence",), confluence_space="SPACE"),
        AppSettings(assurance_path="/tmp/assurance", workbench_root=str(tmp_path)),
        runner=fake_runner,
    )

    assert result.exit_code == 0
    assert result.evidence_path.exists()
    assert (result.run_dir / "request.json").exists()
    assert (result.run_dir / "command.txt").read_text(encoding="utf-8").startswith("/tmp/assurance report evidence-pack")
    assert (result.run_dir / "stdout.log").read_text(encoding="utf-8") == "done"
    assert (result.run_dir / "exit-code.txt").read_text(encoding="utf-8") == "0\n"


def test_run_evidence_pack_records_timeout(tmp_path) -> None:
    def fake_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=1, output="partial", stderr="late")

    result = run_evidence_pack(
        EvidenceForm(topic="booking"),
        AppSettings(assurance_path="/tmp/assurance", workbench_root=str(tmp_path)),
        runner=fake_runner,
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    assert (result.run_dir / "stdout.log").read_text(encoding="utf-8") == "partial"
