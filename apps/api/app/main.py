from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Session, select
from datetime import datetime
from typing import List, Dict

from sentryml_core.db import engine, get_session
from sentryml_core.models import (PredictionEvent, ModelRegistry, 
                                  MonitorConfig, DriftResult,
                                  Incident)
from sentryml_core.schemas import (PredictionEventIn, ModelItem, 
                                   MonitorUpdate)
from app.security import get_org_id


@asynccontextmanager
async def lifespane(app: FastAPI):
    # start up
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="SentryML API",
    lifespan=lifespane
)


@app.post("/v1/events/prediction", response_model=PredictionEvent)
def ingest_predication(
    payload: PredictionEventIn,
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session)
):
    event = PredictionEvent(
        org_id=org_id,
        model_id=payload.model_id,
        entity_id=payload.entity_id,
        score=payload.score,
        prediction=payload.prediction,
        event_time=payload.event_time
    )
    session.add(event)
    model = session.get(ModelRegistry, (org_id, payload.model_id))
    if model:
        model.last_seen_at = datetime.utcnow()
        model.event_count += 1
    else:
        session.add(ModelRegistry(
            org_id=org_id,
            model_id=payload.model_id,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            event_count=1
        ))
        session.add(MonitorConfig(
            org_id=org_id,
            model_id=payload.model_id
        ))
    session.commit()
    session.refresh(event)
    return event


@app.get("/v1/models", response_model=List[ModelItem])
def list_models(
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session),
):
    models = session.exec(
        select(ModelRegistry).where(ModelRegistry.org_id == org_id)
    ).all()

    configs = session.exec(
        select(MonitorConfig).where(MonitorConfig.org_id == org_id)
    ).all()

    cfg_map: Dict[str, MonitorConfig] = {c.model_id: c for c in configs}

    items: List[ModelItem] = []
    for m in models:
        cfg = cfg_map.get(m.model_id)
        # cfg should exist because you create it on first ingest,
        # but keep a safe fallback anyway.
        if cfg is None:
            items.append(ModelItem(
                model_id=m.model_id,
                event_count=m.event_count,
                first_seen_at=m.first_seen_at,
                last_seen_at=m.last_seen_at,
                is_enabled=False,
                baseline_days=14,
                current_days=7,
                num_bins=10,
                min_samples=500,
                warn_threshold=0.1,
                critical_threshold=0.2
            ))
        else:
            items.append(ModelItem(
                model_id=m.model_id,
                event_count=m.event_count,
                first_seen_at=m.first_seen_at,
                last_seen_at=m.last_seen_at,
                is_enabled=cfg.is_enabled,
                baseline_days=cfg.baseline_days,
                current_days=cfg.current_days,
                num_bins=cfg.num_bins,
                min_samples=cfg.min_samples,
                warn_threshold=cfg.warn_threshold,
                critical_threshold=cfg.critical_threshold,
            ))
    
    # optional: sort newest first
    items.sort(key=lambda x: x.last_seen_at, reverse=True)
    return items


@app.put("/v1/models/{model_id}/monitor", response_model=MonitorConfig)
def update_monitor(
    model_id: str,
    payload: MonitorUpdate,
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session)
):
    cfg = session.exec(
        select(MonitorConfig).where(
            (MonitorConfig.org_id == org_id) & (MonitorConfig.model_id == model_id)
        )
    ).first()

    if cfg is None:
        raise HTTPException(status_code=404, detail="Monitor config not found")
    
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cfg, k, v)

    cfg.updated_at = datetime.utcnow()

    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@app.get("/v1/models/{model_id}/drift", response_model=List[DriftResult])
def get_drift_history(
    model_id: str,
    limit: int = 50,
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(DriftResult)
        .where((DriftResult.org_id == org_id) & (DriftResult.model_id == model_id))
        .order_by(DriftResult.computed_at.desc())
        .limit(limit)
    ).all()
    return rows


@app.get("/v1/incidents", response_model=List[Incident])
def list_incidents(
    status: str = "open",
    limit: int = 50,
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session),
):
    q = select(Incident).where(Incident.org_id == org_id)

    if status == "open":
        q = q.where(Incident.closed_at == None)  # noqa: E711
    elif status == "closed":
        q = q.where(Incident.closed_at != None)  # noqa: E711
    else:
        # any status => no extra filter
        pass

    rows = session.exec(
        q.order_by(Incident.opened_at.desc()).limit(limit)
    ).all()
    return rows