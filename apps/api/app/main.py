from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Session

from app.db import engine, get_session
from app.models import PredictionEvent, PredictionEventIn



@asynccontextmanager
async def lifespane(app: FastAPI):
    # start up
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="SentryML API",
    lifespan=lifespane
)

@app.post("/v1/events/predication", response_model=PredictionEvent)
def ingest_predication(
    payload: PredictionEventIn,
    session: Session = Depends(get_session)
):
    event = PredictionEvent.model_validate(payload)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
