from app.db.base import Base
from app.models import UserManagerCardSource, UserManagerSyncRun


def test_user_manager_sync_tables_are_registered():
    assert "user_manager_sync_runs" in Base.metadata.tables
    assert "user_manager_card_sources" in Base.metadata.tables


def test_user_manager_source_has_stable_source_identity_and_unique_card_link():
    table = UserManagerCardSource.__table__
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, __import__("sqlalchemy").UniqueConstraint)
    }
    assert ("router_id", "external_user_id") in constraints
    assert ("card_id",) in constraints


def test_sync_run_keeps_checkpoint_and_audit_summaries():
    table = UserManagerSyncRun.__table__
    assert "checkpoint" in table.c
    assert "source_summary" in table.c
    assert "error_summary" in table.c
