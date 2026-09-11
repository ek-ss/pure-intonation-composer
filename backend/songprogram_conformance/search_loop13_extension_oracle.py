"""Independent SearchLoop13 v1.1 authority algorithms; no production imports."""
from __future__ import annotations

import hashlib
from fractions import Fraction
from typing import Any, Mapping, Sequence

from .evaluation_operator_oracle import I128_MAX, I128_MIN, _round_half_even


class ExtensionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


Q31_MIN, Q31_MAX = -(2**31), 2**31 - 1


def _q31(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not Q31_MIN <= value <= Q31_MAX:
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    return value


def genre_similarity_q(candidate: Sequence[Any], references: Sequence[Sequence[Any]]) -> int:
    """normalized-L1 Q31 similarity, followed by the lower median score."""
    if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or not candidate:
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    if not isinstance(references, Sequence) or isinstance(references, (str, bytes)) or not references:
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    vector = [_q31(v) for v in candidate]
    denominator = len(vector) * (2**32 - 1)
    scores: list[int] = []
    for reference in references:
        if not isinstance(reference, Sequence) or isinstance(reference, (str, bytes)) or len(reference) != len(vector):
            raise ExtensionError("GENRE_SIMILARITY_DIMENSION_MISMATCH")
        total = 0
        for left, right in zip(vector, reference, strict=True):
            total += abs(left - _q31(right))
            if not I128_MIN <= total <= I128_MAX:
                raise ExtensionError("GENRE_SIMILARITY_ACCUMULATOR_OVERFLOW")
        distance_q = _round_half_even(Fraction(10_000 * total, denominator))
        score = 10_000 - distance_q
        if not 0 <= score <= 10_000:
            raise ExtensionError("GENRE_SIMILARITY_RESULT_INVALID")
        scores.append(score)
    return sorted(scores)[(len(scores) - 1) // 2]


def validate_reference_members(members: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    previous: bytes | None = None
    for member in members:
        reference_id, partition = member.get("reference_id"), member.get("partition")
        if not isinstance(reference_id, str) or partition not in {"calibration", "validation", "holdout"}:
            raise ExtensionError("REFERENCE_MEMBER_INVALID")
        encoded = reference_id.encode("utf-8")
        if reference_id in seen or (previous is not None and encoded <= previous):
            raise ExtensionError("REFERENCE_SPLIT_INVALID")
        seen.add(reference_id)
        previous = encoded


def validate_response_rows(rows: Sequence[Mapping[str, Any]], participant_hashes: Sequence[str], strata: Sequence[str]) -> None:
    allowed_people, allowed_strata = set(participant_hashes), set(strata)
    seen: set[tuple[str, str, int]] = set()
    previous: tuple[bytes, bytes, int] | None = None
    for row in rows:
        key = (row.get("participant_hash"), row.get("item_id"), row.get("presentation_ordinal"))
        if not isinstance(key[0], str) or not isinstance(key[1], str) or not isinstance(key[2], int):
            raise ExtensionError("CALIBRATION_ROW_INVALID")
        if key[0] not in allowed_people or row.get("stratum") not in allowed_strata or key in seen:
            raise ExtensionError("CALIBRATION_ROW_INVALID")
        order = (key[0].encode("ascii"), key[1].encode("utf-8"), key[2])
        if previous is not None and order <= previous:
            raise ExtensionError("CALIBRATION_ROW_ORDER_INVALID")
        seen.add(key); previous = order


def bootstrap_indices(seed: int, replicate: int, stratum: str, population: int) -> list[int]:
    if not (0 <= seed < 2**64 and replicate >= 0 and population > 0):
        raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")
    key = b"cps.calibration-bootstrap/v1\0" + seed.to_bytes(8, "big") + replicate.to_bytes(8, "big") + stratum.encode("utf-8")
    return [int.from_bytes(hashlib.sha256(key + i.to_bytes(8, "big")).digest()[:8], "big") % population for i in range(population)]


def rank_interval(values: Sequence[int], lower_num: int, lower_den: int, upper_num: int, upper_den: int) -> tuple[int, int]:
    if (not values or min(lower_num, upper_num) < 0 or min(lower_den, upper_den) <= 0
            or lower_num > lower_den or upper_num > upper_den):
        raise ExtensionError("CALIBRATION_RANK_INVALID")
    if lower_num * upper_den > upper_num * lower_den:
        raise ExtensionError("CALIBRATION_RANK_INVALID")
    ordered = sorted(values)
    n = len(ordered)
    lower = (n - 1) * lower_num // lower_den
    upper = (n - 1) * upper_num // upper_den
    return ordered[lower], ordered[upper]


def criterion_ratio(numerator: int, denominator: int) -> int | None:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ExtensionError("CALIBRATION_RATIO_INVALID")
    if denominator == 0:
        return None
    return _round_half_even(Fraction(10_000 * numerator, denominator))


def calibrated_criterion(value: int | None, *, minimum: int | None = None, maximum: int | None = None) -> bool:
    return value is not None and (minimum is None or value >= minimum) and (maximum is None or value <= maximum)


def challenger_ni_imp(metrics: Sequence[Mapping[str, Any]], challenger: Sequence[int], champion: Sequence[int] | None, challenger_hash: str, champion_hash: str | None, hard_checks_passed: bool) -> tuple[str, str, bool, str]:
    if len(metrics) != len(challenger) or (champion is not None and len(champion) != len(metrics)):
        raise ExtensionError("CHALLENGER_ARITY_INVALID")
    ids = [item.get("id") for item in metrics]; ordinals = [item.get("ordinal") for item in metrics]
    if len(ids) != len(set(ids)) or ordinals != list(range(len(metrics))):
        raise ExtensionError("CHALLENGER_POLICY_ORDER_INVALID")
    if not hard_checks_passed:
        return "ineligible", "ineligible", False, champion_hash or challenger_hash
    if champion is None:
        return "no_champion", "not_needed", True, challenger_hash
    c_ok = p_ok = True; c_better = p_better = False; c_key: list[int] = []; p_key: list[int] = []
    for spec, c, p in zip(metrics, challenger, champion, strict=True):
        ni, imp = spec["noninferiority_margin_q"], spec["improvement_margin_q"]
        if spec["direction"] == "maximize":
            c_ok &= c + ni >= p; p_ok &= p + ni >= c; c_better |= c >= p + imp; p_better |= p >= c + imp; c_key.append(c); p_key.append(p)
        else:
            c_ok &= c - ni <= p; p_ok &= p - ni <= c; c_better |= c <= p - imp; p_better |= p <= c - imp; c_key.append(-c); p_key.append(-p)
    if c_ok and c_better: return "challenger_dominates", "not_needed", True, challenger_hash
    if p_ok and p_better: return "champion_dominates", "not_needed", False, champion_hash  # type: ignore[return-value]
    accepted = tuple(c_key) > tuple(p_key) or (tuple(c_key) == tuple(p_key) and challenger_hash < champion_hash)
    return "non_dominated", "challenger" if accepted else "champion", accepted, challenger_hash if accepted else champion_hash  # type: ignore[return-value]


def material_improvement(rows: Sequence[Mapping[str, Any]], threshold: int) -> bool:
    if threshold < 1:
        raise ExtensionError("ROUND_IMPROVEMENT_INVALID")
    seen: set[tuple[int, ...]] = set()
    result = False
    for row in rows:
        cell = tuple(row.get("cell", []))
        if not cell or cell in seen:
            raise ExtensionError("ROUND_IMPROVEMENT_INVALID")
        seen.add(cell)
        kind, delta, meets = row.get("kind"), row.get("direction_normalized_delta"), row.get("meets_threshold")
        expected = kind == "new_cell" or (kind == "replacement" and isinstance(delta, int) and delta >= threshold)
        if meets is not expected:
            raise ExtensionError("ROUND_IMPROVEMENT_INVALID")
        result |= expected
    return result


def validate_evaluation_rows(manifest_rows: Sequence[Mapping[str, Any]], report_rows: Sequence[Mapping[str, Any]]) -> None:
    expected = [(row.get("id"), row.get("ordinal")) for row in manifest_rows]
    actual = [(row.get("id"), row.get("ordinal")) for row in report_rows]
    if expected != actual or len({item[0] for item in expected}) != len(expected) or [item[1] for item in expected] != list(range(len(expected))):
        raise ExtensionError("EVALUATION_ROW_ORDER_INVALID")


_SCHEDULE = {
    (0, 2): "candidate_source_decision", (0, 3): "sampler_request", (0, 4): "sampler_result", (0, 5): "production_request", (0, 6): "production_result",
    (1, 2): "planner_request", (1, 3): "planner_response", (1, 4): "fallback_request", (1, 5): "mutation_request",
    (2, 2): "mutation_result", (2, 3): "fallback_result", (3, 2): "compile_request", (3, 3): "compile_result",
    (4, 2): "fingerprint_result", (5, 2): "near_duplicate_decision", (6, 2): "render_request", (6, 3): "render_reservation",
    (7, 2): "render_dispatch", (7, 3): "render_result", (8, 2): "evaluation_request", (8, 3): "metric_report",
    (9, 2): "challenger_acceptance_decision", (10, 2): "archive_admission_decision", (10, 3): "archive_update", (11, 2): "round_decision", (12, 2): "checkpoint", (13, 2): "checkpoint",
}


def validate_event_schedule(records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[tuple[int, int, int, int]] = set()
    for record in records:
        coordinate = record.get("coordinate", record)
        key = (coordinate.get("round"), coordinate.get("phase_ordinal"), coordinate.get("candidate_ordinal"), coordinate.get("event_ordinal"))
        if not all(isinstance(part, int) for part in key) or key in seen:
            raise ExtensionError("EVENT_COORDINATE_INVALID")
        seen.add(key)
        phase, event, kind = key[1], key[3], record.get("kind")
        if event == 0 and phase <= 12:
            if kind != "cancellation_request": raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
        elif event == 1 and phase <= 12:
            if kind != "cancellation_decision": raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
        elif _SCHEDULE.get((phase, event)) != kind:
            raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
