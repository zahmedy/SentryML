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

def _fmt_num(value, places: int = 4, trim: bool = False) -> str:
    if value is None or value == "":
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    out = f"{num:.{places}f}"
    if trim:
        out = out.rstrip("0").rstrip(".")
    return out

templates.env.filters["fmt_num"] = _fmt_num
templates.env.filters["fmt_num_trim"] = lambda v: _fmt_num(v, trim=True)

def api_cookie_jar(request: Request) -> dict:
    sid = request.cookies.get("sentryml_session")
    return {"sentryml_session": sid} if sid else {}

def require_session(request: Request):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)
    return None

def _load_settings_data(request: Request) -> dict:
    resp = requests.get(
        f"{API_BASE}/v1/ui/settings",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    settings = resp.json()

    keys_resp = requests.get(
        f"{API_BASE}/v1/api-keys",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    keys_resp.raise_for_status()

    return {
        "monitors": settings.get("monitors", []),
        "slack": settings.get("slack"),
        "org_id": settings.get("org_id"),
        "keys": keys_resp.json(),
    }


def _get_stats(request: Request) -> dict:
    try:
        resp = requests.get(
            f"{API_BASE}/v1/ui/stats",
            cookies=api_cookie_jar(request),
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {
            "worker_status": "unknown",
            "last_worker_run": None,
            "monitored_models": 0,
            "open_incidents": 0,
            "last_alert_at": None,
        }


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    r = require_session(request)
    if r:
        return r

    data = _load_settings_data(request)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "stats": _get_stats(request),
            "monitors": data["monitors"],
            "slack": data["slack"],
            "org_id": data.get("org_id"),
            "keys": data["keys"],
            "new_key": None,
        },
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    r = require_session(request)
    if r:
        return r
    return templates.TemplateResponse(
        "privacy.html",
        {"request": request},
    )


@app.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    r = require_session(request)
    if r:
        return r
    return templates.TemplateResponse(
        "contact.html",
        {"request": request},
    )

@app.get("/settings/api-keys", response_class=HTMLResponse)
def api_keys_page(request: Request):
    return settings_page(request)

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

    data = _load_settings_data(request)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "stats": _get_stats(request),
            "monitors": data["monitors"],
            "slack": data["slack"],
            "org_id": data.get("org_id"),
            "keys": data["keys"],
            "new_key": resp.json(),
        },
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

    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/monitor/{model_id}")
def settings_update_monitor(
    request: Request,
    model_id: str,
    is_enabled: str | None = Form(default=None),
    baseline_days: int = Form(...),
    current_days: int = Form(...),
    num_bins: int = Form(...),
    min_samples: int = Form(...),
    warn_threshold: float = Form(...),
    critical_threshold: float = Form(...),
):
    payload = {
        "is_enabled": bool(is_enabled),
        "baseline_days": baseline_days,
        "current_days": current_days,
        "num_bins": num_bins,
        "min_samples": min_samples,
        "warn_threshold": warn_threshold,
        "critical_threshold": critical_threshold,
    }
    resp = requests.post(
        f"{API_BASE}/v1/ui/models/{model_id}/monitor",
        json=payload,
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/slack")
def settings_update_slack(
    request: Request,
    slack_webhook_url: str = Form(default=""),
    is_enabled: str | None = Form(default=None),
):
    payload = {
        "slack_webhook_url": slack_webhook_url,
        "is_enabled": bool(is_enabled),
    }
    resp = requests.post(
        f"{API_BASE}/v1/ui/settings/slack",
        json=payload,
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse("/settings", status_code=303)

@app.get("/", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@app.get("/signup", response_class=HTMLResponse)
def signup(request: Request):
    return templates.TemplateResponse(
        "signup.html",
        {"request": request, "error": None},
    )

@app.post("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("sentryml_session")
    return resp

@app.post("/auth")
def auth(request: Request, email: str = Form(...), password: str = Form(...)):
    resp = requests.post(
        f"{API_BASE}/v1/auth/login",
        json={"email": email, "password": password},
        timeout=5,
    )
    if resp.status_code != 200:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password.",
            },
            status_code=401,
        )

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


@app.post("/signup")
def signup_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    resp = requests.post(
        f"{API_BASE}/v1/auth/signup",
        json={"email": email, "password": password},
        timeout=5,
    )
    if resp.status_code != 200:
        msg = "Email already registered. Please sign in."
        try:
            detail = resp.json().get("detail")
            if isinstance(detail, list):
                msg = "Please enter a valid email address."
            elif isinstance(detail, str) and detail:
                msg = detail
        except Exception:
            pass
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": msg,
            },
            status_code=400,
        )

    session_cookie = resp.cookies.get("sentryml_session")
    if not session_cookie:
        return RedirectResponse("/signup", status_code=303)

    out = RedirectResponse("/dashboard?onboarding=1", status_code=303)
    out.set_cookie(
        key="sentryml_session",
        value=session_cookie,
        httponly=True,
        samesite="lax",
    )
    return out

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, onboarding: int = 0):
    # Redirect to login if not authenticated
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(f"{API_BASE}/v1/ui/dashboard", cookies=api_cookie_jar(request), timeout=5)
    resp.raise_for_status()
    data = resp.json()
    keys_resp = requests.get(
        f"{API_BASE}/v1/api-keys",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    keys_resp.raise_for_status()
    has_keys = len(keys_resp.json()) > 0
    has_models = len(data.get("models", [])) > 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "onboarding": bool(onboarding),
            "has_keys": has_keys,
            "has_models": has_models,
            "stats": _get_stats(request),
            "open_incidents": data.get("open_incidents", []),
            "latest_drift": data.get("latest_drift", []),
            "models": data.get("models", []),
            "show_model_detected": bool(data.get("has_unmonitored")),
        },
    )

@app.get("/models/{model_id}", response_class=HTMLResponse)
def model_detail(
    request: Request,
    model_id: str,
    pred_limit: int = 200,
    drift_limit: int = 50,
):
    if not request.cookies.get("sentryml_session"):
        return RedirectResponse("/", status_code=302)

    resp = requests.get(
        f"{API_BASE}/v1/ui/models/{model_id}",
        params={"pred_limit": pred_limit, "drift_limit": drift_limit},
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    return templates.TemplateResponse(
        "model_detail.html",
        {
            "request": request,
            "stats": _get_stats(request),
            "model_id": data["model_id"],
            "drift": data["drift"],
            "incidents": data["incidents"],
            "pred_limit": pred_limit,
            "drift_limit": drift_limit,
            "recent_predictions": data.get("recent_predictions", []),
            "monitor": data.get("monitor"),
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


@app.post("/models/{model_id}/delete")
def ui_delete_model(request: Request, model_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/models/{model_id}/delete",
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
            "stats": _get_stats(request),
            "incident": data["incident"],
            "events": data.get("events", []),
            "drift": data.get("drift"),
            "monitor": data.get("monitor"),
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


@app.post("/incidents/{incident_id}/unack")
def ui_incident_unack(request: Request, incident_id: str):
    resp = requests.post(
        f"{API_BASE}/v1/ui/incidents/{incident_id}/unack",
        cookies=api_cookie_jar(request),
        timeout=5,
    )
    resp.raise_for_status()
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)
