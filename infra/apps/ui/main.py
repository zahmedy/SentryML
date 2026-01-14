from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests
import os

app = FastAPI(title="SentryML UI")

templates = Jinja2Templates(directory="apps/ui/templates")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
API_KEY = os.getenv("UI_API_KEY")


def get_headers():
    return {"X-API-Key": API_KEY}

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/models")

@app.get("/models", response_class=HTMLResponse)
def models(request: Request):
    resp = requests.get(
        f"{API_BASE}/v1/models",
        headers=get_headers(),
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
