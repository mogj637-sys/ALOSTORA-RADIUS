from app.services.user_manager_batches import (
    BatchPolicy,
    BatchSafetyError,
    SourcePage,
    run_bounded_batches,
)


def test_bounded_batches_respect_budgets_and_persist_each_page_with_checkpoint():
    pages = {
        None: SourcePage([{"id": "a"}, {"id": "b"}], "c2", False),
        "c2": SourcePage([{"id": "c"}], "c3", False),
    }
    requested_limits = []
    persisted = []

    def fetch(cursor, limit):
        requested_limits.append(limit)
        page = pages[cursor]
        assert len(page.records) <= limit
        return page

    result = run_bounded_batches(
        fetch_page=fetch,
        persist_page=lambda rows, checkpoint: persisted.append((list(rows), dict(checkpoint))),
        policy=BatchPolicy(page_size=2, max_records=3, max_pages=5, max_seconds=10),
    )

    assert result.status == "paused"
    assert result.processed_records == 3
    assert result.processed_pages == 2
    assert requested_limits == [2, 1]
    assert len(persisted) == 2
    assert [row["id"] for row in persisted[0][0]] == ["a", "b"]
    assert persisted[0][1]["cursor"] == "c2"
    assert [row["id"] for row in persisted[1][0]] == ["c"]
    assert persisted[1][1]["cursor"] == "c3"


def test_failed_atomic_persistence_does_not_advance_checkpoint():
    committed = []

    def fail_transaction(rows, checkpoint):
        # A real implementation rolls back its transaction before raising.
        raise RuntimeError("database unavailable; transaction rolled back")

    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage([{"id": "x"}], "next", False),
            persist_page=fail_transaction,
            policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
        )
    except RuntimeError as exc:
        assert "rolled back" in str(exc)
    else:
        raise AssertionError("Expected persistence failure")

    assert committed == []


def test_bounded_batches_reject_source_that_ignores_page_limit():
    persisted = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage(
                [{"id": "1"}, {"id": "2"}], "next", False
            ),
            persist_page=lambda rows, checkpoint: persisted.append((rows, checkpoint)),
            policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "exceeded" in str(exc)
    else:
        raise AssertionError("Expected bounded-page contract failure")

    assert persisted == []


def test_bounded_batches_reject_repeated_cursor_before_persisting_repeated_page():
    calls = iter([
        SourcePage([{"id": "1"}], "same", False),
        SourcePage([{"id": "2"}], "same", False),
    ])
    persisted = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: next(calls),
            persist_page=lambda rows, checkpoint: persisted.append((list(rows), dict(checkpoint))),
            policy=BatchPolicy(page_size=1, max_records=2, max_pages=2, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "repeated" in str(exc)
    else:
        raise AssertionError("Expected repeated cursor failure")

    assert len(persisted) == 1
    assert persisted[0][0] == [{"id": "1"}]


def test_bounded_batches_resume_pending_cursor_and_keep_cumulative_counters():
    first = run_bounded_batches(
        fetch_page=lambda _cursor, _limit: SourcePage([{"id": "a"}], "cursor-2", False),
        persist_page=lambda _rows, _checkpoint: None,
        policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
    )
    assert first.checkpoint["cursor"] == "cursor-2"
    assert first.checkpoint["processed_records"] == 1
    assert first.checkpoint["processed_pages"] == 1
    assert first.checkpoint["cursor_history"] == []

    requested = []
    second = run_bounded_batches(
        fetch_page=lambda cursor, _limit: (
            requested.append(cursor) or SourcePage([{"id": "b"}], None, True)
        ),
        persist_page=lambda _rows, _checkpoint: None,
        checkpoint=first.checkpoint,
        policy=BatchPolicy(page_size=1, max_records=10, max_pages=10, max_seconds=5),
    )
    assert requested == ["cursor-2"]
    assert second.status == "completed"
    assert second.checkpoint["processed_records"] == 2
    assert second.checkpoint["processed_pages"] == 2


def test_bounded_batches_reject_corrupt_checkpoint_before_source_or_persistence():
    called = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: (
                called.append("fetch") or SourcePage([{"id": "x"}], None, True)
            ),
            persist_page=lambda _rows, _checkpoint: called.append("persist"),
            checkpoint={"processed_records": -1},
        )
    except BatchSafetyError as exc:
        assert "counters" in str(exc)
    else:
        raise AssertionError("Expected invalid checkpoint failure")
    assert called == []


def test_bounded_batches_reject_cursor_cycle_across_resume():
    first = run_bounded_batches(
        fetch_page=lambda _cursor, _limit: SourcePage([{"id": "a"}], "cursor-2", False),
        persist_page=lambda _rows, _checkpoint: None,
        policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
    )
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage([{"id": "b"}], None, True),
            persist_page=lambda _rows, _checkpoint: None,
            checkpoint={**first.checkpoint, "cursor_history": ["cursor-2"]},
            policy=BatchPolicy(page_size=1, max_records=5, max_pages=5, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "already processed" in str(exc)
    else:
        raise AssertionError("Expected repeated checkpoint cursor failure")



def test_bounded_batches_do_not_persist_page_returned_after_time_budget():
    now = [0.0]
    persisted = []

    def fetch_page(_cursor, _limit):
        now[0] = 2.0
        return SourcePage([{"id": "late-page"}], "next", False)

    result = run_bounded_batches(
        fetch_page=fetch_page,
        persist_page=lambda rows, checkpoint: persisted.append((list(rows), dict(checkpoint))),
        policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=1),
        clock=lambda: now[0],
    )

    assert result.status == "paused"
    assert result.processed_records == 0
    assert result.processed_pages == 0
    assert result.checkpoint == {}
    assert persisted == []
