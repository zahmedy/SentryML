import os
import secrets
from uuid import uuid4
from datetime import datetime

from sqlmodel import Session, create_engine

from apps.sentryml_core.models import Org, ApiKey
from apps.api.app.security import hash_api_key



def generate_api_key() -> str:
    # ~43 chars of entropy in the token part (URL-safe)
    token = secrets.token_urlsafe(32)
    return f"sk_live_{token}"


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    
    org_name = os.getenv("ORG_NAME", "Demo Org")

    engine = create_engine(database_url, echo=False)

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    org = Org(org_id=uuid4(), name=org_name)
    api_key = ApiKey(
        key_id=uuid4(),
        org_id=org.org_id,
        key_hash=key_hash,
        created_at=datetime.utcnow(),
        revoked_at=None
    )

    with Session(engine, expire_on_commit=False) as session:
        session.add(org)
        session.add(api_key)
        session.commit()

    print("\n✅ Created org + API key")
    print(f"org_id: {org.org_id}")
    print(f"api_key: {raw_key}")
    print("\nStore this key somewhere safe — it will NOT be shown again.\n")


if __name__ == "__main__":
    main()