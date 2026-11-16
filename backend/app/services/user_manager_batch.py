"""Bounded, resumable orchestration for already-bounded User Manager pages.

This module deliberately does not implement RouterOS pagination. A source adapter
must prove that its page request is bounded before it can be plugged into this
runner. The persistence callback must atomically store the page and checkpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Callable, Sequence


class UnsafeBatchPage(ValueError):
    """Raised when a source violates the bounded-page contract."""


@dataclass(frozen=True)
class BatchBudget:
    page_size: int = 50
    max_records: int = 500
    max_pages: int = 10
    max_elapsed_seconds: float = 30.0
    inter_page_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if not 1 <= self.max_records <= 1000:
            raise ValueError("max_records must be between 1 and 1000")
        if not 1 <= self.max_pages <= 20:
            raise ValueError("max_pages must be between 1 and 20")
        if self.max_elapsed_seconds <= 0 or self.max_elapsed_seconds > 120:
            raise ValueError("max_elapsed_seconds must be greater than 0 and at most 120")
        if self.inter_page_delay_seconds < 0 or self.inter_page_delay_seconds > 10:
            raise ValueError("inter_page_delay_seconds must be between 0 and 10")


@dataclass(frozen=True)
class BatchPage:
    records: Sequence[dict[str, Any]]
    next_cursor: str | None
    exhausted: bool


@dataclass(frozen=True)
class BatchProgress:
    records_processed: int
    pages_processed: int
    checkpoint: str | None
    exhausted: bool
    stop_reason: str


def run_bounded_batch_scan(
    *,
    fetch_page: Callable[[str | None, int], BatchPage],
    persist_page: Callable[[Sequence[dict[str, Any]], str | None], None],
    budget: BatchBudget = BatchBudget(),
    initial_checkpoint: str | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    clock: Callable[[], float] = monotonic,
    pause: Callable[[float], None] = sleep,
) -> BatchProgress:
    """Process a bounded number of pages; persist each page with its checkpoint.

    fetch_page must enforce the requested limit at the source. persist_page must
    atomically persist records and next_cursor, so retries cannot skip a page.
    """
    started = clock()
    cursor = initial_checkpoint
    processed = pages = 0
    exhausted = False
    reason = "page_budget_reached"

    while pages < budget.max_pages and processed < budget.max_records:
        if should_stop():
            reason = "cancelled"
            break
        if clock() - started >= budget.max_elapsed_seconds:
            reason = "time_budget_reached"
            break

        requested = min(budget.page_size, budget.max_records - processed)
        page = fetch_page(cursor, requested)
        if not isinstance(page, BatchPage):
            raise UnsafeBatchPage("fetch_page must return BatchPage")
        if len(page.records) > requested:
            raise UnsafeBatchPage("source page exceeded the requested record limit")
        if any(not isinstance(row, dict) for row in page.records):
            raise UnsafeBatchPage("every source row must be an object")
        if not page.exhausted and not page.next_cursor:
            raise UnsafeBatchPage("non-final page must provide a resumable cursor")
        if page.next_cursor is not None and page.next_cursor == cursor:
            raise UnsafeBatchPage("source cursor did not advance")

        # A successful atomic persist is the only point at which the checkpoint
        # advances. If persistence fails, the caller retries from the old cursor.
        persist_page(page.records, page.next_cursor)
        processed += len(page.records)
        pages += 1
        cursor = page.next_cursor
        exhausted = page.exhausted

        if exhausted:
            reason = "source_exhausted"
            break
        if processed >= budget.max_records:
            reason = "record_budget_reached"
            break
        if pages >= budget.max_pages:
            reason = "page_budget_reached"
            break
        if should_stop():
            reason = "cancelled"
            break
        remaining = budget.max_elapsed_seconds - (clock() - started)
        if remaining <= 0:
            reason = "time_budget_reached"
            break
        delay = min(budget.inter_page_delay_seconds, remaining)
        if delay:
            pause(delay)

    return BatchProgress(
        records_processed=processed,
        pages_processed=pages,
        checkpoint=cursor,
        exhausted=exhausted,
        stop_reason=reason,
    )
