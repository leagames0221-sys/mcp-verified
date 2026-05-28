"""Tests for `mcp_verified.cli` — T-15 e2e surface."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from mcp_verified.cli import main


FIXTURE_PAYLOAD = {
    "servers": [
        {
            "server": {
                "name": "remote-only/server",
                "version": "1.0.0",
                "description": "no repo",
                "remotes": [{"type": "streamable-http", "url": "https://x.example/mcp"}],
            },
            "_meta": {
                "io.modelcontextprotocol.registry/official": {
                    "status": "active",
                    "publishedAt": "2026-05-29T00:00:00Z",
                    "updatedAt": "2026-05-29T00:00:00Z",
                    "isLatest": True,
                }
            },
        },
    ],
    "metadata": {"nextCursor": None, "count": 1},
}


@pytest.fixture
def fixture_path(tmp_path: Path) -> Path:
    path = tmp_path / "registry-fixture.json"
    path.write_text(json.dumps(FIXTURE_PAYLOAD), encoding="utf-8")
    return path


def _capture(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


# ---------- version ----------


class TestVersion:
    def test_version_prints_to_stdout(self) -> None:
        rc, out = _capture(["version"])
        assert rc == 0
        assert out.strip()


# ---------- audit ----------


class TestAudit:
    def test_audit_with_remote_only_entry_produces_unknown_summary(
        self, tmp_path: Path, fixture_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        rc, output = _capture(
            [
                "audit",
                "--fixture",
                str(fixture_path),
                "--top",
                "1",
                "--out",
                str(out_dir),
                "--provider",
                "mock",
            ]
        )
        assert rc == 0
        # The summary line carries the seven counters.
        line = output.strip().splitlines()[-1]
        for token in (
            "audited=1",
            "verified=",
            "caution=",
            "risky=",
            "unknown=1",
            "timeout=",
            "error=",
        ):
            assert token in line
        # The verdict registry directory must exist and contain at least one
        # audit-manifest.json (the unknown-verdict candidate's manifest).
        manifest_paths = list(out_dir.rglob("audit-manifest.json"))
        assert len(manifest_paths) >= 1
        loaded = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
        assert loaded["audit_metadata"]["verdict"] == "unknown"

    def test_audit_top_zero_is_rejected(self, tmp_path: Path, fixture_path: Path) -> None:
        rc, _ = _capture(
            [
                "audit",
                "--fixture",
                str(fixture_path),
                "--top",
                "0",
                "--out",
                str(tmp_path / "out"),
                "--provider",
                "mock",
            ]
        )
        assert rc == 2


# ---------- export-audit-db ----------


class TestExportSubcommand:
    def test_missing_target_returns_nonzero(self, tmp_path: Path) -> None:
        rc, _ = _capture(
            [
                "export-audit-db",
                "--target",
                str(tmp_path / "does-not-exist"),
                "--output",
                str(tmp_path / "x.tar.gz"),
            ]
        )
        assert rc == 1


# ---------- arg parsing ----------


class TestArgParsing:
    def test_missing_subcommand_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_unknown_provider_exits_nonzero(
        self, tmp_path: Path, fixture_path: Path
    ) -> None:
        with pytest.raises(SystemExit):
            main(
                [
                    "audit",
                    "--fixture",
                    str(fixture_path),
                    "--top",
                    "1",
                    "--out",
                    str(tmp_path / "out"),
                    "--provider",
                    "bogus",
                ]
            )
