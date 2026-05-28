"""Tests for `mcp_verified.checks.frontmatter` — parser subset behaviour."""

from __future__ import annotations

import pytest

from mcp_verified.checks.frontmatter import (
    Frontmatter,
    FrontmatterParseError,
    parse_frontmatter,
)


class TestEnvelope:
    def test_strips_dashed_envelope(self) -> None:
        text = "---\ntitle: Foo\n---\nbody text\n"
        result = parse_frontmatter(text)
        assert result.fields == {"title": "Foo"}
        # splitlines() drops the trailing newline; the body is the line content.
        assert result.body == "body text"

    def test_handles_crlf_envelope(self) -> None:
        text = "---\r\ntitle: Foo\r\n---\r\nbody\r\n"
        result = parse_frontmatter(text)
        assert result.fields == {"title": "Foo"}

    def test_rejects_missing_opening_marker(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("title: Foo\n---\nbody\n")

    def test_rejects_missing_closing_marker(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\ntitle: Foo\nbody\n")

    def test_empty_frontmatter_body(self) -> None:
        result = parse_frontmatter("---\n---\n")
        assert result.fields == {}
        assert result.body == ""


class TestScalarValues:
    def test_string_value(self) -> None:
        result = parse_frontmatter("---\ntitle: Hello world\n---\n")
        assert result.fields == {"title": "Hello world"}

    def test_int_value(self) -> None:
        result = parse_frontmatter("---\ncwe-primary: 798\n---\n")
        assert result.fields == {"cwe-primary": 798}

    def test_float_value(self) -> None:
        result = parse_frontmatter("---\nversion: 1.0\n---\n")
        assert result.fields == {"version": 1.0}

    def test_bool_true(self) -> None:
        result = parse_frontmatter("---\nenabled: true\n---\n")
        assert result.fields == {"enabled": True}

    def test_bool_false(self) -> None:
        result = parse_frontmatter("---\nenabled: false\n---\n")
        assert result.fields == {"enabled": False}

    def test_double_quoted_string(self) -> None:
        result = parse_frontmatter('---\ntitle: "Quoted Title"\n---\n')
        assert result.fields == {"title": "Quoted Title"}

    def test_single_quoted_string(self) -> None:
        result = parse_frontmatter("---\ntitle: 'Single quoted'\n---\n")
        assert result.fields == {"title": "Single quoted"}


class TestListValues:
    def test_empty_list(self) -> None:
        result = parse_frontmatter("---\nvulnerability-db: []\n---\n")
        assert result.fields == {"vulnerability-db": []}

    def test_string_list(self) -> None:
        result = parse_frontmatter("---\ntags: [a, b, c]\n---\n")
        assert result.fields == {"tags": ["a", "b", "c"]}

    def test_int_list(self) -> None:
        result = parse_frontmatter("---\ncwe: [798, 200, 522]\n---\n")
        assert result.fields == {"cwe": [798, 200, 522]}

    def test_rejects_nested_list(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\nnested: [[1, 2], [3, 4]]\n---\n")

    def test_rejects_nested_map_in_list(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\nnested: [{a: 1}, {b: 2}]\n---\n")


class TestStructureRejection:
    def test_rejects_block_list(self) -> None:
        text = (
            "---\n"
            "cwe:\n"
            "  - 798\n"
            "  - 200\n"
            "---\n"
        )
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter(text)

    def test_rejects_inline_map(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\nmap: {a: 1, b: 2}\n---\n")

    def test_rejects_duplicate_key(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\ntitle: a\ntitle: b\n---\n")

    def test_rejects_non_key_value_line(self) -> None:
        with pytest.raises(FrontmatterParseError):
            parse_frontmatter("---\nnot a key value line\n---\n")


class TestBodyExtraction:
    def test_body_preserved_with_internal_dashes(self) -> None:
        text = (
            "---\n"
            "title: x\n"
            "---\n"
            "## Section\n"
            "Body with --- internal triple-dash.\n"
        )
        result = parse_frontmatter(text)
        assert result.body == "## Section\nBody with --- internal triple-dash."

    def test_blank_lines_in_frontmatter_skipped(self) -> None:
        text = "---\ntitle: a\n\nversion: 1\n---\n"
        result = parse_frontmatter(text)
        assert result.fields == {"title": "a", "version": 1}

    def test_comment_lines_skipped(self) -> None:
        text = "---\n# a comment\ntitle: a\n---\n"
        result = parse_frontmatter(text)
        assert result.fields == {"title": "a"}


def test_result_is_frozen_dataclass() -> None:
    result = parse_frontmatter("---\ntitle: x\n---\n")
    assert isinstance(result, Frontmatter)
    with pytest.raises(Exception):
        result.fields = {}  # type: ignore[misc]
