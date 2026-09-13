from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.songprogram.perceptual import PilError
from app.songprogram.pil_fixture_suite import (
    PIL_REQUIRED_COVERAGE,
    execute_pil_oracle_case,
    execute_pil_oracle_matrix,
    validate_pil_matrix_receipt,
    validate_pil_oracle_case_bindings,
    validate_pil_fixture_suite,
)
from app.songprogram import perceptual
from tools.build_pil_oracle_case_templates import build_cases
from app.songprogram.search_decisions import decision_artifact_hash


AUTHORITATIVE = Path(__file__).resolve().parents[1] / "songprogram_conformance/fixtures/pil_oracle"


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


def test_authoritative_pil_suite_closes_and_all_expected_reports_match() -> None:
    suite = json.loads((AUTHORITATIVE / "suite_index.json").read_text(encoding="utf-8"))
    case_schema = Path(__file__).resolve().parents[1] / (
        "songprogram_conformance/schemas/pil_oracle_case.schema.json"
    )
    raw_schema = case_schema.read_bytes()
    schema_hash = _raw_hash(raw_schema)
    cases = validate_pil_fixture_suite(
        suite,
        AUTHORITATIVE,
        {schema_hash: raw_schema},
        lambda case, schema: validate_pil_oracle_case_bindings(case),
    )
    assert len(cases) == 18
    for case in cases:
        execute_pil_oracle_case(case)

    nonfunctional = next(
        case for case in cases if case["case_id"] == "pil_nonfunctional_two_reports"
    )
    report = execute_pil_oracle_case(nonfunctional)
    assert report["native_ji_report_hash"] == (
        "sha256:87f4b48b1369484d693798ddb865a94f9ed0a2272e04b040b6dc5ab8c654f3d4"
    )
    assert report["trajectory_interpretations"][0]["similarity_q"] <= 5000


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


def test_case_binding_accepts_full_project_and_phase_exact_null_assets() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "songprogram_conformance/fixtures/pack/minimal_direct_project.json"
    )
    project = json.loads(fixture.read_text(encoding="utf-8"))
    manifest = {
        "schema": "cps.perceptual-interpretation-manifest",
        "schema_version": "1.0.0",
        "algorithm": "pil-parallel-interpretation/v1",
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "numeric_contract_hash": perceptual.NUMERIC_CONTRACT_HASH,
        "implementation_build_id": perceptual.PIL_IMPLEMENTATION_BUILD_ID,
        "interpretation_period": "2/1",
        "pitch_kernel": {
            "algorithm": "triangular-millicent-q31/v1",
            "radius_millicents": 100_000,
            "normalization_total": perceptual.Q31_TOTAL,
        },
        "segmentation_policy_schema_hash": perceptual.SEGMENTATION_POLICY_SCHEMA_HASH,
        "segmentation_policy_hash": "sha256:" + "03" * 32,
        "feature_spec_hash": "sha256:" + "04" * 32,
        "vocabulary_hash": "sha256:" + "05" * 32,
        "voice_matching_policy_hash": "sha256:" + "06" * 32,
        "trajectory_template_set_hash": "sha256:" + "07" * 32,
        "genre_model_hash": None,
    }
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    case = {
        "manifest": manifest,
        "project": project,
        "project_hash": perceptual.project_hash(project),
        "segmentation_policy": None,
        "feature_spec": None,
        "vocabulary": None,
        "voice_matching_policy": None,
        "trajectory_template_set": None,
    }
    validate_pil_oracle_case_bindings(case)
    case["project_hash"] = "sha256:" + "00" * 32
    with pytest.raises(PilError, match="PIL_FIXTURE_SUITE_INVALID"):
        validate_pil_oracle_case_bindings(case)


def test_case_executor_compares_report_bytes_and_cache_parity() -> None:
    case = next(case for case in build_cases() if case["case_id"] == "pil_cache_parity")
    report = perceptual.run_perceptual_interpretation(
        case["project"], case["manifest"], expected_project_hash=case["project_hash"]
    )
    case["expected"] = {
        "status": report["status"],
        "error": report["error"],
        "report_hash": report["report_hash"],
        "canonical_report_sha256": "sha256:"
        + hashlib.sha256(perceptual.canonical_report_bytes(report)).hexdigest(),
    }
    assert execute_pil_oracle_case(case) == report
    case["expected"]["report_hash"] = "sha256:" + "00" * 32
    with pytest.raises(PilError, match="PIL_FIXTURE_SUITE_INVALID"):
        execute_pil_oracle_case(case)


def test_matrix_uses_fresh_processes_and_is_worker_count_invariant() -> None:
    case = next(case for case in build_cases() if case["case_id"] == "pil_cache_parity")
    report = perceptual.run_perceptual_interpretation(
        case["project"], case["manifest"], expected_project_hash=case["project_hash"]
    )
    canonical = perceptual.canonical_report_bytes(report)
    case["expected"] = {
        "status": report["status"],
        "error": report["error"],
        "report_hash": report["report_hash"],
        "canonical_report_sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }
    case["execution"]["pythonhashseeds"] = ["0"]
    receipt = execute_pil_oracle_matrix("sha256:" + "ab" * 32, [case])
    assert [row["worker_count"] for row in receipt["executions"]] == [1, 2, 4, 8]
    assert len({row["case_results_hash"] for row in receipt["executions"]}) == 1
    assert receipt["case_results"] == [
        {
            "case_id": case["case_id"],
            "report_hash": report["report_hash"],
            "canonical_report_sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        }
    ]
    assert receipt["matrix_hash"] == decision_artifact_hash(receipt, "matrix_hash")
    damaged = json.loads(json.dumps(receipt))
    damaged["executions"][0]["worker_count"] = 2
    damaged["matrix_hash"] = decision_artifact_hash(damaged, "matrix_hash")
    with pytest.raises(PilError, match="PIL_FIXTURE_SUITE_INVALID"):
        validate_pil_matrix_receipt(damaged, "sha256:" + "ab" * 32, [case])


@pytest.mark.parametrize("seed", ["01", "-1", "4294967296"])
def test_matrix_rejects_noncanonical_pythonhashseed(seed: str) -> None:
    case = next(case for case in build_cases() if case["case_id"] == "pil_cache_parity")
    case["execution"]["pythonhashseeds"] = [seed]
    with pytest.raises(PilError, match="PIL_FIXTURE_SUITE_INVALID"):
        execute_pil_oracle_matrix("sha256:" + "ab" * 32, [case])
