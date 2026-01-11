from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from sentryml_core.db import engine
from sentryml_core.models import MonitorConfig, PredictionEvent, DriftResult
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


def main() -> int:
    now = utcnow()

    with Session(engine) as session:
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

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
