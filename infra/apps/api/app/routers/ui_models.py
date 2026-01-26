from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta
from sqlalchemy import func

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import (
    DriftResult,
    Incident,
    User,
    MonitorConfig,
    PredictionEvent,
    ModelRegistry,
)
from apps.api.app.deps_auth import get_current_user
from apps.sentryml_core.schemas import MonitorUpdate

router = APIRouter(prefix="/v1/ui", tags=["ui"])


@router.get("/models/{model_id}")
def ui_model_detail(
    model_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
    drift_limit: int = 50,
    pred_limit: int = 50,
):
    model = session.get(ModelRegistry, (user.org_id, model_id))
    if not model or model.is_deleted:
        raise HTTPException(status_code=404, detail="Model not found")

    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()
    if not cfg:
        cfg = MonitorConfig(org_id=user.org_id, model_id=model_id)

    current_days = cfg.current_days or 1
    baseline_days = cfg.baseline_days or 7
    current_start = datetime.utcnow() - timedelta(days=current_days)
    baseline_start = datetime.utcnow() - timedelta(days=baseline_days)
    current_total = session.exec(
        select(func.count()).select_from(PredictionEvent).where(
            (PredictionEvent.org_id == user.org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= current_start)
        )
    ).one()
    current_scored = session.exec(
        select(func.count()).select_from(PredictionEvent).where(
            (PredictionEvent.org_id == user.org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= current_start)
            & (PredictionEvent.score != None)  # noqa: E711
        )
    ).one()
    baseline_total = session.exec(
        select(func.count()).select_from(PredictionEvent).where(
            (PredictionEvent.org_id == user.org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= baseline_start)
        )
    ).one()
    baseline_scored = session.exec(
        select(func.count()).select_from(PredictionEvent).where(
            (PredictionEvent.org_id == user.org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= baseline_start)
            & (PredictionEvent.score != None)  # noqa: E711
        )
    ).one()

    drift = session.exec(
        select(DriftResult)
        .where((DriftResult.org_id == user.org_id) & (DriftResult.model_id == model_id))
        .order_by(DriftResult.computed_at.desc())
        .limit(drift_limit)
    ).all()

    incidents = session.exec(
        select(Incident)
        .where((Incident.org_id == user.org_id) & (Incident.model_id == model_id))
        .order_by(Incident.opened_at.desc())
        .limit(limit)
    ).all()

    preds = session.exec(
        select(PredictionEvent)
        .where((PredictionEvent.org_id == user.org_id) & (PredictionEvent.model_id == model_id))
        .order_by(PredictionEvent.event_time.desc())
        .limit(pred_limit)
    ).all()

    pred_count = session.exec(
        select(func.count()).select_from(PredictionEvent).where(
            (PredictionEvent.org_id == user.org_id)
            & (PredictionEvent.model_id == model_id)
        )
    ).one()

    return {
        "model_id": model_id, 
        "drift": drift, 
        "incidents": incidents,
        "recent_predictions": preds,
        "monitor": cfg,
        "model": {
            "event_count": model.event_count,
            "prediction_count": pred_count,
            "last_seen_at": model.last_seen_at,
        },
        "monitor_stats": {
            "current_window_events": current_total,
            "current_window_scored": current_scored,
            "baseline_window_events": baseline_total,
            "baseline_window_scored": baseline_scored,
            "min_samples": cfg.min_samples,
            "current_days": current_days,
            "baseline_days": baseline_days,
        },
    }

@router.post("/models/{model_id}/monitoring/enable")
def enable_monitoring(
    model_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="MonitorConfig not found")

    cfg.is_enabled = True
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/models/{model_id}/monitoring/disable")
def disable_monitoring(
    model_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="MonitorConfig not found")

    cfg.is_enabled = False
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/models/{model_id}/monitor")
def update_monitor(
    model_id: str,
    payload: MonitorUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()
    if not cfg:
        cfg = MonitorConfig(
            org_id=user.org_id,
            model_id=model_id,
        )

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cfg, k, v)

    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/models/{model_id}/delete")
def delete_model(
    model_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    model = session.get(ModelRegistry, (user.org_id, model_id))
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model.is_deleted = True
    model.deleted_at = datetime.utcnow()
    session.add(model)

    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == user.org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()
    if cfg:
        cfg.is_enabled = False
        cfg.updated_at = datetime.utcnow()
        session.add(cfg)

    session.commit()
    return {"ok": True}
