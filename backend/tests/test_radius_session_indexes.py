from app.models.core import RadiusSession


def test_card_session_history_has_composite_pagination_index():
    index = next(
        (
            item
            for item in RadiusSession.__table__.indexes
            if item.name == "ix_radius_sessions_card_started"
        ),
        None,
    )

    assert index is not None
    assert tuple(column.name for column in index.columns) == (
        "card_id",
        "started_at",
        "id",
    )
