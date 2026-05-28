"""Tests for `mcp_verified.checks.executors.deterministic` — T-06 surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_verified.checks.executors.deterministic import (
    DEFAULT_PATTERNS,
    DeterministicExecutor,
    Finding,
    Pattern,
    _redact_match,
)


# ---------- Fixture builders ----------


VULNERABLE_PY = """\
# Synthetic vulnerable file. Every pattern in the default set fires here.
# All credential-shaped strings are deliberately marked EXAMPLE so they
# cannot be confused with real secrets by automated scanners.
import os
import subprocess

OPENAI_TOKEN = "sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE0123"  # gitleaks:allow
ANTHROPIC_TOKEN = "sk-ant-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE01234567"  # gitleaks:allow
AWS_ACCESS = "AKIAEXAMPLEKEY012345"  # gitleaks:allow
DB_PASSWORD = "password = 'hunter2-very-secret'"

def render(expr):
    return eval(expr)

def shadow(expr):
    return exec(expr)

def run(cmd):
    return subprocess.run(cmd, shell=True)
"""


CLEAN_PY = """\
# Synthetic clean file: no rule should fire here.
import os
import subprocess


def render(expr: str) -> str:
    # Templating only; not dynamic code evaluation.
    return expr.format(x=1)


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, check=True)


def from_env() -> str:
    return os.environ["SERVICE_TOKEN"]
