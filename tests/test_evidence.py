import subprocess
from datetime import datetime
from pathlib import Path

from app.evidence import (
    EvidenceForm,
    EvidenceRunSummary,
    build_evidence_command,
    build_run_command,
    create_run_dir,
    delete_evidence_run,
    evidence_form_from_data,
    filter_evidence_runs,
    form_from_saved_request,
    list_evidence_runs,
    load_evidence_run,
    open_run_folder,
    output_folder_preview,
    preview_markdown,
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
        AppSettings(
            confluence_space="SPACE",
            jira_project="ABC",
            azure_resource_group="rg",
            repo_roots="/tmp/dev",
            repos="service-a",
            exclude_confluence_parents="983238177",
            jira_team_field="customfield_12345",
            exclude_jira_teams="DSP Assurance",
        ),
    )

    assert form.confluence_space == "SPACE"
    assert form.jira_project == "ABC"
    assert form.repo_roots == ("/tmp/dev",)
    assert form.repos == ("service-a",)
    assert form.exclude_confluence_parents == ("983238177",)
    assert form.jira_team_field == "customfield_12345"
    assert form.exclude_jira_teams == ("DSP Assurance",)
    assert form.limit == 20


def test_build_evidence_command_with_exclusions() -> None:
    command = build_evidence_command(
        EvidenceForm(
            topic="booking",
            sources=("confluence", "jira"),
            exclude_confluence_parents=("983238177",),
            jira_team_field="customfield_12345",
            exclude_jira_teams=("DSP Assurance",),
        )
    )

    assert "--exclude-confluence-parent" in command
    assert command[command.index("--exclude-confluence-parent") + 1] == "983238177"
    assert "--jira-team-field" in command
    assert command[command.index("--jira-team-field") + 1] == "customfield_12345"
    assert "--exclude-jira-team" in command
    assert command[command.index("--exclude-jira-team") + 1] == "DSP Assurance"


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


def test_build_run_command_uses_resolved_assurance_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.evidence.resolve_assurance_path", lambda configured: "/tmp/from-venv")

    command = build_run_command(EvidenceForm(topic="booking"), assurance_path="", evidence_path=tmp_path / "evidence-pack.md")

    assert command[0] == "/tmp/from-venv"


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
    assert '"criteria":' in (result.run_dir / "gaps-and-warnings.json").read_text(encoding="utf-8")
    assert '"locations":' in (result.run_dir / "gaps-and-warnings.json").read_text(encoding="utf-8")
    assert "Explicit gap or warning language found" in (result.run_dir / "assurance-checks.md").read_text(encoding="utf-8")
    assert "Analyst Questions" in (result.run_dir / "analyst-brief.md").read_text(encoding="utf-8")


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


def test_form_from_saved_request_preserves_json_lists() -> None:
    form = form_from_saved_request(
        {
            "topic": "https://github.com/dvsa/dsp-integrations/pull/237",
            "sources": ["code"],
            "repo_roots": ["/Users/rich/dev/dev-work/dvsa-dsp"],
            "repos": ["dsp-integrations"],
            "exclude_confluence_parents": ["983238177"],
            "exclude_jira_teams": ["DSP Assurance"],
            "include_prs": True,
            "include_diffs": True,
        }
    )

    command = build_evidence_command(form)

    assert form.repo_roots == ("/Users/rich/dev/dev-work/dvsa-dsp",)
    assert form.repos == ("dsp-integrations",)
    assert "--repo-root" in command
    assert "['/Users/rich/dev/dev-work/dvsa-dsp']" not in command
    assert command[command.index("--repo-root") + 1] == "/Users/rich/dev/dev-work/dvsa-dsp"
    assert command[command.index("--repo") + 1] == "dsp-integrations"


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
    assert "<h1>Evidence</h1>" in detail.evidence_preview_html
    assert detail.evidence_preview_truncated is False
    assert detail.evidence_line_count == 3
    assert "<li>gap: missing Jira context</li>" in detail.evidence_html
    assert detail.warnings == ("- gap: missing Jira context", "warning: partial data")
    assert detail.stdout == "started\n"


def test_preview_markdown_limits_sections() -> None:
    markdown = "\n".join(
        [
            "# Evidence",
            "Intro",
            "## One",
            "First",
            "## Two",
            "Second",
            "## Three",
            "Third",
        ]
    )

    preview, truncated = preview_markdown(markdown, max_sections=2, max_chars=10_000)

    assert truncated is True
    assert "## One" in preview
    assert "## Two" in preview
    assert "## Three" not in preview


