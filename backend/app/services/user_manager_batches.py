"""Safety-bounded orchestration for already-paginated User Manager source readers.

This module deliberately does not implement RouterOS pagination. A source adapter
must first prove that it can enforce a server-side page limit and provide a stable
continuation cursor. Never wrap an unbounded RouterOS print() response here.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Mapping, Sequence


class BatchSafetyError(RuntimeError):
    """Raised when a source reader violates the bounded-page contract."""


@dataclass(frozen=True)
class BatchPolicy:
    page_size: int = 100
    max_records: int = 500
    max_pages: int = 5
    max_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= 500:
            raise ValueError("page_size must be between 1 and 500")
        if not 1 <= self.max_records <= 5000:
            raise ValueError("max_records must be between 1 and 5000")
        if not 1 <= self.max_pages <= 50:
            raise ValueError("max_pages must be between 1 and 50")
        if not 0.1 <= self.max_seconds <= 300:
            raise ValueError("max_seconds must be between 0.1 and 300")


@dataclass(frozen=True)
class SourcePage:
    records: Sequence[Mapping[str, Any]]
    next_cursor: str | None
    exhausted: bool


@dataclass(frozen=True)
class BatchResult:
    status: str
    processed_records: int
    processed_pages: int
    checkpoint: dict[str, Any]


def run_bounded_batches(
    *,
    fetch_page: Callable[[str | None, int], SourcePage],
    persist_page: Callable[[Sequence[Mapping[str, Any]], dict[str, Any]], None],
    checkpoint: Mapping[str, Any] | None = None,
    policy: BatchPolicy | None = None,
    clock: Callable[[], float] = monotonic,
) -> BatchResult:
    """Fetch bounded pages and persist each page with its checkpoint atomically.

    The fetcher must enforce the requested limit at the source, not fetch an
    unbounded result and slice it. The persistence callback owns one transaction:
    it must write all page records and the supplied checkpoint together, then
    commit. If any write fails, it must roll back and raise. This function never
    persists page data and checkpoint through separate callbacks.
    """
    limits = policy or BatchPolicy()
    state = dict(checkpoint or {})
    cursor = state.get("cursor")
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        raise BatchSafetyError("checkpoint cursor must be a non-empty string or null")

    prior_records = state.get("processed_records", 0)
    prior_pages = state.get("processed_pages", 0)
    if (
        isinstance(prior_records, bool) or not isinstance(prior_records, int)
        or prior_records < 0
        or isinstance(prior_pages, bool) or not isinstance(prior_pages, int)
        or prior_pages < 0
    ):
        raise BatchSafetyError("checkpoint counters must be non-negative integers")
    if state.get("source_complete") is True:
        return BatchResult("completed", 0, 0, state)
    if prior_records >= limits.max_records or prior_pages >= limits.max_pages:
        return BatchResult("paused", 0, 0, state)

    processed_records = 0
    processed_pages = 0
    started = clock()
    history = state.get("cursor_history", [])
    if not isinstance(history, list) or any(not isinstance(item, str) or not item for item in history):
        raise BatchSafetyError("checkpoint cursor_history must be a list of non-empty strings")
    seen_cursors: set[str] = set(history)

    while processed_pages < limits.max_pages and processed_records < limits.max_records:
        if clock() - started >= limits.max_seconds:
            break

        # A cursor becomes consumed when its page is about to be fetched. A
        # pending next_cursor is not recorded until the next page is persisted.
        if cursor is not None:
            if cursor in seen_cursors:
                raise BatchSafetyError("checkpoint cursor was already processed")
            seen_cursors.add(cursor)

        remaining = limits.max_records - processed_records
        requested = min(limits.page_size, remaining)
        page = fetch_page(cursor, requested)

        if not isinstance(page, SourcePage):
            raise BatchSafetyError("source adapter returned an invalid page object")
        if len(page.records) > requested:
            raise BatchSafetyError("source adapter exceeded the requested page limit")
        if not page.records and not page.exhausted:
            raise BatchSafetyError("empty non-final page would prevent safe progress")

        next_cursor = page.next_cursor
        if next_cursor is not None:
            if not isinstance(next_cursor, str) or not next_cursor:
                raise BatchSafetyError("source adapter returned an invalid continuation cursor")
            if next_cursor in seen_cursors:
                raise BatchSafetyError("source adapter repeated a continuation cursor")

        next_records = processed_records + len(page.records)
        next_pages = processed_pages + 1
        next_state = {
            "cursor": next_cursor,
            "processed_records": prior_records + next_records,
            "processed_pages": prior_pages + next_pages,
            "cursor_history": sorted(seen_cursors),
            "source_complete": bool(page.exhausted),
        }

        # The callback must commit records and next_state in the same DB
        # transaction. Do not advance local state until that callback succeeds.
        persist_page(page.records, next_state)
        processed_records = next_records
        processed_pages = next_pages
        cursor = next_cursor
        state = next_state

        if page.exhausted:
            return BatchResult("completed", processed_records, processed_pages, state)
        if cursor is None:
            raise BatchSafetyError("non-final page did not provide a continuation cursor")

    return BatchResult("paused", processed_records, processed_pages, state)
