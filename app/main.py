from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.cli import check_assurance_cli, check_azure, check_dataverse
from app.evidence import (
    build_evidence_command,
    evidence_form_from_data,
    filter_evidence_runs,
    form_from_saved_request,
    list_evidence_runs,
    load_evidence_run,
    open_run_folder,
    open_run_in_vscode,
    output_folder_preview,
    run_evidence_pack,
    run_file_path,
    shell_command,
)
from app.jobs import cancel_job, get_job, start_evidence_pack_job
from app.settings import load_settings, save_settings, settings_from_form

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Assurance Workbench UI")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    current_settings = load_settings()
    default_form = evidence_form_from_data({"sources_present": "1"}, current_settings)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active_nav": "home",
            "title": "Assurance Workbench",
            "settings": current_settings,
            "output_preview": output_folder_preview(current_settings.workbench_root, default_form),
        },
    )


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request) -> HTMLResponse:
    current_settings = load_settings()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "active_nav": "settings",
            "title": "Settings",
            "settings": current_settings,
        },
    )


@app.post("/settings", response_class=HTMLResponse)
async def save_settings_route(request: Request) -> HTMLResponse:
    form = await request.form()
    current_settings = settings_from_form(form)
    save_settings(current_settings)
    return templates.TemplateResponse(
        request,
        "partials/settings_status.html",
        {
            "status": "success",
            "message": "Settings saved locally.",
        },
    )


@app.post("/settings/check-assurance", response_class=HTMLResponse)
async def check_assurance_route(request: Request) -> HTMLResponse:
    form = await request.form()
    current_settings = settings_from_form(form)
    result = check_assurance_cli(current_settings.assurance_path)
    return templates.TemplateResponse(
        request,
        "partials/cli_check_result.html",
        {
            "result": result,
        },
    )


@app.post("/settings/check-azure", response_class=HTMLResponse)
async def check_azure_route(request: Request) -> HTMLResponse:
    form = await request.form()
    current_settings = settings_from_form(form)
    result = check_azure(current_settings.assurance_path)
    return templates.TemplateResponse(
        request,
        "partials/cli_check_result.html",
        {
            "result": result,
        },
    )


@app.post("/settings/check-dataverse", response_class=HTMLResponse)
async def check_dataverse_route(request: Request) -> HTMLResponse:
    form = await request.form()
    current_settings = settings_from_form(form)
    result = check_dataverse(current_settings.assurance_path)
    return templates.TemplateResponse(
        request,
        "partials/cli_check_result.html",
        {
            "result": result,
        },
    )


@app.post("/preview-command", response_class=HTMLResponse)
async def preview_command_route(request: Request) -> HTMLResponse:
    form_data = await request.form()
    form = evidence_form_from_data(form_data, load_settings())
    command = build_evidence_command(form)
    current_settings = load_settings()
    return templates.TemplateResponse(
        request,
        "partials/command_preview.html",
        {
            "command": command,
            "shell_command": shell_command(command),
            "output_preview": output_folder_preview(current_settings.workbench_root, form),
        },
    )


@app.post("/run-evidence-pack", response_class=HTMLResponse)
async def run_evidence_pack_route(request: Request) -> HTMLResponse:
    form_data = await request.form()
    current_settings = load_settings()
    form = evidence_form_from_data(form_data, current_settings)
    result = run_evidence_pack(form, current_settings)
    return templates.TemplateResponse(
        request,
        "partials/run_result.html",
        {
            "result": result,
            "shell_command": shell_command(result.command),
        },
    )


@app.post("/start-evidence-pack", response_class=HTMLResponse)
async def start_evidence_pack_route(request: Request) -> HTMLResponse:
    form_data = await request.form()
    current_settings = load_settings()
    form = evidence_form_from_data(form_data, current_settings)
    job = start_evidence_pack_job(form, current_settings)
    return templates.TemplateResponse(
        request,
        "partials/job_status.html",
        {
            "job": job,
            "shell_command": shell_command(job.command),
        },
    )


@app.get("/runs", response_class=HTMLResponse)
def runs(request: Request) -> HTMLResponse:
    current_settings = load_settings()
    topic = request.query_params.get("topic", "")
    preset = request.query_params.get("preset", "")
    source = request.query_params.get("source", "")
    all_runs = list_evidence_runs(current_settings)
    return templates.TemplateResponse(
        request,
        "runs.html",
        {
            "active_nav": "runs",
            "title": "Runs",
            "runs": filter_evidence_runs(all_runs, topic=topic, preset=preset, source=source),
            "total_runs": len(all_runs),
            "filters": {"topic": topic, "preset": preset, "source": source},
            "settings": current_settings,
        },
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str) -> HTMLResponse:
    current_settings = load_settings()
    detail = load_evidence_run(current_settings, run_id)
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "active_nav": "runs",
            "title": "Run Detail",
            "detail": detail,
            "run_id": run_id,
        },
        status_code=200 if detail else 404,
    )


@app.post("/runs/{run_id}/rerun", response_class=HTMLResponse)
def rerun(request: Request, run_id: str) -> HTMLResponse:
    current_settings = load_settings()
    detail = load_evidence_run(current_settings, run_id)
    if not detail:
        return templates.TemplateResponse(
            request,
            "partials/file_action_result.html",
            {"result": {"ok": False, "message": "Run not found.", "command": []}},
            status_code=404,
        )
    form = form_from_saved_request(detail.request, current_settings)
    job = start_evidence_pack_job(form, current_settings)
    return templates.TemplateResponse(
        request,
        "partials/job_status.html",
        {
            "job": job,
            "shell_command": shell_command(job.command),
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_status(request: Request, job_id: str) -> HTMLResponse:
    job = get_job(job_id)
    return templates.TemplateResponse(
        request,
        "partials/job_status.html",
        {
            "job": job,
            "shell_command": shell_command(job.command) if job else "",
        },
        status_code=200 if job else 404,
    )


@app.post("/jobs/{job_id}/cancel", response_class=HTMLResponse)
def cancel_job_route(request: Request, job_id: str) -> HTMLResponse:
    job = cancel_job(job_id)
    return templates.TemplateResponse(
        request,
        "partials/job_status.html",
        {
            "job": job,
            "shell_command": shell_command(job.command) if job else "",
        },
        status_code=200 if job else 404,
    )


@app.get("/runs/{run_id}/files/{filename}", response_class=PlainTextResponse)
def run_file(run_id: str, filename: str) -> PlainTextResponse:
    path = run_file_path(load_settings(), run_id, filename)
    if not path:
        return PlainTextResponse("File not found.", status_code=404)
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@app.post("/runs/{run_id}/open-folder", response_class=HTMLResponse)
def open_run_folder_route(request: Request, run_id: str) -> HTMLResponse:
    result = open_run_folder(load_settings(), run_id)
    return templates.TemplateResponse(
        request,
        "partials/file_action_result.html",
        {"result": result},
    )


@app.post("/runs/{run_id}/open-vscode", response_class=HTMLResponse)
def open_run_vscode_route(request: Request, run_id: str) -> HTMLResponse:
    result = open_run_in_vscode(load_settings(), run_id)
    return templates.TemplateResponse(
        request,
        "partials/file_action_result.html",
        {"result": result},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
