"""Per-server wall-clock budget enforcer.

Implements T-10 / AC-1.5.

`run_with_budget(work, timeout_seconds=...)` runs a zero-argument callable
in a worker thread with a hard wall-clock deadline. On expiry the call
returns a `BudgetResult` with `completed=False` and `value=None`; the
worker thread is left to its own devices (Python threads cannot be
externally killed in user code) and the caller continues to the next
candidate. On normal return the call returns `BudgetResult.completed=True`
with the callable's return value.

Exceptions raised by `work` propagate to the caller — the budget enforcer
catches only the wall-clock condition, not application errors.

Cross-platform: uses `concurrent.futures.ThreadPoolExecutor` so the same
implementation works on Windows, Linux, and macOS without relying on
POSIX `signal.alarm`.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from mcp_verified.checks.executors.deterministic import Finding

T = TypeVar("T")

DEFAULT_PER_SERVER_BUDGET_SECONDS = 300.0  # 5-minute per-candidate cap (AC-1.5).
TIMEOUT_RULE_ID = "CHECK-RUN-TIMEOUT"


@dataclass(frozen=True)
class BudgetResult(Generic[T]):
    """Outcome of a budgeted call.

    Attributes
    ----------
    completed
        True if `work` returned within the budget, False on timeout.
    value
        The callable's return value when `completed=True`, otherwise None.
    elapsed_seconds
        Wall-clock seconds spent. Capped at the configured budget on
        timeout (the worker may keep running beyond this).
    """

    completed: bool
    value: T | None
    elapsed_seconds: float


def run_with_budget(
    work: Callable[[], T],
    *,
    timeout_seconds: float = DEFAULT_PER_SERVER_BUDGET_SECONDS,
) -> BudgetResult[T]:
    if timeout_seconds <= 0:
        raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}")
    pool = ThreadPoolExecutor(max_workers=1)
    start = time.monotonic()
    try:
        future = pool.submit(work)
        try:
            value = future.result(timeout=timeout_seconds)
            elapsed = time.monotonic() - start
            return BudgetResult(completed=True, value=value, elapsed_seconds=elapsed)
        except _FuturesTimeoutError:
            elapsed = time.monotonic() - start
            # `cancel()` is a no-op once the task has started running, which is
            # the case here. Python threads cannot be externally killed, so the
            # worker keeps running in the background until its I/O completes.
            future.cancel()
            return BudgetResult(completed=False, value=None, elapsed_seconds=elapsed)
    finally:
        # `wait=False` returns immediately so the caller can proceed with the
        # next candidate while the stuck worker drains its I/O in the
        # background. The thread is non-daemon, so process exit still waits
        # for it; long-running production loops can drop the reference once
        # the result is consumed.
        pool.shutdown(wait=False)


def timeout_finding(
    timeout_seconds: float = DEFAULT_PER_SERVER_BUDGET_SECONDS,
    *,
    candidate: str | None = None,
) -> Finding:
    """Build the synthetic Finding recorded when a candidate hits the budget."""
    suffix = f" while processing {candidate!r}" if candidate else ""
    return Finding(
        rule_id=TIMEOUT_RULE_ID,
        severity="info",
        cwe=None,
        file_path="",
        line_number=0,
        redacted_snippet="",
        description=(
            f"Per-server budget of {timeout_seconds:.0f}s exceeded{suffix}; "
            "candidate skipped, audit continues with the next entry."
        ),
    )


def _unused_marker(_: Any) -> None:
    """Placeholder kept so that linters do not strip the `Any` import."""
