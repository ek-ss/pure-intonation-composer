"""Production-independent EvaluationManifest operator reference."""
from __future__ import annotations

from fractions import Fraction
import hashlib
from typing import Any

from .canonical import canonical_bytes


class EvaluationOperatorError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


I64_MIN, I64_MAX = -(2**63), 2**63 - 1
I128_MIN, I128_MAX = -(2**127), 2**127 - 1


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvaluationOperatorError("EVALUATION_SOURCE_TYPE_INVALID")
    return value


def _checked_i128(value: int) -> int:
    if value < I128_MIN or value > I128_MAX:
        raise EvaluationOperatorError("EVALUATION_ACCUMULATOR_OVERFLOW")
    return value


def _round_half_even(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return quotient
    if doubled > value.denominator:
        return quotient + 1
    return quotient + (quotient & 1)


def _require_shape(operator: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(operator, dict) or set(operator) != keys:
        raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
    return operator


def metric(operator: Any, values: Any) -> int:
    if not isinstance(values, list) or not isinstance(operator, dict):
        raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
    kind = operator.get("kind")
    if kind == "integer_identity":
        _require_shape(operator, {"kind"})
        if len(values) != 1:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_ARITY_INVALID")
        result = _integer(values[0])
    elif kind == "absolute_difference":
        _require_shape(operator, {"kind"})
        if len(values) != 2:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_ARITY_INVALID")
        difference = _checked_i128(_integer(values[0]) - _integer(values[1]))
        result = _checked_i128(abs(difference))
    elif kind == "weighted_sum_q":
        _require_shape(operator, {"kind", "weights", "divisor"})
        weights, divisor = operator["weights"], operator["divisor"]
        if not isinstance(weights, list) or isinstance(divisor, bool) or not isinstance(divisor, int) or divisor <= 0:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
        if len(weights) != len(values) or not values:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_ARITY_INVALID")
        total = 0
        for value, weight in zip(values, weights, strict=True):
            product = _checked_i128(_integer(value) * _integer(weight))
            total = _checked_i128(total + product)
        result = _round_half_even(Fraction(total, divisor))
    else:
        raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
    if result < I64_MIN or result > I64_MAX:
        raise EvaluationOperatorError("EVALUATION_RESULT_OVERFLOW")
    return result


def hard_check(operator: Any, values: Any) -> bool:
    if not isinstance(values, list) or not isinstance(operator, dict):
        raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
    kind = operator.get("kind")
    if kind == "bool_identity":
        _require_shape(operator, {"kind"})
        if len(values) != 1:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_ARITY_INVALID")
        if not isinstance(values[0], bool):
            raise EvaluationOperatorError("EVALUATION_SOURCE_TYPE_INVALID")
        return values[0]
    if kind == "integer_compare":
        _require_shape(operator, {"kind", "comparator", "threshold"})
        if len(values) != 1:
            raise EvaluationOperatorError("EVALUATION_OPERATOR_ARITY_INVALID")
        value, threshold, comparator = _integer(values[0]), _integer(operator["threshold"]), operator["comparator"]
        if comparator == "ge": return value >= threshold
        if comparator == "le": return value <= threshold
        if comparator == "eq": return value == threshold
        raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")
    raise EvaluationOperatorError("EVALUATION_OPERATOR_INVALID")


def evidence_hash(source_bindings: object, operator: object, inputs: object, result: object) -> str:
    value = {"source_bindings": source_bindings, "operator": operator, "inputs": inputs, "result": result}
    return "sha256:" + hashlib.sha256(b"cps.evaluation-evidence/v1\0" + canonical_bytes(value) + b"\n").hexdigest()
