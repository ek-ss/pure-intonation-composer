"""Production parity tests for the read-only Search Decision fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.songprogram.search import SearchArtifactError
from app.songprogram.search_decisions import (
    archive_admission,
    cancellation_cutoff_action_id,
    challenger_acceptance,
    comparison_set_hash,
    decision_action_id,
    decision_artifact_hash,
    make_archive_admission_decision,
    make_cancellation_decision,
    make_challenger_acceptance_decision,
    make_near_duplicate_decision,
    make_round_decision,
    make_render_charge,
    make_render_result,
    near_duplicate,
    reserve_render,
    round_decision,
    select_render_candidates,
    validate_calibration_rank_policy,
    validate_cancellation_scenario,
    validate_decision_components,
    validate_parallel_scenario,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "songprogram_conformance" / "fixtures" / "search_decisions"


def test_search_loop13_cross_field_fixture_validators() -> None:
    validate_calibration_rank_policy({"lower_rank_numerator": 1, "lower_rank_denominator": 4, "upper_rank_numerator": 3, "upper_rank_denominator": 4})
    with pytest.raises(SearchArtifactError, match="CALIBRATION_RANK_INVALID"):
        validate_calibration_rank_policy({"lower_rank_numerator": 5, "lower_rank_denominator": 4, "upper_rank_numerator": 1, "upper_rank_denominator": 1})
    coordinates = {"act_a": (0, 1, 0, 0), "act_b": (0, 1, 1, 0)}
    validate_parallel_scenario({"scheduled_action_ids": ["act_a", "act_b"], "completion_permutation": ["act_b", "act_a"]}, coordinates)
    with pytest.raises(SearchArtifactError, match="PARALLEL_SCENARIO_INVALID"):
        validate_parallel_scenario({"scheduled_action_ids": ["act_b", "act_a"], "completion_permutation": ["act_a", "act_b"]}, coordinates)
    validate_cancellation_scenario({"arrivals": [{"inbox_record_hash": "h1", "arrival_barrier_coordinate": {"round": 0, "phase_ordinal": 1, "candidate_ordinal": 0, "event_ordinal": 0}}]}, "cancelled")
    with pytest.raises(SearchArtifactError, match="CANCELLATION_SCENARIO_INVALID"):
        validate_cancellation_scenario({"arrivals": []}, "cancelled")


def _load(path: str):
    return json.loads((FIXTURES / path).read_text(encoding="utf-8"))


def test_authoritative_success_fixture_parity() -> None:
    cases, expected = _load("success/cases.json"), _load("success/expected.json")
    assert list(archive_admission(**cases["archive"])) == expected["archive"]
    assert list(challenger_acceptance(**cases["challenger"])) == expected["challenger"]
    assert json.loads(json.dumps(near_duplicate(**cases["near_duplicate"]))) == expected["near_duplicate"]
    assert comparison_set_hash(["sha256:" + "1" * 64, "sha256:" + "2" * 64]) == expected["comparison_set_hash"]
    assert list(round_decision(**cases["stopping"])) == expected["stopping"]
    assert cancellation_cutoff_action_id(cases["cancellation"]["run_hash"], cases["cancellation"]["coordinate"]) == expected["cancellation_action_id"]
    assert decision_action_id(cases["cancellation"]["run_hash"], 2, 7, 3) == expected["cancellation_action_id"]
    assert list(reserve_render(**cases["render"])) == expected["render"]


def test_authoritative_boundary_fixture_parity() -> None:
    cases, expected = _load("boundary/cases.json"), _load("boundary/expected.json")
    for name in ("archive_empty", "archive_hash_tie"):
        assert list(archive_admission(**cases[name])) == expected[name]
    assert list(challenger_acceptance(**cases["challenger_exact_margins"])) == expected["challenger_exact_margins"]
    for name in ("near_exact_threshold", "near_threshold_plus_one"):
        assert json.loads(json.dumps(near_duplicate(**cases[name]))) == expected[name]
    for name in ("render_exact", "render_plus_one"):
        assert list(reserve_render(**cases[name])) == expected[name]
    for name in ("stop_precedence", "patience_exact"):
        assert list(round_decision(**cases[name])) == expected[name]


def test_authoritative_negative_fixture_parity() -> None:
    cases, expected = _load("negative/cases.json"), _load("negative/expected.json")
    functions = {
        "validate_action": lambda value: _validate_action(value),
        "validate_charge": lambda value: _validate_charge(value),
        "comparison_set_hash": comparison_set_hash,
        "validate_components": validate_decision_components,
        "reserve_render": lambda value: reserve_render(**value),
    }
    for case in cases:
        with pytest.raises(SearchArtifactError) as caught:
            functions[case["call"]](case["input"])
        assert caught.value.code == expected[case["id"]]["code"]


def _validate_action(value: dict[str, object]) -> None:
    if decision_action_id(value["run_hash"], value["round"], value["phase_ordinal"], value["candidate_ordinal"]) != value["action_id"]:  # type: ignore[arg-type]
        raise SearchArtifactError("ACTION_ID_MISMATCH")


def _validate_charge(value: dict[str, int | str]) -> None:
    status, used_after = reserve_render(value["used_before"], value["requested_frames"], value["ceiling"])  # type: ignore[arg-type]
    if (status, used_after) != (value["reservation_status"], value["used_after"]):
        raise SearchArtifactError("RENDER_CHARGE_ARITHMETIC_MISMATCH")


def test_render_cache_charge_and_selection_order_are_process_independent() -> None:
    """Charge is committed before the cache outcome; sorting ignores input order."""
    h = lambda digit: "sha256:" + digit * 64
    charge = make_render_charge(h("a"), h("b"), 400, 600, 1000)
    assert charge["reservation_status"] == "reserved"
    cache_hit = make_render_result(h("a"), "act_" + "a" * 26, h("b"), charge["charge_hash"], "cache_hit", cache_entry_hash=h("c"), audio_artifact_hash=h("d"))
    failed = make_render_result(h("a"), "act_" + "b" * 26, h("b"), charge["charge_hash"], "render_failed", failure_hash=h("e"))
    assert cache_hit["charge_hash"] == failed["charge_hash"] == charge["charge_hash"]
    assert charge["used_after"] == 1000  # neither outcome refunds its reservation
    candidates = [
        {"program_hash": h("2"), "compile_valid": True, "distinct": True, "components": [10, 4]},
        {"program_hash": h("1"), "compile_valid": True, "distinct": True, "components": [10, 3]},
        {"program_hash": h("0"), "compile_valid": False, "distinct": True, "components": [99, 0]},
    ]
    assert select_render_candidates(candidates, ["maximize", "minimize"], 2) == [h("1"), h("2")]
    assert select_render_candidates(list(reversed(candidates)), ["maximize", "minimize"], 2) == [h("1"), h("2")]


def test_decision_artifacts_self_hash_and_preserve_causal_inputs() -> None:
    """Decision records never derive ambient policy or evidence inputs."""
    h = lambda digit: "sha256:" + digit * 64
    archive_policy = {"quality_components": [{"id": "quality", "direction": "maximize", "source": {"artifact_kind": "evaluation_report", "schema_hash": h("a"), "json_pointer": "/quality"}}]}
    archive = make_archive_admission_decision(h("1"), archive_policy, h("2"), h("3"), h("4"), h("5"), h("6"), [0, 1], None, [10], True)
    assert archive["resulting_champion"]["program_hash"] == h("3")

    metric = {"id": "genre", "direction": "maximize", "margin_q": 1, "ordinal": 0, "source": {"artifact_kind": "evaluation_report", "schema_hash": h("a"), "json_pointer": "/genre"}}
    challenger = make_challenger_acceptance_decision(h("1"), {"metrics": [metric]}, h("2"), h("3"), {"program_hash": h("4"), "project_hash": h("5"), "evaluation_report_hash": h("6")}, None, [10], None, True)
    assert challenger["accepted"] is True

    duplicate = make_near_duplicate_decision(h("1"), h("2"), 0, h("3"), h("4"), [], 100)
    assert duplicate["classification"] == "distinct"
    round_record = make_round_decision(h("1"), h("2"), 0, h("3"), h("4"), [], 1, True, 2, 3, 5, False, False, False)
    assert round_record["patience_after"] == 0
    cancellation = make_cancellation_decision(h("1"), h("2"), {"round": 0, "phase_ordinal": 6, "candidate_ordinal": 0}, None, None, h("3"))
    for artifact, member in ((archive, "decision_hash"), (challenger, "decision_hash"), (duplicate, "decision_hash"), (round_record, "decision_hash"), (cancellation, "decision_hash")):
        assert artifact[member] == decision_artifact_hash(artifact, member)
