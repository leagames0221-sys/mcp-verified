"""Verdict aggregator: pure function from `list[Finding]` to a top-level tier.

Implements T-11 / F-002 / AC-2.2 / ADR-006.

Verdict semantics (ADR-006 plain-word naming, NOT ordinal stars):

- **verified** — Audit ran to completion and no `medium`-or-higher finding
  was recorded against the candidate. `low` and `info` findings (such as
  the synthetic `CHECK-RUN-ERROR-*` and `CHECK-RUN-TIMEOUT` markers) do
  not downgrade the verdict.
- **caution** — At least one `medium` finding; no `high` or `critical`.
- **risky** — At least one `high` or `critical` finding.
- **unknown** — The audit could not complete (the caller signals this via
  the `audit_completed=False` argument). The verdict carries no claim
  about the underlying server.

The two functions here are pure: same inputs produce the same outputs,
no I/O, no global state. They are unit-testable in isolation.
"""

from __future__ import annotations

from collections.abc import Iterable

from mcp_verified.checks.executors.deterministic import Finding

VERDICT_VERIFIED = "verified"
VERDICT_CAUTION = "caution"
VERDICT_RISKY = "risky"
VERDICT_UNKNOWN = "unknown"
VERDICTS: tuple[str, ...] = (
    VERDICT_VERIFIED,
    VERDICT_CAUTION,
    VERDICT_RISKY,
    VERDICT_UNKNOWN,
)

# Canonical severity buckets used in `findings_summary` and `aggregate_verdict`.
SEVERITY_ORDER: tuple[str, ...] = ("info", "low", "medium", "high", "critical")
HIGH_SEVERITIES: frozenset[str] = frozenset({"high", "critical"})
MEDIUM_SEVERITIES: frozenset[str] = frozenset({"medium"})


def aggregate_verdict(
    findings: Iterable[Finding],
    *,
    audit_completed: bool = True,
) -> str:
    """Decide the top-level verdict from a finding list + completion flag.

    The rule is documented in the module docstring. The `audit_completed`
    flag is the caller's signal that the audit pipeline produced
    meaningful coverage; setting it to False (e.g., the candidate's
    source was unreachable per AC-1.4) yields `unknown` regardless of
    the finding list.
    """
    if not audit_completed:
        return VERDICT_UNKNOWN
    seen_high = False
    seen_medium = False
    for finding in findings:
        severity = (finding.severity or "").lower()
        if severity in HIGH_SEVERITIES:
            seen_high = True
            break  # `risky` cannot be downgraded by anything below it.
        if severity in MEDIUM_SEVERITIES:
            seen_medium = True
    if seen_high:
        return VERDICT_RISKY
    if seen_medium:
        return VERDICT_CAUTION
    return VERDICT_VERIFIED


def findings_summary(findings: Iterable[Finding]) -> dict[str, int]:
    """Severity counts for `audit-manifest.json` `findings_summary`.

    Always returns a dict whose keys are the canonical severities in
    `SEVERITY_ORDER`, even when a bucket is empty (downstream JSON
    consumers benefit from a stable shape). Unknown severity strings
    are counted under an `unknown` key only if any are observed; if
    none are observed, the `unknown` key is omitted.
    """
    summary: dict[str, int] = {severity: 0 for severity in SEVERITY_ORDER}
    unknown_count = 0
    for finding in findings:
        severity = (finding.severity or "").lower()
        if severity in summary:
            summary[severity] += 1
        else:
            unknown_count += 1
    if unknown_count:
        summary["unknown"] = unknown_count
    return summary
