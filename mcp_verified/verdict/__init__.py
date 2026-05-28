"""Verdict aggregation subpackage."""

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

__all__ = [
    "HIGH_SEVERITIES",
    "MEDIUM_SEVERITIES",
    "SEVERITY_ORDER",
    "VERDICT_CAUTION",
    "VERDICT_RISKY",
    "VERDICT_UNKNOWN",
    "VERDICT_VERIFIED",
    "VERDICTS",
    "aggregate_verdict",
    "findings_summary",
]
