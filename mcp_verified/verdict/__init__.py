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
from mcp_verified.verdict.divergence import (
    DivergenceReport,
    detect_divergence,
    find_latest_prior_audit,
    load_manifest,
    render_discrepancy_md,
    write_discrepancy_md,
)

__all__ = [
    "DivergenceReport",
    "HIGH_SEVERITIES",
    "MEDIUM_SEVERITIES",
    "SEVERITY_ORDER",
    "VERDICT_CAUTION",
    "VERDICT_RISKY",
    "VERDICT_UNKNOWN",
    "VERDICT_VERIFIED",
    "VERDICTS",
    "aggregate_verdict",
    "detect_divergence",
    "find_latest_prior_audit",
    "findings_summary",
    "load_manifest",
    "render_discrepancy_md",
    "write_discrepancy_md",
]
