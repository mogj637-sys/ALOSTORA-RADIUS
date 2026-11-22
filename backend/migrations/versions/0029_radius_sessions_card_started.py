"""index card session history by card and start time

Revision ID: 0029_radius_session_idx
Revises: 0028_pos_delete_policy
"""
from alembic import op


revision = "0029_radius_session_idx"
down_revision = "0028_pos_delete_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Build without holding a long write lock on a populated accounting table.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_radius_sessions_card_started",
            "radius_sessions",
            ["card_id", "started_at", "id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_radius_sessions_card_started",
            table_name="radius_sessions",
            postgresql_concurrently=True,
        )
