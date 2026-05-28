#!/usr/bin/env python3
"""Stdlib-only line coverage measurement.

Implements the T-18 verify step (`pytest --cov=mcp_verified --cov-fail-under=80`)
using Python's built-in `trace` module so the gate can be exercised without
adding `pytest-cov` to the local environment. Returns the overall percentage
and exits non-zero if the configured floor is not met.

Usage:
    python scripts/coverage_stdlib.py              # default floor = 80%
    python scripts/coverage_stdlib.py --floor 90   # custom floor
    python scripts/coverage_stdlib.py --per-file   # per-file table only

`pytest-cov` remains the canonical CI tool; CI workflows install it in a
fresh environment and run `pytest --cov=mcp_verified --cov-fail-under=80`.
This script exists so developers can run the same gate locally without
the install step.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import trace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "mcp_verified"


def _executable_lines(path: Path) -> set[int]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or not hasattr(node, "lineno"):
            continue
        # Pure top-level docstrings (Expr->Constant str) are not executable code.
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        out.add(node.lineno)
    return out


def _trace_pytest() -> dict[tuple[str, int], int]:
    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, sys.exec_prefix],
        ignoremods=["pytest", "_pytest", "pluggy"],
    )

    import pytest as _pytest

    def _run() -> None:
        _pytest.main(["-q", str(REPO_ROOT / "tests")])

    tracer.runfunc(_run)
    return tracer.results().counts


def measure() -> tuple[float, dict[str, tuple[int, int]]]:
    """Return (overall_pct, {rel_path: (executed, total)}).

    A file is considered if at least one of its lines was traced.
    """
    raw = _trace_pytest()
    per_file_hits: dict[str, set[int]] = {}
    src_str = str(SRC_ROOT)
    for (filename, lineno), _ in raw.items():
        if not filename.startswith(src_str):
            continue
        rel = os.path.relpath(filename, src_str).replace("\\", "/")
        per_file_hits.setdefault(rel, set()).add(lineno)

    rows: dict[str, tuple[int, int]] = {}
    total_exec = 0
    total_hit = 0
    for rel, hit_set in per_file_hits.items():
        path = SRC_ROOT / rel
        if path.suffix != ".py":
            continue
        execs = _executable_lines(path)
        if not execs:
            continue
        hits = hit_set & execs
        rows[rel] = (len(hits), len(execs))
        total_exec += len(execs)
        total_hit += len(hits)
    overall = (100.0 * total_hit / total_exec) if total_exec else 0.0
    return overall, rows


def _print_table(rows: dict[str, tuple[int, int]]) -> None:
    print(f"{'file':50s} {'exec':>5s} {'hit':>5s} {'pct':>6s}")
    print("-" * 70)
    for rel in sorted(rows.keys()):
        hit, exec_ = rows[rel]
        pct = (100.0 * hit / exec_) if exec_ else 0.0
        print(f"{rel:50s} {exec_:5d} {hit:5d} {pct:5.1f}%")
    total_hit = sum(h for h, _ in rows.values())
    total_exec = sum(e for _, e in rows.values())
    overall = (100.0 * total_hit / total_exec) if total_exec else 0.0
    print("-" * 70)
    print(f"OVERALL: {total_hit}/{total_exec} = {overall:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--floor", type=float, default=80.0)
    parser.add_argument("--per-file", action="store_true")
    args = parser.parse_args()

    overall, rows = measure()
    if args.per_file:
        _print_table(rows)
    else:
        print(f"coverage_stdlib: {overall:.1f}% over {len(rows)} modules")
    if overall < args.floor:
        print(
            f"coverage_stdlib: floor {args.floor:.1f}% not met (got {overall:.1f}%)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
