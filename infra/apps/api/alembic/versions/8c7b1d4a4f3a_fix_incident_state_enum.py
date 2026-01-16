"""fix incident_state enum

Revision ID: 8c7b1d4a4f3a
Revises: f02dc4f9f9bf
Create Date: 2026-01-16 17:30:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "8c7b1d4a4f3a"
down_revision = "f02dc4f9f9bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure incidentstate enum uses OPEN/ACK/RESOLVED/CLOSED.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                WHERE t.typname = 'incidentstate'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'incidentstate' AND e.enumlabel = 'OPEN'
                ) THEN
                    -- If incident_events still uses incidentstate enum, cast to text first.
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'incident_events'
                          AND column_name IN ('prev_state', 'new_state')
                    ) THEN
                        ALTER TABLE incident_events
                        ALTER COLUMN prev_state TYPE VARCHAR
                        USING prev_state::text;
                        ALTER TABLE incident_events
                        ALTER COLUMN new_state TYPE VARCHAR
                        USING new_state::text;
                    END IF;

                    CREATE TYPE incidentstate_new AS ENUM ('OPEN', 'ACK', 'RESOLVED', 'CLOSED');
                    ALTER TABLE incidents
                    ALTER COLUMN state TYPE incidentstate_new
                    USING (
                        CASE
                            WHEN state::text IN ('WARN', 'CRITICAL') THEN 'OPEN'
                            WHEN state::text IN ('NONE') THEN 'RESOLVED'
                            WHEN state::text IN ('OPEN', 'ACK', 'RESOLVED', 'CLOSED') THEN state::text
                            ELSE 'OPEN'
                        END
                    )::incidentstate_new;
                    DROP TYPE incidentstate;
                    ALTER TYPE incidentstate_new RENAME TO incidentstate;
                END IF;
            ELSE
                CREATE TYPE incidentstate AS ENUM ('OPEN', 'ACK', 'RESOLVED', 'CLOSED');
                ALTER TABLE incidents
                ALTER COLUMN state TYPE incidentstate
                USING 'OPEN'::incidentstate;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Best-effort downgrade back to NONE/WARN/CRITICAL.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                WHERE t.typname = 'incidentstate'
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'incidentstate' AND e.enumlabel = 'OPEN'
                ) THEN
                    CREATE TYPE incidentstate_old AS ENUM ('NONE', 'WARN', 'CRITICAL');
                    ALTER TABLE incidents
                    ALTER COLUMN state TYPE incidentstate_old
                    USING (
                        CASE
                            WHEN state IN ('ACK', 'RESOLVED', 'CLOSED') THEN 'NONE'
                            WHEN state = 'OPEN' THEN 'WARN'
                            ELSE 'NONE'
                        END
                    )::incidentstate_old;
                    DROP TYPE incidentstate;
                    ALTER TYPE incidentstate_old RENAME TO incidentstate;
                END IF;
            END IF;
        END$$;
        """
    )
