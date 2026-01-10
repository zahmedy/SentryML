from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

from app.db import engine
from app.models import PredictionEvent



@asynccontextmanager
async def lifespane(app: FastAPI):
    # start up
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="SentryML API",
    lifespan=lifespane
)