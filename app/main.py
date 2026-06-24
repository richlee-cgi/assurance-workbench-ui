from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.cli import check_assurance_cli, check_azure, check_dataverse
from app.settings import load_settings, save_settings, settings_from_form

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Assurance Workbench UI")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active_nav": "home",
            "title": "Assurance Workbench",
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
