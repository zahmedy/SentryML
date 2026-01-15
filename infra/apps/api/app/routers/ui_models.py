from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import DriftResult, Incident, User
from apps.api.app.deps_auth import get_current_user

router = APIRouter(prefix="/v1/ui", tags=["ui"])


@router.get("/models/{model_id}")
def ui_model_detail(
    model_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
):
    drift = session.exec(
        select(DriftResult)
        .where((DriftResult.org_id == user.org_id) & (DriftResult.model_id == model_id))
        .order_by(DriftResult.computed_at.desc())
        .limit(limit)
    ).all()

    incidents = session.exec(
        select(Incident)
        .where((Incident.org_id == user.org_id) & (Incident.model_id == model_id))
        .order_by(Incident.opened_at.desc())
        .limit(limit)
    ).all()

    return {"model_id": model_id, "drift": drift, "incidents": incidents}
