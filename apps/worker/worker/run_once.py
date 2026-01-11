from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from sentryml_core.db import engine
from sentryml_core.models import (MonitorConfig, PredictionEvent, 
                                  DriftResult, Incident, AlertRoute)
from sentryml_core.drift import psi_quantile


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # store naive UTC to match your DB


def fetch_scores(session: Session, org_id, model_id: str, start: datetime, end: datetime) -> list[float]:
    rows = session.exec(
        select(PredictionEvent.score).where(
            (PredictionEvent.org_id == org_id)
            & (PredictionEvent.model_id == model_id)
            & (PredictionEvent.event_time >= start)
            & (PredictionEvent.event_time < end)
        )
    ).all()
    return list(rows)

def severity_for_psi(psi_score: float, warn: float, critical: float) -> str:
    if psi_score >= critical:
        return "critical"
    if psi_score >= warn:
        return "warn"
    return "ok"

def format_incident_text(action: str, model_id: str, severity: str, psi_score: float,
                         baseline_n: int, current_n: int,
                         baseline_start, baseline_end, current_start, current_end) -> str:
    emoji = {"opened": "🚨", "escalated": "🔥", "resolved": "✅"}.get(action, "ℹ️")
    return (
        f"{emoji} SentryML incident {action}: {model_id} drift **{severity.upper()}** (PSI={psi_score:.4f})\n"
        f"Baseline: {baseline_start} → {baseline_end} (n={baseline_n})\n"
        f"Current:  {current_start} → {current_end} (n={current_n})"
    )

def main() -> int:
    now = utcnow()

    with Session(engine) as session:
        routes = session.exec(select(AlertRoute).where(AlertRoute.is_enabled == True)).all()  # noqa: E712
        route_map = {r.org_id: r for r in routes}
        monitors = session.exec(
            select(MonitorConfig).where(MonitorConfig.is_enabled == True)  # noqa: E712
        ).all()

        for m in monitors:
            current_end = now
            current_start = now - timedelta(days=m.current_days)

            baseline_end = current_start
            baseline_start = baseline_end - timedelta(days=m.baseline_days)

            baseline_scores = fetch_scores(session, m.org_id, m.model_id, baseline_start, baseline_end)
            current_scores = fetch_scores(session, m.org_id, m.model_id, current_start, current_end)

            if len(baseline_scores) < m.min_samples or len(current_scores) < m.min_samples:
                continue

            psi_score = psi_quantile(baseline_scores, current_scores, num_bins=m.num_bins)

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

            sev = severity_for_psi(psi_score, m.warn_threshold, m.critical_threshold)

            open_incident = session.exec(
                select(Incident).where(
                    (Incident.org_id == m.org_id)
                    & (Incident.model_id == m.model_id)
                    & (Incident.metric == "psi_score")
                    & (Incident.closed_at == None)
                )
            ).first()

            now = utcnow()

            if sev == "ok":
                # close if one is open
                if open_incident:
                    open_incident.closed_at = now
                    session.add(open_incident)
            else:
                # warn/critical
                if open_incident is None:
                    session.add(Incident(
                        org_id=m.org_id,
                        model_id=m.model_id,
                        metric="psi_score",
                        severity=sev,
                        value=psi_score,
                        opened_at=now,
                        closed_at=None,
                        drift_id=drift.drift_id,
                    ))
                else:
                    # if it escalates (warn -> critical), update severity/value and keep it open
                    if open_incident.severity != sev:
                        open_incident.severity = sev
                    open_incident.value = psi_score
                    open_incident.drift_id = drift.drift_id
                    session.add(open_incident)

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
