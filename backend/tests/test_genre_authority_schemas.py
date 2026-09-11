from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
def load(name: str) -> dict: return json.loads((SCHEMAS / name).read_text())

def test_genre_authority_artifacts_are_closed() -> None:
    for name in ("genre_license_policy", "reference_source_provenance", "listener_cohort_manifest", "blinded_assignment_manifest", "calibration_dataset_manifest", "calibration_acceptance_policy", "calibration_statistic_operator", "calibration_response_set", "calibration_bootstrap_trace", "calibration_evidence_summary"):
        assert load(f"{name}.schema.json")["additionalProperties"] is False

def test_bootstrap_is_parameterized_and_recomputable() -> None:
    p = load("calibration_acceptance_policy.schema.json")
    assert p["properties"]["algorithm"]["const"] == "deterministic-stratified-bootstrap-q/v1"
    for key in ("root_seed", "replicate_count", "lower_rank_numerator", "lower_rank_denominator", "upper_rank_numerator", "upper_rank_denominator"):
        assert key in p["required"]
    assert load("calibration_dataset_manifest.schema.json")["properties"]["partition_leakage_count"] == {"const": 0}

def test_calibration_integer_operator_and_recomputation_evidence_are_closed() -> None:
    operator = load("calibration_statistic_operator.schema.json")
    assert operator["properties"]["quantum"] == {"const": 10000}
    assert operator["properties"]["ordinal_weight_matrix_q"]["prefixItems"] == [
        {"const": [10000, 7500, 0]}, {"const": [7500, 10000, 7500]}, {"const": [0, 7500, 10000]},
    ]
    responses = load("calibration_response_set.schema.json")
    assert responses["properties"]["rows"]["items"] == {"$ref": "#/$defs/row"}
    dataset = load("calibration_dataset_manifest.schema.json")
    assert "response_schema_hash" in dataset["required"]
    evidence = load("calibration_evidence_summary.schema.json")
    assert {"statistic_operator_hash", "repeat_pair_count", "inter_rater_pair_count",
            "auto_small_count", "auto_small_true_positive_count", "large_or_broken_count",
            "large_or_broken_false_accept_count", "bootstrap_trace_hash"} <= set(evidence["required"])

def test_calibration_formula_and_failure_precedence_are_normative() -> None:
    text = (ROOT.parent / "docs" / "song_program_evaluation_operator_contract.md").read_text()
    assert "RHE(10000*max(0,n*O-E)/(10000*n*n-E))" in text
    assert "RHE(10000*TP/P)" in text and "RHE(10000*FA/L)" in text
    assert "Only the first applicable code is emitted" in text

def test_calibration_owns_promoted_margins_and_policy_repeats_them() -> None:
    d = load("calibration_decision.schema.json")
    promotion = d["$defs"]["promotion"]
    assert promotion["required"] == ["metric_id", "noninferiority_margin_q", "improvement_margin_q", "evidence_hash"]
    assert "calibration_decision_hash" not in load("challenger_acceptance_policy.schema.json")["required"]
    policy = load("challenger_acceptance_policy_1_1.schema.json")
    assert "calibration_decision_hash" in policy["required"]
    assert policy["properties"]["schema_version"]["const"] == "1.1.0"
    calibration_policy = load("calibration_acceptance_policy.schema.json")
    assert {"statistic_operator_hash", "evaluation_epoch_day"} <= set(calibration_policy["required"])
    metric = policy["$defs"]["metric"]
    assert "noninferiority_margin_q" in metric["required"]
    assert "improvement_margin_q" in metric["required"]
    assert "calibration_decision_hash" not in load("challenger_acceptance_decision.schema.json")["required"]
    decision = load("challenger_acceptance_decision_1_1.schema.json")
    assert "calibration_decision_hash" in decision["required"]

def test_search_overview_does_not_assign_margins_to_genre_intent() -> None:
    text = (ROOT.parent / "docs" / "song_program_search_loop_contract.md").read_text()
    assert "It does not own Pareto margins" in text
    assert "ChallengerAcceptancePolicy is the sole margin authority" in text
