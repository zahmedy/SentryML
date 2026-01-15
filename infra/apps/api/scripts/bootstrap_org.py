import os
import secrets
from uuid import uuid4
from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine

from apps.sentryml_core.models import Org, ApiKey, User
from apps.api.app.security import hash_api_key, hash_password



def generate_api_key(prefix) -> str:
    # ~43 chars of entropy in the token part (URL-safe)
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}"


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    
    org_name = os.getenv("ORG_NAME", "Demo Org")
    user_email = os.getenv("USER_EMAIL", "Admin")
    password = os.getenv("PASSWORD", "admin123")

    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)

    prefix = "sk_live_"
    raw_key = generate_api_key(prefix)
    key_prefix = raw_key[:12]
    key_hash = hash_api_key(raw_key)
    pass_hash = hash_password(password)

    org = Org(org_id=uuid4(), name=org_name)
    user = User(
        user_id=uuid4(),
        org_id=org.org_id,
        email=user_email,
        password_hash=pass_hash,
        created_at=datetime.utcnow()
    )

    api_key = ApiKey(
        key_id=uuid4(),
        org_id=org.org_id,
        user_id=user.user_id,
        prefix=key_prefix,
        key_hash=key_hash,
        name="prod",
        created_at=datetime.utcnow(),
        revoked_at=None
    )

    

    with Session(engine, expire_on_commit=False) as session:
        session.add(org)
        session.add(user)
        session.add(api_key)
        session.commit()

    print("\n✅ Created org + API key")
    print(f"org_id: {org.org_id}")
    print(f"api_key: {raw_key}")
    print("\nStore this key somewhere safe — it will NOT be shown again.\n")


if __name__ == "__main__":
    main()
