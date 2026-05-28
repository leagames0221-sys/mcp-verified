"""Tests for `mcp_verified.budget.per_server` — T-10 surface."""

from __future__ import annotations

import time

import pytest

from mcp_verified.budget.per_server import (
    DEFAULT_PER_SERVER_BUDGET_SECONDS,
    TIMEOUT_RULE_ID,
    BudgetResult,
    run_with_budget,
    timeout_finding,
)


class TestRunWithBudgetHappyPath:
    def test_fast_work_returns_value(self) -> None:
        result = run_with_budget(lambda: 42, timeout_seconds=2.0)
        assert isinstance(result, BudgetResult)
        assert result.completed is True
        assert result.value == 42
        assert result.elapsed_seconds < 2.0

    def test_elapsed_seconds_is_close_to_zero_for_trivial_work(self) -> None:
        result = run_with_budget(lambda: "ok", timeout_seconds=5.0)
        assert result.elapsed_seconds < 1.0

    def test_exception_in_work_propagates(self) -> None:
        def boom() -> None:
            raise RuntimeError("synthetic")

        with pytest.raises(RuntimeError, match="synthetic"):
            run_with_budget(boom, timeout_seconds=2.0)


class TestRunWithBudgetTimeout:
    def test_slow_work_returns_incomplete(self) -> None:
        def slow() -> int:
            time.sleep(3.0)
            return 7

        result = run_with_budget(slow, timeout_seconds=0.5)
        assert result.completed is False
        assert result.value is None
        assert result.elapsed_seconds >= 0.5
        # Allow generous slack on slower runners; the spec says +/- 5s in
        # the original verify step, but for a 0.5 s budget we use 2 s.
        assert result.elapsed_seconds < 2.5

    def test_timeout_does_not_raise(self) -> None:
        """The budget enforcer must surface timeout as data, not as an
        exception — the caller is expected to continue with the next
        candidate."""
        result = run_with_budget(lambda: time.sleep(2.0), timeout_seconds=0.3)
        assert result.completed is False


class TestRunWithBudgetValidation:
    def test_zero_timeout_raises(self) -> None:
        with pytest.raises(ValueError):
            run_with_budget(lambda: 1, timeout_seconds=0)

    def test_negative_timeout_raises(self) -> None:
        with pytest.raises(ValueError):
            run_with_budget(lambda: 1, timeout_seconds=-1.0)


class TestTimeoutFinding:
    def test_shape(self) -> None:
        f = timeout_finding(300.0)
        assert f.rule_id == TIMEOUT_RULE_ID
        assert f.severity == "info"
        assert f.cwe is None
        assert "300s" in f.description
        assert "next entry" in f.description

    def test_default_budget_matches_module_constant(self) -> None:
        f = timeout_finding()
        # The rendered description should mention the default cap value.
        assert f"{DEFAULT_PER_SERVER_BUDGET_SECONDS:.0f}s" in f.description

    def test_candidate_included_in_description(self) -> None:
        f = timeout_finding(60.0, candidate="github.com/owner/repo")
        assert "github.com/owner/repo" in f.description