"""


@pytest.fixture
def vulnerable_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "vuln.py").write_text(VULNERABLE_PY, encoding="utf-8")
    return tmp_path


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "safe.py").write_text(CLEAN_PY, encoding="utf-8")
    return tmp_path


# ---------- Default pattern coverage ----------


class TestVulnerableFixture:
    def test_every_default_rule_fires_at_least_once(self, vulnerable_repo: Path) -> None:
        result = DeterministicExecutor().run(vulnerable_repo)
        rule_ids = {f.rule_id for f in result}
        for pattern in DEFAULT_PATTERNS:
            assert pattern.rule_id in rule_ids, f"{pattern.rule_id} did not fire"

    def test_findings_record_relative_path(self, vulnerable_repo: Path) -> None:
        result = DeterministicExecutor().run(vulnerable_repo)
        for finding in result:
            assert finding.file_path == "src/vuln.py"
            assert isinstance(finding, Finding)

    def test_credential_matches_are_redacted(self, vulnerable_repo: Path) -> None:
        result = DeterministicExecutor().run(vulnerable_repo)
        # No finding's redacted_snippet should contain the literal full
        # OpenAI / Anthropic / AWS token from the synthetic fixture.
        for finding in result:
            if finding.rule_id == "CRED-API-KEY-OPENAI":
                assert "EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE0123" not in finding.redacted_snippet
                assert "REDACTED" in finding.redacted_snippet
            if finding.rule_id == "CRED-API-KEY-ANTHROPIC":
                assert "EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE01234567" not in finding.redacted_snippet
            if finding.rule_id == "CRED-AWS-ACCESS-KEY-ID":
                assert "AKIAEXAMPLEKEY012345" not in finding.redacted_snippet

    def test_eval_and_exec_not_redacted(self, vulnerable_repo: Path) -> None:
        """Code-execution-pattern findings are not credential leaks; their
        snippet is left intact for assessment context."""
        result = DeterministicExecutor().run(vulnerable_repo)
        for finding in result:
            if finding.rule_id == "EXEC-EVAL-CALL":
                assert "REDACTED" not in finding.redacted_snippet
                assert "eval" in finding.redacted_snippet
            if finding.rule_id == "EXEC-EXEC-CALL":
                assert "REDACTED" not in finding.redacted_snippet
                assert "exec" in finding.redacted_snippet
            if finding.rule_id == "EXEC-SHELL-TRUE":
                assert "REDACTED" not in finding.redacted_snippet
                assert "shell" in finding.redacted_snippet

    def test_cwe_recorded_per_finding(self, vulnerable_repo: Path) -> None:
        result = DeterministicExecutor().run(vulnerable_repo)
        cwe_by_rule = {
            "CRED-API-KEY-OPENAI": 798,
            "CRED-API-KEY-ANTHROPIC": 798,
            "CRED-AWS-ACCESS-KEY-ID": 798,
            "CRED-PASSWORD-ASSIGN": 798,
            "EXEC-EVAL-CALL": 95,
            "EXEC-EXEC-CALL": 95,
            "EXEC-SHELL-TRUE": 78,
        }
        for finding in result:
            assert finding.cwe == cwe_by_rule[finding.rule_id]


class TestCleanFixture:
    def test_zero_findings_on_safe_code(self, clean_repo: Path) -> None:
        result = DeterministicExecutor().run(clean_repo)
        assert result == []


# ---------- Determinism ----------


class TestDeterministicOrdering:
    def test_two_runs_produce_identical_output(self, vulnerable_repo: Path) -> None:
        executor = DeterministicExecutor()
        run1 = executor.run(vulnerable_repo)
        run2 = executor.run(vulnerable_repo)
        assert run1 == run2

    def test_findings_are_sorted_by_file_line_rule(self, vulnerable_repo: Path) -> None:
        # Add a second file to verify multi-file ordering.
        (vulnerable_repo / "src" / "another.py").write_text(
            "TOKEN = 'sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLEZZZZ'  # gitleaks:allow\n",
            encoding="utf-8",
        )
        result = DeterministicExecutor().run(vulnerable_repo)
        keys = [(f.file_path, f.line_number, f.rule_id) for f in result]
        assert keys == sorted(keys)


# ---------- File walker behaviour ----------


class TestFileWalker:
    def test_skip_dirs_excluded(self, tmp_path: Path) -> None:
        # Vulnerable file inside .git/ should be skipped.
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "leak.py").write_text(
            'TOKEN = "sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE0123"  # gitleaks:allow\n',
            encoding="utf-8",
        )
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "leak.js").write_text(
            'const t = "sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLEZZZ";  // gitleaks:allow\n',
            encoding="utf-8",
        )
        result = DeterministicExecutor().run(tmp_path)
        assert result == []

    def test_extensions_outside_text_set_are_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "blob.bin").write_bytes(b"\x00\x01" + b"sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE0123")
        result = DeterministicExecutor().run(tmp_path)
        assert result == []

    def test_files_larger_than_max_size_are_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "huge.py"
        # Build a >1 KB file but configure the executor with max_file_size=512.
        path.write_text(("# pad\n" * 200) + "TOKEN = 'sk-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE0123'  # gitleaks:allow\n", encoding="utf-8")
        executor = DeterministicExecutor(max_file_size=512)
        result = executor.run(tmp_path)
        assert result == []

    def test_undecodable_file_is_skipped(self, tmp_path: Path) -> None:
        # Write invalid UTF-8 sequences into a .py file.
        (tmp_path / "bad.py").write_bytes(b"\xff\xfe\xfd\xfc broken-utf8")
        result = DeterministicExecutor().run(tmp_path)
        assert result == []

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(NotADirectoryError):
            DeterministicExecutor().run(tmp_path / "does-not-exist")


# ---------- Custom pattern injection ----------


class TestCustomPatterns:
    def test_can_run_with_user_supplied_patterns(self, tmp_path: Path) -> None:
        import re

        (tmp_path / "x.py").write_text("TODO: implement this\n", encoding="utf-8")
        custom = (
            Pattern(
                rule_id="TODO-COMMENT",
                severity="info",
                cwe=None,
                regex=re.compile(r"\bTODO\b"),
                description="Outstanding TODO marker.",
                redact=False,
            ),
        )
        result = DeterministicExecutor(patterns=custom).run(tmp_path)
        assert len(result) == 1
        assert result[0].rule_id == "TODO-COMMENT"
        assert result[0].cwe is None
        assert result[0].severity == "info"


# ---------- _redact_match unit behaviour ----------


class TestRedactMatch:
    def test_short_match_fully_redacted(self) -> None:
        assert _redact_match("abc") == "[REDACTED-3]"

    def test_longer_match_keeps_head(self) -> None:
        out = _redact_match("sk-abcdefghij")
        assert out.startswith("sk-a")
        assert "REDACTED-13" in out

    def test_head_parameter_respected(self) -> None:
        out = _redact_match("AKIAEXAMPLEKEY12345", head=4)
        assert out.startswith("AKIA")
        assert "REDACTED-19" in out
