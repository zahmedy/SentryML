import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine

from apps.sentryml_core.models import ApiKey
from apps.api.app.security import get_org_id, hash_api_key


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_get_org_id_valid_key(session, monkeypatch):
    monkeypatch.setenv("API_KEY_SECRET", "test-secret")
    raw_key = "sk_test_valid"
    key_hash = hash_api_key(raw_key)
    org_id = uuid4()

    session.add(ApiKey(key_id=uuid4(), org_id=org_id, user_id=uuid4(), prefix="sk_", key_hash=key_hash))
    session.commit()

    out = get_org_id(x_api_key=raw_key, session=session)
    assert out == org_id


def test_get_org_id_revoked_key(session, monkeypatch):
    monkeypatch.setenv("API_KEY_SECRET", "test-secret")
    raw_key = "sk_test_revoked"
    key_hash = hash_api_key(raw_key)

    session.add(
        ApiKey(
            key_id=uuid4(),
            org_id=uuid4(),
            user_id=uuid4(),
            prefix="sk_",
            key_hash=key_hash,
            revoked_at=datetime.utcnow(),
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc:
        get_org_id(x_api_key=raw_key, session=session)
    assert exc.value.status_code == 401
