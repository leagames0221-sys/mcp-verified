"""Verdict divergence detector.

Implements T-12 / AC-2.5.

When the audit pipeline runs the same target a second time at the same
commit hash and produces a different verdict from the previous run, the
divergence detector emits a `discrepancy.md` alongside the new
`security-assessment.md` so the reviewer can see at a glance which axis
flipped (verdict, severity counts, finding ids).

The detector is split into three pure-ish pieces:

- `detect_divergence(prior_manifest, current_manifest, ...)` returns a
  `DivergenceReport` if and only if the two top-level verdicts disagree,
  otherwise `None`. Same-verdict-with-different-finding-counts is treated
  as expected churn and does not trip the gate.
- `find_latest_prior_audit(target_dir, current_audit_id)` locates the
  most recent prior audit directory under a target so the caller can
  read its manifest. Pure file-system scan, no JSON parsing.
- `write_discrepancy_md(report, path)` writes a small human-readable
  markdown file. Idempotent; the same report against the same path
  produces byte-identical output.

The detector reads the audit-manifest schema from ADR-005 but does not
require all fields — missing fields are reported as `"(unknown)"` in the
discrepancy markdown rather than raising.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DivergenceReport:
    """Describes one (target, commit) pair whose verdict changed between runs.

    All fields are pulled from the two audit manifests being compared.
    When a field is absent from one of the manifests, its value here is
    the literal string `"(unknown)"` so the markdown report remains
    legible.
    """

    target_repo_url: str
    target_commit_hash: str
    prior_audit_id: str
    current_audit_id: str
    prior_verdict: str
    current_verdict: str
    prior_findings_summary: dict[str, int]
    current_findings_summary: dict[str, int]


def _get(d: dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is default:
            return default
    return cur


def detect_divergence(
    prior_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    *,
    prior_verdict: str | None = None,
    current_verdict: str | None = None,
) -> DivergenceReport | None:
    """Return a DivergenceReport iff the two manifests' verdicts disagree.

    The verdicts can be supplied explicitly (the typical pipeline path)
    or read from the manifests at `audit_metadata.verdict` (the storage
    path).
    """
    p_verdict = (
        prior_verdict
        if prior_verdict is not None
        else _get(prior_manifest, "audit_metadata", "verdict", default="(unknown)")
    )
    c_verdict = (
        current_verdict
        if current_verdict is not None
        else _get(current_manifest, "audit_metadata", "verdict", default="(unknown)")
    )
    if p_verdict == c_verdict:
        return None

    return DivergenceReport(
        target_repo_url=str(_get(current_manifest, "target", "repo_url", default="(unknown)")),
        target_commit_hash=str(
            _get(current_manifest, "target", "commit_hash", default="(unknown)")
        ),
        prior_audit_id=str(_get(prior_manifest, "audit_id", default="(unknown)")),
        current_audit_id=str(_get(current_manifest, "audit_id", default="(unknown)")),
        prior_verdict=str(p_verdict),
        current_verdict=str(c_verdict),
        prior_findings_summary=_get(prior_manifest, "findings_summary", default={}) or {},
        current_findings_summary=_get(current_manifest, "findings_summary", default={}) or {},
    )


def find_latest_prior_audit(
    target_dir: Path,
    current_audit_id: str | None = None,
) -> Path | None:
    """Locate the most recent prior audit directory under `target_dir/audits/`.

    Returns the directory path with the highest lex-sorted name (the
    audit-id format `<auditor>-<YYYY-MM-DD>-<NNN>` sorts chronologically
    under standard naming). If `current_audit_id` is provided, that
    directory is excluded from the candidate set.
    """
    audits_dir = target_dir / "audits"
    if not audits_dir.is_dir():
        return None
    candidates = sorted(
        (d for d in audits_dir.iterdir() if d.is_dir() and d.name != current_audit_id),
        key=lambda p: p.name,
    )
    return candidates[-1] if candidates else None


def render_discrepancy_md(report: DivergenceReport) -> str:
    """Render the divergence as a small human-readable markdown document."""
    lines = [
        "# Verdict discrepancy",
        "",
        f"- **Target**: `{report.target_repo_url}`",
        f"- **Commit**: `{report.target_commit_hash}`",
        "",
        "| Axis | Prior run | Current run |",
        "|---|---|---|",
        f"| Audit id | `{report.prior_audit_id}` | `{report.current_audit_id}` |",
        f"| Verdict | **{report.prior_verdict}** | **{report.current_verdict}** |",
    ]
    severities = sorted(set(report.prior_findings_summary) | set(report.current_findings_summary))
    for sev in severities:
        prior = report.prior_findings_summary.get(sev, 0)
        current = report.current_findings_summary.get(sev, 0)
        if prior != current:
            lines.append(f"| Findings: {sev} | {prior} | {current} |")
        else:
            lines.append(f"| Findings: {sev} | {prior} | {current} |")
    lines.append("")
    lines.append(
        "The audit pipeline produced a different top-level verdict on the "
        "second run than on the first against the same `(repo_url, commit_hash)` "
        "target. Investigate before relying on the newer verdict; the most "
        "common causes are non-deterministic LLM responses (Phase 1 mitigates "
        "this with temperature=0 but does not eliminate it) and check-set "
        "version drift."
    )
    return "\n".join(lines) + "\n"


def write_discrepancy_md(report: DivergenceReport, path: Path) -> Path:
    """Write the rendered discrepancy markdown. Returns the path written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_discrepancy_md(report), encoding="utf-8")
    return path


def load_manifest(path: Path) -> dict[str, Any]:
    """Convenience helper: read a JSON manifest from disk into a dict."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"manifest is not a JSON object: {path}")
    return data
