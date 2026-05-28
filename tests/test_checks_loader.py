"""Tests for `mcp_verified.checks.loader` — T-05 acceptance surface."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mcp_verified.checks.loader import (
    ACTIVE_STATUS,
    CheckDefinition,
    CheckLoadError,
    load_check,
    load_checks,
    sha256_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "checks"


class TestSha256File:
    def test_matches_standalone_hash(self, tmp_path: Path) -> None:
        path = tmp_path / "x.md"
        payload = b"hello-loader-fixture-bytes"
        path.write_bytes(payload)
        expected = hashlib.sha256(payload).hexdigest()
        assert sha256_file(path) == expected

    def test_handles_large_files_in_chunks(self, tmp_path: Path) -> None:
        path = tmp_path / "x.md"
        # ~256 KiB to force multiple read iterations through the loop.
        payload = b"x" * (256 * 1024)
        path.write_bytes(payload)
        assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


class TestLoadCheckActive:
    def test_loads_active_fixture(self) -> None:
        path = FIXTURES_DIR / "sample-active.md"
        check = load_check(path)
        assert isinstance(check, CheckDefinition)
        assert check.id == "sample-active"
        assert check.title == "Sample Active Credential Check"
        assert check.status == ACTIVE_STATUS
        assert check.priority == "high"
        assert check.cwe == (798, 200)
        assert check.cwe_primary == 798
        assert "security" in check.tags
        assert "credentials" in check.tags

    def test_sha256_matches_file_bytes(self) -> None:
        path = FIXTURES_DIR / "sample-active.md"
        check = load_check(path)
        assert check is not None
        assert check.sha256 == sha256_file(path)
        assert len(check.sha256) == 64

    def test_h2_sections_extracted(self) -> None:
        path = FIXTURES_DIR / "sample-active.md"
        check = load_check(path)
        assert check is not None
        assert "Purpose" in check.sections
        assert "Why This Matters" in check.sections
        assert "For AI Assistants: Automated Analysis" in check.sections
        assert "For Humans: Manual Assessment Steps" in check.sections
        assert "Implementation Examples" in check.sections
        assert "minimal active check" in check.sections["Purpose"]

    def test_raw_frontmatter_preserved(self) -> None:
        path = FIXTURES_DIR / "sample-active.md"
        check = load_check(path)
        assert check is not None
        assert check.raw_frontmatter["title"] == check.title
        assert check.raw_frontmatter["cwe"] == [798, 200]


class TestLoadCheckSkipsInactive:
    def test_deprecated_status_returns_none(self) -> None:
        path = FIXTURES_DIR / "sample-deprecated.md"
        assert load_check(path) is None


class TestLoadCheckErrors:
    def test_missing_frontmatter_raises(self) -> None:
        with pytest.raises(CheckLoadError):
            load_check(FIXTURES_DIR / "sample-no-frontmatter.md")

    def test_malformed_block_list_raises(self) -> None:
        with pytest.raises(CheckLoadError):
            load_check(FIXTURES_DIR / "sample-malformed.md")

    def test_missing_status_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "no-status.md"
        path.write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
        with pytest.raises(CheckLoadError):
            load_check(path)

    def test_missing_title_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "no-title.md"
        path.write_text("---\nstatus: active\n---\nbody\n", encoding="utf-8")
        with pytest.raises(CheckLoadError):
            load_check(path)

    def test_non_integer_cwe_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad-cwe.md"
        path.write_text(
            "---\ntitle: x\nstatus: active\ncwe: [798, abc]\n---\nbody\n",
            encoding="utf-8",
        )
        with pytest.raises(CheckLoadError):
            load_check(path)


class TestLoadChecks:
    def test_loads_only_active_from_fixtures(self) -> None:
        with pytest.raises(CheckLoadError):
            # The fixture directory contains malformed.md and no-frontmatter.md
            # which raise on load. Test against a curated tmp dir instead.
            load_checks(FIXTURES_DIR)

    def test_curated_directory_returns_sorted_actives(self, tmp_path: Path) -> None:
        # Copy only the well-formed fixtures into the curated dir.
        active = (FIXTURES_DIR / "sample-active.md").read_text(encoding="utf-8")
        deprecated = (FIXTURES_DIR / "sample-deprecated.md").read_text(encoding="utf-8")
        (tmp_path / "b-active.md").write_text(active, encoding="utf-8")
        (tmp_path / "a-deprecated.md").write_text(deprecated, encoding="utf-8")
        (tmp_path / "c-active.md").write_text(active, encoding="utf-8")

        result = load_checks(tmp_path)
        ids = [c.id for c in result]
        # Only the two active files; sorted by id.
        assert ids == ["b-active", "c-active"]

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        assert load_checks(tmp_path) == []

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CheckLoadError):
            load_checks(tmp_path / "does-not-exist")
