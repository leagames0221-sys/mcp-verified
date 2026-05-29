"""Tests for `mcp_verified.output.exporter` — T-14 surface."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from mcp_verified.checks.executors.deterministic import Finding
from mcp_verified.output import (
    AuditDirWriter,
    AuditManifest,
    AuditMetadata,
    Auditor,
    ExportError,
    Target,
    export_audit_db_target,
)


def _populate_target(tmp_path: Path) -> Path:
    """Build a small writer-produced target tree under tmp_path; return target dir."""
    writer = AuditDirWriter(root_dir=tmp_path)
    manifest = AuditManifest(
        audit_id="mcp-verified-2026-05-29-001",
        auditor=Auditor(name="mcp-verified", github="leagames0221-sys"),
        target=Target(
            repo_url="https://github.com/owner/repo",
            commit_hash="abc123",
            version="0.0.1",
        ),
        audit_metadata=AuditMetadata(
            started_at="2026-05-29T12:00:00Z",
            finished_at="2026-05-29T12:01:00Z",
            status="completed",
            time_spent_minutes=1.0,
            verdict="risky",
        ),
        findings_summary={"info": 0, "low": 0, "medium": 0, "high": 1, "critical": 0},
        tools_used=("mcp-verified/0.0.1",),
        compliance_checks=("CWE-798",),
    )
    findings = [
        Finding(
            rule_id="CRED-API-KEY-OPENAI",
            severity="high",
            cwe=798,
            file_path="src/leak.py",
            line_number=12,
            redacted_snippet="sk-X...[REDACTED-44]",
            description="Hard-coded credential.",
        )
    ]
    writer.write(manifest, findings)
    return writer.target_dir(manifest)


# ---------- Happy path ----------


class TestExportHappyPath:
    def test_export_then_extract_round_trip(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        output_path = tmp_path / "export.tar.gz"
        export_audit_db_target(target_dir, output_path)

        # Extract into a fresh dir and assert layout.
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with tarfile.open(output_path, mode="r:gz") as tar:
            tar.extractall(extract_dir)

        expected_audit_dir = (
            extract_dir
            / "audits"
            / "github.com"
            / "owner"
            / "repo"
            / "audits"
            / "mcp-verified-2026-05-29-001"
        )
        assert (expected_audit_dir / "audit-manifest.json").exists()
        assert (expected_audit_dir / "security-assessment.md").exists()
        assert (expected_audit_dir / "findings").is_dir()
        # Target-level metadata.json was also captured.
        target_meta = extract_dir / "audits" / "github.com" / "owner" / "repo" / "metadata.json"
        assert target_meta.exists()

    def test_returns_output_path(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        output_path = tmp_path / "export.tar.gz"
        result = export_audit_db_target(target_dir, output_path)
        assert result == output_path


# ---------- Deterministic tar payload ----------


def _tar_member_table(path: Path) -> list[tuple[str, int, int, int, int, int]]:
    """Return a sorted list of (name, size, mtime, mode, uid, gid) for the
    tarball at `path`. Used for byte-level structural equality assertions
    that ignore the gzip header's filesystem timestamp."""
    with tarfile.open(path, mode="r:gz") as tar:
        rows = [(m.name, m.size, m.mtime, m.mode, m.uid, m.gid) for m in tar.getmembers()]
    return sorted(rows)


def _tar_payload_bytes(path: Path) -> bytes:
    """Concatenate every file member's bytes in name-sorted order."""
    chunks: list[bytes] = []
    with tarfile.open(path, mode="r:gz") as tar:
        members = sorted(tar.getmembers(), key=lambda m: m.name)
        for member in members:
            chunks.append(member.name.encode("utf-8"))
            chunks.append(b"\x00")
            if member.isfile():
                f = tar.extractfile(member)
                if f is not None:
                    chunks.append(f.read())
                    chunks.append(b"\x00")
    return b"".join(chunks)


class TestDeterminism:
    def test_two_exports_produce_identical_member_table(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        out_a = tmp_path / "a.tar.gz"
        out_b = tmp_path / "b.tar.gz"
        export_audit_db_target(target_dir, out_a)
        export_audit_db_target(target_dir, out_b)
        assert _tar_member_table(out_a) == _tar_member_table(out_b)

    def test_two_exports_produce_identical_payload_bytes(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        out_a = tmp_path / "a.tar.gz"
        out_b = tmp_path / "b.tar.gz"
        export_audit_db_target(target_dir, out_a)
        export_audit_db_target(target_dir, out_b)
        assert _tar_payload_bytes(out_a) == _tar_payload_bytes(out_b)

    def test_mtime_zero_by_default(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        out = tmp_path / "x.tar.gz"
        export_audit_db_target(target_dir, out)
        with tarfile.open(out, mode="r:gz") as tar:
            for member in tar.getmembers():
                assert member.mtime == 0
                assert member.uid == 0
                assert member.gid == 0
                assert member.uname == ""
                assert member.gname == ""


# ---------- host/owner/repo override + inference ----------


class TestPrefixInference:
    def test_inference_from_target_dir(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        output_path = tmp_path / "export.tar.gz"
        export_audit_db_target(target_dir, output_path)
        with tarfile.open(output_path, mode="r:gz") as tar:
            names = {m.name for m in tar.getmembers()}
        assert any(n.startswith("audits/github.com/owner/repo/") for n in names)

    def test_explicit_override(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        output_path = tmp_path / "export.tar.gz"
        export_audit_db_target(
            target_dir,
            output_path,
            host="example.org",
            owner="other",
            repo="renamed",
        )
        with tarfile.open(output_path, mode="r:gz") as tar:
            names = {m.name for m in tar.getmembers()}
        assert any(n.startswith("audits/example.org/other/renamed/") for n in names)


# ---------- Error paths ----------


class TestErrorPaths:
    def test_missing_target_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExportError):
            export_audit_db_target(tmp_path / "does-not-exist", tmp_path / "x.tar.gz")

    def test_target_is_file_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(ExportError):
            export_audit_db_target(f, tmp_path / "out.tar.gz")


# ---------- Output dir creation ----------


class TestOutputPath:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target_dir = _populate_target(tmp_path)
        nested = tmp_path / "deep" / "nested" / "export.tar.gz"
        export_audit_db_target(target_dir, nested)
        assert nested.exists()
        assert nested.parent.is_dir()
