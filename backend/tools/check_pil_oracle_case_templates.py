"""Pre-flight checks for the non-authoritative PIL oracle case templates.

The templates in ``docs/pil_oracle_case_templates/`` are implementation-side
case *inputs*; only the oracle maintainer may promote them into authoritative
fixtures by filling the golden fields.  This tool keeps the templates honest
between regenerations:

1. every case passes ``validate_pil_oracle_case_bindings`` (phase-exact
   assets and every locally recomputable binding);
2. every golden/expected field stays null — a non-null golden in this
   directory means someone bypassed the authoritative-update workflow;
3. coverage labels are subsets of ``PIL_REQUIRED_COVERAGE`` and the template
   set covers every required label;
4. the suite index mirrors the case files (case IDs, paths, coverage rows)
   with all of its own hashes null.

The tool is read-only.  Run from the backend directory:

    python tools/check_pil_oracle_case_templates.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.pil_fixture_suite import (  # noqa: E402
    PIL_REQUIRED_COVERAGE,
    validate_pil_oracle_case_bindings,
)

TEMPLATE_DIR = BACKEND.parent / "docs" / "pil_oracle_case_templates"

FAILURES: list[str] = []


def _fail(message: str) -> None:
    FAILURES.append(message)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    case_paths = sorted(TEMPLATE_DIR.glob("pil_*.json"))
    if not case_paths:
        _fail(f"no case templates found in {TEMPLATE_DIR}")
    index_path = TEMPLATE_DIR / "suite_index.json"
    if not index_path.exists():
        _fail("suite_index.json missing")
        index = {"cases": [], "required_coverage": []}
    else:
        index = _load(index_path)

    covered: set[str] = set()
    case_ids: list[str] = []
    for path in case_paths:
        case = _load(path)
        case_id = case.get("case_id")
        case_ids.append(case_id)

        try:
            validate_pil_oracle_case_bindings(case)
        except Exception as exc:  # noqa: BLE001 - report any binding failure
            _fail(f"{path.name}: binding validation failed: {exc}")

        if case.get("case_hash") is not None:
            _fail(f"{path.name}: case_hash must stay null in templates")
        expected = case.get("expected", {})
        for key, value in sorted(expected.items()):
            if value is not None:
                _fail(f"{path.name}: expected.{key} must stay null in templates")

        coverage = case.get("coverage", [])
        unknown = sorted(set(coverage) - set(PIL_REQUIRED_COVERAGE))
        if unknown:
            _fail(f"{path.name}: unknown coverage labels {unknown}")
        covered.update(coverage)

    missing = sorted(set(PIL_REQUIRED_COVERAGE) - covered)
    if missing:
        _fail(f"required coverage labels without any template: {missing}")

    if index.get("required_coverage") != PIL_REQUIRED_COVERAGE:
        _fail("suite_index required_coverage differs from PIL_REQUIRED_COVERAGE")
    for key in ("suite_hash", "suite_version"):
        if index.get(key) is not None:
            _fail(f"suite_index.{key} must stay null in templates")
    rows = index.get("cases", [])
    if [row.get("case_id") for row in rows] != sorted(case_ids):
        _fail("suite_index case rows do not match the template case IDs")
    by_id = {row.get("case_id"): row for row in rows}
    for path in case_paths:
        case = _load(path)
        row = by_id.get(case["case_id"])
        if row is None:
            continue
        if row.get("path") != path.name:
            _fail(f"{path.name}: suite_index path mismatch: {row.get('path')}")
        if row.get("coverage") != case.get("coverage"):
            _fail(f"{path.name}: suite_index coverage row differs from case coverage")
        for key in ("raw_file_sha256", "case_hash", "case_schema_hash"):
            if row.get(key) is not None:
                _fail(f"{path.name}: suite_index row {key} must stay null")

    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}")
        return 1
    print(f"pil oracle case templates: OK ({len(case_paths)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
