import hmac
import bcrypt
import hashlib
import os
from fastapi import Header, HTTPException, Depends
from sqlmodel import Session, select
from datetime import datetime

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import ApiKey



def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8")
    )

def hash_api_key(raw_key: str) -> str:
    pepper = os.getenv("API_KEY_SECRET")
    if not pepper: 
        raise RuntimeError("API_KEY_SECRET is not set")
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
                           .where(ApiKey.key_hash == key_hash).distinct()
                           .where(ApiKey.revoked_at is None) 
                            ).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    api_key.last_used_at = datetime.utcnow()
    return api_key.org_id