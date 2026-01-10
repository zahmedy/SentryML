from datetime import datetime, timezone
from typing import Optional
from pydantic import field_validator
from sqlmodel import SQLModel

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
        return min(v, now)
