from app.services.user_manager_batches import (
    BatchPolicy,
    BatchSafetyError,
    SourcePage,
    run_bounded_batches,
)


def test_bounded_batches_respect_record_and_page_budgets_and_checkpoint_each_page():
    pages = {
        None: SourcePage([{"id": "a"}, {"id": "b"}], "c2", False),
        "c2": SourcePage([{"id": "c"}], "c3", False),
    }
    requested_limits = []
    processed = []
    checkpoints = []

    def fetch(cursor, limit):
        requested_limits.append(limit)
        page = pages[cursor]
        assert len(page.records) <= limit
        return page

    result = run_bounded_batches(
        fetch_page=fetch,
        process_page=lambda rows: processed.extend(row["id"] for row in rows),
        save_checkpoint=lambda value: checkpoints.append(dict(value)),
        policy=BatchPolicy(page_size=2, max_records=3, max_pages=5, max_seconds=10),
    )

    assert result.status == "paused"
    assert result.processed_records == 3
    assert result.processed_pages == 2
    assert processed == ["a", "b", "c"]
    assert requested_limits == [2, 1]
    assert len(checkpoints) == 2
    assert checkpoints[-1]["cursor"] == "c3"


def test_bounded_batches_do_not_checkpoint_a_failed_page():
    saved = []

    def fail_processing(_rows):
        raise RuntimeError("database unavailable")

    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage([{"id": "x"}], "next", False),
            process_page=fail_processing,
            save_checkpoint=lambda value: saved.append(value),
            policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected processing failure")

    assert saved == []


def test_bounded_batches_reject_source_that_ignores_page_limit():
    processed = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage(
                [{"id": "1"}, {"id": "2"}], "next", False
            ),
            process_page=lambda rows: processed.extend(rows),
            save_checkpoint=lambda _value: None,
            policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "exceeded" in str(exc)
    else:
        raise AssertionError("Expected bounded-page contract failure")

    assert processed == []


def test_bounded_batches_reject_repeated_cursor_before_processing_or_checkpointing():
    calls = iter([
        SourcePage([{"id": "1"}], "same", False),
        SourcePage([{"id": "2"}], "same", False),
    ])
    processed = []
    saved = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: next(calls),
            process_page=lambda rows: processed.extend(rows),
            save_checkpoint=lambda value: saved.append(value),
            policy=BatchPolicy(page_size=1, max_records=2, max_pages=2, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "repeated" in str(exc)
    else:
        raise AssertionError("Expected repeated cursor failure")

    assert processed == [{"id": "1"}]
    assert len(saved) == 1


def test_bounded_batches_resume_pending_cursor_and_keep_cumulative_counters():
    first = run_bounded_batches(
        fetch_page=lambda _cursor, _limit: SourcePage([{"id": "a"}], "cursor-2", False),
        process_page=lambda _rows: None,
        save_checkpoint=lambda _value: None,
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
        process_page=lambda _rows: None,
        save_checkpoint=lambda _value: None,
        checkpoint=first.checkpoint,
        policy=BatchPolicy(page_size=1, max_records=10, max_pages=10, max_seconds=5),
    )
    assert requested == ["cursor-2"]
    assert second.status == "completed"
    assert second.checkpoint["processed_records"] == 2
    assert second.checkpoint["processed_pages"] == 2


def test_bounded_batches_reject_corrupt_checkpoint_before_source_or_processing():
    called = []
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: (
                called.append("fetch") or SourcePage([{"id": "x"}], None, True)
            ),
            process_page=lambda _rows: called.append("process"),
            save_checkpoint=lambda _value: None,
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
        process_page=lambda _rows: None,
        save_checkpoint=lambda _value: None,
        policy=BatchPolicy(page_size=1, max_records=1, max_pages=1, max_seconds=5),
    )
    try:
        run_bounded_batches(
            fetch_page=lambda _cursor, _limit: SourcePage([{"id": "b"}], None, True),
            process_page=lambda _rows: None,
            save_checkpoint=lambda _value: None,
            checkpoint={**first.checkpoint, "cursor_history": ["cursor-2"]},
            policy=BatchPolicy(page_size=1, max_records=5, max_pages=5, max_seconds=5),
        )
    except BatchSafetyError as exc:
        assert "already processed" in str(exc)
    else:
        raise AssertionError("Expected repeated checkpoint cursor failure")
