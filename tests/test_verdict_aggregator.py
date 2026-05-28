"""Tests for `mcp_verified.verdict.aggregator` — T-11 surface."""

from __future__ import annotations

import pytest

from mcp_verified.checks.executors.deterministic import Finding
from mcp_verified.verdict.aggregator import (
    HIGH_SEVERITIES,
    MEDIUM_SEVERITIES,
    SEVERITY_ORDER,
    VERDICT_CAUTION,
    VERDICT_RISKY,
    VERDICT_UNKNOWN,
    VERDICT_VERIFIED,
    VERDICTS,
    aggregate_verdict,
    findings_summary,
)


def _finding(severity: str, *, rule_id: str = "TEST") -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        cwe=None,
        file_path="src/x.py",
        line_number=1,
        redacted_snippet="",
        description="synthetic",
    )


# ---------- aggregate_verdict: four branches ----------


class TestAggregateVerdict:
    def test_empty_findings_verified(self) -> None:
        assert aggregate_verdict([], audit_completed=True) == VERDICT_VERIFIED

    def test_only_info_findings_verified(self) -> None:
        assert aggregate_verdict([_finding("info"), _finding("info")]) == VERDICT_VERIFIED

    def test_only_low_findings_verified(self) -> None:
        assert aggregate_verdict([_finding("low")]) == VERDICT_VERIFIED

    def test_medium_finding_caution(self) -> None:
        assert aggregate_verdict([_finding("medium")]) == VERDICT_CAUTION

    def test_multiple_medium_caution(self) -> None:
        assert aggregate_verdict([_finding("medium"), _finding("medium")]) == VERDICT_CAUTION

    def test_high_finding_risky(self) -> None:
        assert aggregate_verdict([_finding("high")]) == VERDICT_RISKY

    def test_critical_finding_risky(self) -> None:
        assert aggregate_verdict([_finding("critical")]) == VERDICT_RISKY

    def test_high_beats_medium_low_info(self) -> None:
        findings = [
            _finding("info"),
            _finding("low"),
            _finding("medium"),
            _finding("high"),
        ]
        assert aggregate_verdict(findings) == VERDICT_RISKY

    def test_medium_beats_low_info(self) -> None:
        findings = [_finding("info"), _finding("low"), _finding("medium")]
        assert aggregate_verdict(findings) == VERDICT_CAUTION

    def test_audit_not_completed_yields_unknown(self) -> None:
        # Even with high findings, audit_completed=False forces unknown.
        assert (
            aggregate_verdict([_finding("high")], audit_completed=False)
            == VERDICT_UNKNOWN
        )

    def test_audit_not_completed_with_no_findings_yields_unknown(self) -> None:
        assert aggregate_verdict([], audit_completed=False) == VERDICT_UNKNOWN

    def test_uppercase_severity_treated_case_insensitively(self) -> None:
        assert aggregate_verdict([_finding("HIGH")]) == VERDICT_RISKY
        assert aggregate_verdict([_finding("Medium")]) == VERDICT_CAUTION

    def test_unknown_severity_does_not_downgrade(self) -> None:
        """An unrecognized severity string should be ignored by the
        decision (the bucket is unknown, not high or medium)."""
        assert (
            aggregate_verdict([_finding("totally-made-up")]) == VERDICT_VERIFIED
        )


# ---------- findings_summary ----------


class TestFindingsSummary:
    def test_empty_returns_zeroed_buckets(self) -> None:
        assert findings_summary([]) == {
            "info": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }

    def test_counts_per_severity(self) -> None:
        findings = [
            _finding("high"),
            _finding("high"),
            _finding("medium"),
            _finding("low"),
            _finding("low"),
            _finding("low"),
            _finding("info"),
        ]
        summary = findings_summary(findings)
        assert summary["high"] == 2
        assert summary["medium"] == 1
        assert summary["low"] == 3
        assert summary["info"] == 1
        assert summary["critical"] == 0

    def test_unknown_severity_bucketed_separately(self) -> None:
        findings = [_finding("weird"), _finding("weird"), _finding("medium")]
        summary = findings_summary(findings)
        assert summary["medium"] == 1
        assert summary.get("unknown") == 2

    def test_unknown_bucket_absent_when_no_unknowns(self) -> None:
        summary = findings_summary([_finding("high")])
        assert "unknown" not in summary


# ---------- Constants integrity ----------


class TestConstants:
    def test_severity_order_complete(self) -> None:
        assert SEVERITY_ORDER == ("info", "low", "medium", "high", "critical")

    def test_high_severities_set(self) -> None:
        assert HIGH_SEVERITIES == frozenset({"high", "critical"})

    def test_medium_severities_set(self) -> None:
        assert MEDIUM_SEVERITIES == frozenset({"medium"})

    def test_verdicts_tuple_complete(self) -> None:
        assert VERDICTS == (
            VERDICT_VERIFIED,
            VERDICT_CAUTION,
            VERDICT_RISKY,
            VERDICT_UNKNOWN,
        )

    @pytest.mark.parametrize(
        "verdict,expected",
        [
            (VERDICT_VERIFIED, "verified"),
            (VERDICT_CAUTION, "caution"),
            (VERDICT_RISKY, "risky"),
            (VERDICT_UNKNOWN, "unknown"),
        ],
    )
    def test_verdict_values_are_plain_words(self, verdict: str, expected: str) -> None:
        assert verdict == expected
