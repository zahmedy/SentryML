from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import Incident, DriftResult, User
from apps.api.app.deps_auth import get_current_user

router = APIRouter(prefix="/v1/ui", tags=["ui"])


@router.get("/dashboard")
def ui_dashboard(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 20,
):
    open_incidents = session.exec(
        select(Incident)
        .where((Incident.org_id == user.org_id) & (Incident.closed_at == None))
        .order_by(Incident.opened_at.desc())
        .limit(limit)
    ).all()

    latest_drift = session.exec(
        select(DriftResult)
        .where(DriftResult.org_id == user.org_id)
        .order_by(DriftResult.computed_at.desc())
        .limit(limit)
    ).all()

    return {
        "open_incidents": open_incidents,
        "latest_drift": latest_drift,
    }
