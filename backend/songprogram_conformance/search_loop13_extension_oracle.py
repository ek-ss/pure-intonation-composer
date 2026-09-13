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
ORDINAL_INDEX = {"smaller": 0, "similar": 1, "larger": 2}
ORDINAL_WEIGHT_Q = (
    (10_000, 7_500, 0),
    (7_500, 10_000, 7_500),
    (0, 7_500, 10_000),
)


def _nonnegative_rhe(numerator: int, denominator: int) -> int:
    """Contract-named RHE: ties round upward for non-negative quotients."""
    if numerator < 0 or denominator <= 0:
        raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID")
    quotient, remainder = divmod(numerator, denominator)
    return quotient + (2 * remainder >= denominator)


def _q31(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not Q31_MIN <= value <= Q31_MAX:
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    return value


def genre_similarity_q(candidate: Sequence[Any], references: Sequence[Sequence[Any]]) -> int:
    """normalized-L1 Q31 similarity, followed by the lower median score."""
    if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or not candidate:
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    if (
        not isinstance(references, Sequence)
        or isinstance(references, (str, bytes))
        or not references
    ):
        raise ExtensionError("GENRE_SIMILARITY_INPUT_INVALID")
    vector = [_q31(v) for v in candidate]
    denominator = len(vector) * (2**32 - 1)
    scores: list[int] = []
    for reference in references:
        if (
            not isinstance(reference, Sequence)
            or isinstance(reference, (str, bytes))
            or len(reference) != len(vector)
        ):
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
        if not isinstance(reference_id, str) or partition not in {
            "calibration",
            "validation",
            "holdout",
        }:
            raise ExtensionError("REFERENCE_MEMBER_INVALID")
        encoded = reference_id.encode("utf-8")
        if reference_id in seen or (previous is not None and encoded <= previous):
            raise ExtensionError("REFERENCE_SPLIT_INVALID")
        seen.add(reference_id)
        previous = encoded


def validate_response_rows(
    rows: Sequence[Mapping[str, Any]], participant_hashes: Sequence[str], strata: Sequence[str]
) -> None:
    allowed_people, allowed_strata = set(participant_hashes), set(strata)
    seen: set[tuple[str, str, int]] = set()
    inter_rater_members: set[tuple[str, str, str]] = set()
    previous: tuple[bytes, bytes, bytes, int] | None = None
    for row in rows:
        key = (row.get("participant_hash"), row.get("item_id"), row.get("presentation_ordinal"))
        if (
            not isinstance(key[0], str)
            or not isinstance(key[1], str)
            or not isinstance(key[2], int)
        ):
            raise ExtensionError("CALIBRATION_ROW_INVALID")
        if key[0] not in allowed_people or row.get("stratum") not in allowed_strata or key in seen:
            raise ExtensionError("CALIBRATION_ROW_INVALID")
        inter_rater_member = (row["stratum"], key[1], key[0])
        if inter_rater_member in inter_rater_members:
            raise ExtensionError("CALIBRATION_ROW_INVALID")
        order = (
            row["stratum"].encode("utf-8"),
            key[1].encode("utf-8"),
            key[0].encode("ascii"),
            key[2],
        )
        if previous is not None and order <= previous:
            raise ExtensionError("CALIBRATION_ROW_ORDER_INVALID")
        seen.add(key)
        inter_rater_members.add(inter_rater_member)
        previous = order


def bootstrap_indices(
    seed: int,
    statistic_id: str,
    replicate: int,
    stratum: str,
    population: int,
) -> list[int]:
    if (
        not 0 <= seed < 2**64
        or not isinstance(statistic_id, str)
        or not statistic_id
        or replicate < 0
        or not isinstance(stratum, str)
        or not stratum
        or population <= 0
    ):
        raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")
    key = (
        b"cps-calibration-bootstrap/v1\0"
        + seed.to_bytes(8, "big")
        + statistic_id.encode("utf-8")
        + b"\0"
        + replicate.to_bytes(8, "big")
        + stratum.encode("utf-8")
        + b"\0"
    )
    return [
        int.from_bytes(hashlib.sha256(key + draw.to_bytes(8, "big")).digest()[:8], "big")
        % population
        for draw in range(population)
    ]


def rank_interval(
    values: Sequence[int], lower_num: int, lower_den: int, upper_num: int, upper_den: int
) -> tuple[int, int]:
    if (
        not values
        or min(lower_num, upper_num) < 0
        or min(lower_den, upper_den) <= 0
        or lower_num > lower_den
        or upper_num > upper_den
    ):
        raise ExtensionError("CALIBRATION_RANK_INVALID")
    if lower_num * upper_den > upper_num * lower_den:
        raise ExtensionError("CALIBRATION_RANK_INVALID")
    ordered = sorted(values)
    n = len(ordered)
    lower = (n - 1) * lower_num // lower_den
    upper_product = (n - 1) * upper_num
    upper = (upper_product + upper_den - 1) // upper_den
    return ordered[lower], ordered[upper]


def criterion_ratio(numerator: int, denominator: int) -> int | None:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ExtensionError("CALIBRATION_RATIO_INVALID")
    if denominator == 0:
        return None
    return _nonnegative_rhe(10_000 * numerator, denominator)


def calibration_statistics(rows: Sequence[Mapping[str, Any]]) -> dict[str, int | None]:
    """Recompute the four calibration point statistics and their counts."""
    if not rows:
        raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID")
    try:
        indexed = [(row, ORDINAL_INDEX[row["ordinal_judgment"]]) for row in rows]
    except (KeyError, TypeError) as error:
        raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID") from error

    repeat_groups: dict[tuple[Any, Any, Any], list[tuple[Mapping[str, Any], int]]] = {}
    item_groups: dict[tuple[Any, Any], list[tuple[Mapping[str, Any], int]]] = {}
    for row, ordinal in indexed:
        participant = row.get("participant_hash")
        stratum = row.get("stratum")
        item = row.get("item_id")
        presentation = row.get("presentation_ordinal")
        if (
            not isinstance(participant, str)
            or not isinstance(stratum, str)
            or not isinstance(item, str)
        ):
            raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID")
        if isinstance(presentation, bool) or not isinstance(presentation, int) or presentation < 0:
            raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID")
        item_groups.setdefault((stratum, item), []).append((row, ordinal))
        repeat_id = row.get("repeat_pair_id")
        if repeat_id is not None:
            if not isinstance(repeat_id, str):
                raise ExtensionError("CALIBRATION_STATISTIC_INPUT_INVALID")
            repeat_groups.setdefault((participant, stratum, repeat_id), []).append((row, ordinal))

    first_marginal = [0, 0, 0]
    second_marginal = [0, 0, 0]
    observed = 0
    for pair in repeat_groups.values():
        if len(pair) != 2:
            raise ExtensionError("CALIBRATION_REPEAT_PAIR_INVALID")
        pair.sort(key=lambda item: item[0]["presentation_ordinal"])
        if pair[0][0]["presentation_ordinal"] == pair[1][0]["presentation_ordinal"]:
            raise ExtensionError("CALIBRATION_REPEAT_PAIR_INVALID")
        first, second = pair[0][1], pair[1][1]
        first_marginal[first] += 1
        second_marginal[second] += 1
        observed += ORDINAL_WEIGHT_Q[first][second]
    pair_count = len(repeat_groups)
    within: int | None = None
    if pair_count:
        expected = sum(
            first_marginal[i] * second_marginal[j] * ORDINAL_WEIGHT_Q[i][j]
            for i in range(3)
            for j in range(3)
        )
        denominator = 10_000 * pair_count * pair_count - expected
        if denominator:
            within = _nonnegative_rhe(
                10_000 * max(0, pair_count * observed - expected),
                denominator,
            )

    inter_total = 0
    inter_count = 0
    for group in item_groups.values():
        by_participant: dict[str, int] = {}
        for row, ordinal in group:
            participant = row["participant_hash"]
            if participant in by_participant:
                raise ExtensionError("CALIBRATION_INTER_RATER_UNIT_INVALID")
            by_participant[participant] = ordinal
        participants = sorted(by_participant)
        for left_index, left in enumerate(participants):
            for right in participants[left_index + 1 :]:
                inter_total += ORDINAL_WEIGHT_Q[by_participant[left]][by_participant[right]]
                inter_count += 1
    inter = _nonnegative_rhe(inter_total, inter_count) if inter_count else None

    auto_small = sum(bool(row.get("auto_small")) for row, _ in indexed)
    true_positive = sum(
        bool(row.get("auto_small"))
        and row.get("ordinal_judgment") == "similar"
        and row.get("broken") is False
        for row, _ in indexed
    )
    large_or_broken = sum(
        row.get("ordinal_judgment") == "larger" or row.get("broken") is True for row, _ in indexed
    )
    false_accept = sum(
        bool(row.get("auto_small"))
        and (row.get("ordinal_judgment") == "larger" or row.get("broken") is True)
        for row, _ in indexed
    )
    return {
        "repeat_pair_count": pair_count,
        "inter_rater_pair_count": inter_count,
        "auto_small_count": auto_small,
        "auto_small_true_positive_count": true_positive,
        "large_or_broken_count": large_or_broken,
        "large_or_broken_false_accept_count": false_accept,
        "within_rater_q": within,
        "inter_rater_q": inter,
        "precision_q": criterion_ratio(true_positive, auto_small),
        "false_accept_q": criterion_ratio(false_accept, large_or_broken),
    }


def calibration_bootstrap_values(
    rows: Sequence[Mapping[str, Any]],
    *,
    root_seed: int,
    replicate_count: int,
    strata: Sequence[str],
) -> dict[str, list[int]]:
    """Compute the four path-addressed, stratified bootstrap arrays."""
    if replicate_count < 1 or len(strata) != len(set(strata)) or not strata:
        raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")
    ordered_strata = sorted(strata, key=lambda item: item.encode("utf-8"))
    if list(strata) != ordered_strata:
        raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")

    by_stratum = {
        stratum: [row for row in rows if row.get("stratum") == stratum] for stratum in strata
    }
    if any(not values for values in by_stratum.values()) or sum(
        map(len, by_stratum.values())
    ) != len(rows):
        raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")

    repeat_units: dict[str, list[list[Mapping[str, Any]]]] = {}
    item_units: dict[str, list[list[Mapping[str, Any]]]] = {}
    for stratum, stratum_rows in by_stratum.items():
        repeat_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        item_groups: dict[str, list[Mapping[str, Any]]] = {}
        for row in stratum_rows:
            item_groups.setdefault(str(row["item_id"]), []).append(row)
            repeat_id = row.get("repeat_pair_id")
            if repeat_id is not None:
                repeat_groups.setdefault((str(row["participant_hash"]), str(repeat_id)), []).append(
                    row
                )
        repeat_units[stratum] = [repeat_groups[key] for key in sorted(repeat_groups)]
        item_units[stratum] = [item_groups[key] for key in sorted(item_groups)]
        if not repeat_units[stratum] or not item_units[stratum]:
            raise ExtensionError("CALIBRATION_BOOTSTRAP_INPUT_INVALID")

    output = {name: [] for name in ("within_rater", "inter_rater", "precision", "false_accept")}
    for replicate in range(replicate_count):
        sampled_pairs: list[list[Mapping[str, Any]]] = []
        sampled_items: list[list[Mapping[str, Any]]] = []
        sampled_precision: list[Mapping[str, Any]] = []
        sampled_false_accept: list[Mapping[str, Any]] = []
        for stratum in strata:
            pairs = repeat_units[stratum]
            sampled_pairs.extend(
                pairs[index]
                for index in bootstrap_indices(
                    root_seed, "within_rater", replicate, stratum, len(pairs)
                )
            )
            items = item_units[stratum]
            sampled_items.extend(
                items[index]
                for index in bootstrap_indices(
                    root_seed, "inter_rater", replicate, stratum, len(items)
                )
            )
            source_rows = by_stratum[stratum]
            sampled_precision.extend(
                source_rows[index]
                for index in bootstrap_indices(
                    root_seed, "precision", replicate, stratum, len(source_rows)
                )
            )
            sampled_false_accept.extend(
                source_rows[index]
                for index in bootstrap_indices(
                    root_seed, "false_accept", replicate, stratum, len(source_rows)
                )
            )

        first_marginal = [0, 0, 0]
        second_marginal = [0, 0, 0]
        observed = 0
        for pair in sampled_pairs:
            if len(pair) != 2:
                raise ExtensionError("CALIBRATION_REPEAT_PAIR_INVALID")
            ordered_pair = sorted(pair, key=lambda row: row["presentation_ordinal"])
            first = ORDINAL_INDEX[ordered_pair[0]["ordinal_judgment"]]
            second = ORDINAL_INDEX[ordered_pair[1]["ordinal_judgment"]]
            first_marginal[first] += 1
            second_marginal[second] += 1
            observed += ORDINAL_WEIGHT_Q[first][second]
        pair_count = len(sampled_pairs)
        expected = sum(
            first_marginal[i] * second_marginal[j] * ORDINAL_WEIGHT_Q[i][j]
            for i in range(3)
            for j in range(3)
        )
        denominator = 10_000 * pair_count * pair_count - expected
        within = (
            _nonnegative_rhe(10_000 * max(0, pair_count * observed - expected), denominator)
            if denominator
            else 0
        )

        inter_weights: list[int] = []
        for group in sampled_items:
            participants = sorted(
                (
                    (str(row["participant_hash"]), ORDINAL_INDEX[row["ordinal_judgment"]])
                    for row in group
                )
            )
            for left_index, (_, left) in enumerate(participants):
                inter_weights.extend(
                    ORDINAL_WEIGHT_Q[left][right] for _, right in participants[left_index + 1 :]
                )
        inter = _nonnegative_rhe(sum(inter_weights), len(inter_weights)) if inter_weights else 0

        precision_numerator = sum(
            bool(row.get("auto_small"))
            and row.get("ordinal_judgment") == "similar"
            and row.get("broken") is False
            for row in sampled_precision
        )
        precision_denominator = sum(bool(row.get("auto_small")) for row in sampled_precision)
        false_numerator = sum(
            bool(row.get("auto_small"))
            and (row.get("ordinal_judgment") == "larger" or row.get("broken") is True)
            for row in sampled_false_accept
        )
        false_denominator = sum(
            row.get("ordinal_judgment") == "larger" or row.get("broken") is True
            for row in sampled_false_accept
        )
        output["within_rater"].append(within)
        output["inter_rater"].append(inter)
        output["precision"].append(criterion_ratio(precision_numerator, precision_denominator) or 0)
        output["false_accept"].append(criterion_ratio(false_numerator, false_denominator) or 0)
    return output


def calibrated_criterion(
    value: int | None, *, minimum: int | None = None, maximum: int | None = None
) -> bool:
    return (
        value is not None
        and (minimum is None or value >= minimum)
        and (maximum is None or value <= maximum)
    )


def challenger_ni_imp(
    metrics: Sequence[Mapping[str, Any]],
    challenger: Sequence[int],
    champion: Sequence[int] | None,
    challenger_hash: str,
    champion_hash: str | None,
    hard_checks_passed: bool,
) -> tuple[str, str, bool, str]:
    if len(metrics) != len(challenger) or (champion is not None and len(champion) != len(metrics)):
        raise ExtensionError("CHALLENGER_ARITY_INVALID")
    ids = [item.get("id") for item in metrics]
    ordinals = [item.get("ordinal") for item in metrics]
    if len(ids) != len(set(ids)) or ordinals != list(range(len(metrics))):
        raise ExtensionError("CHALLENGER_POLICY_ORDER_INVALID")
    if not hard_checks_passed:
        return "ineligible", "ineligible", False, champion_hash or challenger_hash
    if champion is None:
        return "no_champion", "not_needed", True, challenger_hash
    c_ok = p_ok = True
    c_better = p_better = False
    c_key: list[int] = []
    p_key: list[int] = []
    for spec, c, p in zip(metrics, challenger, champion, strict=True):
        ni, imp = spec["noninferiority_margin_q"], spec["improvement_margin_q"]
        if spec["direction"] == "maximize":
            c_ok &= c + ni >= p
            p_ok &= p + ni >= c
            c_better |= c >= p + imp
            p_better |= p >= c + imp
            c_key.append(c)
            p_key.append(p)
        else:
            c_ok &= c - ni <= p
            p_ok &= p - ni <= c
            c_better |= c <= p - imp
            p_better |= p <= c - imp
            c_key.append(-c)
            p_key.append(-p)
    if c_ok and c_better:
        return "challenger_dominates", "not_needed", True, challenger_hash
    if p_ok and p_better:
        return "champion_dominates", "not_needed", False, champion_hash  # type: ignore[return-value]
    accepted = tuple(c_key) > tuple(p_key) or (
        tuple(c_key) == tuple(p_key) and challenger_hash < champion_hash
    )
    return (
        "non_dominated",
        "challenger" if accepted else "champion",
        accepted,
        challenger_hash if accepted else champion_hash,
    )  # type: ignore[return-value]


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
        kind, delta, meets = (
            row.get("kind"),
            row.get("direction_normalized_delta"),
            row.get("meets_threshold"),
        )
        expected = kind == "new_cell" or (
            kind == "replacement" and isinstance(delta, int) and delta >= threshold
        )
        if meets is not expected:
            raise ExtensionError("ROUND_IMPROVEMENT_INVALID")
        result |= expected
    return result


def validate_evaluation_rows(
    manifest_rows: Sequence[Mapping[str, Any]], report_rows: Sequence[Mapping[str, Any]]
) -> None:
    expected = [(row.get("id"), row.get("ordinal")) for row in manifest_rows]
    actual = [(row.get("id"), row.get("ordinal")) for row in report_rows]
    if (
        expected != actual
        or len({item[0] for item in expected}) != len(expected)
        or [item[1] for item in expected] != list(range(len(expected)))
    ):
        raise ExtensionError("EVALUATION_ROW_ORDER_INVALID")


_SCHEDULE = {
    (0, 2): "candidate_source_decision",
    (0, 3): "sampler_request",
    (0, 4): "sampler_result",
    (0, 5): "production_request",
    (0, 6): "production_result",
    (1, 2): "planner_request",
    (1, 3): "planner_response",
    (1, 4): "fallback_request",
    (1, 5): "mutation_request",
    (2, 2): "mutation_result",
    (2, 3): "fallback_result",
    (3, 2): "compile_request",
    (3, 3): "compile_result",
    (4, 2): "fingerprint_result",
    (5, 2): "near_duplicate_decision",
    (6, 2): "render_request",
    (6, 3): "render_reservation",
    (7, 2): "render_dispatch",
    (7, 3): "render_result",
    (8, 2): "evaluation_request",
    (8, 3): "metric_report",
    (9, 2): "challenger_acceptance_decision",
    (10, 2): "archive_admission_decision",
    (10, 3): "archive_update",
    (11, 2): "round_decision",
    (12, 2): "checkpoint",
    (13, 2): "checkpoint",
}


def validate_event_schedule(records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[tuple[int, int, int, int]] = set()
    for record in records:
        coordinate = record.get("coordinate", record)
        key = (
            coordinate.get("round"),
            coordinate.get("phase_ordinal"),
            coordinate.get("candidate_ordinal"),
            coordinate.get("event_ordinal"),
        )
        if not all(isinstance(part, int) for part in key) or key in seen:
            raise ExtensionError("EVENT_COORDINATE_INVALID")
        seen.add(key)
        phase, event, kind = key[1], key[3], record.get("kind")
        if event == 0 and phase <= 12:
            if kind != "cancellation_request":
                raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
        elif event == 1 and phase <= 12:
            if kind != "cancellation_decision":
                raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
        elif _SCHEDULE.get((phase, event)) != kind:
            raise ExtensionError("EVENT_SCHEDULE_MISMATCH")
