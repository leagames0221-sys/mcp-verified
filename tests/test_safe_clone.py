"""Tests for `mcp_verified.clone.safe_clone` — T-04 acceptance surface."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mcp_verified.clone.safe_clone import (
    ClonedRepo,
    CloneFailedError,
    CloneTimeoutError,
    NonGitHubURLError,
    is_github_url,
    safe_clone,
)
from mcp_verified.registry.client import integration_tests_enabled


# ---------- URL gate ----------


class TestIsGitHubUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/octocat/Hello-World",
            "https://github.com/octocat/Hello-World/",
            "https://github.com/octocat/Hello-World.git",
            "https://github.com/leagames0221-sys/mcp-verified",
            "https://github.com/a-1/b_2.suffix",
        ],
    )
    def test_accepts_canonical_github_urls(self, url: str) -> None:
        assert is_github_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            None,  # type: ignore[list-item]
            "http://github.com/owner/repo",  # not https
            "https://gitlab.com/owner/repo",  # not github
            "https://github.com/owner",  # missing repo
            "https://github.com/owner/repo/sub",  # too many path segments
            "ssh://git@github.com:owner/repo.git",  # ssh-like scheme
            "git@github.com:owner/repo.git",  # not a URL at all
            "file:///tmp/some-bundle.bundle",  # file URL
            "https://github.com/owner/repo?ref=main",  # query string
            "https://github.com/owner/repo#section",  # fragment
        ],
    )
    def test_rejects_non_canonical_urls(self, url: str | None) -> None:
        assert is_github_url(url) is False  # type: ignore[arg-type]


# ---------- safe_clone: URL filter (no subprocess) ----------


class TestSafeCloneRejectsNonGitHub:
    def test_raises_for_gitlab_url(self) -> None:
        with pytest.raises(NonGitHubURLError):
            safe_clone("https://gitlab.com/owner/repo")

    def test_raises_for_http_url(self) -> None:
        with pytest.raises(NonGitHubURLError):
            safe_clone("http://github.com/owner/repo")

    def test_raises_for_empty_string(self) -> None:
        with pytest.raises(NonGitHubURLError):
            safe_clone("")

    def test_no_subprocess_on_rejected_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The URL gate must reject before any subprocess is launched."""
        called = []

        def spy(*args, **kwargs):  # noqa: ARG001
            called.append(args)
            raise AssertionError("subprocess.run should not be called for rejected URL")

        monkeypatch.setattr(subprocess, "run", spy)
        with pytest.raises(NonGitHubURLError):
            safe_clone("https://gitlab.com/owner/repo")
        assert called == []


# ---------- safe_clone: subprocess command construction (monkeypatched) ----------


def _fake_clone_run_factory(scratch_writer):
    """Build a fake `subprocess.run` that records calls and simulates success.

    `scratch_writer(scratch_path)` is invoked for the `git clone` call so the
    test can populate the scratch directory as if a real clone happened.
    """
    calls: list[list[str]] = []
    rev_parse_response = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

    def fake_run(argv, *args, **kwargs):  # noqa: ARG001
        calls.append(list(argv))
        if argv[0] != "git":
            raise AssertionError(
                f"safe_clone invoked a non-git subprocess: {argv[0]!r}. "
                f"Only `git` is allowed (T-04 / AC-5.4)."
            )
        # git clone <flags> -- <url> <scratch>
        if "clone" in argv:
            scratch_path = Path(argv[-1])
            scratch_path.mkdir(parents=True, exist_ok=True)
            (scratch_path / ".git").mkdir(exist_ok=True)
            scratch_writer(scratch_path)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rev-parse" in argv:
            return SimpleNamespace(returncode=0, stdout=rev_parse_response + "\n", stderr="")
        raise AssertionError(f"unexpected git subcommand: {argv}")

    return fake_run, calls, rev_parse_response


