from app.db.base import Base
from app.models import UserManagerCardSource, UserManagerImportPreview, UserManagerSyncRun


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


def test_import_preview_is_staged_per_sync_run_and_source_identity():
    table = UserManagerImportPreview.__table__
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, __import__("sqlalchemy").UniqueConstraint)
    }
    assert ("sync_run_id", "external_user_id") in constraints
    assert "safe_snapshot" in table.c
    assert "issues" in table.c
    assert "source_fingerprint" in table.c
    assert "matched_card_id" in table.c
