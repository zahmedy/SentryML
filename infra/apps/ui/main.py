import os
import requests

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="SentryML UI")
templates = Jinja2Templates(directory="apps/ui/templates")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

def api_cookie_jar(request: Request) -> dict:
    sid = request.cookies.get("sentryml_session")
    return {"sentryml_session": sid} if sid else {}

def require_session(request: Request):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)
    return None

@app.get("/settings/api-keys", response_class=HTMLResponse)
def api_keys_page(request: Request):
    r = require_session(request)
    if r:
        return r

    resp = requests.get(
        f"{API_BASE}/v1/api-keys",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()

    return templates.TemplateResponse(
        "api_keys.html",
        {"request": request, "keys": resp.json(), "new_key": None},
    )

@app.post("/settings/api-keys/create")
def api_keys_create(request: Request, name: str = Form(default="")):
    r = require_session(request)
    if r:
        return r

    resp = requests.post(
        f"{API_BASE}/v1/api-keys",
        json={"name": name or None},
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()

    # Re-fetch list so page renders current state
    keys_resp = requests.get(
        f"{API_BASE}/v1/api-keys",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    keys_resp.raise_for_status()

    return templates.TemplateResponse(
        "api_keys.html",
        {"request": request, "keys": keys_resp.json(), "new_key": resp.json()},
    )

@app.post("/settings/api-keys/{key_id}/revoke")
def api_keys_revoke(request: Request, key_id: str):
    r = require_session(request)
    if r:
        return r

    resp = requests.post(
        f"{API_BASE}/v1/api-keys/{key_id}/revoke",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()

    return RedirectResponse("/settings/api-keys", status_code=303)

@app.get("/", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )

@app.post("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("sentryml_session")
    return resp

@app.post("/auth")
def auth(email: str = Form(...), password: str = Form(...)):
    resp = requests.post(
        f"{API_BASE}/v1/auth/login",
        json={"email": email, "password": password},
        timeout=5,
    )
    if resp.status_code != 200:
        return RedirectResponse("/", status_code=303)

    # grab session cookie from API response
    session_cookie = resp.cookies.get("sentryml_session")
    if not session_cookie:
        return RedirectResponse("/", status_code=303)

    out = RedirectResponse("/dashboard", status_code=303)
    out.set_cookie(
        key="sentryml_session",
        value=session_cookie,
        httponly=True,
        samesite="lax",
    )
    return out

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    # Redirect to login if not authenticated
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(f"{API_BASE}/v1/ui/dashboard", cookies=api_cookie_jar(request), timeout=5)
    resp.raise_for_status()
    data = resp.json()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "open_incidents": data.get("open_incidents", []),
            "latest_drift": data.get("latest_drift", []),
        },
    )

@app.get("/models/{model_id}", response_class=HTMLResponse)
def model_detail(request: Request, model_id: str):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(
        f"{API_BASE}/v1/ui/models/{model_id}",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    return templates.TemplateResponse(
        "model_detail.html",
        {"request": request, "model_id": model_id, "drift": data["drift"], "incidents": data["incidents"]},
    )


