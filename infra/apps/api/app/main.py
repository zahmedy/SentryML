from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Session, select
from datetime import datetime
from typing import List, Dict

from apps.sentryml_core.db import engine, get_session
from apps.sentryml_core.models import (PredictionEvent, ModelRegistry,
                                  MonitorConfig, DriftResult,
                                  Incident, AlertRoute, User, SessionToken)
from apps.sentryml_core.schemas import (PredictionEventIn, ModelItem,
                                   MonitorUpdate, SlackRouteIn)
from apps.api.app.security import (get_org_id, verify_password)
from apps.api.app.routers.auth import router as auth_router
from apps.api.app.routers.api_keys import router as api_keys_router
from apps.api.app.routers.ui_dashboard import router as ui_dashboard_router
from apps.api.app.routers.ui_models import router as ui_models_router
from apps.api.app.routers.ui_incidents import router as ui_incidents_router
from apps.api.app.routers.ui_settings import router as ui_settings_router



@asynccontextmanager
async def lifespane(app: FastAPI):
    # start up
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="SentryML API",
    lifespan=lifespane
)

app.include_router(auth_router)
app.include_router(api_keys_router)
app.include_router(ui_dashboard_router)
app.include_router(ui_models_router)
app.include_router(ui_incidents_router)
app.include_router(ui_settings_router)


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
        select(ModelRegistry)
        .where(ModelRegistry.org_id == org_id)
    ).all()

    open_incidents = session.exec(
        select(Incident)
        .where(
            (Incident.org_id == org_id) &
            (Incident.closed_at == None)
        )
    ).all()

    incident_map = {i.model_id: i for i in open_incidents}

    configs = session.exec(
        select(MonitorConfig)
        .where(MonitorConfig.org_id == org_id)
    ).all()

    cfg_map = {c.model_id: c for c in configs}

    items: List[ModelItem] = []

    for m in models:
        cfg = cfg_map.get(m.model_id)
        incident = incident_map.get(m.model_id)

        status = "ok"
        if incident:
            status = incident.severity  # warn | critical

        items.append(
            ModelItem(
                model_id=m.model_id,
                event_count=m.event_count,
                first_seen_at=m.first_seen_at,
                last_seen_at=m.last_seen_at,
                is_enabled=cfg.is_enabled if cfg else False,
                baseline_days=cfg.baseline_days if cfg else 14,
                current_days=cfg.current_days if cfg else 7,
                num_bins=cfg.num_bins if cfg else 10,
                min_samples=cfg.min_samples if cfg else 500,
                warn_threshold=cfg.warn_threshold if cfg else 0.1,
                critical_threshold=cfg.critical_threshold if cfg else 0.2,
                status=status,
            )
        )

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


@app.put("/v1/alerts/slack", response_model=AlertRoute)
def upsert_slack_route(
    payload: SlackRouteIn,
    org_id = Depends(get_org_id),
    session: Session = Depends(get_session),
):
    route = session.exec(
        select(AlertRoute).where(AlertRoute.org_id == org_id)
    ).first()

    now = datetime.utcnow()
    if route is None:
        route = AlertRoute(
            org_id=org_id,
            kind="slack",
            slack_webhook_url=payload.slack_webhook_url,
            is_enabled=payload.is_enabled,
            created_at=now,
            updated_at=now,
        )
        session.add(route)
    else:
        route.slack_webhook_url = payload.slack_webhook_url
        route.is_enabled = payload.is_enabled
        route.updated_at = now
    
    session.add(route)
    session.commit()
    session.refresh(route)
    return route
