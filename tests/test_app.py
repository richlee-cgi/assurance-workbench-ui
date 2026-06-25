from fastapi.testclient import TestClient

from app.cli import CliCheckResult, CodeRepoDiscoveryResult
from app.evidence import EvidenceRunDetail, EvidenceRunResult, EvidenceRunSummary, FileActionResult
from app.jobs import EvidenceJob
from app.main import app
from app.settings import SETTINGS_PATH_ENV


client = TestClient(app)


def test_home_page() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Assurance Workbench" in response.text
    assert "Evidence pack runner" in response.text
    assert "hx-post=\"/preview-command\"" in response.text
    assert "Output folder" in response.text
    assert "Code repositories" in response.text
    assert "Repo roots" in response.text
    assert "Discover repos" in response.text


def test_settings_page() -> None:
    response = client.get("/settings")

    assert response.status_code == 200
    assert "Assurance executable" in response.text
    assert "Workbench evidence root" in response.text
    assert "Default repo roots" in response.text
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
            "repo_roots": "/tmp/dev",
            "repos": "booking-service",
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
    assert "&lt;timestamp&gt;-booking-allocation" in response.text


def test_preview_command_route_with_code_source() -> None:
    response = client.post(
        "/preview-command",
        data={
            "topic": "booking",
            "sources": ["code"],
            "sources_present": "1",
            "repo_roots": "/tmp/dev",
            "repos": "booking-service\nshared-lib",
            "include_prs": "on",
            "include_diffs": "on",
            "github_fallback": "on",
            "max_diff_lines": "300",
            "limit": "5",
        },
    )

    assert response.status_code == 200
    assert "--include-code" in response.text
    assert "--repo-root /tmp/dev" in response.text
    assert "--repo booking-service" in response.text
    assert "--repo shared-lib" in response.text
    assert "--include-prs" in response.text
    assert "--include-diffs" in response.text
    assert "--github-fallback" in response.text
    assert "--max-diff-lines 300" in response.text


def test_discover_code_repos_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.discover_code_repos",
        lambda path, roots: CodeRepoDiscoveryResult(
            ok=True,
            command=[path, "code", "repos", "--raw"],
            repositories=[{"name": "booking-service", "path": "/tmp/dev/booking-service", "branch": "main", "dirty": False}],
            message="Discovered 1 repositories.",
        ),
    )

    response = client.post("/discover-code-repos", data={"repo_roots": "/tmp/dev"})

    assert response.status_code == 200
    assert "Discovered 1 repositories" in response.text
    assert "booking-service" in response.text


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
    assert f"/runs/{run_dir.name}" in response.text


