"""`security-assessment.md` writer.

Implements T-13 assessment path.

The assessment is the top-level human-readable summary for one (target,
commit, audit-run) tuple. It quotes the target identity, the run
metadata, the verdict, and the per-severity finding counts; it includes
a compact table of every finding's rule_id and location so a reviewer
can scan the entire run in one screen.
"""

from __future__ import annotations

from pathlib import Path

from mcp_verified.checks.executors.deterministic import Finding
from mcp_verified.output.manifest import AuditManifest


def render_assessment_md(manifest: AuditManifest, findings: list[Finding]) -> str:
    target = manifest.target
    md = manifest.audit_metadata
    auditor = manifest.auditor
    summary = manifest.findings_summary

    lines: list[str] = [
        "# Security assessment",
        "",
        f"- **Target**: `{target.repo_url}`",
        f"- **Commit**: `{target.commit_hash}`",
        f"- **Audit id**: `{manifest.audit_id}`",
        f"- **Auditor**: {auditor.name} ({auditor.github})",
        f"- **Verdict**: **{md.verdict}**",
        f"- **Status**: {md.status}",
        f"- **Started**: {md.started_at}",
        f"- **Finished**: {md.finished_at}",
        f"- **Time spent**: {md.time_spent_minutes:.2f} min",
        "",
        "## Findings summary",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for severity in ("critical", "high", "medium", "low", "info", "unknown"):
        if severity in summary:
            lines.append(f"| {severity} | {summary[severity]} |")
    if not findings:
        lines.append("")
        lines.append(
            "No findings were recorded against this target by the Phase 1 check set."
        )
    else:
        lines.append("")
        lines.append("## Findings")
        lines.append("")
        lines.append("| Rule | Severity | Location | CWE |")
        lines.append("|---|---|---|---|")
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                f.severity.lower(),
                f.file_path,
                f.line_number,
                f.rule_id,
            ),
        )
        for f in sorted_findings:
            cwe = f"CWE-{f.cwe}" if f.cwe is not None else "(none)"
            location = (
                f"`{f.file_path}:{f.line_number}`" if f.file_path else "(none)"
            )
            lines.append(
                f"| `{f.rule_id}` | {f.severity} | {location} | {cwe} |"
            )
    lines.append("")
    lines.append("## Tools used")
    lines.append("")
    if manifest.tools_used:
        for tool in manifest.tools_used:
            lines.append(f"- `{tool}`")
    else:
        lines.append("- (none recorded)")
    if manifest.compliance_checks:
        lines.append("")
        lines.append("## Compliance checks")
        lines.append("")
        for ref in manifest.compliance_checks:
            lines.append(f"- `{ref}`")
    return "\n".join(lines) + "\n"


def write_assessment_md(
    manifest: AuditManifest, findings: list[Finding], path: Path
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_assessment_md(manifest, findings), encoding="utf-8")
    return path
