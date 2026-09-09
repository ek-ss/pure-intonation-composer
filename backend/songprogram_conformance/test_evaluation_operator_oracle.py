import pytest

from .canonical import CanonicalJsonError
from .evaluation_operator_oracle import EvaluationOperatorError, evidence_hash, hard_check, metric


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
