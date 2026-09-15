"""GEN0 1,000-seed cohort gate production tests.

All manifests, records, ledgers and reports here are synthetic unit fixtures
built with the module's own identity functions; no authoritative conformance
fixture, oracle, golden, or expected hash is created or modified.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.songprogram import gen0_cohort as gc
from app.songprogram.gen0_cohort import CohortGateError

SHA_A = "sha256:" + "aa" * 32
SHA_B = "sha256:" + "bb" * 32
SHA_C = "sha256:" + "cc" * 32
KEY_1 = "sha256:" + "11" * 32
KEY_2 = "sha256:" + "22" * 32

_BINDING_KEYS = (
    "sampler_manifest_hash",
    "structural_lowering_manifest_hash",
    "production_lowering_manifest_hash",
    "compiler_manifest_hash",
    "evaluation_manifest_hash",
    "fingerprint_spec_hash",
    "qd_manifest_hash",
    "candidate_record_schema_hash",
    "gate_report_schema_hash",
)
_SCHEMA_HASH_KINDS = (
    "sampler_manifest",
    "structural_lowering_manifest",
    "production_lowering_manifest",
    "compiler_manifest",
    "evaluation_manifest",
    "fingerprint_spec",
    "qd_manifest",
)
_STAGE_ARTIFACTS = {
    "sampler": ("sampler_result",),
    "production": ("sampler_result", "production_result"),
    "compiler": ("sampler_result", "production_result", "program", "compile_report"),
    "evaluation": (
        "sampler_result",
        "production_result",
        "program",
        "compile_report",
        "project",
        "evaluation_report",
    ),
    "fingerprint": (
        "sampler_result",
        "production_result",
        "program",
        "compile_report",
        "project",
        "evaluation_report",
    ),
    "duplicate": (
        "sampler_result",
        "production_result",
        "program",
        "compile_report",
        "project",
        "evaluation_report",
        "fingerprint_record",
    ),
    "complete": (
        "sampler_result",
        "production_result",
        "program",
        "compile_report",
        "project",
        "evaluation_report",
        "fingerprint_record",
        "near_duplicate_decision",
    ),
}
_STAGE_CODES = {
    "sampler": "SAMPLER_FAILED",
    "production": "PRODUCTION_FAILED",
    "compiler": "COMPILE_FAILED",
    "evaluation": "EVALUATION_FAILED",
    "fingerprint": "FINGERPRINT_COMPUTATION_FAILED",
    "duplicate": "NEAR_DUPLICATE_DECISION_FAILED",
    "complete": None,
}


def _manifest(policy: str = "audit_only") -> dict:
    manifest = {
        "schema": gc.MANIFEST_SCHEMA,
        "schema_version": gc.COHORT_SCHEMA_VERSION,
        "contract": gc.COHORT_CONTRACT,
        "root_seed": 42,
        "cohort_size": 1000,
        "coordinate_rule": "candidate-ordinal-equals-cohort-index-0-through-999/v1",
        "bindings": {key: SHA_A for key in _BINDING_KEYS},
        "binding_schema_hashes": {key: SHA_B for key in _SCHEMA_HASH_KINDS},
        "thresholds_bp": dict(gc.THRESHOLDS_BP),
        "rate_algorithm": "round-half-even-10000-times-count-over-1000/v1",
        "mode_algorithm": "order2-root-chord-plus-harmony-rhythm-candidate-prevalence/v1",
        "near_duplicate_policy": {
            "status": policy,
            "calibration_decision_hash": SHA_C if policy == "enforced" else None,
        },
    }
    manifest["manifest_hash"] = gc.manifest_hash(manifest)
    return manifest


def _record(
    ordinal: int,
    manifest: dict,
    stage: str = "complete",
    *,
    viable: bool = True,
    recall: bool = True,
    classification: str | None = "distinct",
    qd_cell: list | None = None,
    mode_keys: dict | None = None,
) -> dict:
    stage_index = gc.TERMINAL_STAGES.index(stage)
    present = set(_STAGE_ARTIFACTS[stage])
    record = {
        "schema": gc.RECORD_SCHEMA,
        "schema_version": gc.COHORT_SCHEMA_VERSION,
        "cohort_manifest_hash": manifest["manifest_hash"],
        "candidate_ordinal": ordinal,
        "root_seed": manifest["root_seed"],
        "cohort_index": ordinal,
        "terminal_stage": stage,
        "terminal_code": _STAGE_CODES[stage],
        "artifact_hashes": {
            key: SHA_A if key in present else None for key in _STAGE_ARTIFACTS["complete"]
        },
        "compile_success": stage_index >= gc.TERMINAL_STAGES.index("evaluation"),
        "automatic_viable": viable and stage_index >= gc.TERMINAL_STAGES.index("fingerprint"),
        "has_transformed_recall": recall and stage_index >= gc.TERMINAL_STAGES.index("fingerprint"),
        "duplicate_classification": classification if stage == "complete" else None,
        "qd_cell": qd_cell,
        "mode_keys": mode_keys
        or {family: [] for family in gc.MODE_FAMILIES},
        "record_hash": SHA_B,
    }
    record["record_hash"] = gc.record_hash(record)
    return record


def _ledger(records: list[dict], manifest: dict) -> dict:
    ledger = {
        "schema": gc.LEDGER_SCHEMA,
        "schema_version": gc.COHORT_SCHEMA_VERSION,
        "cohort_manifest_hash": manifest["manifest_hash"],
        "records": records,
        "ledger_hash": SHA_B,
    }
    ledger["ledger_hash"] = gc.ledger_hash([record["record_hash"] for record in records])
    return ledger


def _cohort(manifest: dict, **overrides) -> tuple[dict, dict]:
    records = [_record(index, manifest, **overrides) for index in range(1000)]
    return manifest, _ledger(records, manifest)


def _expect(code: str, *arguments) -> None:
    with pytest.raises(CohortGateError) as caught:
        gc.build_gen0_cohort_report(*arguments)
    assert caught.value.code == code


def test_identity_functions_are_stable() -> None:
    manifest = _manifest()
    assert gc.manifest_hash(manifest) == manifest["manifest_hash"]
    record = _record(0, manifest)
    assert gc.record_hash(record) == record["record_hash"]
    ledger = _ledger([_record(i, manifest) for i in range(1000)], manifest)
    assert gc.ledger_hash([r["record_hash"] for r in ledger["records"]]) == ledger["ledger_hash"]
    assert gc.mode_key("root_anchor_ngram", [[0, 1]]) == gc.mode_key(
        "root_anchor_ngram", [[0, 1]]
    )
    assert gc.mode_key("root_anchor_ngram", [[0, 1]]) != gc.mode_key(
        "chord_intent_ngram", [[0, 1]]
    )
    with pytest.raises(CohortGateError):
        gc.mode_key("unknown_family", [])
    assert gc.rate_bp(0) == 0
    assert gc.rate_bp(95) == 950
    assert gc.rate_bp(1000) == 10000


def test_happy_path_passes_initial_gen0() -> None:
    manifest, ledger = _cohort(_manifest())
    report = gc.build_gen0_cohort_report(manifest, ledger)
    assert report["status"] == "success" and report["failure_code"] is None
    assert report["candidate_count"] == 1000
    assert report["terminal_stage_counts"]["complete"] == 1000
    assert report["counts"] == {
        "compile_success": 1000,
        "automatic_viable": 1000,
        "exact_duplicate": 0,
        "near_duplicate": 0,
        "distinct": 1000,
        "transformed_recall": 1000,
    }
    assert report["rates_bp"]["compile_success"] == 10000
    assert report["gates"]["near_duplicate"]["status"] == "not_enforced"
    assert report["initial_gen0_passed"] is True
    # audit_only near-duplicate gate keeps planner eligibility closed.
    assert report["planner_eligible"] is False
    gc.validate_gen0_cohort_report(report, manifest, ledger)


def test_enforced_near_gate_allows_planner_eligibility() -> None:
    manifest, ledger = _cohort(_manifest(policy="enforced"))
    report = gc.build_gen0_cohort_report(manifest, ledger)
    assert report["gates"]["near_duplicate"]["status"] == "passed"
    assert report["planner_eligible"] is True


@pytest.mark.parametrize(
    "count,threshold_passes",
    [(949, False), (950, True)],
)
def test_compile_gate_boundary(count: int, threshold_passes: bool) -> None:
    manifest = _manifest()
    records = [
        _record(index, manifest) if index < count else _record(index, manifest, "compiler")
        for index in range(1000)
    ]
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    assert report["rates_bp"]["compile_success"] == count * 10
    assert (report["gates"]["compile_success"]["status"] == "passed") is threshold_passes


@pytest.mark.parametrize("count,passes", [(9, True), (10, False)])
def test_exact_duplicate_gate_boundary(count: int, passes: bool) -> None:
    manifest = _manifest()
    records = [
        _record(
            index,
            manifest,
            classification="exact_duplicate" if index < count else "distinct",
        )
        for index in range(1000)
    ]
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    assert report["counts"]["exact_duplicate"] == count
    assert (report["gates"]["exact_duplicate"]["status"] == "passed") is passes


@pytest.mark.parametrize("count,passes", [(99, True), (100, False)])
def test_near_duplicate_gate_boundary_when_enforced(count: int, passes: bool) -> None:
    manifest = _manifest(policy="enforced")
    records = [
        _record(
            index, manifest, classification="near_duplicate" if index < count else "distinct"
        )
        for index in range(1000)
    ]
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    assert report["rates_bp"]["near_duplicate"] == count * 10
    assert (report["gates"]["near_duplicate"]["status"] == "passed") is passes


@pytest.mark.parametrize("count,passes", [(350, True), (351, False)])
def test_mode_prevalence_gate_boundary(count: int, passes: bool) -> None:
    manifest = _manifest()
    keys = {family: [] for family in gc.MODE_FAMILIES}
    records = []
    for index in range(1000):
        shared = {**keys, "root_anchor_ngram": [KEY_1]} if index < count else keys
        records.append(_record(index, manifest, mode_keys=shared))
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    root_maximum = report["mode_maxima"][0]
    assert root_maximum["family"] == "root_anchor_ngram"
    assert root_maximum["candidate_count"] == count
    assert root_maximum["prevalence_bp"] == count * 10
    assert (report["gates"]["mode_prevalence"]["status"] == "passed") is passes


def test_mode_maximum_tie_breaks_by_key_bytes() -> None:
    manifest = _manifest()
    records = []
    for index in range(1000):
        key = KEY_2 if index % 2 else KEY_1
        records.append(
            _record(index, manifest, mode_keys={"root_anchor_ngram": [key],
                                                "chord_intent_ngram": [],
                                                "harmony_rhythm_fingerprint": []})
        )
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    assert report["mode_maxima"][0]["key"] == KEY_1
    assert report["mode_maxima"][0]["candidate_count"] == 500


def test_qd_occupied_cells_only_viable_distinct() -> None:
    manifest = _manifest()
    records = []
    for index in range(1000):
        if index < 100:
            records.append(_record(index, manifest, qd_cell=[2, 1]))
        elif index < 200:
            records.append(_record(index, manifest, qd_cell=[0, 3], viable=False))
        elif index < 300:
            records.append(
                _record(index, manifest, qd_cell=[9, 9], classification="near_duplicate")
            )
        else:
            records.append(_record(index, manifest))
    report = gc.build_gen0_cohort_report(manifest, _ledger(records, manifest))
    assert report["qd_occupied_cells"] == [[2, 1]]


def test_terminal_stage_histogram_and_failed_records() -> None:
    manifest = _manifest()
    records = [_record(index, manifest) for index in range(1000)]
    records[0] = _record(0, manifest, "sampler")
    records[1] = _record(1, manifest, "fingerprint")
    ledger = _ledger(records, manifest)
    report = gc.build_gen0_cohort_report(manifest, ledger)
    assert report["terminal_stage_counts"]["sampler"] == 1
    assert report["terminal_stage_counts"]["fingerprint"] == 1
    assert report["counts"]["compile_success"] == 999
    assert report["counts"]["automatic_viable"] == 999


def test_manifest_validation_and_hash() -> None:
    manifest = _manifest()
    gc.validate_cohort_manifest(manifest)
    bad = deepcopy(manifest)
    bad["thresholds_bp"]["compile_success_ge"] = 9000
    _expect("COHORT_MANIFEST_INVALID", bad, _ledger([_record(i, manifest) for i in range(1000)], manifest))
    bad = deepcopy(manifest)
    bad["manifest_hash"] = SHA_B
    _expect(
        "COHORT_MANIFEST_HASH_MISMATCH",
        bad,
        _ledger([_record(i, manifest) for i in range(1000)], manifest),
    )
    bad = deepcopy(manifest)
    bad["near_duplicate_policy"] = {"status": "enforced", "calibration_decision_hash": None}
    with pytest.raises(CohortGateError) as caught:
        gc.validate_cohort_manifest(bad)
    assert caught.value.code == "COHORT_MANIFEST_INVALID"


def test_ledger_count_order_hash_precedence() -> None:
    manifest = _manifest()
    records = [_record(index, manifest) for index in range(1000)]

    short = _ledger(records[:999], manifest)
    _expect("COHORT_RECORD_COUNT_MISMATCH", manifest, short)

    swapped = list(records)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    _expect("COHORT_RECORD_ORDER_INVALID", manifest, _ledger(swapped, manifest))

    tampered = deepcopy(records)
    tampered[0]["terminal_code"] = "DIFFERENT_CODE"
    _expect("COHORT_RECORD_HASH_MISMATCH", manifest, _ledger(tampered, manifest))

    ledger = _ledger(records, manifest)
    ledger["ledger_hash"] = SHA_B
    _expect("COHORT_LEDGER_HASH_MISMATCH", manifest, ledger)


def test_coordinate_and_presence_validation() -> None:
    manifest = _manifest()
    records = [_record(index, manifest) for index in range(1000)]
    bad = deepcopy(records)
    bad[7]["cohort_index"] = 8
    bad[7]["record_hash"] = gc.record_hash(bad[7])
    _expect("COHORT_COORDINATE_MISMATCH", manifest, _ledger(bad, manifest))

    bad = deepcopy(records)
    bad[3]["artifact_hashes"]["project"] = None
    bad[3]["record_hash"] = gc.record_hash(bad[3])
    _expect("COHORT_STAGE_PRECEDENCE_INVALID", manifest, _ledger(bad, manifest))

    bad = deepcopy(records)
    bad[4]["terminal_code"] = "UNEXPECTED_CODE"
    bad[4]["record_hash"] = gc.record_hash(bad[4])
    _expect("COHORT_STAGE_PRECEDENCE_INVALID", manifest, _ledger(bad, manifest))


def test_report_tamper_detection_codes() -> None:
    manifest, ledger = _cohort(_manifest())
    report = gc.build_gen0_cohort_report(manifest, ledger)

    tampered = deepcopy(report)
    tampered["counts"]["distinct"] = 999
    tampered["report_hash"] = gc.report_hash(tampered)
    with pytest.raises(CohortGateError) as caught:
        gc.validate_gen0_cohort_report(tampered, manifest, ledger)
    assert caught.value.code == "COHORT_AGGREGATE_MISMATCH"

    tampered = deepcopy(report)
    tampered["gates"]["compile_success"]["status"] = "failed"
    tampered["report_hash"] = gc.report_hash(tampered)
    with pytest.raises(CohortGateError) as caught:
        gc.validate_gen0_cohort_report(tampered, manifest, ledger)
    assert caught.value.code == "COHORT_GATE_RESULT_MISMATCH"

    tampered = deepcopy(report)
    tampered["report_hash"] = SHA_B
    with pytest.raises(CohortGateError) as caught:
        gc.validate_gen0_cohort_report(tampered, manifest, ledger)
    assert caught.value.code == "COHORT_REPORT_HASH_MISMATCH"


def test_rejected_structural_variants() -> None:
    manifest = _manifest()
    with pytest.raises(CohortGateError) as caught:
        gc.rate_bp(1001)
    assert caught.value.code == "COHORT_AGGREGATE_MISMATCH"

    bad = _manifest()
    del bad["contract"]
    with pytest.raises(CohortGateError):
        gc.validate_cohort_manifest(bad)

    records = [_record(index, manifest) for index in range(1000)]
    bad_ledger = _ledger(records, manifest)
    bad_ledger["unexpected"] = True
    _expect("COHORT_REPORT_SCHEMA_INVALID", manifest, bad_ledger)
