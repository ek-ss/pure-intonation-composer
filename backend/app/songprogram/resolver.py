"""Production GEN0-A/B exact resolvers.

This module intentionally does not import the conformance package: the latter
is the independent oracle used to test this implementation.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from itertools import combinations, permutations
from math import gcd
from typing import Any, Iterable

NUMERIC_CONTRACT = "cps-numeric/decimal-log2-rhe-v1"
_PRECISIONS = (80, 112, 144, 176, 208, 240, 256)


def _ratio(text: str) -> Fraction:
    numerator, denominator = (int(part) for part in text.split("/", 1))
    if numerator <= 0 or denominator <= 0 or gcd(numerator, denominator) != 1:
        raise ValueError("ratio must be positive and reduced")
    return Fraction(numerator, denominator)


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _stable(compute: Any) -> int:
    previous: int | None = None
    for precision in _PRECISIONS:
        with localcontext() as context:
            context.prec = precision
            context.rounding = ROUND_HALF_EVEN
            context.Emin, context.Emax = -999_999, 999_999
            context.traps[InvalidOperation] = True
            context.traps[DivisionByZero] = True
            context.traps[Overflow] = True
            value = compute()
        if value == previous:
            return value
        previous = value
    raise ValueError("NUMERIC_INDETERMINATE")


def _mc(value: Fraction) -> int:
    return _stable(lambda: int((Decimal(1_200_000) * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln()) / Decimal(2).ln()).to_integral_value(rounding=ROUND_HALF_EVEN)))


def _edo(equave: Fraction, divisions: int, step: int) -> int:
    return _stable(lambda: int((Decimal(1_200_000) * ((Decimal(equave.numerator).ln() - Decimal(equave.denominator).ln()) / Decimal(2).ln()) * (step % divisions) / divisions).to_integral_value(rounding=ROUND_HALF_EVEN)))


def _rms(errors: tuple[int, ...]) -> int:
    return _stable(lambda: int((Decimal(sum(item * item for item in errors)) / len(errors)).sqrt().to_integral_value(rounding=ROUND_HALF_EVEN)))


def _wrap(value: int, period: int) -> int:
    return ((value + period // 2) % period) - period // 2


def _reduce(value: Fraction, equave: Fraction) -> Fraction:
    while value >= equave:
        value /= equave
    while value < 1:
        value *= equave
    return value


def _odd(value: Fraction, equave: Fraction) -> int:
    value = _reduce(value, equave)
    def odd_part(part: int) -> int:
        while part % 2 == 0:
            part //= 2
        return part
    return max(odd_part(value.numerator), odd_part(value.denominator))


def _vector_ratio(generators: tuple[Fraction, ...], vector: tuple[int, ...], equave: Fraction, exponent: int) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector):
        value *= generator ** power
    return value * equave ** exponent


def _complexity(ratios: tuple[Fraction, ...], equave: Fraction) -> int:
    return sum((_reduce(max(left, right) / min(left, right), equave).numerator.bit_length() + _reduce(max(left, right) / min(left, right), equave).denominator.bit_length() - 2) for left, right in combinations(ratios, 2))


def _axes(bounds: list[list[int]]) -> Iterable[tuple[int, ...]]:
    if not bounds:
        yield ()
    else:
        for head in range(bounds[0][0], bounds[0][1] + 1):
            for tail in _axes(bounds[1:]):
                yield (head, *tail)


def resolve_joint_bnb(query: dict[str, Any], requested_k: int = 24) -> list[dict[str, Any]]:
    """Return the exact ordered GEN0-A top-K cores for an OracleQuery v1.

    Candidate generation is canonical.  Every partial duplicate is eliminated;
    ranking ties are deliberately retained until complete score comparison.
    """
    if not 1 <= requested_k <= 24 or query.get("numeric_contract") != NUMERIC_CONTRACT:
        raise ValueError("invalid resolver query")
    domain, intent, anchor = query["domain"], query["intent"], query["anchor"]
    equave = _ratio(domain["equave"])
    generators = tuple(_ratio(item) for item in domain["generators"])
    bounds = domain["coordinate_bounds"]
    anchor_vector, anchor_exponent = tuple(anchor["vector"]), anchor["equave_exponent"]
    reference = _ratio(intent["reference_equave"])
    period = _mc(reference)
    targets = sorted((_edo(reference, intent["reference_divisions"], step), step % intent["reference_divisions"]) for step in intent["steps"])
    if len({phase for phase, _ in targets}) != len(targets):
        raise ValueError("duplicate target phase")
    count = len(targets)
    placed: dict[Fraction, tuple[tuple[int, ...], int, Fraction]] = {}
    for vector in _axes(bounds):
        for exponent in range(domain["register_bounds"][0], domain["register_bounds"][1] + 1):
            ratio = _vector_ratio(generators, vector, equave, exponent)
            reduced = _reduce(ratio, equave)
            if _odd(ratio, equave) <= domain["maximum_odd_limit"] and reduced.numerator.bit_length() + reduced.denominator.bit_length() <= domain["maximum_reduced_complexity_bits"]:
                placed.setdefault(ratio, (vector, exponent, ratio))
    anchor_ratio = _vector_ratio(generators, anchor_vector, equave, anchor_exponent)
    anchor_pitch = (anchor_vector, anchor_exponent, anchor_ratio)
    pitches = [item for ratio, item in sorted(placed.items(), key=lambda item: (item[1][0], item[1][1])) if ratio != anchor_ratio]
    results: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    examined = 0
    for selected in combinations(pitches, count - 1):
        for tail in permutations(selected):
            examined += 1
            voices = (anchor_pitch, *tail)
            ratios = tuple(item[2] for item in voices)
            absolute = tuple(_mc(item) for item in ratios)
            order = sorted(range(count), key=lambda index: (absolute[index], ratios[index].numerator, ratios[index].denominator, voices[index][0], voices[index][1]))
            if min(absolute[order[index + 1]] - absolute[order[index]] for index in range(count - 1)) < intent["minimum_spacing_millicents"] or absolute[order[-1]] - absolute[order[0]] > intent["maximum_span_millicents"]:
                continue
            if intent["bass_policy"] == "preserve_target" and order[0] != intent["bass_target_ordinal"]:
                continue
            errors = tuple(_wrap(_wrap(_mc(ratios[right] / ratios[left]), period) - _wrap(targets[right][0] - targets[left][0], period), period) for left, right in combinations(range(count), 2))
            maximum, rms, complexity = max(map(abs, errors)), _rms(errors), _complexity(ratios, reference)
            if maximum > intent["maximum_pair_error_millicents"] or rms > intent["maximum_pair_rms_millicents"] or complexity > intent["complexity_budget"]:
                continue
            assignment = tuple((absolute[index] % period, ratios[index].numerator, ratios[index].denominator, voices[index][0], voices[index][1]) for index in range(count))
            shape = tuple((tuple(value - anchor_vector[axis] for axis, value in enumerate(voice[0])), voice[1] - anchor_exponent, ratio.numerator, ratio.denominator) for voice, ratio in zip(voices, ratios))
            core = {"schema": "cps.sp0-oracle-result/v1", "search_completeness": "exact", "canonical_steps": [step for _, step in targets], "vectors": [list(voice[0]) for voice in voices], "equave_exponents": [voice[1] for voice in voices], "exact_ratios": [_ratio_text(ratio) for ratio in ratios], "pair_errors_millicents": list(errors), "pair_max_millicents": maximum, "pair_rms_millicents": rms, "complexity_score": complexity, "score_prefix": [rms, maximum, complexity], "examined_assignments": 0}
            results.append(((rms, maximum, complexity, assignment, shape), core))
    ordered = [core for _, core in sorted(results, key=lambda item: item[0])[:requested_k]]
    for core in ordered:
        core["examined_assignments"] = examined
    return ordered


def _matching(left: list[dict[str, Any]], right: list[dict[str, Any]], equave_mc: int) -> tuple[Any, ...] | None:
    smaller_left = len(left) <= len(right)
    pairs_by_small = permutations(range(len(right) if smaller_left else len(left)), min(len(left), len(right)))
    best: tuple[Any, ...] | None = None
    for targets in pairs_by_small:
        pairs = tuple((index, target) if smaller_left else (target, index) for index, target in enumerate(targets))
        unmatched_left = [index for index in range(len(left)) if index not in {pair[0] for pair in pairs}]
        unmatched_right = [index for index in range(len(right)) if index not in {pair[1] for pair in pairs}]
        key = (0 if smaller_left else 1, len(pairs), *(item for pair in pairs for item in pair), 8, *unmatched_left, 8, *unmatched_right)
        motions = [abs(right[b]["ratio_millicents"] - left[a]["ratio_millicents"]) for a, b in pairs]
        lost = sum(left[a]["exact_ratio"] != right[b]["exact_ratio"] for a, b in pairs)
        crossing = sum(
            ((left[a]["ratio_millicents"], a) < (left[c]["ratio_millicents"], c))
            != ((right[b]["ratio_millicents"], b) < (right[d]["ratio_millicents"], d))
            for (a, b), (c, d) in combinations(pairs, 2)
        )
        drift = 0
        for a, b in pairs:
            if left[a]["exact_ratio"] == right[b]["exact_ratio"] or left[a]["target_ordinal"] != right[b]["target_ordinal"]:
                continue
            difference = right[b]["ratio_millicents"] - left[a]["ratio_millicents"]
            quotient, _ = divmod(difference, equave_mc)
            phase = min((difference - quotient * equave_mc, difference - (quotient + 1) * equave_mc), key=lambda value: (abs(value), value))
            drift += abs(difference - phase)
        l1 = sum(sum(abs(x - y) for x, y in zip(left[a]["absolute_vector"], right[b]["absolute_vector"])) + abs(left[a]["equave_exponent"] - right[b]["equave_exponent"]) for a, b in pairs)
        low_left = min(left, key=lambda voice: (voice["ratio_millicents"], voice["target_ordinal"], voice["absolute_vector"], voice["equave_exponent"], voice["exact_ratio"]))
        low_right = min(right, key=lambda voice: (voice["ratio_millicents"], voice["target_ordinal"], voice["absolute_vector"], voice["equave_exponent"], voice["exact_ratio"]))
        value = (abs(len(left) - len(right)), lost, crossing, sum(motions), max(motions, default=0), abs(low_right["ratio_millicents"] - low_left["ratio_millicents"]), drift, l1, key, pairs)
        if best is None or value[:-1] < best[:-1]:
            best = value
    return best


def resolve_progression(query: dict[str, Any]) -> dict[str, Any]:
    """Exact layered Viterbi over self-contained GEN0-B candidate cores."""
    if query.get("schema_version") != "1.2.0" or query.get("numeric_contract") != NUMERIC_CONTRACT:
        raise ValueError("PROGRESSION_QUERY_CONTEXT_INVALID")
    equave_mc = _mc(_ratio(query["domain_equave"]))
    layers = [sorted(item["candidate_cores"], key=lambda core: (core["local_pair_rms_millicents"], core["local_pair_max_millicents"], core["local_complexity"], core["core_hash"])) for item in query["occurrences"]]
    paths: list[tuple[tuple[Any, ...], list[dict[str, Any]], list[list[int]]]] = []
    first_occurrence = query["occurrences"][0]
    for core in layers[0]:
        if len(core["voices"]) > first_occurrence["maximum_polyphony"] or any(not first_occurrence["register_millicents"][0] <= voice["ratio_millicents"] <= first_occurrence["register_millicents"][1] for voice in core["voices"]):
            continue
        paths.append(((0, 0, 0, 0, 0, 0, 0, 0, core["local_pair_rms_millicents"], core["local_pair_max_millicents"], core["local_complexity"], ((query["occurrences"][0]["id"], core["core_hash"], None),)), [core], []))
    for layer_index in range(1, len(layers)):
        next_paths: list[tuple[tuple[Any, ...], list[dict[str, Any]], list[list[int]]]] = []
        for core in layers[layer_index]:
            occurrence = query["occurrences"][layer_index]
            if len(core["voices"]) > occurrence["maximum_polyphony"] or any(not occurrence["register_millicents"][0] <= voice["ratio_millicents"] <= occurrence["register_millicents"][1] for voice in core["voices"]):
                continue
            options = []
            for score, selected, keys in paths:
                edge = _matching(selected[-1]["voices"], core["voices"], equave_mc)
                if edge is None or edge[4] > query["maximum_voice_motion_millicents"] or (query["crossing_policy"] == "forbid" and edge[2] != 0):
                    continue
                values, key = edge[:8], list(edge[8])
                combined = (
                    *(score[index] + values[index] for index in range(4)),
                    max(score[4], values[4]),
                    *(score[index] + values[index] for index in range(5, 8)),
                    score[8] + core["local_pair_rms_millicents"],
                    score[9] + core["local_pair_max_millicents"],
                    score[10] + core["local_complexity"],
                    score[11] + ((query["occurrences"][layer_index]["id"], core["core_hash"], key),),
                )
                options.append((combined, selected + [core], keys + [key]))
            if options:
                next_paths.append(min(options, key=lambda item: item[0]))
        paths = next_paths
    if not paths:
        raise ValueError("PROGRESSION_NO_PATH")
    score, selected, keys = min(paths, key=lambda item: item[0])
    result = {"schema": "cps.progression-result", "schema_version": "1.1.0", "search_completeness": "exact", "selected_core_hashes": [core["core_hash"] for core in selected], "edge_matching_keys": keys, "score_prefix": list(score[:11]), "canonical_path_key": [{"occurrence_id": occurrence[0], "resolved_core_hash": occurrence[1], "matching_key": occurrence[2]} for occurrence in score[11]]}
    result["path_hash"] = "sha256:" + hashlib.sha256(_canonical(result)).hexdigest()
    return result


def _canonical(value: Any) -> bytes:
    """Canonical JSON subset used only for path-hash identity."""
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
