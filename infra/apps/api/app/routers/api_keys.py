# infra/apps/api/app/routers/api_keys.py

import secrets
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import ApiKey, User
from apps.api.app.security import hash_api_key  # your HMAC hash
from apps.api.app.deps_auth import get_current_user       # the cookie session dep

router = APIRouter(prefix="/v1/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str | None = None


def generate_api_key(prefix: str = "sk_live_") -> str:
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}"


@router.get("")
def list_api_keys(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    keys = session.exec(
        select(ApiKey)
        .where(ApiKey.org_id == user.org_id)
        .order_by(ApiKey.created_at.desc())
    ).all()

    # Return safe fields only
    return [
        {
            "key_id": str(k.key_id),
            "name": k.name,
            "prefix": k.prefix,
            "created_at": k.created_at,
            "revoked_at": k.revoked_at,
            "last_used_at": k.last_used_at,
            "user_id": str(k.user_id),
        }
        for k in keys
    ]


@router.post("")
def create_api_key(
    payload: CreateApiKeyRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    raw_key = generate_api_key("sk_live_")
    key_hash = hash_api_key(raw_key)
    display_prefix = raw_key[:12]

    row = ApiKey(
        key_id=uuid4(),
        org_id=user.org_id,
        user_id=user.user_id,
        name=payload.name,
        prefix=display_prefix,
        key_hash=key_hash,
        created_at=datetime.utcnow(),
        revoked_at=None,
        last_used_at=None,
    )
    session.add(row)
    session.commit()

    # show once
    return {
        "key_id": str(row.key_id),
        "prefix": row.prefix,
        "api_key": raw_key,
    }


@router.post("/{key_id}/revoke")
def revoke_api_key(
    key_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    row = session.exec(
        select(ApiKey).where((ApiKey.key_id == key_id) & (ApiKey.org_id == user.org_id))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    if row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        session.add(row)
        session.commit()

    return {"ok": True}
