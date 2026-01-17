from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import (
    AlertRoute,
    DriftResult,
    Incident,
    IncidentEvent,
    ModelRegistry,
    MonitorConfig,
    User,
)
from apps.sentryml_core.schemas import SlackRouteIn
from apps.api.app.deps_auth import get_current_user

router = APIRouter(prefix="/v1/ui", tags=["ui"])


@router.get("/settings")
def ui_settings(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    models = session.exec(
        select(ModelRegistry).where(ModelRegistry.org_id == user.org_id)
    ).all()
    configs = session.exec(
        select(MonitorConfig).where(MonitorConfig.org_id == user.org_id)
    ).all()
    cfg_map = {c.model_id: c for c in configs}

    monitors = []
    for m in models:
        cfg = cfg_map.get(m.model_id)
        monitors.append(
            {
                "model_id": m.model_id,
                "event_count": m.event_count,
                "last_seen_at": m.last_seen_at,
                "is_enabled": cfg.is_enabled if cfg else False,
                "baseline_days": cfg.baseline_days if cfg else 1,
                "current_days": cfg.current_days if cfg else 1,
                "num_bins": cfg.num_bins if cfg else 10,
                "min_samples": cfg.min_samples if cfg else 3,
                "warn_threshold": cfg.warn_threshold if cfg else 0.1,
                "critical_threshold": cfg.critical_threshold if cfg else 0.2,
            }
        )

    slack = session.exec(
        select(AlertRoute).where(AlertRoute.org_id == user.org_id)
    ).first()
    slack_data = None
    if slack:
        slack_data = {
            "slack_webhook_url": slack.slack_webhook_url,
            "is_enabled": slack.is_enabled,
        }

    return {"monitors": monitors, "slack": slack_data}


@router.post("/settings/slack")
def ui_update_slack(
    payload: SlackRouteIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    route = session.exec(
        select(AlertRoute).where(AlertRoute.org_id == user.org_id)
    ).first()
    if not route:
        route = AlertRoute(
            org_id=user.org_id,
            slack_webhook_url=payload.slack_webhook_url,
            is_enabled=payload.is_enabled,
        )
    else:
        route.slack_webhook_url = payload.slack_webhook_url
        route.is_enabled = payload.is_enabled

    session.add(route)
    session.commit()
    return {"ok": True}


@router.get("/stats")
def ui_stats(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    monitored_count = session.exec(
        select(func.count()).select_from(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.is_enabled == True)  # noqa: E712
        )
    ).one()

    open_incidents = session.exec(
        select(func.count()).select_from(Incident).where(
            (Incident.org_id == user.org_id) & (Incident.closed_at == None)  # noqa: E711
        )
    ).one()

    last_worker_run = session.exec(
        select(func.max(DriftResult.computed_at)).where(DriftResult.org_id == user.org_id)
    ).one()

    last_alert_at = session.exec(
        select(func.max(IncidentEvent.ts)).where(IncidentEvent.org_id == user.org_id)
    ).one()

    max_window_days = session.exec(
        select(func.max(MonitorConfig.current_days)).where(MonitorConfig.org_id == user.org_id)
    ).one()
    max_window_days = max_window_days or 1

    status = "unknown"
    if last_worker_run:
        status = "ok"
        if last_worker_run < datetime.utcnow() - timedelta(days=max_window_days * 2):
            status = "stale"

    return {
        "worker_status": status,
        "last_worker_run": last_worker_run,
        "monitored_models": monitored_count or 0,
        "open_incidents": open_incidents or 0,
        "last_alert_at": last_alert_at,
    }
