"""Candidate selection: rank registry entries by a deterministic score.

Implements T-03 / AC-1.2.

The Phase 1 score is registry-recency-only by design. The full rationale,
trade-off analysis, and the live-registry probe that established the
absence of popularity fields live in:

- docs/adr/ADR-008-phase1-popularity-signal.md
- docs/evidence/2026-05-29-registry-no-popularity-signal-probe.md

Formula (pinned, revision phase1-v1):

    candidates = [e for e in entries if e.is_latest and e.status == "active"]
    score(entry) = 1.0 / (1.0 + days_since(updatedAt) / 30.0)
    sort key = (-score, name)         # higher score first, name lex for ties

Two runs against the same input produce identical ordering. Changing the
filter or the score function requires bumping SCORE_FORMULA_REVISION below
and recording the bump in audit-manifest.json `audit_metadata.tools_used`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from mcp_verified.registry.client import RegistryEntry

SCORE_FORMULA_REVISION = "phase1-v1"
FRESHNESS_HALF_LIFE_DAYS = 30.0
ACTIVE_STATUS = "active"


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse an RFC 3339 timestamp tolerantly.

    The registry emits timestamps like '2026-04-13T17:32:20.852269Z'. We
    accept the trailing 'Z' (UTC) and any sub-second precision Python's
    fromisoformat supports.
    """
    if not ts:
        return None
    s = ts
    # Python 3.11+ fromisoformat accepts 'Z' since 3.11, but be explicit
    # for robustness against older runtimes that might import this module.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _days_since(timestamp: str, *, now: datetime | None = None) -> float | None:
    """Days elapsed between `timestamp` and `now` (default: current UTC).

    Returns None if the timestamp is unparseable. Returns 0.0 for future
    timestamps (clock skew tolerance) rather than negative.
    """
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    reference = now if now is not None else datetime.now(UTC)
    delta = reference - parsed
    days = delta.total_seconds() / 86400.0
    return max(days, 0.0)


def score_entry(entry: RegistryEntry, *, now: datetime | None = None) -> float:
    """Compute the phase1-v1 freshness score for a single entry.

    Range: (0.0, 1.0]. Score 1.0 means "updated right now"; score decays
    smoothly with a 30-day half-life equivalent (score(30 days) = 0.5).
    Entries with an unparseable updatedAt score 0.0.
    """
    days = _days_since(entry.updated_at, now=now)
    if days is None:
        return 0.0
    return 1.0 / (1.0 + days / FRESHNESS_HALF_LIFE_DAYS)


@dataclass(frozen=True)
class ScoredCandidate:
    """An entry plus its score and the formula revision used to produce it."""

    entry: RegistryEntry
    score: float
    formula_revision: str

    @property
    def name(self) -> str:
        return self.entry.name


class CandidateScorer:
    """Filter + score + rank a list of RegistryEntry into top-N candidates.

    Pure function-of-input under a fixed `now` argument: same inventory,
    same `now`, same ordering. The default `now` is the current UTC time,
    so production runs are not bit-identical across invocations spaced
    days apart; tests pin `now` for determinism.
    """

    def __init__(
        self,
        *,
        formula_revision: str = SCORE_FORMULA_REVISION,
        require_latest: bool = True,
        active_status: str = ACTIVE_STATUS,
    ) -> None:
        self.formula_revision = formula_revision
        self.require_latest = require_latest
        self.active_status = active_status

    def candidates(
        self, entries: Iterable[RegistryEntry], *, now: datetime | None = None
    ) -> list[ScoredCandidate]:
        """Filter, score, and sort. Returns all candidates, not just top-N."""
        filtered = [
            e
            for e in entries
            if (not self.require_latest or e.is_latest) and e.status == self.active_status
        ]
        scored = [
            ScoredCandidate(
                entry=e, score=score_entry(e, now=now), formula_revision=self.formula_revision
            )
            for e in filtered
        ]
        # Sort: higher score first; lex on name for tiebreak (deterministic).
        scored.sort(key=lambda c: (-c.score, c.name))
        return scored

    def top_n(
        self, entries: Iterable[RegistryEntry], n: int, *, now: datetime | None = None
    ) -> list[ScoredCandidate]:
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        return self.candidates(entries, now=now)[:n]


def top_candidates(
    entries: Iterable[RegistryEntry], n: int, *, now: datetime | None = None
) -> list[ScoredCandidate]:
    """Convenience: default CandidateScorer + top-N selection."""
    return CandidateScorer().top_n(entries, n, now=now)
