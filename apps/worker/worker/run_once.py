from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Tuple

from sqlmodel import Session, select

from sentryml_core.db import engine
from sentryml_core.models import (
    MonitorConfig,
    PredictionEvent,
    DriftResult,
    Incident,
    AlertRoute,
)
from sentryml_core.drift import psi_quantile
from worker.worker.slack import send_slack 
from worker.worker.incident_fsm import incident_fsm


# -------------------------
# Utilities
# -------------------------

def utcnow() -> datetime:
    """Return naive UTC datetime (matches DB storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fetch_scores(
    session: Session,
    org_id,
    model_id: str,
    start: datetime,
    end: datetime,
) -> list[float]:
    rows = session.exec(
        select(PredictionEvent.score).where(
            (PredictionEvent.org_id == org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= start)
            & (PredictionEvent.event_time < end)
        )
    ).all()
    return list(rows)


def severity_for_psi(
    psi_score: float,
    warn: float,
    critical: float,
) -> Literal["ok", "warn", "critical"]:
    if psi_score >= critical:
        return "critical"
    if psi_score >= warn:
        return "warn"
    return "ok"


# -------------------------
# Slack formatter
# -------------------------

def format_slack_message(
    action: str,
    model_id: str,
    severity: str,
    psi_score: float,
    baseline_n: int,
    current_n: int,
    baseline_start: datetime,
    baseline_end: datetime,
    current_start: datetime,
    current_end: datetime,
) -> str:
    emoji = {
        "open": "🚨",
        "escalate": "🔥",
        "downgrade": "🟡",
        "resolve": "✅",
    }.get(action, "ℹ️")

    return (
        f"{emoji} SentryML incident *{action.upper()}*\n"
        f"Model: `{model_id}`\n"
        f"Severity: *{severity.upper()}* (PSI={psi_score:.4f})\n\n"
        f"*Baseline*: {baseline_start} → {baseline_end} (n={baseline_n})\n"
        f"*Current*:  {current_start} → {current_end} (n={current_n})"
    )


# -------------------------
# MAIN
# -------------------------

def main() -> int:
    now = utcnow()

    with Session(engine) as session:
        # Load enabled alert routes (Slack, etc.)
        routes = session.exec(
            select(AlertRoute).where(AlertRoute.is_enabled == True)  # noqa: E712
        ).all()
        route_map = {r.org_id: r for r in routes}

        # Load enabled monitors
        monitors = session.exec(
            select(MonitorConfig).where(MonitorConfig.is_enabled == True)  # noqa: E712
        ).all()

        for m in monitors:
            # -------------------------
            # Time windows
            # -------------------------
            current_end = now
            current_start = now - timedelta(days=m.current_days)

            baseline_end = current_start
            baseline_start = baseline_end - timedelta(days=m.baseline_days)

            # -------------------------
            # Fetch scores
            # -------------------------
            baseline_scores = fetch_scores(
                session,
                m.org_id,
                m.model_id,
                baseline_start,
                baseline_end,
            )
            current_scores = fetch_scores(
                session,
                m.org_id,
                m.model_id,
                current_start,
                current_end,
            )

            if (
                len(baseline_scores) < m.min_samples
                or len(current_scores) < m.min_samples
            ):
                continue

            # -------------------------
            # Compute PSI
            # -------------------------
            psi_score = psi_quantile(
                baseline_scores,
                current_scores,
                num_bins=m.num_bins,
            )

            drift = DriftResult(
                org_id=m.org_id,
                model_id=m.model_id,
                computed_at=now,
                baseline_start=baseline_start,
                baseline_end=baseline_end,
                current_start=current_start,
                current_end=current_end,
                psi_score=psi_score,
                baseline_n=len(baseline_scores),
                current_n=len(current_scores),
            )
            session.add(drift)

            # -------------------------
            # Incident logic (FSM)
            # -------------------------
            new_severity = severity_for_psi(
                psi_score,
                m.warn_threshold,
                m.critical_threshold,
            )

            open_incident = session.exec(
                select(Incident).where(
                    (Incident.org_id == m.org_id)
                    & (Incident.model_id == m.model_id)
                    & (Incident.metric == "psi_score")
                    & (Incident.closed_at == None)
                )
            ).first()

            current_state: State = (
                "none" if open_incident is None else open_incident.severity
            )

            next_state, action = incident_fsm(
                current_state,
                new_severity,
            )

            # -------------------------
            # Apply DB changes
            # -------------------------
            if action == "open":
                incident = Incident(
                    org_id=m.org_id,
                    model_id=m.model_id,
                    metric="psi_score",
                    severity=next_state,
                    value=psi_score,
                    opened_at=now,
                    closed_at=None,
                    drift_id=drift.drift_id,
                )
                session.add(incident)

            elif action in {"escalate", "downgrade", "update"}:
                open_incident.severity = next_state
                open_incident.value = psi_score
                open_incident.drift_id = drift.drift_id
                session.add(open_incident)

            elif action == "resolve":
                open_incident.closed_at = now
                session.add(open_incident)

            # -------------------------
            # Slack notification
            # -------------------------
            if action in {"open", "escalate", "downgrade", "resolve"}:
                route = route_map.get(m.org_id)
                if route:
                    send_slack(
                        route.webhook_url,
                        format_slack_message(
                            action=action,
                            model_id=m.model_id,
                            severity=next_state,
                            psi_score=psi_score,
                            baseline_n=len(baseline_scores),
                            current_n=len(current_scores),
                            baseline_start=baseline_start,
                            baseline_end=baseline_end,
                            current_start=current_start,
                            current_end=current_end,
                        ),
                    )

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
