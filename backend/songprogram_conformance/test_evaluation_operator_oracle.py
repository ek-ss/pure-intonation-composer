import json
from pathlib import Path

import pytest

from .canonical import CanonicalJsonError
from .evaluation_operator_oracle import EvaluationOperatorError, evidence_hash, hard_check, metric, verify_evidence

SCHEMAS = Path(__file__).parent / "schemas"


def test_operators_and_round_half_even_positive_and_negative_ties() -> None:
    weighted = lambda n: metric({"kind": "weighted_sum_q", "weights": [1], "divisor": 2}, [n])
    assert [weighted(n) for n in (1, 3, -1, -3)] == [0, 2, 0, -2]
    assert hard_check({"kind": "integer_compare", "comparator": "ge", "threshold": 2}, [2])
    assert hard_check({"kind": "bool_identity"}, [True])


@pytest.mark.parametrize("weight", [2**127, -(2**127) - 1])
def test_weighted_product_rejects_both_signed128_overflow_bounds(weight: int) -> None:
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_ACCUMULATOR_OVERFLOW"):
        metric({"kind": "weighted_sum_q", "weights": [weight], "divisor": 1}, [1])


def test_sequential_addition_and_final_signed64_are_checked() -> None:
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_ACCUMULATOR_OVERFLOW"):
        metric({"kind": "weighted_sum_q", "weights": [1, 1], "divisor": 1}, [2**127 - 1, 1])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_ACCUMULATOR_OVERFLOW"):
        metric({"kind": "weighted_sum_q", "weights": [1, 1], "divisor": 1}, [-(2**127), -1])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_RESULT_OVERFLOW"):
        metric({"kind": "integer_identity"}, [2**63])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_RESULT_OVERFLOW"):
        metric({"kind": "integer_identity"}, [-(2**63) - 1])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_ACCUMULATOR_OVERFLOW"):
        metric({"kind": "absolute_difference"}, [-(2**127), 0])


def test_operator_arity_shape_and_source_type_are_rejected() -> None:
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_SOURCE_TYPE_INVALID"):
        metric({"kind": "integer_identity"}, [True])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_OPERATOR_ARITY_INVALID"):
        metric({"kind": "absolute_difference"}, [1])
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_OPERATOR_INVALID"):
        metric({"kind": "integer_identity", "extra": 1}, [1])


def test_evidence_hash_uses_conformance_canonical_nfc_and_final_lf() -> None:
    assert evidence_hash([], {"kind": "integer_identity"}, [1], 1) == (
        "sha256:3b06a3908d2f8e1d42c7d9fc369360985a56bfa3ebd0034020b0db50e2901aba"
    )
    with pytest.raises(CanonicalJsonError):
        evidence_hash([{"name": "e\u0301"}], {"kind": "integer_identity"}, [1], 1)


def test_evidence_must_preserve_manifest_source_order_and_verified_hashes() -> None:
    sources = [
        {"artifact_kind": "project", "schema_hash": "sha256:" + "a" * 64, "json_pointer": "/x"},
        {"artifact_kind": "compile_report", "schema_hash": "sha256:" + "b" * 64, "json_pointer": "/y"},
    ]
    bindings = [
        {**sources[0], "artifact_hash": "sha256:" + "c" * 64},
        {**sources[1], "artifact_hash": "sha256:" + "d" * 64},
    ]
    operator = {"kind": "weighted_sum_q", "weights": [1, 2], "divisor": 2}
    evidence = {
        "source_bindings": bindings, "operator": operator, "inputs": [3, 4], "result": 6,
        "evidence_hash": evidence_hash(bindings, operator, [3, 4], 6),
    }
    assert verify_evidence(
        manifest_sources=sources, artifact_hashes=["sha256:" + "c" * 64, "sha256:" + "d" * 64],
        manifest_operator=operator,
        hard=False, evidence=evidence,
    ) == 6
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_SOURCE_MISMATCH"):
        verify_evidence(
            manifest_sources=sources, artifact_hashes=["sha256:" + "d" * 64, "sha256:" + "c" * 64],
            manifest_operator=operator,
            hard=False, evidence=evidence,
        )
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_SOURCE_MISMATCH"):
        verify_evidence(
            manifest_sources=sources, artifact_hashes=["sha256:" + "c" * 64, "sha256:" + "d" * 64],
            manifest_operator={"kind": "weighted_sum_q", "weights": [2, 1], "divisor": 2},
            hard=False, evidence=evidence,
        )
    evidence["evidence_hash"] = "sha256:" + "0" * 64
    with pytest.raises(EvaluationOperatorError, match="EVALUATION_RESULT_INVALID"):
        verify_evidence(
            manifest_sources=sources, artifact_hashes=["sha256:" + "c" * 64, "sha256:" + "d" * 64],
            manifest_operator=operator,
            hard=False, evidence=evidence,
        )


def test_genre_similarity_authorities_are_closed_and_bound() -> None:
    intent = json.loads((SCHEMAS / "genre_intent.schema.json").read_text())
    spec = json.loads((SCHEMAS / "genre_similarity_spec.schema.json").read_text())
    record = json.loads((SCHEMAS / "genre_feature_record.schema.json").read_text())
    assert "genre_similarity_spec_hash" in intent["required"]
    assert spec["properties"]["algorithm"]["const"] == "normalized-l1-q31/v1"
    assert spec["properties"]["aggregation"]["const"] == "lower-median-reference-score/v1"
    assert record["properties"]["embedding_q31"]["items"] == {
        "type": "integer", "minimum": -2147483648, "maximum": 2147483647,
    }
