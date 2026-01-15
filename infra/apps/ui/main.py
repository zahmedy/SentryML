import os
import requests

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="SentryML UI")
templates = Jinja2Templates(directory="apps/ui/templates")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
API_KEY = os.getenv("UI_API_KEY")

def get_api_headers(request: Request) -> dict:
    api_key = request.cookies.get("api_key")
    if not api_key:
        raise RedirectResponse("/", status_code=302)
    return {"X-API-Key": api_key}

@app.get("/", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )

@app.post("/auth")
def auth(api_key: str = Form(...)):
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key="api_key",
        value=api_key,
        httponly=True,
    )
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    # Redirect to login if not authenticated
    if not request.cookies.get("api_key"):
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request},
    )

@app.get("/models", response_class=HTMLResponse)
def models(request: Request):
    headers = get_api_headers(request)

    resp = requests.get(
        f"{API_BASE}/v1/models",
        headers=headers,
        timeout=5,
    )
    resp.raise_for_status()

    models = resp.json()

    return templates.TemplateResponse(
        "models.html",
        {
            "request": request,
            "models": models,
        },
    )

@app.get("/incidents", response_class=HTMLResponse)
def incidents(request: Request):
    headers = get_api_headers(request)

    resp = requests.get(
        f"{API_BASE}/v1/incidents",
        headers=headers,
        timeout=5,
    )
    resp.raise_for_status()

    return templates.TemplateResponse(
        "incidents.html",
        {
            "request": request,
            "incidents": resp.json(),
        },
    )

@app.get("/drift", response_class=HTMLResponse)
def drift(
    request: Request,
    model_id: str | None = None,
):
    headers = get_api_headers(request)

    # 1. Fetch models
    models_resp = requests.get(
        f"{API_BASE}/v1/models",
        headers=headers,
        timeout=5,
    )
    models_resp.raise_for_status()
    models = models_resp.json()

    if not models:
        return templates.TemplateResponse(
            "drift.html",
            {"request": request, "models": [], "drift": [], "model_id": None},
        )

    # 2. Choose model
    if model_id is None:
        model_id = models[0]["model_id"]

    # 3. Fetch drift for selected model
    drift_resp = requests.get(
        f"{API_BASE}/v1/models/{model_id}/drift",
        headers=headers,
        timeout=5,
    )
    drift_resp.raise_for_status()

    drift = drift_resp.json()

    return templates.TemplateResponse(
        "drift.html",
        {
            "request": request,
            "models": models,
            "drift": drift,
            "model_id": model_id,
        },
    )

