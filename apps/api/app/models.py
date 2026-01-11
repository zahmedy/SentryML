from datetime import datetime, timezone
from pydantic import field_validator
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from sqlalchemy import Index



class Org(SQLModel, table=True):
    __tablename__ = "orgs"
    org_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    key_id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True)
    key_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None


class PredictionEvent(SQLModel, table=True):
    __tablename__ = "prediction_events"
    __table_args__ = (
        Index("ix_pred_org_model_time", "org_id", "model_id", "event_time"),
    )

    event_id: UUID = Field(default_factory=uuid4, primary_key=True)

    org_id: UUID = Field(index=True)
    model_id: str = Field(index=True)
    entity_id: str = Field(index=True)

    score: float
    prediction: Optional[str] = None

    event_time: datetime = Field(index=True)
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )


class ModelRegistry(SQLModel, table=True):
    __tablename__ = "models"

    org_id: UUID = Field(primary_key=True, index=True)
    model_id: str = Field(primary_key=True, index=True)

    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    event_count: int = Field(default=0)


class MonitorConfig(SQLModel, table=True):
    __tablename__ = "monitor_configs"

    monitor_id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True)
    model_id: str = Field(index=True)

    is_enabled: bool = Field(default=False)

    baseline_days: int = Field(default=14)
    current_days: int = Field(default=7)
    num_bins: int = Field(default=10)
    min_samples: int = Field(default=500)

    warn_threshold: float = Field(default=0.1)
    critical_threshold: float = Field(default=0.2)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)