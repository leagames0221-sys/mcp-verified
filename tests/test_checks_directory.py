"""Verify the shipped `checks/` directory parses cleanly — T-17 surface."""

from __future__ import annotations

from pathlib import Path

from mcp_verified.checks.loader import load_check, load_checks

REPO_CHECKS_DIR = Path(__file__).parent.parent / "checks"


class TestShippedChecksDirectory:
    def test_load_checks_returns_at_least_seven_active(self) -> None:
        active = load_checks(REPO_CHECKS_DIR)
        ids = [c.id for c in active]
        # 4 upstream verbatim (active) + 3 MCP-specific = 7.
        assert len(active) >= 7
        # Every shipped MCP-specific check must surface.
        for required in (
            "mcp-transport-security",
            "tool-poisoning-detection",
            "redirect-hijacking",
        ):
            assert required in ids

    def test_credential_management_seeded_from_upstream(self) -> None:
        path = REPO_CHECKS_DIR / "credential-management-security.md"
        check = load_check(path)
        assert check is not None
        assert check.priority == "critical"
        assert 798 in check.cwe

    def test_draft_files_skipped_by_loader(self) -> None:
        ci_secrets = REPO_CHECKS_DIR / "ci-secrets.md"
        if ci_secrets.exists():
            # The upstream draft file is shipped for documentation purposes
            # but must not be loaded as an active check.
            assert load_check(ci_secrets) is None

    def test_mcp_specific_checks_are_active(self) -> None:
        for slug in (
            "mcp-transport-security",
            "tool-poisoning-detection",
            "redirect-hijacking",
        ):
            path = REPO_CHECKS_DIR / f"{slug}.md"
            check = load_check(path)
            assert check is not None
            assert check.status == "active"

    def test_attribution_file_exists(self) -> None:
        attribution = REPO_CHECKS_DIR / "ATTRIBUTION.md"
        assert attribution.exists()
        text = attribution.read_text(encoding="utf-8")
        # Pinned upstream commit must appear so the fork origin is auditable.
        assert "8e54ffb77e710bd26009786d93a5df154fa4b45d" in text
        assert "Apache" in text
