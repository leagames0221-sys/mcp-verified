"""LLM-assisted check executor.

Implements T-09 / AC-3.2 / AC-3.4.

For every loaded `CheckDefinition` whose frontmatter declares
`requires_llm: true`, the executor:

1. Renders a prompt that combines the check's `For AI Assistants` section
   (or a configured fallback section) with a bounded excerpt of every
   candidate file in the cloned tree.
2. Calls the configured `Provider` with that prompt and a per-check
   JSON schema describing the expected response shape.
3. Parses the response, coerces each entry into a `Finding`, and adds it
   to the output list.
4. On `ProviderResponseError` for a single check, emits one synthetic
   `error` Finding for that check and continues with the next check —
   the run is never aborted by a malformed LLM response.

`ProviderUnreachableError` is **not** caught here; the caller is expected
to wrap the executor with `query_with_fallback` if it wants to swap to
`MockProvider` on connection failure. This split keeps the executor's
contract simple: unreachable means "do not produce a verdict at all",
malformed means "produce an error finding".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_verified.checks.executors.deterministic import (
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_SKIP_DIRS,
    DEFAULT_TEXT_EXTENSIONS,
    Finding,
)
from mcp_verified.checks.loader import CheckDefinition
from mcp_verified.providers.base import (
    Provider,
    ProviderResponseError,
)
from mcp_verified.providers.mock import MockProvider

DEFAULT_AI_SECTION_TITLES: tuple[str, ...] = (
    "For AI Assistants: Automated Analysis",
    "For AI Assistants",
    "AI instructions",
)
DEFAULT_FILE_EXCERPT_CHARS = 8000
DEFAULT_MAX_FILES_PER_PROMPT = 25


def _select_ai_section(check: CheckDefinition, candidates: tuple[str, ...]) -> str:
    for title in candidates:
        if title in check.sections:
            return check.sections[title]
    # Fall back to the entire body so the LLM has at least some context.
    return "\n\n".join(check.sections.values())


def _file_excerpt(path: Path, *, max_chars: int) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if len(text) > max_chars:
        return text[:max_chars] + "\n... [truncated]"
    return text


def _iter_excerpt_paths(
    root: Path,
    *,
    skip_dirs: frozenset[str],
    text_extensions: frozenset[str],
    max_file_size: int,
    max_files: int,
) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in skip_dirs for part in rel_parts):
            continue
        if path.suffix.lower() not in text_extensions:
            continue
        try:
            if path.stat().st_size > max_file_size:
                continue
        except OSError:
            continue
        paths.append(path)
        if len(paths) >= max_files:
            break
    return paths


def _build_prompt(
    check: CheckDefinition,
    excerpts: list[tuple[str, str]],
    ai_section_titles: tuple[str, ...],
) -> str:
    instructions = _select_ai_section(check, ai_section_titles)
    parts = [
        f"# Check: {check.title}",
        "",
        "## Instructions",
        instructions.strip(),
        "",
        "## Expected output (JSON)",
        '{"findings": [{"rule_id": str, "severity": "critical"|"high"|"medium"|"low"|"info",'
        ' "cwe": int|null, "file_path": str, "line_number": int, "snippet": str,'
        ' "description": str}]}',
        "",
        "## Candidate files",
    ]
    for rel_path, body in excerpts:
        parts.append(f"### {rel_path}")
        parts.append("```")
        parts.append(body)
        parts.append("```")
    parts.append("")
    parts.append("Respond with the JSON object only. No prose.")
    return "\n".join(parts)


def _schema_for(check: CheckDefinition) -> dict[str, Any]:
    """Schema hint passed to the provider. Phase 1 keeps this minimal."""
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string"},
                        "severity": {"type": "string"},
                        "cwe": {"type": ["integer", "null"]},
                        "file_path": {"type": "string"},
                        "line_number": {"type": "integer"},
                        "snippet": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            }
        },
        "_check_id": check.id,
    }


def _coerce_finding(check: CheckDefinition, raw: dict[str, Any]) -> Finding | None:
    """Coerce one LLM-produced entry to a Finding. Return None on failure."""
    try:
        rule_id = str(raw.get("rule_id") or f"LLM-{check.id}")
        severity = str(raw.get("severity") or "info")
        cwe_raw = raw.get("cwe")
        cwe = int(cwe_raw) if isinstance(cwe_raw, int) and not isinstance(cwe_raw, bool) else None
        file_path = str(raw.get("file_path") or "")
        line_number_raw = raw.get("line_number")
        line_number = (
            int(line_number_raw)
            if isinstance(line_number_raw, int) and not isinstance(line_number_raw, bool)
            else 0
        )
        snippet = str(raw.get("snippet") or "")
        description = str(raw.get("description") or check.title)
    except (TypeError, ValueError):
        return None
    return Finding(
        rule_id=rule_id,
        severity=severity,
        cwe=cwe,
        file_path=file_path,
        line_number=line_number,
        redacted_snippet=snippet,
        description=description,
    )


def _error_finding(check: CheckDefinition, reason: str) -> Finding:
    return Finding(
        rule_id=f"CHECK-RUN-ERROR-{check.id}",
        severity="info",
        cwe=None,
        file_path="",
        line_number=0,
        redacted_snippet="",
        description=f"LLM-assisted check {check.id!r} failed: {reason}",
    )


@dataclass(frozen=True)
class LLMAssistedExecutor:
    """Runs `requires_llm: true` checks against a cloned tree."""

    provider: Provider = field(default_factory=MockProvider)
    ai_section_titles: tuple[str, ...] = DEFAULT_AI_SECTION_TITLES
    max_file_excerpt_chars: int = DEFAULT_FILE_EXCERPT_CHARS
    max_files_per_prompt: int = DEFAULT_MAX_FILES_PER_PROMPT
    skip_dirs: frozenset[str] = field(default_factory=lambda: DEFAULT_SKIP_DIRS)
    text_extensions: frozenset[str] = field(default_factory=lambda: DEFAULT_TEXT_EXTENSIONS)
    max_file_size: int = DEFAULT_MAX_FILE_SIZE

    def _collect_excerpts(self, repo_root: Path) -> list[tuple[str, str]]:
        excerpts: list[tuple[str, str]] = []
        for path in _iter_excerpt_paths(
            repo_root,
            skip_dirs=self.skip_dirs,
            text_extensions=self.text_extensions,
            max_file_size=self.max_file_size,
            max_files=self.max_files_per_prompt,
        ):
            body = _file_excerpt(path, max_chars=self.max_file_excerpt_chars)
            if body is None:
                continue
            rel = path.relative_to(repo_root).as_posix()
            excerpts.append((rel, body))
        return excerpts

    def run(
        self,
        repo_root: Path,
        checks: list[CheckDefinition],
    ) -> list[Finding]:
        if not repo_root.is_dir():
            raise NotADirectoryError(f"repo_root is not a directory: {repo_root}")
        # Filter to LLM-required checks first; if no candidates, skip the
        # file walk entirely (the LLM is not going to be called).
        eligible = [c for c in checks if c.raw_frontmatter.get("requires_llm") is True]
        if not eligible:
            return []
        excerpts = self._collect_excerpts(repo_root)
        all_findings: list[Finding] = []
        for check in eligible:
            prompt = _build_prompt(check, excerpts, self.ai_section_titles)
            schema = _schema_for(check)
            try:
                response = self.provider.query(prompt, schema)
            except ProviderResponseError as exc:
                all_findings.append(_error_finding(check, str(exc)))
                continue
            raw_findings = response.get("findings") or []
            if not isinstance(raw_findings, list):
                all_findings.append(_error_finding(check, "response.findings is not a list"))
                continue
            for raw in raw_findings:
                if not isinstance(raw, dict):
                    continue
                f = _coerce_finding(check, raw)
                if f is not None:
                    all_findings.append(f)
        all_findings.sort(key=lambda f: (f.file_path, f.line_number, f.rule_id))
        return all_findings
