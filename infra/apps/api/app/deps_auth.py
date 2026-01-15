from datetime import datetime
from fastapi import Cookie, Depends, HTTPException
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import SessionToken, User


def get_current_user(
    sentryml_session: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not sentryml_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = session.exec(
        select(SessionToken).where(SessionToken.session_id == sentryml_session)
    ).first()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    user = session.exec(select(User).where(User.user_id == token.user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user
