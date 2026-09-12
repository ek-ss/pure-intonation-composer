from __future__ import annotations

import hashlib
import json

import pytest

from app.songprogram.fixture_suite import REQUIRED_COVERAGE, validate_fixture_suite
from app.songprogram.search import SearchArtifactError
from app.songprogram.search_decisions import decision_artifact_hash


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _raw_hash(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _suite(tmp_path):
    schema_raw = _bytes({"type": "object"})
    schema_hash = _raw_hash(schema_raw)
    case = {"schema": "fixture", "schema_version": "1.0.0", "case_id": "case_a", "case_hash": ""}
    case["case_hash"] = decision_artifact_hash(case, "case_hash")
    raw = _bytes(case)
    (tmp_path / "case.json").write_bytes(raw)
    row = {
        "case_id": "case_a",
        "path": "case.json",
        "raw_file_sha256": _raw_hash(raw),
        "case_hash": case["case_hash"],
        "case_schema_hash": schema_hash,
        "coverage": REQUIRED_COVERAGE,
    }
    suite = {
        "schema": "cps.search-loop-13-fixture-suite-index",
        "schema_version": "1.0.0",
        "suite_version": "1.0.0",
        "required_coverage": REQUIRED_COVERAGE,
        "cases": [row],
        "suite_hash": "",
    }
    suite["suite_hash"] = decision_artifact_hash(suite, "suite_hash")
    return suite, {schema_hash: schema_raw}


def test_suite_validator_authenticates_raw_and_semantic_identities(tmp_path):
    suite, schemas = _suite(tmp_path)
    assert (
        validate_fixture_suite(suite, tmp_path, schemas, lambda case, schema: None)[0]["case_id"]
        == "case_a"
    )


def test_suite_validator_rejects_traversal_and_raw_byte_changes(tmp_path):
    suite, schemas = _suite(tmp_path)
    suite["cases"][0]["path"] = "../case.json"
    suite["suite_hash"] = decision_artifact_hash(suite, "suite_hash")
    with pytest.raises(SearchArtifactError, match="FIXTURE_SUITE_INVALID"):
        validate_fixture_suite(suite, tmp_path, schemas, lambda case, schema: None)
    suite, schemas = _suite(tmp_path)
    (tmp_path / "case.json").write_bytes(b"{}")
    with pytest.raises(SearchArtifactError, match="FIXTURE_SUITE_INVALID"):
        validate_fixture_suite(suite, tmp_path, schemas, lambda case, schema: None)
