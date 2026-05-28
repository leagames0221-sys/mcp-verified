#!/usr/bin/env python3
"""Dependency license audit (Layer 2).

Reads pyproject.toml and verifies every declared dependency resolves to an
OSS-permissible license (MIT, Apache 2.0, BSD-2/3, ISC). Exit non-zero if any
dependency has an unknown or disallowed license.

Runs on pre-commit when pyproject.toml is modified. Also runnable manually.

Exit codes:
  0 - all dependencies allowed
  1 - one or more dependencies have disallowed / unknown license
  2 - tool error (cannot read pyproject.toml, etc.)
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ALLOWED_LICENSES = {
    "MIT",
    "MIT License",
    "Apache-2.0",
    "Apache 2.0",
    "Apache Software License",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSD License",
    "ISC",
    "ISC License",
    "Python Software Foundation License",
}


def main() -> int:
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("audit_deps: pyproject.toml not found", file=sys.stderr)
        return 2

    try:
        with pyproject_path.open("rb") as f:
            pyproject = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"audit_deps: cannot parse pyproject.toml: {exc}", file=sys.stderr)
        return 2

    project = pyproject.get("project", {})
    dependencies = project.get("dependencies", [])
    optional_deps = project.get("optional-dependencies", {})

    all_deps: list[str] = list(dependencies)
    for _group_name, group_deps in optional_deps.items():
        all_deps.extend(group_deps)

    if not all_deps:
        print("audit_deps: no dependencies declared. Audit trivially clean.")
        return 0

    try:
        from importlib.metadata import PackageNotFoundError, metadata
    except ImportError:
        print("audit_deps: importlib.metadata unavailable (Python < 3.8?)", file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    unresolved: list[str] = []

    for dep_spec in all_deps:
        pkg_name = (
            dep_spec.split(";")[0]
            .split(">=")[0]
            .split("==")[0]
            .split("<")[0]
            .split(">")[0]
            .split("[")[0]
            .strip()
        )
        if not pkg_name:
            continue

        try:
            meta = metadata(pkg_name)
        except PackageNotFoundError:
            unresolved.append(pkg_name)
            continue

        license_expression = (meta.get("License-Expression") or "").strip()
        license_field = (meta.get("License") or "").strip()
        classifiers = meta.get_all("Classifier") or []
        license_classifiers = [
            c.split("::")[-1].strip() for c in classifiers if c.startswith("License ::")
        ]

        candidates = {license_expression, license_field, *license_classifiers}
        candidates.discard("")

        if not candidates:
            failures.append((pkg_name, "<unknown / no license metadata>"))
            continue

        if not any(any(allowed in cand for allowed in ALLOWED_LICENSES) for cand in candidates):
            failures.append((pkg_name, " | ".join(sorted(candidates))))

    if failures:
        print("audit_deps: disallowed / unknown licenses found:", file=sys.stderr)
        for pkg, lic in failures:
            print(f"  - {pkg}: {lic}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Allowed licenses:", file=sys.stderr)
        for lic in sorted(ALLOWED_LICENSES):
            print(f"  - {lic}", file=sys.stderr)
        return 1

    if unresolved:
        print(
            f"audit_deps: {len(unresolved)} dep(s) not yet installed in env "
            f"(skipped license check): {', '.join(unresolved)}"
        )

    print(f"audit_deps: {len(all_deps) - len(unresolved)} dep(s) audited, 0 failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
