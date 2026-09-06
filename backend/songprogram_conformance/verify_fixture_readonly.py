"""Enforce the read-only boundary around SongProgram conformance authority.

This is intentionally a repository-local check: it compares the current worktree
with ``HEAD`` through ``git status`` and therefore needs neither a CI merge-base
nor a remote base reference.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT = Path("backend/app")
PROTECTED_PREFIXES = (
    PurePosixPath("backend/songprogram_conformance/fixtures"),
    PurePosixPath("backend/songprogram_conformance/goldens"),
    PurePosixPath("backend/songprogram_conformance/schemas"),
)
PROTECTED_ORACLE_NAMES = {
    "canonical.py",
    "identifiers.py",
    "protocol.py",
    "reference.py",
    "runner.py",
}
BUILDER_MODULE_PREFIXES = (
    "songprogram_conformance.build_",
    "songprogram_conformance.generate_",
)
BUILDER_PATH_MARKERS = (
    "songprogram_conformance/build_",
    "songprogram_conformance/generate_",
)


class FixtureReadonlyViolation(AssertionError):
    """A production source or worktree change crossed the fixture boundary."""


def is_protected(path: PurePosixPath) -> bool:
    """Return whether a repository-relative path is conformance authority."""

    if any(path == prefix or prefix in path.parents for prefix in PROTECTED_PREFIXES):
        return True
    if path.parent == PurePosixPath("backend/songprogram_conformance") and (
        path.name in PROTECTED_ORACLE_NAMES or "oracle" in path.stem
    ):
        return True
    return path.parent == PurePosixPath("docs") and (
        "contract" in path.stem or path.name == "song_program_spec.md"
    )


def protected_worktree_changes(repository_root: Path) -> list[PurePosixPath]:
    """List changed/untracked protected paths, without relying on a CI base ref."""

    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise FixtureReadonlyViolation(
            "fixture read-only guard requires a Git worktree: " + result.stderr.strip()
        )

    changes: list[PurePosixPath] = []
    for line in result.stdout.splitlines():
        # Porcelain v1 is `XY PATH`; a rename contains `old -> new`, but either
        # endpoint must be treated as a protected change.
        raw_path = line[3:]
        candidates = raw_path.split(" -> ") if " -> " in raw_path else [raw_path]
        for candidate in candidates:
            path = PurePosixPath(candidate.strip().strip('"'))
            if is_protected(path):
                changes.append(path)
    return sorted(set(changes))


def _builder_reference(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return value.startswith(BUILDER_MODULE_PREFIXES) or any(
        marker in normalized for marker in BUILDER_PATH_MARKERS
    )


def production_builder_references(repository_root: Path) -> list[str]:
    """Find direct imports or literal subprocess/module references to builders."""

    violations: list[str] = []
    source_root = repository_root / PRODUCTION_ROOT
    for source in sorted(source_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        relative = source.relative_to(repository_root)
        for node in ast.walk(tree):
            values: list[str] = []
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                values.extend(f"{module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                values.append(node.value)
            for value in values:
                if _builder_reference(value):
                    violations.append(f"{relative}:{node.lineno}: {value}")
    return violations


def verify(repository_root: Path = REPOSITORY_ROOT, *, allow_authoritative_update: bool = False) -> None:
    """Raise when production uses builders or checked-in authority was edited."""

    builder_references = production_builder_references(repository_root)
    if builder_references:
        raise FixtureReadonlyViolation(
            "production code must not invoke conformance fixture builders:\n  "
            + "\n  ".join(builder_references)
        )

    changes = protected_worktree_changes(repository_root)
    if changes and not allow_authoritative_update:
        raise FixtureReadonlyViolation(
            "authoritative fixtures, oracles, and contracts are read-only:\n  "
            + "\n  ".join(str(path) for path in changes)
            + "\nUse --allow-authoritative-update only for the documented oracle-maintainer workflow."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-authoritative-update",
        action="store_true",
        help="permit protected worktree changes for an explicit oracle-maintainer update",
    )
    args = parser.parse_args(argv)
    try:
        verify(allow_authoritative_update=args.allow_authoritative_update)
    except FixtureReadonlyViolation as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
