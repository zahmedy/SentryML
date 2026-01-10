from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Session

from app.db import engine, get_session
from app.models import PredictionEvent
from app.schemas import PredictionEventIn
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
    session.commit()
    session.refresh(event)
    return event
