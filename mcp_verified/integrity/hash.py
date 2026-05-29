"""Audit-integrity hashing.

Implements T-16 / AC-5.5.

The `audit_metadata.integrity` field in `audit-manifest.json` carries:

- `tree_commit`     — the git commit hash captured by `safe_clone`. This
                       identifies the cloned tree exactly as the upstream
                       repository sees it.
- `tree_sha256`     — a deterministic content hash of the cloned tree
                       (concatenated path + length + content bytes for
                       every file under lex-sorted order). Useful when
                       the same `tree_commit` is produced by two clones
                       and we want to verify they materialised identically.
- `checks`          — per-check `{check_id: sha256-of-md-file}` map, so a
                       reviewer can spot whether a verdict was produced
                       by a different version of the check definitions.
- `mcp_verified_version` — the auditor tool version string.

All values are pure functions of their inputs. Two runs of the audit
against the same `(commit, check_set, tool_version)` produce identical
integrity blocks, which is what T-12 (divergence detection) depends on
when it diffs two manifests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mcp_verified.checks.loader import CheckDefinition

_CHUNK_SIZE = 65536


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    """Hex SHA-256 of the file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(
    root: Path,
    *,
    skip_dirs: Iterable[str] = (".git",),
) -> str:
    """Content hash of every regular file under `root`.

    Files are visited in lex-sorted order. For each file we feed:

        <relative POSIX path>\0<8-byte big-endian size><file bytes>

    into a SHA-256 accumulator. Directories outside `skip_dirs` are
    descended; anything in `skip_dirs` (the `.git` index by default)
    is excluded. Symlinks and non-regular entries are skipped.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"sha256_tree expects a directory: {root}")
    skip = frozenset(skip_dirs)
    h = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in skip for part in rel.parts):
            continue
        if not path.is_file():
            continue
        rel_posix = rel.as_posix().encode("utf-8")
        try:
            size = path.stat().st_size
        except OSError:
            continue
        h.update(rel_posix)
        h.update(b"\x00")
        h.update(size.to_bytes(8, "big"))
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
                    h.update(chunk)
        except OSError:
            # Treat unreadable files as zero-content; their path + size are
            # already in the digest so they cannot be confused with a missing
            # entry.
            continue
    return h.hexdigest()


def build_integrity(
    *,
    tree_commit: str | None,
    tree_root: Path | None,
    checks: Iterable[CheckDefinition] | None,
    tool_version: str,
) -> dict[str, Any]:
    """Compose the `audit_metadata.integrity` block.

    Every argument is optional so the same builder can be reused for
    unknown / timeout / clone-failure paths where some inputs are absent.
    Missing inputs simply yield missing fields rather than throwing.
    """
    integrity: dict[str, Any] = {"mcp_verified_version": tool_version}
    if tree_commit:
        integrity["tree_commit"] = tree_commit
    if tree_root is not None and tree_root.is_dir():
        integrity["tree_sha256"] = sha256_tree(tree_root)
    if checks is not None:
        check_map: dict[str, str] = {}
        for check in checks:
            if check.sha256:
                check_map[check.id] = check.sha256
        if check_map:
            integrity["checks"] = dict(sorted(check_map.items()))
    return integrity
