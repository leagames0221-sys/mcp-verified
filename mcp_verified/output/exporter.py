"""`export-audit-db` subcommand backend.

Implements T-14 / AC-6.3.

Takes a single target's audit directory (laid out by `AuditDirWriter`)
and produces a `.tar.gz` archive whose internal layout matches what the
upstream Cloud Security Alliance `audit-db` repository expects from a
pull request:

    audits/<host>/<owner>/<repo>/
    ├── metadata.json
    └── audits/
        └── <audit_id>/
            ├── audit-manifest.json
            ├── security-assessment.md
            └── findings/...

The tar payload is deterministic: entries are written in lex-sorted
order with `mtime=0`, `uid=0`, `gid=0`, empty `uname`/`gname`, and
canonical 0644 / 0755 modes. Two exports of the same target tree
produce identical tar payloads (the outer gzip header may carry the
default filesystem mtime, which the test suite ignores by extracting
and comparing the tree instead of the raw bytes).
"""

from __future__ import annotations

import tarfile
from pathlib import Path


class ExportError(Exception):
    """Raised when the source target directory cannot be exported."""


def _infer_host_owner_repo(target_dir: Path) -> tuple[str, str, str]:
    """Pull the last three path components off the resolved target dir."""
    parts = target_dir.resolve().parts
    if len(parts) < 3:
        raise ExportError(
            f"cannot infer host/owner/repo from target_dir: {target_dir}"
        )
    return parts[-3], parts[-2], parts[-1]


def export_audit_db_target(
    target_dir: Path,
    output_path: Path,
    *,
    host: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    deterministic_mtime: int = 0,
) -> Path:
    """Compress a target's audit subtree into a tarball.

    Parameters
    ----------
    target_dir
        The on-disk directory holding the target's `metadata.json` and
        its `audits/<audit_id>/` subdirectories. Typically
        `<out>/audits/<host>/<owner>/<repo>/`.
    output_path
        Where to write the `.tar.gz`. The parent directory is created
        if it does not yet exist.
    host, owner, repo
        Optional explicit overrides for the in-tarball path prefix
        `audits/<host>/<owner>/<repo>`. If any is None, all three are
        inferred from the last three components of `target_dir`.
    deterministic_mtime
        UNIX timestamp embedded in every tar entry. Default 0 so the
        archive is byte-deterministic across machines.

    Returns
    -------
    Path
        The output path (same as `output_path`).

    Raises
    ------
    ExportError
        Target directory does not exist or is not a directory.
    """
    if not target_dir.exists() or not target_dir.is_dir():
        raise ExportError(f"target_dir does not exist or is not a directory: {target_dir}")

    if host is None or owner is None or repo is None:
        inferred_host, inferred_owner, inferred_repo = _infer_host_owner_repo(target_dir)
        host = host or inferred_host
        owner = owner or inferred_owner
        repo = repo or inferred_repo

    arc_prefix = f"audits/{host}/{owner}/{repo}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Walk lex-sorted so the entry order is stable.
    entries = sorted(target_dir.rglob("*"), key=lambda p: p.as_posix())
    with tarfile.open(output_path, mode="w:gz") as tar:
        # Add the prefix directory itself first so an extractor that
        # honors per-entry mode bits sees a consistent dir entry.
        root_info = tarfile.TarInfo(name=arc_prefix)
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        root_info.mtime = deterministic_mtime
        root_info.uid = 0
        root_info.gid = 0
        root_info.uname = ""
        root_info.gname = ""
        tar.addfile(root_info)

        for path in entries:
            rel = path.relative_to(target_dir).as_posix()
            arc = f"{arc_prefix}/{rel}"
            info = tarfile.TarInfo(name=arc)
            info.mtime = deterministic_mtime
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            if path.is_dir():
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            elif path.is_file():
                info.type = tarfile.REGTYPE
                info.mode = 0o644
                data = path.read_bytes()
                info.size = len(data)
                import io
                tar.addfile(info, fileobj=io.BytesIO(data))
            else:
                # Symlinks / sockets / fifos are out of scope for Phase 1.
                continue

    return output_path
