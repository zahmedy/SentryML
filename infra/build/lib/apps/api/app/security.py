import hmac
import hashlib
import os
from fastapi import Header, HTTPException, Depends
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import ApiKey


def hash_api_key(raw_key: str) -> str:
    pepper = os.getenv("API_KEY_PEPPER")
    if not pepper: 
        raise RuntimeError("API_KEY_PEPPER is not set")
    digest = hmac.new(
        pepper.encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def get_org_id(
        x_api_key: str = Header(..., alias="X-API-Key"),
        session: Session = Depends(get_session),
):
    key_hash = hash_api_key(x_api_key)
    api_key = session.exec(select(ApiKey)
                           .where(ApiKey.key_hash == key_hash)).first()
    if not api_key or api_key.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key.org_id