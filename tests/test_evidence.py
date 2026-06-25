import subprocess
from datetime import datetime
from pathlib import Path

from app.evidence import (
    EvidenceForm,
    EvidenceRunSummary,
    build_evidence_command,
    create_run_dir,
    evidence_form_from_data,
    filter_evidence_runs,
    form_from_saved_request,
    list_evidence_runs,
    load_evidence_run,
    open_run_folder,
    output_folder_preview,
    render_markdown,
    run_evidence_pack,
    run_file_path,
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
        AppSettings(confluence_space="SPACE", jira_project="ABC", azure_resource_group="rg", repo_roots="/tmp/dev", repos="service-a"),
    )

    assert form.confluence_space == "SPACE"
    assert form.jira_project == "ABC"
    assert form.repo_roots == ("/tmp/dev",)
    assert form.repos == ("service-a",)
    assert form.limit == 20


def test_build_evidence_command_with_code_source() -> None:
    command = build_evidence_command(
        EvidenceForm(
            topic="booking",
            sources=("code",),
            repo_roots=("/tmp/dev",),
            repos=("booking-service", "shared-lib"),
            include_prs=True,
            include_diffs=True,
            github_fallback=True,
            max_diff_lines=300,
        )
    )

    assert command == [
        "assurance",
        "report",
        "evidence-pack",
        "booking",
        "--skip-confluence",
        "--skip-jira",
        "--include-code",
        "--repo-root",
        "/tmp/dev",
        "--repo",
        "booking-service",
        "--repo",
        "shared-lib",
        "--include-prs",
        "--include-diffs",
        "--github-fallback",
        "--max-diff-lines",
        "300",
        "--limit",
        "10",
    ]


def test_evidence_form_allows_no_sources_from_ui() -> None:
    form = evidence_form_from_data({"sources_present": "1"})

    assert form.sources == ()


def test_shell_command_quotes_topic() -> None:
    command = shell_command(["assurance", "report", "evidence-pack", "booking allocation"])

    assert command == "assurance report evidence-pack 'booking allocation'"


def test_create_run_dir_uses_slug_and_timestamp(tmp_path) -> None:
    run_dir = create_run_dir(str(tmp_path), EvidenceForm(topic="Booking Allocation!"), now=datetime(2026, 6, 24, 9, 30, 0))

    assert run_dir == tmp_path / "runs" / "2026-06-24-093000-booking-allocation"


def test_output_folder_preview_uses_slug(tmp_path) -> None:
    preview = output_folder_preview(str(tmp_path), EvidenceForm(topic="Booking Allocation!"))

    assert preview == tmp_path / "runs" / "<timestamp>-booking-allocation"


def test_run_evidence_pack_writes_metadata_and_logs(tmp_path) -> None:
    def fake_runner(command, **kwargs):
        out_path = command[command.index("--out") + 1]
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write("# Evidence\n\n- gap: missing Jira context\n")
        return subprocess.CompletedProcess(command, 0, stdout="done", stderr="warning: partial data\n")

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
    assert "- gap: missing Jira context" in (result.run_dir / "gaps-and-warnings.md").read_text(encoding="utf-8")
    assert "warning: partial data" in (result.run_dir / "gaps-and-warnings.json").read_text(encoding="utf-8")


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


def test_list_evidence_runs_reads_saved_metadata(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    (run_dir / "request.json").write_text(
        '{"topic": "booking", "preset": "", "sources": ["confluence", "jira"]}',
        encoding="utf-8",
    )
    (run_dir / "command.txt").write_text("assurance report evidence-pack booking\n", encoding="utf-8")
    (run_dir / "exit-code.txt").write_text("0\n", encoding="utf-8")
    (run_dir / "evidence-pack.md").write_text("# Evidence\n", encoding="utf-8")

    runs = list_evidence_runs(AppSettings(workbench_root=str(tmp_path)))

    assert len(runs) == 1
    assert runs[0].id == "2026-06-25-090000-booking"
    assert runs[0].topic == "booking"
    assert runs[0].sources == ("confluence", "jira")
    assert runs[0].exit_code == 0
    assert runs[0].has_evidence is True


def test_filter_evidence_runs() -> None:
    runs = [
        EvidenceRunSummary(
            "run-1",
            Path("/tmp/run-1"),
            "booking flow",
            "architecture",
            ("jira",),
            0,
            "",
            Path("/tmp/run-1/evidence-pack.md"),
            True,
        ),
        EvidenceRunSummary(
            "run-2",
            Path("/tmp/run-2"),
            "performance",
            "performance",
            ("azure",),
            0,
            "",
            Path("/tmp/run-2/evidence-pack.md"),
            True,
        ),
    ]

    filtered = filter_evidence_runs(runs, topic="book", preset="architecture", source="jira")

    assert [run.id for run in filtered] == ["run-1"]


def test_form_from_saved_request_preserves_empty_sources() -> None:
    form = form_from_saved_request({"topic": "no sources", "sources": []})

    assert form.topic == "no sources"
    assert form.sources == ()


def test_load_evidence_run_renders_markdown_and_warnings(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    (run_dir / "request.json").write_text('{"topic": "booking", "sources": ["azure"]}', encoding="utf-8")
    (run_dir / "command.txt").write_text("assurance report evidence-pack booking\n", encoding="utf-8")
    (run_dir / "exit-code.txt").write_text("1\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("warning: partial data\n", encoding="utf-8")
    (run_dir / "stdout.log").write_text("started\n", encoding="utf-8")
    (run_dir / "evidence-pack.md").write_text("# Evidence\n\n- gap: missing Jira context\n", encoding="utf-8")

    detail = load_evidence_run(AppSettings(workbench_root=str(tmp_path)), "2026-06-25-090000-booking")

    assert detail is not None
    assert "<h1>Evidence</h1>" in detail.evidence_html
    assert "<li>gap: missing Jira context</li>" in detail.evidence_html
    assert detail.warnings == ("- gap: missing Jira context", "warning: partial data")
    assert detail.stdout == "started\n"


def test_load_evidence_run_rejects_path_traversal(tmp_path) -> None:
    detail = load_evidence_run(AppSettings(workbench_root=str(tmp_path)), "../secret")

    assert detail is None


def test_run_file_path_allows_gaps_and_warnings_artifacts(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    artifact = run_dir / "gaps-and-warnings.json"
    artifact.write_text('{"items": []}\n', encoding="utf-8")

    path = run_file_path(AppSettings(workbench_root=str(tmp_path)), run_dir.name, "gaps-and-warnings.json")

    assert path == artifact


def test_open_run_folder_uses_local_open_command(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    (run_dir / "request.json").write_text('{"topic": "booking"}', encoding="utf-8")

    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = open_run_folder(AppSettings(workbench_root=str(tmp_path)), run_dir.name, runner=fake_runner)

    assert result.ok is True
    assert calls == [["open", str(run_dir)]]


def test_render_markdown_escapes_html() -> None:
    html = render_markdown("# <script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
