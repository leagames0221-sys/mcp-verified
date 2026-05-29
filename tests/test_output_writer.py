"""Tests for `mcp_verified.output.*` — T-13 surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_verified.checks.executors.deterministic import Finding
from mcp_verified.output import (
    AuditDirWriter,
    AuditManifest,
    AuditMetadata,
    Auditor,
    Target,
    finding_filename,
    render_assessment_md,
    render_finding_md,
    slugify,
    target_host_owner_repo,
    to_manifest_dict,
    write_findings_dir,
    write_manifest_json,
)


def _finding(
    severity: str = "high",
    *,
    rule_id: str = "CRED-API-KEY-OPENAI",
    file_path: str = "src/leak.py",
    line_number: int = 42,
    cwe: int | None = 798,
    description: str = "Hard-coded credential detected.",
    snippet: str = "sk-X...[REDACTED-44]",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        cwe=cwe,
        file_path=file_path,
        line_number=line_number,
        redacted_snippet=snippet,
        description=description,
    )


def _manifest(
    *,
    audit_id: str = "mcp-verified-2026-05-29-001",
    repo_url: str = "https://github.com/owner/repo",
    commit_hash: str = "abc123def456",
    verdict: str = "risky",
    summary: dict[str, int] | None = None,
) -> AuditManifest:
    return AuditManifest(
        audit_id=audit_id,
        auditor=Auditor(name="mcp-verified", github="leagames0221-sys", org=""),
        target=Target(repo_url=repo_url, commit_hash=commit_hash, version="0.0.1"),
        audit_metadata=AuditMetadata(
            started_at="2026-05-29T12:00:00Z",
            finished_at="2026-05-29T12:03:00Z",
            status="completed",
            time_spent_minutes=3.0,
            verdict=verdict,
            integrity={"tree_sha256": "0" * 64},
        ),
        findings_summary=summary
        if summary is not None
        else {"info": 0, "low": 0, "medium": 0, "high": 1, "critical": 0},
        tools_used=("mcp-verified/0.0.1", "ollama/gemma3:4b"),
        compliance_checks=("CWE-798",),
    )


# ---------- slugify + finding_filename ----------


class TestSlugify:
    def test_lowercases_and_hyphenates(self) -> None:
        assert slugify("CRED API KEY OPENAI") == "cred-api-key-openai"

    def test_collapses_non_alphanumeric_runs(self) -> None:
        assert slugify("a__b!!c#d") == "a-b-c-d"

    def test_trims_leading_trailing_hyphens(self) -> None:
        assert slugify("---abc---") == "abc"

    def test_empty_input_falls_back_to_finding(self) -> None:
        assert slugify("") == "finding"
        assert slugify("!!!") == "finding"

    def test_truncates_long_inputs(self) -> None:
        long = "a" * 100
        assert len(slugify(long)) == 40


class TestFindingFilename:
    def test_format(self) -> None:
        assert (
            finding_filename("high", 1, "CRED-API-KEY-OPENAI") == "high-001-cred-api-key-openai.md"
        )

    def test_zero_padded_sequence(self) -> None:
        assert finding_filename("medium", 12, "X") == "medium-012-x.md"


# ---------- Manifest writer ----------


class TestManifestWriter:
    def test_to_manifest_dict_includes_all_fields(self) -> None:
        m = _manifest()
        d = to_manifest_dict(m)
        assert d["audit_id"] == m.audit_id
        assert d["auditor"]["name"] == "mcp-verified"
        assert d["target"]["repo_url"] == "https://github.com/owner/repo"
        assert d["audit_metadata"]["verdict"] == "risky"
        assert d["findings_summary"]["high"] == 1
        assert d["tools_used"] == ["mcp-verified/0.0.1", "ollama/gemma3:4b"]
        assert d["compliance_checks"] == ["CWE-798"]

    def test_write_manifest_is_deterministic(self, tmp_path: Path) -> None:
        m = _manifest()
        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        write_manifest_json(m, path_a)
        write_manifest_json(m, path_b)
        assert path_a.read_bytes() == path_b.read_bytes()

    def test_write_manifest_sorts_keys(self, tmp_path: Path) -> None:
        m = _manifest()
        path = tmp_path / "audit-manifest.json"
        write_manifest_json(m, path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        keys = list(loaded.keys())
        assert keys == sorted(keys)


# ---------- Findings dir writer ----------


class TestFindingsDir:
    def test_per_severity_sequence(self, tmp_path: Path) -> None:
        findings = [
            _finding(severity="high", rule_id="A"),
            _finding(severity="high", rule_id="B"),
            _finding(severity="medium", rule_id="C"),
        ]
        written = write_findings_dir(findings, tmp_path)
        names = sorted(p.name for p in written)
        assert names == [
            "high-001-a.md",
            "high-002-b.md",
            "medium-001-c.md",
        ]

    def test_render_finding_md_contains_key_fields(self) -> None:
        f = _finding()
        text = render_finding_md(f)
        assert "CRED-API-KEY-OPENAI" in text
        assert "high" in text
        assert "CWE-798" in text
        assert "src/leak.py:42" in text
        assert "Hard-coded credential" in text
        # The snippet must be the redacted one, never the literal credential.
        assert "REDACTED-44" in text


# ---------- Assessment renderer ----------


class TestAssessment:
    def test_includes_target_and_verdict(self) -> None:
        m = _manifest()
        text = render_assessment_md(m, [_finding()])
        assert "https://github.com/owner/repo" in text
        assert "abc123def456" in text
        assert "**risky**" in text
        assert "mcp-verified" in text
        assert "CRED-API-KEY-OPENAI" in text

    def test_renders_empty_findings_branch(self) -> None:
        m = _manifest(verdict="verified")
        text = render_assessment_md(m, [])
        assert "No findings were recorded" in text


# ---------- AuditDirWriter ----------


class TestAuditDirWriter:
    def test_writes_full_directory_tree(self, tmp_path: Path) -> None:
        writer = AuditDirWriter(root_dir=tmp_path)
        manifest = _manifest()
        findings = [
            _finding(severity="high", rule_id="X"),
            _finding(severity="medium", rule_id="Y"),
        ]
        audit_dir = writer.write(manifest, findings)
        # Manifest
        assert (audit_dir / "audit-manifest.json").exists()
        # Assessment
        assert (audit_dir / "security-assessment.md").exists()
        # Findings dir
        finding_files = sorted((audit_dir / "findings").iterdir())
        assert len(finding_files) == 2
        # Target metadata.json one level up
        target_dir = audit_dir.parent.parent
        assert (target_dir / "metadata.json").exists()

    def test_target_metadata_records_latest_verdict_and_id(self, tmp_path: Path) -> None:
        writer = AuditDirWriter(root_dir=tmp_path)
        m1 = _manifest(audit_id="mcp-verified-2026-05-28-001", verdict="verified")
        writer.write(m1, [])
        m2 = _manifest(audit_id="mcp-verified-2026-05-29-001", verdict="risky")
        writer.write(m2, [_finding()])
        target_dir = writer.target_dir(m2)
        meta = json.loads((target_dir / "metadata.json").read_text(encoding="utf-8"))
        assert meta["audit_count"] == 2
        assert meta["latest_audit_id"] == "mcp-verified-2026-05-29-001"
        assert meta["latest_verdict"] == "risky"
        assert sorted(meta["audit_ids"]) == [
            "mcp-verified-2026-05-28-001",
            "mcp-verified-2026-05-29-001",
        ]

    def test_audit_dir_path_layout(self, tmp_path: Path) -> None:
        writer = AuditDirWriter(root_dir=tmp_path)
        manifest = _manifest(
            audit_id="auditor-2026-05-29-001",
            repo_url="https://github.com/octo/example.git",
        )
        audit_dir = writer.audit_dir(manifest)
        expected = (
            tmp_path
            / "audits"
            / "github.com"
            / "octo"
            / "example"
            / "audits"
            / "auditor-2026-05-29-001"
        )
        assert audit_dir == expected


# ---------- target_host_owner_repo ----------


class TestTargetDecomposition:
    @pytest.mark.parametrize(
        "url,expected",
        [
            (
                "https://github.com/owner/repo",
                ("github.com", "owner", "repo"),
            ),
            (
                "https://github.com/owner/repo.git",
                ("github.com", "owner", "repo"),
            ),
            (
                "https://github.com/owner/repo/",
                ("github.com", "owner", "repo"),
            ),
        ],
    )
    def test_canonical_urls(self, url: str, expected: tuple[str, str, str]) -> None:
        assert target_host_owner_repo(url) == expected

    @pytest.mark.parametrize("url", ["", "https://github.com/", "not a url"])
    def test_invalid_url_raises(self, url: str) -> None:
        with pytest.raises(ValueError):
            target_host_owner_repo(url)
