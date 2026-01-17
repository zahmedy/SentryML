from datetime import datetime
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import (
    Incident,
    IncidentEvent,
    IncidentEventAction,
    IncidentEventActor,
    IncidentState,
    AlertRoute,
    User,
)
from apps.api.app.deps_auth import get_current_user
from apps.worker.worker.slack import send_slack

router = APIRouter(prefix="/v1/ui", tags=["ui"])


@router.get("/incidents/{incident_id}")
def ui_incident_detail(
    incident_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 200,
):
    inc = session.exec(
        select(Incident).where((Incident.incident_id == incident_id) & (Incident.org_id == user.org_id))
    ).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    events = session.exec(
        select(IncidentEvent)
        .where((IncidentEvent.incident_id == incident_id) & (IncidentEvent.org_id == user.org_id))
        .order_by(IncidentEvent.ts.asc())
        .limit(limit)
    ).all()

    return {"incident": inc, "events": events}


@router.post("/incidents/{incident_id}/ack")
def ui_incident_ack(
    incident_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    inc = session.exec(
        select(Incident).where((Incident.incident_id == incident_id) & (Incident.org_id == user.org_id))
    ).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if inc.state != IncidentState.OPEN:
        raise HTTPException(status_code=400, detail="Only open incidents can be acknowledged")

    prev_state = inc.state
    prev_sev = inc.severity

    inc.state = IncidentState.ACK
    inc.acknowledged_at = datetime.utcnow()
    inc.acknowledged_by_user_id = user.user_id
    session.add(inc)

    ev = IncidentEvent(
        incident_id=inc.incident_id,
        org_id=inc.org_id,
        model_id=inc.model_id,
        metric=inc.metric,
        ts=datetime.utcnow(),
        action=IncidentEventAction.ACK,
        prev_state=prev_state,
        new_state=inc.state,
        prev_severity=prev_sev,
        new_severity=inc.severity,
        value=inc.value,
        actor=IncidentEventActor.USER,
        actor_user_id=user.user_id,
    )
    session.add(ev)
    session.commit()

    return {"ok": True}


@router.post("/incidents/{incident_id}/resolve")
def ui_incident_resolve(
    incident_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    inc = session.exec(
        select(Incident).where((Incident.incident_id == incident_id) & (Incident.org_id == user.org_id))
    ).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if inc.state != IncidentState.ACK:
        raise HTTPException(status_code=400, detail="Only acknowledged incidents can be resolved")

    prev_state = inc.state
    prev_sev = inc.severity

    inc.state = IncidentState.RESOLVED
    inc.resolved_at = datetime.utcnow()
    session.add(inc)

    ev = IncidentEvent(
        incident_id=inc.incident_id,
        org_id=inc.org_id,
        model_id=inc.model_id,
        metric=inc.metric,
        ts=datetime.utcnow(),
        action=IncidentEventAction.RESOLVE,
        prev_state=prev_state,
        new_state=inc.state,
        prev_severity=prev_sev,
        new_severity=inc.severity,
        value=inc.value,
        actor=IncidentEventActor.USER,
        actor_user_id=user.user_id,
    )
    session.add(ev)
    session.commit()

    route = session.exec(
        select(AlertRoute).where(
            (AlertRoute.org_id == inc.org_id) & (AlertRoute.is_enabled == True)  # noqa: E712
        )
    ).first()
    if route:
        ui_base = os.getenv("UI_BASE_URL", "http://localhost:9000")
        psi_val = f"{inc.value:.4f}" if inc.value is not None else "—"
        send_slack(
            route.slack_webhook_url,
            (
                "✅ SentryML incident RESOLVED\n"
                f"Model: `{inc.model_id}`\n"
                f"Severity: {inc.severity}\n"
                f"PSI: {psi_val}\n"
                f"Incident: {ui_base}/incidents/{inc.incident_id}\n"
                "Ack in UI to mark as seen."
            ),
        )

    return {"ok": True}


@router.post("/incidents/{incident_id}/close")
def ui_incident_close(
    incident_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    inc = session.exec(
        select(Incident).where((Incident.incident_id == incident_id) & (Incident.org_id == user.org_id))
    ).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if inc.state not in (IncidentState.ACK, IncidentState.RESOLVED):
        raise HTTPException(status_code=400, detail="Only acknowledged or resolved incidents can be closed")

    prev_state = inc.state
    prev_sev = inc.severity

    inc.state = IncidentState.CLOSED
    inc.closed_at = datetime.utcnow()
    session.add(inc)

    ev = IncidentEvent(
        incident_id=inc.incident_id,
        org_id=inc.org_id,
        model_id=inc.model_id,
        metric=inc.metric,
        ts=datetime.utcnow(),
        action=IncidentEventAction.CLOSE,
        prev_state=prev_state,
        new_state=inc.state,
        prev_severity=prev_sev,
        new_severity=inc.severity,
        value=inc.value,
        actor=IncidentEventActor.USER,
        actor_user_id=user.user_id,
    )
    session.add(ev)
    session.commit()

    route = session.exec(
        select(AlertRoute).where(
            (AlertRoute.org_id == inc.org_id) & (AlertRoute.is_enabled == True)  # noqa: E712
        )
    ).first()
    if route:
        ui_base = os.getenv("UI_BASE_URL", "http://localhost:9000")
        psi_val = f"{inc.value:.4f}" if inc.value is not None else "—"
        send_slack(
            route.slack_webhook_url,
            (
                "✅ SentryML incident CLOSED\n"
                f"Model: `{inc.model_id}`\n"
                f"Severity: {inc.severity}\n"
                f"PSI: {psi_val}\n"
                f"Incident: {ui_base}/incidents/{inc.incident_id}\n"
                "Ack in UI to mark as seen."
            ),
        )

    return {"ok": True}
