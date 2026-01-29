from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlmodel import Session, select

from apps.sentryml_core.db import engine
from apps.sentryml_core.models import (
    MonitorConfig,
    PredictionEvent,
    DriftResult,
    Incident,
    AlertRoute,
    IncidentSeverity,
    IncidentState,
    IncidentEvent,
    IncidentEventActor,
)
from apps.sentryml_core.drift import psi_quantile
from apps.worker.worker.slack import send_slack
from apps.worker.worker.incident_fsm import incident_fsm


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

def normalize_scores(scores: list[float | None]) -> list[float]:
    return [float(s) for s in scores if s is not None]


def has_enough_samples(scores: list[float], min_samples: int) -> bool:
    return len(scores) >= min_samples


def eligible_for_monitoring(
    baseline_scores: list[float | None],
    current_scores: list[float | None],
    min_samples: int,
) -> tuple[list[float], list[float]]:
    baseline = normalize_scores(baseline_scores)
    current = normalize_scores(current_scores)
    if not has_enough_samples(baseline, min_samples):
        return [], []
    if not has_enough_samples(current, min_samples):
        return [], []
    return baseline, current


def severity_for_psi(
    psi_score: float,
    warn: float,
    critical: float,
) -> IncidentSeverity:
    if psi_score >= critical:
        return IncidentSeverity.CRITICAL
    if psi_score >= warn:
        return IncidentSeverity.WARN
    return IncidentSeverity.NONE


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
    incident_id: str | None = None,
) -> str:
    severity_norm = (severity or "").lower()
    if action == "escalate":
        ui_base = os.getenv("UI_BASE_URL", "http://localhost:9000")
        incident_link = f"{ui_base}/incidents/{incident_id}" if incident_id else ""
        return (
            "🚨 Data drift severity increased\n\n"
            f"The distribution shift for {model_id} has worsened and crossed the critical threshold.\n\n"
            f"View incident details: {incident_link}"
        )

    if action == "resolve":
        title = "✅ Data drift resolved"
        sev_line = f"Incoming data for {model_id} has returned to its baseline distribution."
    else:
        emoji = "🚨" if severity_norm == "critical" else "⚠️"
        title = f"{emoji} Data drift detected ({severity_norm})"
        sev_line = "The distribution shift exceeds the warning threshold."
        if severity_norm == "critical":
            sev_line = "The distribution shift exceeds the critical threshold and may impact model behavior."

    ui_base = os.getenv("UI_BASE_URL", "http://localhost:9000")
    incident_link = f"{ui_base}/incidents/{incident_id}" if incident_id else ""

    current_range = f"{current_start:%b %d} → {current_end:%b %d}"

    body = (
        f"{title}\n\n"
        f"Incoming prediction data for {model_id} has drifted from its baseline distribution.\n"
        f"{sev_line}\n\n"
        f"• Model: {model_id}\n"
        f"• Severity: {severity_norm}\n"
        f"• PSI: {psi_score:.2f}\n"
        f"• Current window: {current_range}\n\n"
        "SentryML will continue monitoring this model on the next scheduled run.\n"
            "The incident will resolve automatically if the data returns to normal.\n\n"
            f"🔍 View incident details\n{incident_link}"
    )
    if action == "resolve":
        resolved_at = datetime.now(timezone.utc).strftime("%b %d, %H:%M UTC")
        body = (
            f"{title}\n\n"
            f"{sev_line}\n"
            "This incident has been resolved automatically.\n\n"
            f"• Final PSI: {psi_score:.2f}\n"
            f"• Resolved at: {resolved_at}\n\n"
            f"🔍 View incident timeline\n{incident_link}"
        )
    return body


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

            baseline_scores, current_scores = eligible_for_monitoring(
                baseline_scores,
                current_scores,
                m.min_samples,
            )
            if not baseline_scores or not current_scores:
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

            current_severity: IncidentSeverity = (
                IncidentSeverity.NONE if open_incident is None else open_incident.severity
            )

            next_severity, action = incident_fsm(
                current_severity,
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
                    severity=next_severity,
                    value=psi_score,
                    opened_at=now,
                    closed_at=None,
                    drift_id=drift.drift_id,
                    state=IncidentState.OPEN,
                )
                session.add(incident)
                session.flush()
                session.add(
                    IncidentEvent(
                        incident_id=incident.incident_id,
                        org_id=m.org_id,
                        model_id=m.model_id,
                        metric="psi_score",
                        ts=now,
                        action="open",
                        prev_state="none",
                        new_state=incident.state.value,
                        prev_severity=IncidentSeverity.NONE.value,
                        new_severity=incident.severity.value,
                        value=psi_score,
                        actor=IncidentEventActor.WORKER.value,
                        actor_user_id=None,
                    )
                )

            elif action in {"escalate", "downgrade", "update"}:
                prev_state = open_incident.state.value
                prev_sev = open_incident.severity.value
                prev_value = open_incident.value
                open_incident.severity = next_severity
                open_incident.value = psi_score
                open_incident.drift_id = drift.drift_id
                session.add(open_incident)
                changed = (prev_sev != next_severity.value) or (abs(prev_value - psi_score) > 1e-6)
                if changed:
                    session.add(
                        IncidentEvent(
                            incident_id=open_incident.incident_id,
                            org_id=m.org_id,
                            model_id=m.model_id,
                            metric="psi_score",
                            ts=now,
                            action=action,
                            prev_state=prev_state,
                            new_state=open_incident.state.value,
                            prev_severity=prev_sev,
                            new_severity=open_incident.severity.value,
                            value=psi_score,
                            actor=IncidentEventActor.WORKER.value,
                            actor_user_id=None,
                        )
                    )

            elif action == "resolve":
                prev_state = open_incident.state.value
                prev_sev = open_incident.severity.value
                # Auto-resolve and close when PSI returns to normal.
                open_incident.state = IncidentState.CLOSED
                open_incident.resolved_at = now
                open_incident.closed_at = now
                session.add(open_incident)
                session.add(
                    IncidentEvent(
                        incident_id=open_incident.incident_id,
                        org_id=m.org_id,
                        model_id=m.model_id,
                        metric="psi_score",
                        ts=now,
                        action="resolve",
                        prev_state=prev_state,
                        new_state=open_incident.state.value,
                        prev_severity=prev_sev,
                        new_severity=open_incident.severity.value,
                        value=psi_score,
                        actor=IncidentEventActor.WORKER.value,
                        actor_user_id=None,
                    )
                )

            # -------------------------
            # Slack notification
            # -------------------------
            if action in {"open", "escalate", "resolve"}:
                route = route_map.get(m.org_id)
                if route:
                    inc_id = None
                    if action == "open":
                        inc_id = str(incident.incident_id)
                    elif open_incident is not None:
                        inc_id = str(open_incident.incident_id)
                    send_slack(
                        route.slack_webhook_url,
                        format_slack_message(
                            action=action,
                            model_id=m.model_id,
                            severity=next_severity.value,
                            psi_score=psi_score,
                            baseline_n=len(baseline_scores),
                            current_n=len(current_scores),
                            baseline_start=baseline_start,
                            baseline_end=baseline_end,
                            current_start=current_start,
                            current_end=current_end,
                            incident_id=inc_id,
                        ),
                    )

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
