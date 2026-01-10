from datetime import datetime, timezone
from pydantic import field_validator
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from sqlalchemy import Index


class PredictionEvent(SQLModel, table=False):
    __tablename__ = "prediction_events"
    __table_args__ = (
        Index("ix_pred_model_time", "model_id", "event_time")
    )

    event_id: UUID = Field(default_factory=uuid4, primary_key=True)

    model_id: str = Field(index=True)
    entity_id: str = Field(index=True)

    score: float
    prediction: Optional[str] = None

    event_time: datetime = Field(index=True)
    ingested_time: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )

class PredictionEventIn(SQLModel):
    model_id: str
    entity_id: str
    score: float
    prediction: Optional[str] = None
    event_time: datetime

    @field_validator("event_time")
    @classmethod
    def clamp_future_event_time(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > now:
            return now
        return v