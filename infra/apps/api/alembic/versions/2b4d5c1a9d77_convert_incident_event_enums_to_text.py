"""convert incident_event enums to text

Revision ID: 2b4d5c1a9d77
Revises: 8c7b1d4a4f3a
Create Date: 2026-01-16 17:35:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "2b4d5c1a9d77"
down_revision = "8c7b1d4a4f3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'incident_events'
            ) THEN
                ALTER TABLE incident_events
                ALTER COLUMN action TYPE VARCHAR
                USING action::text;

                ALTER TABLE incident_events
                ALTER COLUMN prev_state TYPE VARCHAR
                USING prev_state::text;

                ALTER TABLE incident_events
                ALTER COLUMN new_state TYPE VARCHAR
                USING new_state::text;

                ALTER TABLE incident_events
                ALTER COLUMN actor TYPE VARCHAR
                USING actor::text;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Best-effort: leave as text to avoid reintroducing enum mismatch.
    pass
