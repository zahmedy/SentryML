import os
from datetime import datetime
import requests

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="SentryML UI")
templates = Jinja2Templates(directory="apps/ui/templates")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

def _fmt_dt(value) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    else:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")

templates.env.filters["fmt_dt"] = _fmt_dt

def _fmt_num(value, places: int = 4) -> str:
    if value is None or value == "":
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{num:.{places}f}"

templates.env.filters["fmt_num"] = _fmt_num

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
            "models": data.get("models", []),
        },
    )

@app.get("/models/{model_id}", response_class=HTMLResponse)
def model_detail(request: Request, model_id: str, pred_limit: int = 200):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(
        f"{API_BASE}/v1/ui/models/{model_id}",
        params={"pred_limit": pred_limit},
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    return templates.TemplateResponse(
        "model_detail.html",
        {
            "request": request,
            "model_id": data["model_id"],
            "drift": data["drift"],
            "incidents": data["incidents"],
            "pred_limit": pred_limit,
            "recent_predictions": data.get("recent_predictions", []),
        },
    )

@app.post("/models/{model_id}/monitoring/enable")
def ui_enable_monitoring(request: Request, model_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/models/{model_id}/monitoring/enable",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/models/{model_id}/monitoring/disable")
def ui_disable_monitoring(request: Request, model_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/models/{model_id}/monitoring/disable",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/incidents/{incident_id}", response_class=HTMLResponse)
def incident_detail(request: Request, incident_id: str):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(
        f"{API_BASE}/v1/ui/incidents/{incident_id}",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    return templates.TemplateResponse(
        "incident_detail.html",
        {
            "request": request,
            "incident": data["incident"],
            "events": data.get("events", []),
        },
    )


@app.post("/incidents/{incident_id}/ack")
def ui_incident_ack(request: Request, incident_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/incidents/{incident_id}/ack",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)


@app.post("/incidents/{incident_id}/close")
def ui_incident_close(request: Request, incident_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/incidents/{incident_id}/close",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)


@app.post("/incidents/{incident_id}/resolve")
def ui_incident_resolve(request: Request, incident_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/incidents/{incident_id}/resolve",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)
