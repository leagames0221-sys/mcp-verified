"""Tests for `mcp_verified.discovery.candidates` — T-03 acceptance surface."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcp_verified.discovery.candidates import (
    FRESHNESS_HALF_LIFE_DAYS,
    SCORE_FORMULA_REVISION,
    CandidateScorer,
    ScoredCandidate,
    score_entry,
    top_candidates,
)
from mcp_verified.registry.client import RegistryEntry, parse_response

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-snapshot-2026-05-28.json"
PINNED_NOW = datetime(2026, 5, 29, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def registry_entries() -> list[RegistryEntry]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    entries, _ = parse_response(payload)
    return entries


def _make_entry(
    name: str,
    *,
    updated_at: str,
    is_latest: bool = True,
    status: str = "active",
    repository_url: str | None = "https://github.com/example/x",
    repository_source: str | None = "github",
) -> RegistryEntry:
    return RegistryEntry(
        name=name,
        version="1.0.0",
        description="",
        title=None,
        repository_url=repository_url,
        repository_source=repository_source,
        remotes=(),
        status=status,
        is_latest=is_latest,
        published_at=updated_at,
        updated_at=updated_at,
        raw={},
    )


# ---------- score_entry: freshness formula behaviour ----------


class TestScoreEntry:
    def test_score_now_equals_one(self) -> None:
        e = _make_entry("a/x", updated_at="2026-05-29T00:00:00Z")
        assert score_entry(e, now=PINNED_NOW) == pytest.approx(1.0)

    def test_score_at_half_life_equals_half(self) -> None:
        e = _make_entry("a/x", updated_at="2026-04-29T00:00:00Z")  # 30 d ago
        assert score_entry(e, now=PINNED_NOW) == pytest.approx(0.5, rel=1e-6)

    def test_score_decays_with_age(self) -> None:
        recent = _make_entry("a/recent", updated_at="2026-05-28T00:00:00Z")
        old = _make_entry("a/old", updated_at="2025-05-28T00:00:00Z")
        assert score_entry(recent, now=PINNED_NOW) > score_entry(old, now=PINNED_NOW)

    def test_score_returns_zero_for_unparseable_timestamp(self) -> None:
        e = _make_entry("a/x", updated_at="not a timestamp")
        assert score_entry(e, now=PINNED_NOW) == 0.0

    def test_score_clamps_future_to_now(self) -> None:
        """Clock skew tolerance: future timestamps score as if they were 'now'."""
        e = _make_entry("a/x", updated_at="2027-01-01T00:00:00Z")
        assert score_entry(e, now=PINNED_NOW) == pytest.approx(1.0)

    def test_half_life_constant_is_thirty_days(self) -> None:
        assert FRESHNESS_HALF_LIFE_DAYS == 30.0


# ---------- CandidateScorer: filter + sort + tiebreak ----------


class TestCandidateScorerFilter:
    def test_excludes_non_latest(self) -> None:
        entries = [
            _make_entry("a/x", updated_at="2026-05-28T00:00:00Z", is_latest=False),
            _make_entry("a/y", updated_at="2026-05-28T00:00:00Z", is_latest=True),
        ]
        result = CandidateScorer().candidates(entries, now=PINNED_NOW)
        assert [c.name for c in result] == ["a/y"]

    def test_excludes_non_active(self) -> None:
        entries = [
            _make_entry("a/x", updated_at="2026-05-28T00:00:00Z", status="deprecated"),
            _make_entry("a/y", updated_at="2026-05-28T00:00:00Z", status="active"),
        ]
        result = CandidateScorer().candidates(entries, now=PINNED_NOW)
        assert [c.name for c in result] == ["a/y"]

    def test_require_latest_can_be_disabled(self) -> None:
        entries = [
            _make_entry("a/x", updated_at="2026-05-28T00:00:00Z", is_latest=False),
            _make_entry("a/y", updated_at="2026-05-28T00:00:00Z", is_latest=True),
        ]
        result = CandidateScorer(require_latest=False).candidates(entries, now=PINNED_NOW)
        assert {c.name for c in result} == {"a/x", "a/y"}


class TestCandidateScorerOrdering:
    def test_sorts_by_score_desc(self) -> None:
        entries = [
            _make_entry("z/old", updated_at="2025-12-01T00:00:00Z"),
            _make_entry("a/new", updated_at="2026-05-28T00:00:00Z"),
            _make_entry("m/mid", updated_at="2026-04-15T00:00:00Z"),
        ]
        result = CandidateScorer().candidates(entries, now=PINNED_NOW)
        names = [c.name for c in result]
        assert names == ["a/new", "m/mid", "z/old"]

    def test_ties_broken_by_name_lex(self) -> None:
        # Three entries with identical timestamps tie on score.
        entries = [
            _make_entry("c/x", updated_at="2026-05-28T00:00:00Z"),
            _make_entry("a/x", updated_at="2026-05-28T00:00:00Z"),
            _make_entry("b/x", updated_at="2026-05-28T00:00:00Z"),
        ]
        result = CandidateScorer().candidates(entries, now=PINNED_NOW)
        assert [c.name for c in result] == ["a/x", "b/x", "c/x"]

    def test_deterministic_across_two_runs(self) -> None:
        """Two runs over the same input must produce identical ordering (AC-1.2)."""
        entries = [
            _make_entry(f"server/{i}", updated_at=f"2026-05-{(i % 28) + 1:02d}T00:00:00Z")
            for i in range(20)
        ]
        run1 = [c.name for c in CandidateScorer().candidates(entries, now=PINNED_NOW)]
        run2 = [c.name for c in CandidateScorer().candidates(entries, now=PINNED_NOW)]
        assert run1 == run2


class TestCandidateScorerTopN:
    def test_top_n_truncates(self) -> None:
        entries = [
            _make_entry(f"server/{i}", updated_at=f"2026-05-{(i % 28) + 1:02d}T00:00:00Z")
            for i in range(20)
        ]
        result = CandidateScorer().top_n(entries, n=5, now=PINNED_NOW)
        assert len(result) == 5

    def test_top_n_zero_returns_empty(self) -> None:
        entries = [_make_entry("a/x", updated_at="2026-05-28T00:00:00Z")]
        assert CandidateScorer().top_n(entries, n=0, now=PINNED_NOW) == []

    def test_top_n_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            CandidateScorer().top_n([], n=-1, now=PINNED_NOW)

    def test_top_n_larger_than_pool_returns_all(self) -> None:
        entries = [_make_entry("a/x", updated_at="2026-05-28T00:00:00Z")]
        result = CandidateScorer().top_n(entries, n=100, now=PINNED_NOW)
        assert len(result) == 1


# ---------- Output dataclass + module convenience ----------


class TestScoredCandidate:
    def test_records_formula_revision(self) -> None:
        entries = [_make_entry("a/x", updated_at="2026-05-28T00:00:00Z")]
        result = CandidateScorer().candidates(entries, now=PINNED_NOW)
        assert len(result) == 1
        assert isinstance(result[0], ScoredCandidate)
        assert result[0].formula_revision == SCORE_FORMULA_REVISION
        assert result[0].name == "a/x"


def test_top_candidates_convenience() -> None:
    entries = [
        _make_entry("a/recent", updated_at="2026-05-28T00:00:00Z"),
        _make_entry("a/old", updated_at="2025-01-01T00:00:00Z"),
    ]
    result = top_candidates(entries, n=1, now=PINNED_NOW)
    assert len(result) == 1
    assert result[0].name == "a/recent"


# ---------- Fixture-based smoke test against the real registry snapshot ----------


def test_scores_real_registry_fixture(registry_entries: list[RegistryEntry]) -> None:
    """The 2026-05-28 fixture should produce a non-empty, deterministically
    sorted candidate list."""
    result = top_candidates(registry_entries, n=10, now=PINNED_NOW)
    # Fixture has 3 entries total: ac.inference.sh/mcp v1.0.0 (isLatest=False),
    # ac.inference.sh/mcp v1.0.1 (isLatest=True), ac.tandem/docs-mcp v0.3.0 (isLatest=False).
    # Only the v1.0.1 should pass the require_latest filter.
    assert len(result) == 1
    assert result[0].name == "ac.inference.sh/mcp"
    assert result[0].entry.version == "1.0.1"
