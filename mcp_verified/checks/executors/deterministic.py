"""Deterministic check executor: regex pattern match over a cloned tree.

Implements T-06 / AC-1.3 / AC-2.2.

The executor walks files under a repo root and applies a list of compiled
patterns. Matches become `Finding` records with:

- a stable `rule_id`,
- `severity` and optional `cwe`,
- the file path relative to the repo root,
- a 1-based `line_number`,
- a **redacted** match snippet (we never echo a literal credential into
  the verdict registry, even when the candidate is already public),
- a human-readable description for the assessment markdown.

The walker is deterministic: files are visited in lexicographically-sorted
order, and within a file findings are reported in `(line, rule_id)` order.
Two runs against the same tree produce byte-identical output.

Phase 1 scope is regex-only (no AST). The default rule set targets the
highest-signal classes — hard-coded credentials, `eval` / `exec`, and
`shell=True` invocations — sourced from CWE-78 (OS command injection),
CWE-95 (code injection), and CWE-798 (use of hard-coded credentials).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB; larger files are likely data, not source.

DEFAULT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".github",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "out",
        "target",
        ".next",
        ".nuxt",
    }
)

DEFAULT_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
        ".md",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".html",
        ".htm",
        ".vue",
        ".svelte",
        ".rb",
        ".go",
        ".java",
        ".rs",
        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".pl",
        ".lua",
        ".scala",
        ".kt",
        ".kts",
        ".swift",
        ".dockerfile",
    }
)


@dataclass(frozen=True)
class Pattern:
    """One rule: a compiled regex plus its taxonomy and severity."""

    rule_id: str
    severity: str  # "critical" | "high" | "medium" | "low" | "info"
    cwe: int | None
    regex: re.Pattern[str]
    description: str
    redact: bool = True  # If True, the match span is replaced with a length tag.


@dataclass(frozen=True)
class Finding:
    """One hit produced by one pattern against one line."""

    rule_id: str
    severity: str
    cwe: int | None
    file_path: str  # forward-slash, relative to repo root
    line_number: int  # 1-based
    redacted_snippet: str
    description: str


def _redact_match(match: str, *, head: int = 4) -> str:
    """Replace a sensitive match with a length-tagged stub.

    The output is structured enough to be useful in a finding ("this look
    like an OpenAI-style key, 51 chars") without ever revealing the
    literal value.
    """
    n = len(match)
    if n <= head:
        return f"[REDACTED-{n}]"
    return f"{match[:head]}...[REDACTED-{n}]"


# Default Phase 1 rule set. Each pattern is intentionally narrow; widening
# them is a follow-up task that requires either an ADR amendment or a new
# checks/ markdown definition.
DEFAULT_PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        rule_id="CRED-API-KEY-OPENAI",
        severity="high",
        cwe=798,
        regex=re.compile(r"sk-[A-Za-z0-9]{32,}"),
        description="OpenAI-shaped API key literal in source.",
    ),
    Pattern(
        rule_id="CRED-API-KEY-ANTHROPIC",
        severity="high",
        cwe=798,
        regex=re.compile(r"sk-ant-[A-Za-z0-9_-]{40,}"),
        description="Anthropic-shaped API key literal in source.",
    ),
    Pattern(
        rule_id="CRED-AWS-ACCESS-KEY-ID",
        severity="high",
        cwe=798,
        regex=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        description="AWS access-key-id literal in source.",
    ),
    Pattern(
        rule_id="CRED-PASSWORD-ASSIGN",
        severity="medium",
        cwe=798,
        regex=re.compile(
            r"""(?ix)
            \b(?:password|passwd|pwd)\s*[=:]\s*
            (?P<q>["'])(?P<val>(?!\s*$)[^"'\\]{6,})(?P=q)
            """
        ),
        description="Hard-coded password literal in source.",
    ),
    Pattern(
        rule_id="EXEC-EVAL-CALL",
        severity="high",
        cwe=95,
        regex=re.compile(r"(?<![A-Za-z0-9_])eval\s*\("),
        description="Use of eval() — dynamic code execution risk.",
        redact=False,
    ),
    Pattern(
        rule_id="EXEC-EXEC-CALL",
        severity="high",
        cwe=95,
        regex=re.compile(r"(?<![A-Za-z0-9_])exec\s*\("),
        description="Use of exec() — dynamic code execution risk.",
        redact=False,
    ),
    Pattern(
        rule_id="EXEC-SHELL-TRUE",
        severity="high",
        cwe=78,
        regex=re.compile(r"shell\s*=\s*True"),
        description="subprocess called with shell=True — command-injection vector.",
        redact=False,
    ),
)


def _iter_candidate_files(
    root: Path,
    *,
    skip_dirs: Iterable[str],
    text_extensions: Iterable[str],
    max_file_size: int,
) -> Iterator[Path]:
    """Yield files under `root` in lex-sorted order, applying the skip rules.

    The walker excludes any path whose parts contain a skip-dir name, files
    with an unrecognized extension, and files larger than `max_file_size`.
    """
    skip_set = frozenset(skip_dirs)
    ext_set = frozenset(text_extensions)
    # Sort the rglob output by string path for deterministic iteration order.
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in skip_set for part in rel_parts):
            continue
        if path.suffix.lower() not in ext_set:
            continue
        try:
            if path.stat().st_size > max_file_size:
                continue
        except OSError:
            continue
        yield path


def _scan_file(
    path: Path,
    rel_path: str,
    patterns: Sequence[Pattern],
) -> list[Finding]:
    """Apply every pattern to every line of one file. Return findings in
    `(line, rule_id)` order.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Binary-ish or unreadable content; static analysis cannot proceed.
        return []
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            for match in pattern.regex.finditer(line):
                snippet = match.group(0)
                if pattern.redact:
                    snippet = _redact_match(snippet)
                findings.append(
                    Finding(
                        rule_id=pattern.rule_id,
                        severity=pattern.severity,
                        cwe=pattern.cwe,
                        file_path=rel_path,
                        line_number=line_number,
                        redacted_snippet=snippet,
                        description=pattern.description,
                    )
                )
    findings.sort(key=lambda f: (f.line_number, f.rule_id))
    return findings


@dataclass(frozen=True)
class DeterministicExecutor:
    """Runs a fixed pattern set over a cloned tree and returns findings.

    Two runs against the same tree produce byte-identical output: the file
    walker is lex-sorted and findings are sorted by `(file, line, rule_id)`.
    """

    patterns: tuple[Pattern, ...] = DEFAULT_PATTERNS
    skip_dirs: frozenset[str] = field(default_factory=lambda: DEFAULT_SKIP_DIRS)
    text_extensions: frozenset[str] = field(default_factory=lambda: DEFAULT_TEXT_EXTENSIONS)
    max_file_size: int = DEFAULT_MAX_FILE_SIZE

    def run(self, repo_root: Path) -> list[Finding]:
        if not repo_root.is_dir():
            raise NotADirectoryError(f"repo_root is not a directory: {repo_root}")
        all_findings: list[Finding] = []
        for path in _iter_candidate_files(
            repo_root,
            skip_dirs=self.skip_dirs,
            text_extensions=self.text_extensions,
            max_file_size=self.max_file_size,
        ):
            rel_path = path.relative_to(repo_root).as_posix()
            all_findings.extend(_scan_file(path, rel_path, self.patterns))
        all_findings.sort(key=lambda f: (f.file_path, f.line_number, f.rule_id))
        return all_findings
