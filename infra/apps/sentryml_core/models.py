from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from sqlalchemy import Index



class Org(SQLModel, table=True):
    __tablename__ = "orgs"
    org_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str


class User(SQLModel, table=True):
    __tablename__ = "users"
    
    user_id: UUID = Field(index=True, primary_key=True)
    
    org_id: UUID = Field(index=True)
    
    email: str = Field(index=True, unique=True)
    password_hash: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    
    key_id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    org_id: UUID = Field(index=True)
    user_id: UUID = Field(index=True)
    
    name: Optional[str] = None
    
    prefix: str = Field(index=True)
    
    key_hash: str = Field(index=True, unique=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    revoked_at: Optional[datetime] = Field(default=None, index=True)
    last_used_at: Optional[datetime] = Field(default=None, index=True)


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

    baseline_days: int = Field(default=1)
    current_days: int = Field(default=1)
    num_bins: int = Field(default=10)
    min_samples: int = Field(default=3)

    warn_threshold: float = Field(default=0.1)
    critical_threshold: float = Field(default=0.2)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DriftResult(SQLModel, table=True):
    __tablename__ = "drift_results"

    drift_id: UUID = Field(default_factory=uuid4, primary_key=True)

    org_id: UUID = Field(index=True)
    model_id: str = Field(index=True)

    computed_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    baseline_start: datetime
    baseline_end: datetime
    current_start: datetime
    current_end: datetime

    psi_score: float
    baseline_n: int
    current_n: int


class IncidentState(str, Enum):
    OPEN = "open"
    ACK = "ack"
    RESOLVED = "resolved"
    CLOSED = "closed"

class IncidentSeverity(str, Enum):
    NONE = "NONE"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    incident_id: UUID = Field(default_factory=uuid4, primary_key=True)

    org_id: UUID = Field(index=True)
    model_id: str = Field(index=True)

    metric: str = Field(default="psi_score", index=True)
    state: IncidentState = Field(default=IncidentState.OPEN, index=True)
    severity: IncidentSeverity = Field(default=IncidentSeverity.NONE ,index=True)  # keep for now, or replace later
    acknowledged_by_user_id: Optional[UUID] = Field(index=True)
    value: float

    opened_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    acknowledged_at: Optional[datetime] = Field(default=None, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    closed_at: Optional[datetime] = Field(default=None, index=True)

    drift_id: Optional[UUID] = None


class IncidentEventAction(str, Enum):
    NOOP = "noop"
    OPEN = "open"
    ESCALATE = "escalate"
    DOWNGRADE = "downgrade"
    UPDATE = "update"
    ACK = "ack"
    RESOLVE = "resolve"
    CLOSE = "close"


class IncidentEventActor(str, Enum):
    WORKER = "worker"
    USER = "user"


class IncidentEvent(SQLModel, table=True):
    __tablename__ = "incident_events"

    event_id: UUID = Field(default_factory=uuid4, primary_key=True)

    incident_id: UUID = Field(index=True)
    org_id: UUID = Field(index=True)
    model_id: str = Field(index=True)
    metric: str = Field(index=True)

    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    action: str = Field(index=True)

    prev_state: str = Field(index=True)
    new_state: str = Field(index=True)

    prev_severity: Optional[str] = Field(default=None, index=True)
    new_severity: Optional[str] = Field(default=None, index=True)
    value: Optional[float] = None

    actor: str = Field(index=True)
    actor_user_id: Optional[UUID] = Field(default=None, index=True)


class AlertRoute(SQLModel, table=True):
    __tablename__ = "alert_routes"

    route_id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, unique=True)   # 1 route per org (MVP)

    kind: str = Field(default="slack")              # only slack for now
    slack_webhook_url: str

    is_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SessionToken(SQLModel, table=True):
    __tablename__ = "sessions"

    session_id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30),
        index=True,
    )
    revoked_at: Optional[datetime] = Field(default=None, index=True)
