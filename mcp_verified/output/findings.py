"""Per-finding markdown writer.

Implements T-13 findings path / AC-2.2.

For each `Finding`, this module produces a small markdown file under
`findings/` named `<severity>-<NNN>-<slug>.md`, where `NNN` is a
3-digit zero-padded sequence within each severity bucket (so a single
audit's `findings/` directory looks like
`high-001-cred-api-key-openai.md`, `high-002-...`, `medium-001-...`,
etc.). The naming convention matches the upstream `audit-db` schema.

The slug is derived from the rule_id, lower-cased, with non-alphanumeric
runs collapsed to single hyphens and truncated to 40 characters.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp_verified.checks.executors.deterministic import Finding

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
SLUG_MAX_LENGTH = 40


def slugify(text: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to hyphens, trim, truncate."""
    lowered = text.lower()
    collapsed = _SLUG_NON_ALNUM.sub("-", lowered).strip("-")
    if not collapsed:
        collapsed = "finding"
    return collapsed[:SLUG_MAX_LENGTH]


def finding_filename(severity: str, sequence: int, rule_id: str) -> str:
    """Build a `<severity>-NNN-<slug>.md` filename."""
    slug = slugify(rule_id)
    return f"{severity.lower()}-{sequence:03d}-{slug}.md"


def render_finding_md(finding: Finding) -> str:
    """Render one finding as a small markdown document.

    The document deliberately echoes the `redacted_snippet` and not any
    raw match — the snippet has already passed through `_redact_match`
    in the executor for credential patterns.
    """
    cwe_line = f"- **CWE**: CWE-{finding.cwe}\n" if finding.cwe is not None else ""
    location = (
        f"- **Location**: `{finding.file_path}:{finding.line_number}`\n"
        if finding.file_path
        else ""
    )
    return (
        f"# {finding.rule_id}\n"
        "\n"
        f"- **Severity**: {finding.severity}\n"
        f"{cwe_line}"
        f"{location}"
        "\n"
        "## Description\n"
        "\n"
        f"{finding.description}\n"
        "\n"
        "## Snippet\n"
        "\n"
        "```\n"
        f"{finding.redacted_snippet}\n"
        "```\n"
    )


def write_findings_dir(findings: list[Finding], findings_dir: Path) -> list[Path]:
    """Write one markdown file per finding under `findings_dir`.

    Findings are first sorted deterministically by (severity, file_path,
    line_number, rule_id); sequence numbers are assigned per severity
    bucket in that order. Returns the list of written paths in write order.
    """
    findings_dir.mkdir(parents=True, exist_ok=True)
    sorted_findings = sorted(
        findings,
        key=lambda f: (f.severity.lower(), f.file_path, f.line_number, f.rule_id),
    )
    counter: dict[str, int] = {}
    written: list[Path] = []
    for finding in sorted_findings:
        severity = finding.severity.lower()
        counter[severity] = counter.get(severity, 0) + 1
        filename = finding_filename(severity, counter[severity], finding.rule_id)
        path = findings_dir / filename
        path.write_text(render_finding_md(finding), encoding="utf-8")
        written.append(path)
    return written
