"""Tests for `mcp_verified.integrity.hash` — T-16 surface."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mcp_verified.checks.loader import CheckDefinition
from mcp_verified.integrity.hash import (
    build_integrity,
    sha256_bytes,
    sha256_path,
    sha256_tree,
)


def _check(check_id: str, *, sha256: str) -> CheckDefinition:
    return CheckDefinition(
        id=check_id,
        title=check_id,
        status="active",
        priority="medium",
        cwe=(),
        cwe_primary=None,
        tags=(),
        sections={},
        file_path=Path(f"/x/{check_id}.md"),
        sha256=sha256,
        raw_frontmatter={},
    )


# ---------- sha256_bytes ----------


class TestSha256Bytes:
    def test_matches_stdlib(self) -> None:
        assert sha256_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()

    def test_empty_bytes(self) -> None:
        assert (
            sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )


# ---------- sha256_path ----------


class TestSha256Path:
    def test_matches_sha256_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "x.bin"
        payload = b"the quick brown fox" * 100
        path.write_bytes(payload)
        assert sha256_path(path) == sha256_bytes(payload)

    def test_handles_large_files_in_chunks(self, tmp_path: Path) -> None:
        path = tmp_path / "big.bin"
        payload = b"y" * (200 * 1024)
        path.write_bytes(payload)
        assert sha256_path(path) == hashlib.sha256(payload).hexdigest()


# ---------- sha256_tree ----------


class TestSha256Tree:
    def test_deterministic_across_two_runs(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")
        assert sha256_tree(tmp_path) == sha256_tree(tmp_path)

    def test_changes_when_content_changes(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("before", encoding="utf-8")
        before = sha256_tree(tmp_path)
        (tmp_path / "a.txt").write_text("after", encoding="utf-8")
        after = sha256_tree(tmp_path)
        assert before != after

    def test_changes_when_file_renamed(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        before = sha256_tree(tmp_path)
        (tmp_path / "a.txt").rename(tmp_path / "b.txt")
        after = sha256_tree(tmp_path)
        assert before != after

    def test_skips_dot_git_by_default(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "index").write_text("garbage", encoding="utf-8")
        with_git = sha256_tree(tmp_path)
        # Remove .git entirely and recompute; should match.
        import shutil

        shutil.rmtree(tmp_path / ".git")
        without_git = sha256_tree(tmp_path)
        assert with_git == without_git

    def test_custom_skip_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "x.js").write_text("x", encoding="utf-8")
        skipped = sha256_tree(tmp_path, skip_dirs=("node_modules",))
        # Reference: same tree without node_modules.
        import shutil

        shutil.rmtree(tmp_path / "node_modules")
        reference = sha256_tree(tmp_path)
        assert skipped == reference

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(NotADirectoryError):
            sha256_tree(tmp_path / "missing")


# ---------- build_integrity ----------


class TestBuildIntegrity:
    def test_includes_tool_version(self) -> None:
        block = build_integrity(
            tree_commit=None,
            tree_root=None,
            checks=None,
            tool_version="0.0.1",
        )
        assert block["mcp_verified_version"] == "0.0.1"

    def test_includes_tree_commit_when_provided(self) -> None:
        block = build_integrity(
            tree_commit="deadbeef",
            tree_root=None,
            checks=None,
            tool_version="0.0.1",
        )
        assert block["tree_commit"] == "deadbeef"

    def test_includes_tree_sha256_when_root_provided(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        block = build_integrity(
            tree_commit=None,
            tree_root=tmp_path,
            checks=None,
            tool_version="0.0.1",
        )
        assert "tree_sha256" in block
        assert len(block["tree_sha256"]) == 64

    def test_checks_are_sorted(self, tmp_path: Path) -> None:
        checks = [_check("z-check", sha256="z"), _check("a-check", sha256="a")]
        block = build_integrity(
            tree_commit=None,
            tree_root=None,
            checks=checks,
            tool_version="0.0.1",
        )
        assert list(block["checks"].keys()) == ["a-check", "z-check"]

    def test_omits_optional_fields_when_inputs_absent(self) -> None:
        block = build_integrity(
            tree_commit=None,
            tree_root=None,
            checks=None,
            tool_version="0.0.1",
        )
        assert "tree_commit" not in block
        assert "tree_sha256" not in block
        assert "checks" not in block

    def test_omits_checks_key_when_no_check_has_a_hash(self) -> None:
        block = build_integrity(
            tree_commit=None,
            tree_root=None,
            checks=[_check("x", sha256="")],
            tool_version="0.0.1",
        )
        assert "checks" not in block
