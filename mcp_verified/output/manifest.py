"""`audit-manifest.json` writer.

Implements T-13 manifest path / AC-2.3 / AC-5.5 / AC-6.1 / ADR-005.

The schema mirrors the upstream Cloud Security Alliance `audit-db`
manifest exactly so the same JSON document is consumable by both
projects without translation:

- `audit_id`            — `<auditor>-<YYYY-MM-DD>-<NNN>`.
- `auditor`             — `{name, github, org}`.
- `target`              — `{repo_url, commit_hash, version}`.
- `audit_metadata`      — `{started_at, finished_at, status,
                            time_spent_minutes, verdict, integrity}`.
- `findings_summary`    — severity counts (stable shape).
- `tools_used`          — list of strings (e.g. `mcp-verified/0.1.0`,
                          `ollama/gemma3:4b`, `mock-provider`).
- `compliance_checks`   — list of strings (CWE tags, framework refs).

Writes use sorted JSON keys and a fixed 2-space indent so two runs of
the same audit produce byte-identical bytes — critical for the
divergence detector (T-12).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Auditor:
    name: str
    github: str
    org: str = ""


@dataclass(frozen=True)
class Target:
    repo_url: str
    commit_hash: str
    version: str = ""


@dataclass(frozen=True)
class AuditMetadata:
    started_at: str  # ISO 8601, e.g. "2026-05-29T12:34:56Z"
    finished_at: str
    status: str  # "completed" | "timeout" | "error"
    time_spent_minutes: float
    verdict: str  # "verified" | "caution" | "risky" | "unknown"
    integrity: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditManifest:
    audit_id: str
    auditor: Auditor
    target: Target
    audit_metadata: AuditMetadata
    findings_summary: dict[str, int]
    tools_used: tuple[str, ...] = ()
    compliance_checks: tuple[str, ...] = ()


def to_manifest_dict(manifest: AuditManifest) -> dict[str, Any]:
    """Convert an AuditManifest to a plain dict ready for JSON serialization.

    Tuples become lists so JSON consumers see arrays.
    """
    data = asdict(manifest)
    data["tools_used"] = list(manifest.tools_used)
    data["compliance_checks"] = list(manifest.compliance_checks)
    return data


def write_manifest_json(manifest: AuditManifest, path: Path) -> Path:
    """Write the manifest as deterministic JSON.

    Sorted keys + 2-space indent + trailing newline. Same input -> same bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = to_manifest_dict(manifest)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
