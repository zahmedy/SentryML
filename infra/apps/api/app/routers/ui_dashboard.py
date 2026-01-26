from datetime import datetime
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy import func

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import (
    ModelRegistry,
    DriftResult,
    Incident,
    User,
    MonitorConfig,
    PredictionEvent,
)
from apps.api.app.deps_auth import get_current_user

router = APIRouter(prefix="/v1/ui", tags=["ui"])


def psi_to_severity(psi: float, warn: float, critical: float) -> str:
    if psi < warn:
        return "ok"
    if psi < critical:
        return "warn"
    return "critical"

INC_RANK = {"critical": 2, "warn": 1, None: 0}
DRIFT_RANK = {"critical": 3, "warn": 2, "ok": 1, None: 0}

def sort_key(r):
    inc_rank = INC_RANK.get(r["open_incident_status"], 0)
    drift_rank = DRIFT_RANK.get(r["drift_severity"], 0)
    last_seen_at = r.get("last_seen_at") or datetime.min
    return (-inc_rank, -drift_rank, last_seen_at)

@router.get("/dashboard")
def ui_dashboard(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 100,
):
    models = session.exec(
        select(ModelRegistry)
        .where(
            (ModelRegistry.org_id == user.org_id)
            & (ModelRegistry.is_deleted == False)  # noqa: E712
        )
        .order_by(ModelRegistry.last_seen_at.desc())
        .limit(limit)
    ).all()

    open_incidents = session.exec(
        select(Incident)
        .where((Incident.org_id == user.org_id) & (Incident.closed_at == None))
        .order_by(Incident.opened_at.desc())
    ).all()

    drift_rows = session.exec(
        select(DriftResult)
        .where(DriftResult.org_id == user.org_id)
        .order_by(DriftResult.computed_at.desc())
    ).all()

    configs = session.exec(
        select(MonitorConfig).where(MonitorConfig.org_id == user.org_id)
    ).all()
    config_by_model = {c.model_id: c for c in configs}

    pred_rows = session.exec(
        select(PredictionEvent.model_id, func.count())
        .where(PredictionEvent.org_id == user.org_id)
        .group_by(PredictionEvent.model_id)
    ).all()
    pred_count_by_model = {m_id: cnt for m_id, cnt in pred_rows}

    # index: model_id -> open incident (at most one)
    open_by_model = {}
    for inc in open_incidents:
        if inc.model_id not in open_by_model:
            open_by_model[inc.model_id] = inc

    # index: model_id -> latest drift row
    latest_drift_by_model = {}
    for d in drift_rows:
        if d.model_id not in latest_drift_by_model:
            latest_drift_by_model[d.model_id] = d

    out = []
    for m in models:
        d = latest_drift_by_model.get(m.model_id)
        inc = open_by_model.get(m.model_id)
        cfg = config_by_model.get(m.model_id)
        warn = cfg.warn_threshold if cfg else 0.1
        critical = cfg.critical_threshold if cfg else 0.2
        if critical < warn:
            warn, critical = critical, warn

        out.append({
            "model_id": m.model_id,
            "first_seen_at": m.first_seen_at,
            "last_seen_at": m.last_seen_at,
            "event_count": getattr(m, "event_count", None),
            "prediction_count": pred_count_by_model.get(m.model_id, 0),
            "monitor_enabled": cfg.is_enabled if cfg else False,

            "last_drift_at": d.computed_at if d else None,
            "last_psi_score": d.psi_score if d else None,
            "drift_severity": (
                psi_to_severity(d.psi_score, warn, critical) if d and d.psi_score is not None else None
            ),

            "open_incident_id": str(inc.incident_id) if inc else None,
            "open_incident_status": inc.state.value if inc else None,
            "open_incident_severity": inc.severity.value.lower() if inc else None,
            "open_incident_opened_at": inc.opened_at if inc else None,
            "open_incident_value": inc.value if inc else None,
        })
    out.sort(key=sort_key)
    has_unmonitored = any(not r.get("monitor_enabled") for r in out)

    return {"models": out, "has_unmonitored": has_unmonitored}
