"""Tests for `mcp_verified.checks.executors.llm_assisted` — T-09 surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mcp_verified.checks.executors.llm_assisted import (
    LLMAssistedExecutor,
    _build_prompt,
)
from mcp_verified.checks.loader import CheckDefinition
from mcp_verified.providers.base import (
    Provider,
    ProviderResponseError,
    ProviderUnreachableError,
)
from mcp_verified.providers.mock import MockProvider


def _make_check(
    check_id: str = "synthetic-check",
    *,
    requires_llm: bool = True,
    title: str = "Synthetic LLM check",
    ai_instructions: str = "Look for synthetic risk patterns.",
) -> CheckDefinition:
    """Build a CheckDefinition without going through the loader / disk."""
    sections = {
        "Purpose": "test purpose",
        "For AI Assistants: Automated Analysis": ai_instructions,
    }
    raw_frontmatter: dict[str, Any] = {
        "title": title,
        "status": "active",
        "priority": "medium",
        "cwe": [],
        "tags": [],
    }
    if requires_llm:
        raw_frontmatter["requires_llm"] = True
    return CheckDefinition(
        id=check_id,
        title=title,
        status="active",
        priority="medium",
        cwe=(),
        cwe_primary=None,
        tags=(),
        sections=sections,
        file_path=Path("/tmp/synthetic.md"),
        sha256="0" * 64,
        raw_frontmatter=raw_frontmatter,
    )


@pytest.fixture
def small_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def world():\n    pass\n", encoding="utf-8")
    return tmp_path


# ---------- Provider stubs ----------


class _RecordingProvider(Provider):
    name = "recording"

    def __init__(self, response: dict[str, Any]) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._response = response

    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((prompt, schema))
        return dict(self._response)


class _RaisingProvider(Provider):
    name = "raising"

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        raise self._exc


# ---------- Determinism + mock fallback ----------


class TestDeterminism:
    def test_two_runs_identical_with_mock(self, small_repo: Path) -> None:
        executor = LLMAssistedExecutor()  # MockProvider by default
        checks = [_make_check("a"), _make_check("b")]
        run1 = executor.run(small_repo, checks)
        run2 = executor.run(small_repo, checks)
        assert run1 == run2

    def test_mock_yields_no_findings(self, small_repo: Path) -> None:
        executor = LLMAssistedExecutor(provider=MockProvider())
        assert executor.run(small_repo, [_make_check()]) == []


# ---------- requires_llm filter ----------


class TestRequiresLlmFilter:
    def test_only_runs_checks_with_requires_llm_true(self, small_repo: Path) -> None:
        provider = _RecordingProvider({"findings": []})
        executor = LLMAssistedExecutor(provider=provider)
        checks = [
            _make_check("with-llm", requires_llm=True),
            _make_check("without-llm", requires_llm=False),
        ]
        executor.run(small_repo, checks)
        assert len(provider.calls) == 1
        # The prompt should reference the LLM-required check, not the other.
        prompt = provider.calls[0][0]
        assert "Synthetic LLM check" in prompt

    def test_no_eligible_checks_means_no_provider_call(self, small_repo: Path) -> None:
        provider = _RecordingProvider({"findings": [{"rule_id": "X"}]})
        executor = LLMAssistedExecutor(provider=provider)
        checks = [_make_check(requires_llm=False)]
        result = executor.run(small_repo, checks)
        assert result == []
        assert provider.calls == []


# ---------- Response parsing ----------


class TestResponseParsing:
    def test_well_formed_findings_surface(self, small_repo: Path) -> None:
        response: dict[str, Any] = {
            "findings": [
                {
                    "rule_id": "LLM-SUSPICIOUS-AUTH",
                    "severity": "high",
                    "cwe": 287,
                    "file_path": "src/a.py",
                    "line_number": 12,
                    "snippet": "if password == 'x':",
                    "description": "Suspicious literal credential check.",
                }
            ]
        }
        executor = LLMAssistedExecutor(provider=_RecordingProvider(response))
        result = executor.run(small_repo, [_make_check()])
        assert len(result) == 1
        finding = result[0]
        assert finding.rule_id == "LLM-SUSPICIOUS-AUTH"
        assert finding.severity == "high"
        assert finding.cwe == 287
        assert finding.line_number == 12

    def test_missing_optional_fields_get_defaults(self, small_repo: Path) -> None:
        response: dict[str, Any] = {
            "findings": [
                {"rule_id": "X"},  # only the rule_id present
            ]
        }
        executor = LLMAssistedExecutor(provider=_RecordingProvider(response))
        result = executor.run(small_repo, [_make_check()])
        assert len(result) == 1
        finding = result[0]
        assert finding.rule_id == "X"
        assert finding.severity == "info"
        assert finding.cwe is None
        assert finding.line_number == 0

    def test_non_dict_finding_entries_are_skipped(self, small_repo: Path) -> None:
        response: dict[str, Any] = {
            "findings": [
                "not a dict",
                42,
                {"rule_id": "OK"},
            ]
        }
        executor = LLMAssistedExecutor(provider=_RecordingProvider(response))
        result = executor.run(small_repo, [_make_check()])
        rule_ids = [f.rule_id for f in result]
        assert rule_ids == ["OK"]

    def test_findings_field_not_a_list_emits_error_finding(self, small_repo: Path) -> None:
        response: dict[str, Any] = {"findings": "not a list"}
        executor = LLMAssistedExecutor(provider=_RecordingProvider(response))
        result = executor.run(small_repo, [_make_check()])
        assert len(result) == 1
        assert result[0].rule_id.startswith("CHECK-RUN-ERROR-")

    def test_missing_findings_field_returns_empty(self, small_repo: Path) -> None:
        response: dict[str, Any] = {"other": True}
        executor = LLMAssistedExecutor(provider=_RecordingProvider(response))
        result = executor.run(small_repo, [_make_check()])
        # `response.get("findings") or []` makes this an empty result, not an error.
        assert result == []


# ---------- Error handling ----------


class TestErrorHandling:
    def test_provider_response_error_yields_one_error_finding(self, small_repo: Path) -> None:
        executor = LLMAssistedExecutor(provider=_RaisingProvider(ProviderResponseError("garbage")))
        result = executor.run(small_repo, [_make_check("c1"), _make_check("c2")])
        # Two checks, each one fails individually -> two error findings.
        assert len(result) == 2
        for finding in result:
            assert finding.rule_id.startswith("CHECK-RUN-ERROR-")
            assert "garbage" in finding.description

    def test_provider_unreachable_propagates(self, small_repo: Path) -> None:
        """T-09 deliberately does not catch Unreachable; callers wrap with
        query_with_fallback if they want a swap to mock."""
        executor = LLMAssistedExecutor(provider=_RaisingProvider(ProviderUnreachableError("down")))
        with pytest.raises(ProviderUnreachableError):
            executor.run(small_repo, [_make_check()])

    def test_missing_repo_root_raises(self, tmp_path: Path) -> None:
        executor = LLMAssistedExecutor()
        with pytest.raises(NotADirectoryError):
            executor.run(tmp_path / "missing", [_make_check()])


# ---------- Prompt construction ----------


class TestPromptConstruction:
    def test_prompt_includes_ai_instructions(self) -> None:
        check = _make_check(ai_instructions="Look for hardcoded tokens and report them.")
        prompt = _build_prompt(
            check,
            excerpts=[("src/a.py", "def x(): pass")],
            ai_section_titles=("For AI Assistants: Automated Analysis",),
        )
        assert "Look for hardcoded tokens" in prompt
        assert "src/a.py" in prompt
        assert "def x(): pass" in prompt

    def test_prompt_falls_back_to_full_body_when_ai_section_missing(self) -> None:
        check = CheckDefinition(
            id="x",
            title="X",
            status="active",
            priority=None,
            cwe=(),
            cwe_primary=None,
            tags=(),
            sections={"Purpose": "only purpose"},
            file_path=Path("/x.md"),
            sha256="0" * 64,
            raw_frontmatter={},
        )
        prompt = _build_prompt(check, excerpts=[], ai_section_titles=("Missing",))
        assert "only purpose" in prompt
