"""Command-line entry point for `mcp-verified`.

Implements T-15 / AC-1.1 / AC-1.7.

Subcommands:

- `audit` — walk the registry, audit candidates, write the verdict tree.
- `export-audit-db` — package one target's audit subtree for upstream PR.
- `version` — print the package version.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mcp_verified import __version__
from mcp_verified._pipeline import (
    DEFAULT_AUDITOR_GITHUB,
    DEFAULT_AUDITOR_NAME,
    PipelineConfig,
    run_audit,
)
from mcp_verified.budget.per_server import DEFAULT_PER_SERVER_BUDGET_SECONDS
from mcp_verified.checks.loader import load_checks
from mcp_verified.output.exporter import ExportError, export_audit_db_target
from mcp_verified.providers.base import Provider
from mcp_verified.providers.mock import MockProvider
from mcp_verified.providers.ollama import OllamaProvider
from mcp_verified.registry.client import RegistryClient

PROVIDER_NAMES = ("ollama", "mock")


def _build_provider(name: str) -> Provider:
    if name == "ollama":
        return OllamaProvider()
    if name == "mock":
        return MockProvider()
    raise SystemExit(f"unknown provider: {name!r}; valid: {PROVIDER_NAMES}")


def _select_top_entries(client: RegistryClient, top: int):
    from mcp_verified.discovery.candidates import top_candidates

    entries = client.list_servers()
    scored = top_candidates(entries, n=top)
    return [c.entry for c in scored]


def cmd_audit(args: argparse.Namespace) -> int:
    if args.top <= 0:
        print("--top must be positive", file=sys.stderr)
        return 2

    provider = _build_provider(args.provider)
    out_dir = Path(args.out)

    checks: tuple = ()
    if args.checks:
        loaded = load_checks(Path(args.checks))
        checks = tuple(loaded)

    if args.fixture:
        # Test path: read entries from a JSON fixture instead of the live API.
        import json

        from mcp_verified.registry.client import parse_response

        payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        entries, _ = parse_response(payload)
    else:
        client = RegistryClient()
        entries = _select_top_entries(client, args.top)

    # If we loaded from a fixture, still honor --top by slicing.
    if args.fixture:
        entries = entries[: args.top]

    config = PipelineConfig(
        out_dir=out_dir,
        provider=provider,
        checks=checks,
        auditor_name=args.auditor or DEFAULT_AUDITOR_NAME,
        auditor_github=args.auditor_github or DEFAULT_AUDITOR_GITHUB,
        per_server_budget_seconds=args.per_server_budget,
        project_version=__version__,
    )
    summary = run_audit(entries, config=config)
    print(summary.to_summary_line())
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    try:
        path = export_audit_db_target(
            target_dir=Path(args.target),
            output_path=Path(args.output),
            host=args.host,
            owner=args.owner,
            repo=args.repo,
        )
    except ExportError as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 1
    print(str(path))
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-verified",
        description=(
            "Reproducible, batched audit of every server in the official MCP "
            "registry under four constraints (free, no credit card, "
            "local-first, security-first)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser(
        "audit",
        help="Walk the registry, audit candidates, write the verdict tree.",
    )
    p_audit.add_argument("--top", type=int, default=50, help="Number of top candidates to audit.")
    p_audit.add_argument("--out", type=str, required=True, help="Root output directory.")
    p_audit.add_argument(
        "--checks",
        type=str,
        default=None,
        help="Directory containing .md check definitions.",
    )
    p_audit.add_argument(
        "--provider",
        type=str,
        default="ollama",
        choices=PROVIDER_NAMES,
        help="LLM provider for the LLM-assisted executor.",
    )
    p_audit.add_argument(
        "--per-server-budget",
        type=float,
        default=DEFAULT_PER_SERVER_BUDGET_SECONDS,
        help="Wall-clock cap per candidate (seconds).",
    )
    p_audit.add_argument(
        "--auditor",
        type=str,
        default=None,
        help="Override auditor name (default mcp-verified).",
    )
    p_audit.add_argument(
        "--auditor-github",
        type=str,
        default=None,
        help="Override auditor GitHub handle.",
    )
    p_audit.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="(test) Read registry payload from this JSON file instead of network.",
    )
    p_audit.set_defaults(func=cmd_audit)

    p_export = sub.add_parser(
        "export-audit-db", help="Package one target's audit subtree as a tarball."
    )
    p_export.add_argument(
        "--target", type=str, required=True, help="Path to the target's audit dir."
    )
    p_export.add_argument("--output", type=str, required=True, help="Path to the .tar.gz to write.")
    p_export.add_argument(
        "--host", type=str, default=None, help="Override host in the tarball prefix."
    )
    p_export.add_argument(
        "--owner", type=str, default=None, help="Override owner in the tarball prefix."
    )
    p_export.add_argument(
        "--repo", type=str, default=None, help="Override repo in the tarball prefix."
    )
    p_export.set_defaults(func=cmd_export)

    p_version = sub.add_parser("version", help="Print the package version.")
    p_version.set_defaults(func=cmd_version)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
