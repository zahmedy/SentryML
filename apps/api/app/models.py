from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class PredictionEvent(SQLModel, table=False):
    __tablename__ = "prediction_events"

    event_id: UUID = Field(default_factory=uuid4, primary_key=True)
    model_id: str = Field(index=True)
    entity_id: str = Field(index=True)

    score: float
    prediction: Optional[str] = None

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )