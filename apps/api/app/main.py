from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Session, select
from datetime import datetime
from typing import List, Dict, Tuple

from app.db import engine, get_session
from app.models import PredictionEvent, ModelRegistry, MonitorConfig
from app.schemas import PredictionEventIn, ModelItem
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