def test_start_evidence_pack_route(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "job"
    evidence_path = run_dir / "evidence-pack.md"
    job = EvidenceJob(
        id="job-1",
        run_dir=run_dir,
        command=["/tmp/assurance", "report", "evidence-pack", "booking", "--out", str(evidence_path)],
        evidence_path=evidence_path,
        stdout="started\n",
    )
    monkeypatch.setattr("app.main.start_evidence_pack_job", lambda form, settings: job)

    response = client.post("/start-evidence-pack", data={"topic": "booking", "sources": ["confluence"]})

    assert response.status_code == 200
    assert "Run in progress" in response.text
    assert "started" in response.text
    assert "/jobs/job-1" in response.text


def test_job_status_route(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "job"
    evidence_path = run_dir / "evidence-pack.md"
    job = EvidenceJob(
        id="job-1",
        run_dir=run_dir,
        command=["/tmp/assurance"],
        evidence_path=evidence_path,
        stdout="done\n",
        exit_code=0,
    )
    monkeypatch.setattr("app.main.get_job", lambda job_id: job)

    response = client.get("/jobs/job-1")

    assert response.status_code == 200
    assert "Run completed" in response.text
    assert f"/runs/{run_dir.name}" in response.text


def test_cancel_job_route(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "job"
    job = EvidenceJob(
        id="job-1",
        run_dir=run_dir,
        command=["/tmp/assurance"],
        evidence_path=run_dir / "evidence-pack.md",
        exit_code=130,
        canceled=True,
    )
    monkeypatch.setattr("app.main.cancel_job", lambda job_id: job)

    response = client.post("/jobs/job-1/cancel")

    assert response.status_code == 200
    assert "Run canceled" in response.text


def test_runs_page(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    evidence_path = run_dir / "evidence-pack.md"
    summary = EvidenceRunSummary(
        id=run_dir.name,
        run_dir=run_dir,
        topic="booking",
        preset="",
        sources=("confluence", "jira"),
        exit_code=0,
        command="assurance report evidence-pack booking",
        evidence_path=evidence_path,
        has_evidence=True,
    )
    monkeypatch.setattr("app.main.list_evidence_runs", lambda settings: [summary])

    response = client.get("/runs")

    assert response.status_code == 200
    assert "Evidence results" in response.text
    assert "booking" in response.text
    assert f"/runs/{run_dir.name}" in response.text


def test_runs_page_filters(monkeypatch, tmp_path) -> None:
    summaries = [
        EvidenceRunSummary(
            id="run-booking",
            run_dir=tmp_path / "runs" / "run-booking",
            topic="booking",
            preset="architecture",
            sources=("jira",),
            exit_code=0,
            command="",
            evidence_path=tmp_path / "runs" / "run-booking" / "evidence-pack.md",
            has_evidence=True,
        ),
        EvidenceRunSummary(
            id="run-scaling",
            run_dir=tmp_path / "runs" / "run-scaling",
            topic="scaling",
            preset="scaling",
            sources=("azure",),
            exit_code=0,
            command="",
            evidence_path=tmp_path / "runs" / "run-scaling" / "evidence-pack.md",
            has_evidence=True,
        ),
    ]
    monkeypatch.setattr("app.main.list_evidence_runs", lambda settings: summaries)

    response = client.get("/runs?topic=book&preset=architecture&source=jira")

    assert response.status_code == 200
    assert "booking" in response.text
    assert "/runs/run-booking" in response.text
    assert "/runs/run-scaling" not in response.text


def test_run_detail_page(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "runs" / "2026-06-25-090000-booking"
    evidence_path = run_dir / "evidence-pack.md"
    summary = EvidenceRunSummary(
        id=run_dir.name,
        run_dir=run_dir,
        topic="booking",
        preset="",
        sources=("azure",),
        exit_code=0,
        command="assurance report evidence-pack booking --include-azure",
        evidence_path=evidence_path,
        has_evidence=True,
    )
    detail = EvidenceRunDetail(
        summary=summary,
        request={"topic": "booking"},
        stdout="done",
        stderr="",
        evidence_markdown="# Evidence",
        evidence_html="<h1>Evidence</h1>",
        warnings=("gap: missing Jira context",),
    )
    monkeypatch.setattr("app.main.load_evidence_run", lambda settings, run_id: detail)

    response = client.get(f"/runs/{run_dir.name}")

    assert response.status_code == 200
    assert "Run metadata" in response.text
    assert "Source coverage" in response.text
    assert "Saved files" in response.text
    assert "Re-run" in response.text
    assert f"/runs/{run_dir.name}/files/evidence-pack.md" in response.text
    assert "assurance report evidence-pack booking --include-azure" in response.text
    assert "<h1>Evidence</h1>" in response.text
    assert "gap: missing Jira context" in response.text


def test_run_detail_page_reports_missing(monkeypatch) -> None:
    monkeypatch.setattr("app.main.load_evidence_run", lambda settings, run_id: None)

    response = client.get("/runs/missing")

    assert response.status_code == 404
    assert "Result not found" in response.text


def test_run_file_route(monkeypatch, tmp_path) -> None:
    artifact = tmp_path / "evidence-pack.md"
    artifact.write_text("# Evidence\n", encoding="utf-8")
    monkeypatch.setattr("app.main.run_file_path", lambda settings, run_id, filename: artifact)

    response = client.get("/runs/run-1/files/evidence-pack.md")

    assert response.status_code == 200
    assert response.text == "# Evidence\n"


def test_run_file_route_reports_missing(monkeypatch) -> None:
    monkeypatch.setattr("app.main.run_file_path", lambda settings, run_id, filename: None)

    response = client.get("/runs/run-1/files/secret.txt")

    assert response.status_code == 404
    assert "File not found" in response.text


def test_open_folder_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.open_run_folder",
        lambda settings, run_id: FileActionResult(True, "Opened run folder.", ["open", "/tmp/run"]),
    )

    response = client.post("/runs/run-1/open-folder")

    assert response.status_code == 200
    assert "Action completed" in response.text
    assert "Opened run folder" in response.text


def test_open_vscode_route_reports_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.open_run_in_vscode",
        lambda settings, run_id: FileActionResult(False, "code was not found", []),
    )

    response = client.post("/runs/run-1/open-vscode")

    assert response.status_code == 200
    assert "Action failed" in response.text
    assert "code was not found" in response.text


def test_rerun_route(monkeypatch, tmp_path) -> None:
    original_dir = tmp_path / "runs" / "original"
    rerun_dir = tmp_path / "runs" / "rerun"
    evidence_path = rerun_dir / "evidence-pack.md"
    summary = EvidenceRunSummary(
        id=original_dir.name,
        run_dir=original_dir,
        topic="booking",
        preset="",
        sources=(),
        exit_code=0,
        command="",
        evidence_path=original_dir / "evidence-pack.md",
        has_evidence=True,
    )
    detail = EvidenceRunDetail(
        summary=summary,
        request={"topic": "booking", "sources": []},
        stdout="",
        stderr="",
        evidence_markdown="",
        evidence_html="",
        warnings=(),
    )
    captured = {}

    def fake_start(form, settings):
        captured["sources"] = form.sources
        return EvidenceJob(
            id="job-rerun",
            run_dir=rerun_dir,
            command=["/tmp/assurance", "report", "evidence-pack", "booking", "--out", str(evidence_path)],
            evidence_path=evidence_path,
            stdout="started",
        )

    monkeypatch.setattr("app.main.load_evidence_run", lambda settings, run_id: detail)
    monkeypatch.setattr("app.main.start_evidence_pack_job", fake_start)

    response = client.post("/runs/original/rerun")

    assert response.status_code == 200
    assert "Run in progress" in response.text
    assert captured["sources"] == ()
