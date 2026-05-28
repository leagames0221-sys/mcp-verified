"""Load `.md` check definitions from a directory.

Implements T-05 / AC-5.5 / AC-6.1.

Each check file is a markdown document with frontmatter (parsed by
`mcp_verified.checks.frontmatter`) and a sequence of H2 sections. Files
whose `status` field is not `"active"` are skipped (returned as None by
`load_check`, omitted by `load_checks`). Each loaded check carries the
SHA-256 of its file contents so the verdict registry can record
content-integrity in `audit-manifest.json`.

Public API:
    sha256_file(path)
    load_check(path) -> CheckDefinition | None
    load_checks(dir) -> list[CheckDefinition]
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_verified.checks.frontmatter import FrontmatterParseError, parse_frontmatter

ACTIVE_STATUS = "active"
_H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$")


class CheckLoadError(Exception):
    """Raised when a check file cannot be parsed cleanly."""


@dataclass(frozen=True)
class CheckDefinition:
    """One check definition: metadata + sections + integrity hash."""

    id: str
    title: str
    status: str
    priority: str | None
    cwe: tuple[int, ...]
    cwe_primary: int | None
    tags: tuple[str, ...]
    sections: dict[str, str]
    file_path: Path
    sha256: str
    raw_frontmatter: dict[str, Any] = field(repr=False)


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of the file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _coerce_int_tuple(value: Any) -> tuple[int, ...]:
    """Accept a list of ints; reject anything else."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CheckLoadError(f"expected list of integers, got {type(value).__name__}: {value!r}")
    out: list[int] = []
    for item in value:
        if isinstance(item, int) and not isinstance(item, bool):
            out.append(item)
        else:
            raise CheckLoadError(f"expected integer in list, got {item!r}")
    return tuple(out)


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    """Accept a list of strings; reject anything else."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CheckLoadError(f"expected list of strings, got {type(value).__name__}: {value!r}")
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        else:
            raise CheckLoadError(f"expected string in list, got {item!r}")
    return tuple(out)


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise CheckLoadError(f"expected integer or absent, got {value!r}")


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise CheckLoadError(f"expected string or absent, got {value!r}")


def _parse_sections(body: str) -> dict[str, str]:
    """Group lines into a {h2_title: body} mapping.

    The body before the first H2 is dropped (it is typically blank).
    If duplicate H2 titles appear, the second instance overwrites the
    first; this is consistent with the upstream convention where each
    H2 title is unique per check file.
    """
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []
    for line in body.splitlines():
        match = _H2_PATTERN.match(line)
        if match is not None:
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip("\n")
            current_title = match.group(1).strip()
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)
    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip("\n")
    return sections


def load_check(path: Path) -> CheckDefinition | None:
    """Parse one check file. Return None when its status is not 'active'.

    Raises CheckLoadError on any parse failure. The caller should treat
    a None return as "file present but disabled by status field" and
    skip it in the registered set.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckLoadError(f"cannot read {path}: {exc}") from exc

    try:
        fm = parse_frontmatter(text)
    except FrontmatterParseError as exc:
        raise CheckLoadError(f"frontmatter parse failure in {path}: {exc}") from exc

    fields = fm.fields

    status_value = fields.get("status")
    if not isinstance(status_value, str):
        raise CheckLoadError(f"{path}: required field 'status' must be a string")
    if status_value != ACTIVE_STATUS:
        return None

    title_value = fields.get("title")
    if not isinstance(title_value, str) or not title_value:
        raise CheckLoadError(f"{path}: required field 'title' must be a non-empty string")

    try:
        cwe_tuple = _coerce_int_tuple(fields.get("cwe"))
        cwe_primary = _coerce_optional_int(fields.get("cwe-primary"))
        tags_tuple = _coerce_str_tuple(fields.get("tags"))
        priority_value = _coerce_optional_str(fields.get("priority"))
    except CheckLoadError as exc:
        raise CheckLoadError(f"{path}: {exc}") from exc

    sections = _parse_sections(fm.body)
    check_id = path.stem

    return CheckDefinition(
        id=check_id,
        title=title_value,
        status=status_value,
        priority=priority_value,
        cwe=cwe_tuple,
        cwe_primary=cwe_primary,
        tags=tags_tuple,
        sections=sections,
        file_path=path,
        sha256=sha256_file(path),
        raw_frontmatter=dict(fields),
    )


def load_checks(checks_dir: Path) -> list[CheckDefinition]:
    """Load every `.md` under `checks_dir`. Skip inactive. Sort by id."""
    if not checks_dir.is_dir():
        raise CheckLoadError(f"checks directory does not exist: {checks_dir}")
    loaded: list[CheckDefinition] = []
    for path in sorted(checks_dir.glob("*.md")):
        check = load_check(path)
        if check is not None:
            loaded.append(check)
    loaded.sort(key=lambda c: c.id)
    return loaded
