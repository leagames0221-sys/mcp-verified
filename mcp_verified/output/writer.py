"""`AuditDirWriter`: orchestrate the audit-db-compatible directory tree.

Implements T-13 / AC-2.1 / AC-2.4.

Given an `AuditManifest` plus a list of `Finding` objects, this module
writes the full per-target audit directory tree:

    <root>/audits/<host>/<owner>/<repo>/
    ├── metadata.json                          (per-target aggregate)
    └── audits/
        └── <audit_id>/
            ├── audit-manifest.json
            ├── security-assessment.md
            └── findings/
                ├── high-001-cred-api-key-openai.md
                └── ...

The host / owner / repo segment is derived from `target.repo_url` so
the same target reused across audit IDs lands under the same path.

The `metadata.json` per-target aggregate records the latest verdict,
the latest audit id, and the cumulative audit count, updated on every
write.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp_verified.checks.executors.deterministic import Finding
from mcp_verified.output.assessment import write_assessment_md
from mcp_verified.output.findings import write_findings_dir
from mcp_verified.output.manifest import AuditManifest, write_manifest_json

MANIFEST_FILENAME = "audit-manifest.json"
ASSESSMENT_FILENAME = "security-assessment.md"
FINDINGS_DIRNAME = "findings"
TARGET_METADATA_FILENAME = "metadata.json"


def target_host_owner_repo(repo_url: str) -> tuple[str, str, str]:
    """Decompose `https://github.com/owner/repo[.git]` into (host, owner, repo).

    Trailing `.git` and trailing slashes are stripped. Raises ValueError
    for anything that does not have at least `<host>/<owner>/<repo>` in
    its URL path.
    """
    parsed = urlparse(repo_url)
    host = parsed.netloc
    parts = [p for p in parsed.path.split("/") if p]
    if not host or len(parts) < 2:
        raise ValueError(f"cannot decompose repo_url: {repo_url!r}")
    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return host, owner, repo


@dataclass(frozen=True)
class AuditDirWriter:
    root_dir: Path
    """Root directory under which `audits/<host>/<owner>/<repo>/...` lands.

    Typically the `--out` flag from the CLI; in tests, a `tmp_path` dir.
    """

    def target_dir(self, manifest: AuditManifest) -> Path:
        host, owner, repo = target_host_owner_repo(manifest.target.repo_url)
        return self.root_dir / "audits" / host / owner / repo

    def audit_dir(self, manifest: AuditManifest) -> Path:
        return self.target_dir(manifest) / "audits" / manifest.audit_id

    def write(
        self,
        manifest: AuditManifest,
        findings: list[Finding],
    ) -> Path:
        """Write the manifest, the assessment, the findings, and update the
        per-target `metadata.json` aggregate. Returns the audit directory path.
        """
        target_dir = self.target_dir(manifest)
        audit_dir = self.audit_dir(manifest)
        audit_dir.mkdir(parents=True, exist_ok=True)
        write_manifest_json(manifest, audit_dir / MANIFEST_FILENAME)
        write_assessment_md(manifest, findings, audit_dir / ASSESSMENT_FILENAME)
        write_findings_dir(findings, audit_dir / FINDINGS_DIRNAME)
        self._update_target_metadata(target_dir, manifest)
        return audit_dir

    def _update_target_metadata(
        self, target_dir: Path, manifest: AuditManifest
    ) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        meta_path = target_dir / TARGET_METADATA_FILENAME
        existing = self._load_existing_metadata(meta_path)
        existing_ids = set(existing.get("audit_ids") or [])
        existing_ids.add(manifest.audit_id)
        audit_ids = sorted(existing_ids)
        payload: dict[str, Any] = {
            "repo_url": manifest.target.repo_url,
            "latest_audit_id": max(audit_ids),
            "latest_verdict": manifest.audit_metadata.verdict,
            "audit_count": len(audit_ids),
            "audit_ids": audit_ids,
        }
        meta_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return meta_path

    @staticmethod
    def _load_existing_metadata(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return data
