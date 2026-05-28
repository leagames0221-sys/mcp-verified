"""Minimal frontmatter parser for check-definition markdown files.

Implements ADR-009 (hand-rolled, zero runtime dependency). Accepts only the
small YAML subset observed in the upstream `mcpserver-audit` check format:

    - `key: scalar`     scalar is string, int, float, or bool
    - `key: [a, b, c]`  inline list of strings or ints
    - `key: []`         empty list

Any other YAML shape (block list, anchor, multi-line string, nested map)
raises `FrontmatterParseError` explicitly. The intent is fail-loud on
schema drift, not silent acceptance of shapes downstream cannot handle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_KEY_VALUE_PATTERN = re.compile(r"^([A-Za-z][\w-]*)\s*:\s*(.*)$")
_INT_PATTERN = re.compile(r"^-?\d+$")
_FLOAT_PATTERN = re.compile(r"^-?\d+\.\d+$")


class FrontmatterParseError(Exception):
    """Raised on any deviation from the supported subset."""


@dataclass(frozen=True)
class Frontmatter:
    fields: dict[str, Any]
    body: str
    raw_yaml: str


def _strip_quotes(value: str) -> str:
    """Strip a single matched pair of outer quotes, if present."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_scalar(value: str) -> Any:
    """Resolve a scalar string to int, float, bool, or str."""
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    if _INT_PATTERN.match(stripped):
        return int(stripped)
    if _FLOAT_PATTERN.match(stripped):
        return float(stripped)
    return _strip_quotes(stripped)


def _parse_inline_list(value: str) -> list[Any]:
    """Parse `[a, b, c]` into a list of scalars."""
    inner = value.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        raise FrontmatterParseError(f"expected inline list, got {value!r}")
    inner = inner[1:-1].strip()
    if not inner:
        return []
    # Reject anything that looks like a nested map or list inside a list.
    if "{" in inner or "[" in inner:
        raise FrontmatterParseError(
            f"nested structures are not supported in inline lists: {value!r}"
        )
    items = [item.strip() for item in inner.split(",")]
    return [_parse_scalar(item) for item in items if item]


def _parse_value(value: str) -> Any:
    """Resolve any RHS — scalar or inline list."""
    stripped = value.strip()
    if stripped.startswith("["):
        return _parse_inline_list(stripped)
    if stripped.startswith("{"):
        raise FrontmatterParseError(
            f"inline maps are not supported in Phase 1 frontmatter: {value!r}"
        )
    return _parse_scalar(stripped)


def parse_frontmatter(text: str) -> Frontmatter:
    """Split a markdown file's YAML frontmatter from its body.

    The frontmatter must be enclosed in `---` lines at the very top of the
    file. The body is everything after the second `---`.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise FrontmatterParseError("file does not begin with the '---' frontmatter marker")
    # Find the closing '---' on its own line.
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        raise FrontmatterParseError("opening '---' marker is missing or malformed")
    closing_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_index = i
            break
    if closing_index is None:
        raise FrontmatterParseError("closing '---' marker not found")
    yaml_lines = lines[1:closing_index]
    body_lines = lines[closing_index + 1 :]

    fields: dict[str, Any] = {}
    for line_number, line in enumerate(yaml_lines, start=2):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped != stripped.lstrip():
            # Indented continuation lines would be block-list / multi-line
            # shapes; we explicitly do not support them.
            raise FrontmatterParseError(
                f"indented line {line_number} suggests an unsupported shape: {line!r}"
            )
        match = _KEY_VALUE_PATTERN.match(stripped)
        if match is None:
            raise FrontmatterParseError(
                f"line {line_number} does not match 'key: value': {line!r}"
            )
        key, value = match.group(1), match.group(2)
        if key in fields:
            raise FrontmatterParseError(f"duplicate key {key!r} at line {line_number}")
        fields[key] = _parse_value(value)

    body = "\n".join(body_lines)
    raw_yaml = "\n".join(yaml_lines)
    return Frontmatter(fields=fields, body=body, raw_yaml=raw_yaml)
