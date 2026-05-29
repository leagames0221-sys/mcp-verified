"""Safe read-only clone of a GitHub-hosted MCP server source repository.

Implements T-04 / AC-1.3 / AC-1.6 / AC-5.4.

Hard guarantees enforced by this module:

1. **GitHub only.** The URL must be `https://github.com/<owner>/<repo>[.git]`.
   Anything else raises `NonGitHubURLError` before any subprocess is invoked.
2. **Read-only.** The only subprocess this module ever spawns is `git`. No
   `npm`, `pip`, `node`, `python`, package-script, or candidate-defined
   binary is executed against the cloned tree.
3. **Shallow.** `git clone --depth=1 --filter=tree:0` is used, so the
   working tree is the tip commit plus on-demand tree objects only.
4. **Deterministic cleanup.** Use as a context manager (`with safe_clone(...)
   as repo:`) and the scratch directory is removed on both normal exit and
   exception, with a Windows-aware `chmod` fallback for read-only pack files.

This module's network surface is `https://github.com/*` only (per the
input filter), satisfying AC-4.4 by construction.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

GITHUB_HOST = "github.com"
DEFAULT_CLONE_TIMEOUT_SECONDS = 120
DEFAULT_REV_PARSE_TIMEOUT_SECONDS = 10
GIT_EXECUTABLE = "git"

# Matches https://github.com/<owner>/<repo> with an optional trailing `.git` or
# slash. `<owner>` and `<repo>` may contain word chars, hyphens, dots, and
# underscores; GitHub permits these for both fields.
_GITHUB_PATH_PATTERN = re.compile(r"^/[\w.\-]+/[\w.\-]+(?:\.git)?/?$")


class CloneError(Exception):
    """Base exception for safe-clone failures."""


class NonGitHubURLError(CloneError):
    """Raised when the URL does not point to a github.com repository."""


class CloneTimeoutError(CloneError):
    """Raised when the clone exceeds the configured timeout."""


class CloneFailedError(CloneError):
    """Raised when `git clone` returns a non-zero exit code."""


def is_github_url(url: str) -> bool:
    """Return True iff `url` is `https://github.com/<owner>/<repo>[.git]`.

    Anything else — non-https schemes, non-github hosts, missing owner/repo,
    extra path segments — returns False.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if parsed.netloc != GITHUB_HOST:
        return False
    if parsed.query or parsed.fragment:
        return False
    return bool(_GITHUB_PATH_PATTERN.match(parsed.path or ""))


def _rmtree_force(path: Path) -> None:
    """Remove a directory tree, tolerating Windows read-only pack files."""

    def _on_error(func, target, exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            # Best-effort cleanup; never raise from cleanup itself.
            pass

    if path.exists():
        shutil.rmtree(path, onerror=_on_error)


@dataclass(frozen=True)
class ClonedRepo:
    """A shallow clone of a GitHub repository on the local filesystem.

    Use as a context manager so the scratch directory is removed on both
    normal exit and exception:

        with safe_clone("https://github.com/owner/repo") as repo:
            do_static_analysis(repo.path)
        # repo.path is gone here.

    `cleanup()` is also exposed for callers that want explicit control.
    """

    path: Path
    url: str
    commit_hash: str

    def cleanup(self) -> None:
        _rmtree_force(self.path)

    def __enter__(self) -> ClonedRepo:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def _read_head_commit(repo_path: Path, timeout_seconds: int) -> str:
    """Run `git rev-parse HEAD` against the freshly cloned tree."""
    argv = [GIT_EXECUTABLE, "-C", str(repo_path), "rev-parse", "HEAD"]
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise CloneFailedError(
            f"git rev-parse failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def safe_clone(
    url: str,
    *,
    clone_timeout_seconds: int = DEFAULT_CLONE_TIMEOUT_SECONDS,
    rev_parse_timeout_seconds: int = DEFAULT_REV_PARSE_TIMEOUT_SECONDS,
    scratch_root: Path | None = None,
    url_validator: Callable[[str], bool] = is_github_url,
) -> ClonedRepo:
    """Shallow-clone a GitHub repository into a scratch directory.

    On success returns a `ClonedRepo`. On any failure, the scratch directory
    is removed before the exception propagates.

    Parameters
    ----------
    url
        Must satisfy `url_validator`. Default validator is `is_github_url`,
        which accepts only `https://github.com/<owner>/<repo>[.git]`.
    clone_timeout_seconds
        Hard timeout on the `git clone` subprocess. On expiry, raises
        `CloneTimeoutError` and removes the scratch directory.
    rev_parse_timeout_seconds
        Hard timeout on the `git rev-parse HEAD` subprocess.
    scratch_root
        Parent directory for the scratch clone. Defaults to the system
        temp directory.
    url_validator
        Override for the URL gate. Defaults to `is_github_url`. Tests use
        this hook to admit a controlled local file URL when needed.
    """
    if not url_validator(url):
        raise NonGitHubURLError(f"refusing to clone non-GitHub URL: {url!r}")

    scratch = Path(tempfile.mkdtemp(prefix="mcp-verified-clone-", dir=scratch_root))
    try:
        argv = [
            GIT_EXECUTABLE,
            "clone",
            "--depth=1",
            "--filter=tree:0",
            "--",
            url,
            str(scratch),
        ]
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=clone_timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            raise CloneFailedError(
                f"git clone exited with {result.returncode}: {result.stderr.strip()}"
            )
        commit_hash = _read_head_commit(scratch, rev_parse_timeout_seconds)
        return ClonedRepo(path=scratch, url=url, commit_hash=commit_hash)
    except subprocess.TimeoutExpired as exc:
        _rmtree_force(scratch)
        raise CloneTimeoutError(
            f"git clone timed out after {clone_timeout_seconds}s: {url!r}"
        ) from exc
    except Exception:
        _rmtree_force(scratch)
        raise
