from datetime import datetime, timedelta
from uuid import uuid4
import os

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from apps.sentryml_core.db import get_session
from apps.sentryml_core.models import (
    Org,
    User,
    SessionToken,
    PasswordResetToken,
)  # your SQLModel tables
from apps.api.app.security import hash_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    # 1) Find user
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2) Verify password
    ok = bcrypt.checkpw(payload.password.encode("utf-8"), user.password_hash.encode("utf-8"))
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 3) Create session token (30 days)
    token = SessionToken(
        user_id=user.user_id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        revoked_at=None,
    )
    session.add(token)
    session.commit()

    # 4) Set cookie
    response.set_cookie(
        key="sentryml_session",
        value=str(token.session_id),
        httponly=True,
        samesite="lax",
        secure=False,  # set True in prod behind HTTPS
        max_age=30 * 24 * 60 * 60,
    )

    return {"ok": True}


@router.post("/signup")
def signup(payload: SignupRequest, response: Response, session: Session = Depends(get_session)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Please use 8 characters password")
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Org(
        org_id=uuid4(),
        name=payload.email.split("@")[0] or "My Org",
    )
    user = User(
        user_id=uuid4(),
        org_id=org.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        created_at=datetime.utcnow(),
    )
    session.add(org)
    session.add(user)

    token = SessionToken(
        user_id=user.user_id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        revoked_at=None,
    )
    session.add(token)
    session.commit()

    response.set_cookie(
        key="sentryml_session",
        value=str(token.session_id),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=30 * 24 * 60 * 60,
    )

    return {"ok": True}


@router.post("/password-reset/request")
def password_reset_request(payload: PasswordResetRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user:
        token = uuid4().hex
        reset = PasswordResetToken(
            user_id=user.user_id,
            token=token,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=None,
        )
        session.add(reset)
        session.commit()
        ui_base = os.getenv("UI_BASE_URL", "http://localhost:9000")
        print(f"Password reset link: {ui_base}/reset/confirm?token={token}")
    return {"ok": True}


@router.post("/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirm, session: Session = Depends(get_session)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Please use 8 characters password")

    reset = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == payload.token)
    ).first()
    if not reset or reset.used_at or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = session.get(User, reset.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(payload.password)
    reset.used_at = datetime.utcnow()

    sessions = session.exec(
        select(SessionToken).where(
            (SessionToken.user_id == user.user_id) & (SessionToken.revoked_at == None)  # noqa: E711
        )
    ).all()
    for s in sessions:
        s.revoked_at = datetime.utcnow()
        session.add(s)

    session.add(user)
    session.add(reset)
    session.commit()
    return {"ok": True}
