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


class ModelItem(SQLModel):
    model_id: str
    event_count: int
    first_seen_at: datetime
    last_seen_at: datetime

    is_enabled: bool
    baseline_days: int
    current_days: int
    num_bins: int
    min_samples: int
    warn_threshold: float
    critical_threshold: float
    status: Optional[str] = None


class MonitorUpdate(SQLModel):
    is_enabled: Optional[bool] = None
    baseline_days: Optional[int] = None
    current_days: Optional[int] = None
    num_bins: Optional[int] = None
    min_samples: Optional[int] = None
    warn_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


class SlackRouteIn(SQLModel):
    slack_webhook_url: str
    is_enabled: bool = True

