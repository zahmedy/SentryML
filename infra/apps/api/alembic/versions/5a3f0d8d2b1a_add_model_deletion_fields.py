"""add model deletion fields

Revision ID: 5a3f0d8d2b1a
Revises: 2b4d5c1a9d77
Create Date: 2026-01-19 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5a3f0d8d2b1a"
down_revision = "2b4d5c1a9d77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("models", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("models", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_models_is_deleted"), "models", ["is_deleted"], unique=False)
    op.alter_column("models", "is_deleted", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_models_is_deleted"), table_name="models")
    op.drop_column("models", "deleted_at")
    op.drop_column("models", "is_deleted")