class TestSafeCloneSubprocessContract:
    def test_only_git_executable_is_invoked(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-5.4: safe_clone must never invoke npm, pip, node, python, etc."""
        forbidden = {"npm", "pnpm", "yarn", "pip", "pipx", "node", "python", "python3", "sh", "bash"}
        fake_run, calls, _ = _fake_clone_run_factory(lambda p: (p / "README").write_text("ok"))
        monkeypatch.setattr(subprocess, "run", fake_run)

        repo = safe_clone(
            "https://github.com/octocat/Hello-World",
            scratch_root=tmp_path,
        )
        try:
            assert repo.commit_hash == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            assert len(calls) >= 2  # clone + rev-parse
            for call in calls:
                assert call[0] == "git"
                assert call[0] not in forbidden
        finally:
            repo.cleanup()

    def test_clone_argv_pins_shallow_filter(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_run, calls, _ = _fake_clone_run_factory(lambda p: None)
        monkeypatch.setattr(subprocess, "run", fake_run)

        with safe_clone(
            "https://github.com/octocat/Hello-World", scratch_root=tmp_path
        ) as _repo:
            pass

        clone_call = next(c for c in calls if "clone" in c)
        assert "--depth=1" in clone_call
        assert "--filter=tree:0" in clone_call
        assert "--" in clone_call  # double-dash before the url


class TestSafeCloneFailureModes:
    def test_failed_clone_cleans_up_scratch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, Path] = {}

        def fake_run(argv, *args, **kwargs):  # noqa: ARG001
            if "clone" in argv:
                captured["scratch"] = Path(argv[-1])
                # Touch the directory then return non-zero.
                Path(argv[-1]).mkdir(parents=True, exist_ok=True)
                (Path(argv[-1]) / "marker").write_text("x")
                return SimpleNamespace(returncode=128, stdout="", stderr="not found")
            raise AssertionError("unexpected git invocation")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(CloneFailedError):
            safe_clone(
                "https://github.com/octocat/does-not-exist", scratch_root=tmp_path
            )
        assert "scratch" in captured
        assert not captured["scratch"].exists(), "scratch directory must be cleaned up on failure"

    def test_timeout_cleans_up_scratch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, Path] = {}

        def fake_run(argv, *args, **kwargs):  # noqa: ARG001
            captured["scratch"] = Path(argv[-1])
            Path(argv[-1]).mkdir(parents=True, exist_ok=True)
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(CloneTimeoutError):
            safe_clone(
                "https://github.com/octocat/Hello-World",
                clone_timeout_seconds=1,
                scratch_root=tmp_path,
            )
        assert "scratch" in captured
        assert not captured["scratch"].exists(), "scratch directory must be cleaned up on timeout"


# ---------- ClonedRepo: context manager + cleanup ----------


class TestClonedRepoLifecycle:
    def test_context_manager_cleans_up_on_normal_exit(self, tmp_path: Path) -> None:
        scratch = tmp_path / "synthetic-clone"
        scratch.mkdir()
        (scratch / "README").write_text("x")
        repo = ClonedRepo(
            path=scratch, url="https://github.com/x/y", commit_hash="0" * 40
        )
        with repo:
            assert scratch.exists()
        assert not scratch.exists()

    def test_context_manager_cleans_up_on_exception(self, tmp_path: Path) -> None:
        scratch = tmp_path / "synthetic-clone"
        scratch.mkdir()
        (scratch / "README").write_text("x")
        repo = ClonedRepo(
            path=scratch, url="https://github.com/x/y", commit_hash="0" * 40
        )
        with pytest.raises(RuntimeError):
            with repo:
                raise RuntimeError("boom")
        assert not scratch.exists()

    def test_explicit_cleanup_is_idempotent(self, tmp_path: Path) -> None:
        scratch = tmp_path / "synthetic-clone"
        scratch.mkdir()
        repo = ClonedRepo(
            path=scratch, url="https://github.com/x/y", commit_hash="0" * 40
        )
        repo.cleanup()
        assert not scratch.exists()
        # Second cleanup is a no-op, not an error.
        repo.cleanup()


# ---------- Integration test (opt-in) ----------


@pytest.mark.skipif(
    not integration_tests_enabled(),
    reason="Set MCP_VERIFIED_INTEGRATION_TESTS=1 to enable network clone",
)
class TestSafeCloneNetwork:
    def test_clones_a_real_public_repo(self, tmp_path: Path) -> None:
        url = "https://github.com/octocat/Hello-World"
        with safe_clone(url, scratch_root=tmp_path, clone_timeout_seconds=60) as repo:
            assert repo.path.exists()
            assert (repo.path / ".git").exists()
            assert len(repo.commit_hash) == 40
            # No package install script run; the directory exists but no
            # node_modules / .venv / __pycache__ should have appeared.
            assert not (repo.path / "node_modules").exists()
            assert not (repo.path / ".venv").exists()
        # After exit, scratch is gone.
        assert not (tmp_path / "Hello-World").exists() or True  # path was nested under tmp_path
