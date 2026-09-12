from __future__ import annotations

import hashlib
import json

import pytest

from app.songprogram.perceptual import PilError
from app.songprogram.pil_fixture_suite import (
    PIL_REQUIRED_COVERAGE,
    validate_pil_fixture_suite,
)
from app.songprogram.search_decisions import decision_artifact_hash


def _bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _suite(tmp_path):
    schema_raw = _bytes({"type": "object"})
    schema_hash = _raw_hash(schema_raw)
    case = {
        "schema": "cps.pil-oracle-case",
        "schema_version": "1.0.0",
        "case_id": "pil_case",
        "coverage": PIL_REQUIRED_COVERAGE,
        "case_hash": "",
    }
    case["case_hash"] = decision_artifact_hash(case, "case_hash")
    raw = _bytes(case)
    (tmp_path / "case.json").write_bytes(raw)
    row = {
        "case_id": case["case_id"],
        "path": "case.json",
        "raw_file_sha256": _raw_hash(raw),
        "case_hash": case["case_hash"],
        "case_schema_hash": schema_hash,
        "coverage": PIL_REQUIRED_COVERAGE,
    }
    suite = {
        "schema": "cps.pil-oracle-suite-index",
        "schema_version": "1.0.0",
        "suite_version": "1.0.0",
        "required_coverage": PIL_REQUIRED_COVERAGE,
        "cases": [row],
        "suite_hash": "",
    }
    suite["suite_hash"] = decision_artifact_hash(suite, "suite_hash")
    return suite, {schema_hash: schema_raw}


def test_pil_suite_authenticates_raw_schema_case_and_coverage(tmp_path) -> None:
    suite, schemas = _suite(tmp_path)
    cases = validate_pil_fixture_suite(suite, tmp_path, schemas, lambda case, schema: None)
    assert cases[0]["case_id"] == "pil_case"


@pytest.mark.parametrize(
    "change", ["unknown_coverage", "case_coverage", "schema_name", "non_string_case_id"]
)
def test_pil_suite_rejects_authority_mismatch(tmp_path, change: str) -> None:
    suite, schemas = _suite(tmp_path)
    if change == "unknown_coverage":
        suite["cases"][0]["coverage"] = [*PIL_REQUIRED_COVERAGE, "unknown"]
    elif change == "case_coverage":
        suite["cases"][0]["coverage"] = PIL_REQUIRED_COVERAGE[:-1]
    elif change == "schema_name":
        suite["schema"] = "cps.search-loop-13-fixture-suite-index"
    else:
        suite["cases"][0]["case_id"] = None
    suite["suite_hash"] = decision_artifact_hash(suite, "suite_hash")
    with pytest.raises(PilError, match="PIL_FIXTURE_SUITE_INVALID"):
        validate_pil_fixture_suite(suite, tmp_path, schemas, lambda case, schema: None)