def test_preview_markdown_limits_size() -> None:
    preview, truncated = preview_markdown("A\nB\nC\nD", max_sections=10, max_chars=4)

    assert truncated is True
    assert preview == "A\nB"


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


def test_run_file_path_allows_analysis_artifacts(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    checks = run_dir / "assurance-checks.md"
    brief = run_dir / "analyst-brief.md"
    checks.write_text("# Assurance Checks\n", encoding="utf-8")
    brief.write_text("# Analyst Brief\n", encoding="utf-8")

    settings = AppSettings(workbench_root=str(tmp_path))

    assert run_file_path(settings, run_dir.name, "assurance-checks.md") == checks
    assert run_file_path(settings, run_dir.name, "analyst-brief.md") == brief


def test_delete_evidence_run_removes_run_folder(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    run_dir.mkdir(parents=True)
    (run_dir / "request.json").write_text('{"topic": "booking"}', encoding="utf-8")

    result = delete_evidence_run(AppSettings(workbench_root=str(tmp_path)), run_dir.name)

    assert result.ok is True
    assert not run_dir.exists()


def test_delete_evidence_run_rejects_path_traversal(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()

    result = delete_evidence_run(AppSettings(workbench_root=str(tmp_path)), "../outside")

    assert result.ok is False
    assert outside.exists()


def test_analysis_artifacts_include_absence_checks(tmp_path) -> None:
    def fake_runner(command, **kwargs):
        out_path = command[command.index("--out") + 1]
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(
                "# Evidence\n\n"
                "## Sources Queried\n\n"
                "- Confluence: `yes`\n"
                "- Jira: `yes`\n\n"
                "## Confluence Evidence\n\n"
                "## Payment LLD\n\n"
                "- URL: https://example.atlassian.net/wiki/spaces/DSP/pages/456/Payment+LLD\n\n"
                "This LLD describes the payment API endpoint and XML payload.\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_evidence_pack(
        EvidenceForm(topic="payment", sources=("confluence", "jira")),
        AppSettings(assurance_path="/tmp/assurance", workbench_root=str(tmp_path)),
        runner=fake_runner,
    )

    checks = (result.run_dir / "assurance-checks.md").read_text(encoding="utf-8")
    brief = (result.run_dir / "analyst-brief.md").read_text(encoding="utf-8")

    assert "LLD NFR coverage" in checks
    assert "XML schema coverage" in checks
    assert "API error-code coverage" in checks
    assert "Confirm whether XML payloads have a documented and tested schema" in brief


def test_gaps_and_warnings_markdown_formats_table_rows(tmp_path) -> None:
    def fake_runner(command, **kwargs):
        out_path = command[command.index("--out") + 1]
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(
                "# Evidence\n\n"
                "## Confluence Evidence\n\n"
                "## Booking Decisions\n\n"
                "- URL: https://example.atlassian.net/wiki/spaces/DSP/pages/123/Booking\n\n"
                "| ❌ Gap | Not defined |\n\n"
                "* identify gaps, inconsistencies, or missing behaviours\n\n"
                "## Gaps / Follow-up Questions\n\n"
                "_No mechanical gaps identified by the retrieval commands._\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_evidence_pack(
        EvidenceForm(topic="booking"),
        AppSettings(assurance_path="/tmp/assurance", workbench_root=str(tmp_path)),
        runner=fake_runner,
    )

    markdown = (result.run_dir / "gaps-and-warnings.md").read_text(encoding="utf-8")
    assert "## 1. Gap" in markdown
    assert "|   |   |" in markdown
    assert "| --- | --- |" in markdown
    assert "| ❌ Gap | Not defined |" in markdown
    assert "- **Source:** confluence: Booking Decisions (https://example.atlassian.net/wiki/spaces/DSP/pages/123/Booking)" in markdown
    assert '- **Criteria:** contains "gap"' in markdown
    assert "```text" not in markdown
    assert "identify gaps" not in markdown
    assert "Gaps / Follow-up Questions" not in markdown
    assert "No mechanical gaps identified" not in markdown


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


def test_render_markdown_tables() -> None:
    html = render_markdown("| Repository | Status |\n| --- | --- |\n| dsp-integrations | clean |")

    assert "<table>" in html
    assert "<th>Repository</th>" in html
    assert "<td>dsp-integrations</td>" in html
    assert "| --- | --- |" not in html


def test_render_markdown_keeps_tables_inside_code_blocks() -> None:
    html = render_markdown("```diff\n+| Repository | Status |\n+| --- | --- |\n```")

    assert "<table>" not in html
    assert "+| Repository | Status |" in html
