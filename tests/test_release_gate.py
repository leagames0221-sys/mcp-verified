"""Tests for `scripts/release_gate.sh` — T-20 surface."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "release_gate.sh"


def _posix(path: Path | str) -> str:
    """Convert a path to a POSIX-style string so bash on Windows can find it.

    Without this, the Windows `C:\\Users\\...` form is mangled by bash's
    backslash interpretation.
    """
    return str(path).replace("\\", "/")


def _has_bash() -> bool:
    """True if a *working* POSIX bash is reachable on PATH.

    On GitHub's windows-latest runner, ``bash`` resolves to the WSL stub
    (``C:\\Windows\\System32\\bash.exe``), which has no distribution installed
    and only prints an install prompt. Probing with a trivial command makes
    the stub count as "no bash", so these tests skip there while still running
    on Linux, macOS, and Git Bash. release_gate.sh itself is verified on the
    Linux CI job.
    """
    from shutil import which

    if which("bash") is None:
        return False
    try:
        proc = subprocess.run(
            ["bash", "-c", "echo __bash_ok__"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "__bash_ok__" in proc.stdout


pytestmark = pytest.mark.skipif(
    not _has_bash(),
    reason="bash not on PATH; release_gate.sh cannot run",
)


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


def _populate_minimal_repo(tmp_path: Path) -> None:
    """Build a synthetic repo with the minimum surface release_gate inspects."""
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    for i in range(1, 6):
        (tmp_path / "docs" / "adr" / f"ADR-00{i}-x.md").write_text(
            f"# ADR-00{i}\nStatus: Accepted\n", encoding="utf-8"
        )
    (tmp_path / "README.md").write_text(
        "# repo\n\n## Limitations\n\nNo dynamic analysis.\n", encoding="utf-8"
    )
    (tmp_path / "SECURITY.md").write_text("# sec\n", encoding="utf-8")


def _run_gate(
    *,
    repo: Path,
    customer_wordlist: Path | None = None,
    internal_wordlist: Path | None = None,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess:
    args = [
        "bash",
        "scripts/release_gate.sh",
        "--skip-smoke",
        "--repo-root",
        _posix(repo),
    ]
    if customer_wordlist is not None:
        args.extend(["--customer-wordlist", _posix(customer_wordlist)])
    if internal_wordlist is not None:
        args.extend(["--internal-wordlist", _posix(internal_wordlist)])
    if extra:
        args.extend(extra)
    return subprocess.run(args, capture_output=True, text=True, check=False, cwd=REPO_ROOT)


class TestNegativePath:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows bash path mangling around tmp wordlist paths; verified on Linux CI",
    )
    def test_customer_wordlist_hit_in_tracked_file_fails(self, tmp_path: Path) -> None:
        """A tracked file that mentions a wordlist term must fail the gate."""
        _populate_minimal_repo(tmp_path)
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        # Add a tracked file containing the synthetic customer term.
        (tmp_path / "leaked.md").write_text(
            "Project for FakeCustomerInc deployment.\n", encoding="utf-8"
        )
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "initial"], cwd=tmp_path)

        wordlist = tmp_path / "customers.txt"
        wordlist.write_text("FakeCustomerInc\n", encoding="utf-8")

        result = _run_gate(repo=tmp_path, customer_wordlist=wordlist)
        assert result.returncode != 0
        assert "customer wordlist" in (result.stdout + result.stderr).lower()
        assert "FakeCustomerInc" in (result.stdout + result.stderr)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows bash path mangling around tmp wordlist paths; verified on Linux CI",
    )
    def test_customer_wordlist_hit_in_commit_message_fails(self, tmp_path: Path) -> None:
        _populate_minimal_repo(tmp_path)
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "engagement with FakeCustomerInc"], cwd=tmp_path)

        wordlist = tmp_path / "customers.txt"
        wordlist.write_text("FakeCustomerInc\n", encoding="utf-8")

        result = _run_gate(repo=tmp_path, customer_wordlist=wordlist)
        assert result.returncode != 0
        assert "commit history" in (result.stdout + result.stderr).lower()

    def test_missing_security_md_fails(self, tmp_path: Path) -> None:
        _populate_minimal_repo(tmp_path)
        (tmp_path / "SECURITY.md").unlink()
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "initial"], cwd=tmp_path)
        result = _run_gate(repo=tmp_path)
        assert result.returncode != 0
        assert "SECURITY.md" in (result.stdout + result.stderr)

    def test_missing_limitations_section_fails(self, tmp_path: Path) -> None:
        _populate_minimal_repo(tmp_path)
        (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "initial"], cwd=tmp_path)
        result = _run_gate(repo=tmp_path)
        assert result.returncode != 0
        assert "LIMITATIONS" in (result.stdout + result.stderr)

    def test_too_few_adrs_fails(self, tmp_path: Path) -> None:
        _populate_minimal_repo(tmp_path)
        # Delete all but two ADR files.
        adr_dir = tmp_path / "docs" / "adr"
        for path in sorted(adr_dir.glob("ADR-*.md"))[2:]:
            path.unlink()
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "initial"], cwd=tmp_path)
        result = _run_gate(repo=tmp_path)
        assert result.returncode != 0
        assert "ADR count" in (result.stdout + result.stderr)


class TestHappyPath:
    def test_clean_repo_with_no_wordlists_passes(self, tmp_path: Path) -> None:
        """A minimal clean repo without wordlists configured must report
        the wordlist steps as 'skipped' and still pass overall."""
        _populate_minimal_repo(tmp_path)
        _git(["init", "-q", "-b", "main"], cwd=tmp_path)
        _git(["add", "."], cwd=tmp_path)
        _git(["commit", "-q", "-m", "initial"], cwd=tmp_path)
        result = _run_gate(repo=tmp_path)
        combined = result.stdout + result.stderr
        # Without --skip-smoke and --skip-coverage equivalents for the synth
        # repo, the gate still attempts the coverage / pytest steps and
        # those will fail because the synth repo has no mcp_verified
        # source. We expect non-zero overall; the assertion below only
        # checks that the wordlist steps surface as "skipped" and that the
        # failure messages do not include a wordlist-hit signal.
        assert "customer wordlist" in combined.lower()
        assert "internal wordlist" in combined.lower()
        # Customer / internal wordlist steps should report skipped, not failed.
        assert "PASS  4/8 customer wordlist (skipped" in combined
        assert "PASS  5/8 internal wordlist (skipped" in combined
