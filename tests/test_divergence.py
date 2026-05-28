"""Tests for `mcp_verified.verdict.divergence` — T-12 surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_verified.verdict.divergence import (
    DivergenceReport,
    detect_divergence,
    find_latest_prior_audit,
    load_manifest,
    render_discrepancy_md,
    write_discrepancy_md,
)


def _manifest(
    *,
    audit_id: str = "auditor-2026-05-29-001",
    verdict: str = "verified",
    repo_url: str = "https://github.com/owner/repo",
    commit_hash: str = "abc123",
    summary: dict[str, int] | None = None,
) -> dict:
    return {
        "audit_id": audit_id,
        "target": {"repo_url": repo_url, "commit_hash": commit_hash},
        "audit_metadata": {"verdict": verdict},
        "findings_summary": summary
        if summary is not None
        else {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0},
    }


# ---------- detect_divergence ----------


class TestDetectDivergence:
    def test_same_verdict_returns_none(self) -> None:
        prior = _manifest(audit_id="a-2026-05-28-001", verdict="verified")
        current = _manifest(audit_id="a-2026-05-29-001", verdict="verified")
        assert detect_divergence(prior, current) is None

    def test_different_verdict_returns_report(self) -> None:
        prior = _manifest(audit_id="a-2026-05-28-001", verdict="verified")
        current = _manifest(audit_id="a-2026-05-29-001", verdict="risky")
        report = detect_divergence(prior, current)
        assert isinstance(report, DivergenceReport)
        assert report.prior_verdict == "verified"
        assert report.current_verdict == "risky"
        assert report.prior_audit_id == "a-2026-05-28-001"
        assert report.current_audit_id == "a-2026-05-29-001"

    def test_explicit_verdicts_override_manifest(self) -> None:
        prior = _manifest(verdict="verified")
        current = _manifest(verdict="verified")
        report = detect_divergence(
            prior, current, prior_verdict="caution", current_verdict="risky"
        )
        assert report is not None
        assert report.prior_verdict == "caution"
        assert report.current_verdict == "risky"

    def test_target_fields_pulled_from_current(self) -> None:
        prior = _manifest(verdict="verified")
        current = _manifest(
            verdict="risky", repo_url="https://github.com/x/y", commit_hash="deadbeef"
        )
        report = detect_divergence(prior, current)
        assert report is not None
        assert report.target_repo_url == "https://github.com/x/y"
        assert report.target_commit_hash == "deadbeef"

    def test_missing_verdict_in_prior_treated_as_unknown_marker(self) -> None:
        prior = {"audit_id": "p", "target": {}, "audit_metadata": {}}
        current = _manifest(verdict="verified")
        report = detect_divergence(prior, current)
        # Different (one is "(unknown)", one is "verified") -> report should fire.
        assert report is not None
        assert report.prior_verdict == "(unknown)"

    def test_missing_findings_summary_is_empty_dict(self) -> None:
        prior = {"audit_id": "p", "target": {}, "audit_metadata": {"verdict": "verified"}}
        current = _manifest(verdict="risky")
        report = detect_divergence(prior, current)
        assert report is not None
        assert report.prior_findings_summary == {}


# ---------- find_latest_prior_audit ----------


class TestFindLatestPriorAudit:
    def test_returns_none_when_audits_dir_missing(self, tmp_path: Path) -> None:
        assert find_latest_prior_audit(tmp_path) is None

    def test_returns_none_when_no_audit_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "audits").mkdir()
        assert find_latest_prior_audit(tmp_path) is None

    def test_returns_only_audit(self, tmp_path: Path) -> None:
        (tmp_path / "audits" / "auditor-2026-05-28-001").mkdir(parents=True)
        result = find_latest_prior_audit(tmp_path)
        assert result is not None
        assert result.name == "auditor-2026-05-28-001"

    def test_returns_lex_latest(self, tmp_path: Path) -> None:
        (tmp_path / "audits" / "auditor-2026-05-28-001").mkdir(parents=True)
        (tmp_path / "audits" / "auditor-2026-05-29-001").mkdir(parents=True)
        (tmp_path / "audits" / "auditor-2026-05-29-002").mkdir(parents=True)
        result = find_latest_prior_audit(tmp_path)
        assert result is not None
        assert result.name == "auditor-2026-05-29-002"

    def test_excludes_current_audit_id(self, tmp_path: Path) -> None:
        (tmp_path / "audits" / "auditor-2026-05-28-001").mkdir(parents=True)
        (tmp_path / "audits" / "auditor-2026-05-29-001").mkdir(parents=True)
        result = find_latest_prior_audit(
            tmp_path, current_audit_id="auditor-2026-05-29-001"
        )
        assert result is not None
        assert result.name == "auditor-2026-05-28-001"


# ---------- render + write discrepancy markdown ----------


class TestDiscrepancyMarkdown:
    def test_includes_target_and_verdicts(self) -> None:
        report = DivergenceReport(
            target_repo_url="https://github.com/owner/repo",
            target_commit_hash="abc123",
            prior_audit_id="a-2026-05-28-001",
            current_audit_id="a-2026-05-29-001",
            prior_verdict="verified",
            current_verdict="risky",
            prior_findings_summary={"info": 0, "high": 0},
            current_findings_summary={"info": 0, "high": 1},
        )
        md = render_discrepancy_md(report)
        assert "https://github.com/owner/repo" in md
        assert "abc123" in md
        assert "verified" in md
        assert "risky" in md
        assert "a-2026-05-28-001" in md
        assert "a-2026-05-29-001" in md

    def test_idempotent_render(self) -> None:
        report = DivergenceReport(
            target_repo_url="x",
            target_commit_hash="y",
            prior_audit_id="p",
            current_audit_id="c",
            prior_verdict="verified",
            current_verdict="risky",
            prior_findings_summary={},
            current_findings_summary={"high": 1},
        )
        assert render_discrepancy_md(report) == render_discrepancy_md(report)

    def test_write_creates_file_with_expected_content(self, tmp_path: Path) -> None:
        report = DivergenceReport(
            target_repo_url="x",
            target_commit_hash="y",
            prior_audit_id="p",
            current_audit_id="c",
            prior_verdict="verified",
            current_verdict="risky",
            prior_findings_summary={},
            current_findings_summary={"high": 1},
        )
        path = tmp_path / "audits" / "deep" / "discrepancy.md"
        written = write_discrepancy_md(report, path)
        assert written == path
        text = path.read_text(encoding="utf-8")
        assert "Verdict discrepancy" in text
        assert "verified" in text
        assert "risky" in text


# ---------- load_manifest ----------


class TestLoadManifest:
    def test_reads_json_into_dict(self, tmp_path: Path) -> None:
        manifest = _manifest()
        path = tmp_path / "audit-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        loaded = load_manifest(path)
        assert loaded == manifest

    def test_raises_when_not_an_object(self, tmp_path: Path) -> None:
        path = tmp_path / "x.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError):
            load_manifest(path)
