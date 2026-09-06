from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from songprogram_conformance.verify_fixture_readonly import (
    FixtureReadonlyViolation,
    production_builder_references,
    protected_worktree_changes,
    verify,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _repository(tmp_path: Path) -> Path:
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "songprogram_conformance" / "fixtures").mkdir(parents=True)
    (tmp_path / "backend" / "songprogram_conformance" / "fixtures" / "case.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "backend" / "app" / "implementation.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=Fixture Guard", "-c", "user.email=guard@example.invalid", "commit", "-qm", "baseline")
    return tmp_path


def test_guard_passes_for_the_repository() -> None:
    verify(REPOSITORY_ROOT)


def test_worktree_check_detects_protected_change_without_a_ci_base_ref(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    protected = root / "backend" / "songprogram_conformance" / "fixtures" / "case.json"
    protected.write_text('{"changed": true}\n', encoding="utf-8")

    assert protected_worktree_changes(root) == [
        Path("backend/songprogram_conformance/fixtures/case.json")
    ]
    with pytest.raises(FixtureReadonlyViolation, match="read-only"):
        verify(root)
    verify(root, allow_authoritative_update=True)


def test_production_import_of_builder_is_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    source = root / "backend" / "app" / "implementation.py"
    source.write_text(
        "from songprogram_conformance.build_project_goldens import build_triad\n",
        encoding="utf-8",
    )

    references = production_builder_references(root)
    assert references == [
        "backend/app/implementation.py:1: songprogram_conformance.build_project_goldens.build_triad"
    ]
    with pytest.raises(FixtureReadonlyViolation, match="must not invoke"):
        verify(root)


def test_production_import_of_oracle_is_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    source = root / "backend" / "app" / "implementation.py"
    source.write_text(
        "from songprogram_conformance.gen0b_receipt_oracle import usage\n",
        encoding="utf-8",
    )

    references = production_builder_references(root)
    assert references == [
        "backend/app/implementation.py:1: songprogram_conformance.gen0b_receipt_oracle"
    ]
    with pytest.raises(FixtureReadonlyViolation, match="must not invoke"):
        verify(root)
