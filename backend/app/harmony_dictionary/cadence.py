"""Cadence generation and independent diagnostics.

A cadence is generated from the axis dictionaries: the tonic root, equave,
and cadence kind are specified, and 2-4 chords (3/4-voice mix allowed) are
assembled.  Kinds:

- ``authentic``:        T -> D -> T
- ``predominant_chain``: T -> S -> D -> T  (renamed from "plagal"; a true
  plagal cadence is IV -> I, which this four-chord chain is not)
- ``open``:             ... -> D (2-3 chords, ending on the dominant)
- ``lattice``:   2-4 dictionary chords with a stability contour

Lattice-native candidates are *not* excluded by 12-EDO match degree alone:
any dictionary variant may fill a slot, ranked by its context-dependent
stability.  When a slot cannot be filled the result carries
``PROGRESSION_NO_PATH`` with the cause.

The generator diagnoses, independently: the stability contour, the final
landing, bass/root motion, voice leading (exact cents), tendency-tone
resolution, beat landing, and connection with a following repetition.
"""

from __future__ import annotations

import random
from decimal import Decimal
from fractions import Fraction

from app.harmony_dictionary.authority import OCTAVE, reduce_on_equave
from app.harmony_dictionary.dictionary import _cents_decimal
from app.harmony_dictionary.stability import (
    DEFAULT_PROFILE,
    DEFAULT_THRESHOLDS,
    StabilityProfile,
    ClassificationThresholds,
    classify_with_context,
    stability_q,
)
from app.tuning.ratios import ratio_text

# 1.1.0: voice leading / common tones / tendency resolution now compare
# actual pitches (root * ratio) instead of root-relative ratios, and the
# "plagal" kind is renamed "predominant_chain".  Diagnostic values change.
CADENCE_VERSION = "1.1.0"

PROGRESSION_NO_PATH = "PROGRESSION_NO_PATH"

# Function roots relative to the tonic (reduced on the equave at use time).
FUNCTION_ROOTS = {
    "T": Fraction(1),
    "D": Fraction(3, 2),
    "S": Fraction(4, 3),
}

# Versioned progression templates per kind.
CADENCE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "authentic": ("T", "D", "T"),
    "predominant_chain": ("T", "S", "D", "T"),
    "open": ("S", "D"),
    "lattice": (),  # length is seeded, 2..max_chords
}

# Versioned selection bounds.
MAX_CANDIDATES = 200
TOP_K = 8
VOICE_LEADING_CAP_CENTS = 400.0


def _variant_pool(
    dictionaries: dict[tuple[int, int], dict[str, object]], equave: Fraction
) -> list[dict[str, object]]:
    """Flatten every dictionary variant into a candidate chord.

    Each candidate carries the exact root-relative ratios (root = 1/1) plus
    its provenance.  Any candidate may fill any function slot: the function
    is a choice of root placement, not a filter on the variant.
    """
    pool: list[dict[str, object]] = []
    for (generator, voice_count), dictionary in sorted(dictionaries.items()):
        for entry in dictionary.get("entries", []):
            for variant in entry.get("variants", []):
                ratios = [Fraction(text) for text in variant["ratios"]]
                reduced = [reduce_on_equave(ratio, equave)[0] for ratio in ratios]
                pool.append(
                    {
                        "generator": generator,
                        "voice_count": voice_count,
                        "index_tuple": variant["index_tuple"],
                        "ratios": reduced,
                        "template": variant["template"],
                    }
                )
    return pool


def _place(candidate: dict[str, object], function: str, tonic: Fraction, equave: Fraction) -> tuple[Fraction, list[Fraction]]:
    """Place a candidate's root at the function position relative to the tonic."""
    factor = FUNCTION_ROOTS[function]
    root, _ = reduce_on_equave(tonic * factor, equave)
    return root, candidate["ratios"]


def _actual_voice_cents(root: Fraction, ratios: list[Fraction]) -> list[Decimal]:
    """Actual pitch of each voice (``root * ratio``) in cents.

    The ratios are root-relative; the root must be applied, otherwise two
    chords with identical relative ratios on different roots would report
    zero movement.
    """
    root_cents = Decimal(repr(float(_cents_decimal(root))))
    return [root_cents + Decimal(repr(float(_cents_decimal(ratio)))) for ratio in ratios]


def _voice_leading(
    first: tuple[Fraction, list[Fraction]], second: tuple[Fraction, list[Fraction]], equave: Fraction
) -> tuple[Decimal, list[int]]:
    """Minimum total voice movement (cents, with equave lifts) + the mapping.

    Each source voice moves independently to its nearest copy (with equave
    lifts) of any target voice; doublings are allowed so mixed 3/4-voice
    chords stay defined.  The returned mapping records, per source voice,
    the index of the target voice it chose (one-to-one-ness is inspectable).
    """
    from app.harmony_dictionary.stability import _equave_cents

    equave_cents = _equave_cents(equave)
    source = _actual_voice_cents(first[0], first[1])
    target = _actual_voice_cents(second[0], second[1])
    total = Decimal(0)
    mapping: list[int] = []
    for value in source:
        best_index, best_distance = 0, Decimal("Infinity")
        for index, other in enumerate(target):
            for steps in (-1, 0, 1):
                distance = abs(value - (other + equave_cents * steps))
                if distance < best_distance:
                    best_index, best_distance = index, distance
        mapping.append(best_index)
        total += best_distance
    return total, mapping


def _voice_leading_cents(
    first: tuple[Fraction, list[Fraction]], second: tuple[Fraction, list[Fraction]], equave: Fraction
) -> float:
    """Minimum total voice movement (cents, with equave lifts) between two chords."""
    return float(_voice_leading(first, second, equave)[0])


def _select_chord(
    pool: list[dict[str, object]],
    function: str,
    tonic: Fraction,
    previous: tuple[Fraction, list[Fraction]] | None,
    *,
    equave: Fraction,
    profile: StabilityProfile,
    thresholds: ClassificationThresholds,
    rng: random.Random,
) -> dict[str, object] | None:
    """Rank candidates for one function slot and pick one (seeded).

    T slots rank by stability descending, D slots ascending, S slots by
    closeness to the threshold midpoint.  A candidate must also satisfy the
    voice-leading cap against the previous chord.  Returns None when no
    candidate passes (the caller records PROGRESSION_NO_PATH).
    """
    if not pool:
        return None
    sampled = pool if len(pool) <= MAX_CANDIDATES else rng.sample(pool, MAX_CANDIDATES)
    midpoint = (thresholds.T_high + thresholds.D_low) / 2
    scored: list[tuple[float, dict[str, object], Fraction, list[Fraction]]] = []
    for candidate in sampled:
        root, ratios = _place(candidate, function, tonic, equave)
        value = stability_q(root, ratios, tonic, equave=equave, profile=profile)
        if function == "T":
            rank = -value
        elif function == "D":
            rank = value
        else:
            rank = abs(value - midpoint)
        scored.append((float(rank), candidate, root, ratios))
    scored.sort(key=lambda item: (item[0], item[1]["generator"], item[1]["index_tuple"]))
    passing = [item for item in scored if previous is None or _voice_leading_cents(previous, (item[2], item[3]), equave) <= VOICE_LEADING_CAP_CENTS]
    if not passing:
        return None
    chosen = rng.choice(passing[:TOP_K])
    _, candidate, root, ratios = chosen
    return {
        "function": function,
        "generator": candidate["generator"],
        "voice_count": candidate["voice_count"],
        "index_tuple": candidate["index_tuple"],
        "template": candidate["template"],
        "root_ratio": ratio_text(root),
        "ratios": [ratio_text(ratio) for ratio in ratios],
    }


def _chord_ratios(chord: dict[str, object]) -> tuple[Fraction, list[Fraction]]:
    root = Fraction(chord["root_ratio"])  # type: ignore[arg-type]
    ratios = [Fraction(text) for text in chord["ratios"]]  # type: ignore[arg-type]
    return root, ratios


def _describe_motion(first_root: Fraction, second_root: Fraction, equave: Fraction) -> str:
    """Name the root motion on the equave circle (versioned table)."""
    from app.harmony_dictionary.stability import _circular_distance_cents

    distance = float(_circular_distance_cents(first_root, second_root, equave))
    if distance < 50.0:
        return "root stationary"
    if distance < 150.0:
        return "stepwise root motion"
    if distance < 300.0:
        return "third-like root motion"
    if distance < 550.0:
        return "fourth/fifth root motion"
    return "wide root motion"


def diagnose_stability_contour(
    chords: list[dict[str, object]], tonic: Fraction, *, equave: Fraction, profile: StabilityProfile
) -> list[int]:
    """The stability_q of each chord against the tonic (the contour)."""
    contour = []
    for chord in chords:
        root, ratios = _chord_ratios(chord)
        contour.append(stability_q(root, ratios, tonic, equave=equave, profile=profile))
    return contour


def diagnose_final_landing(
    chords: list[dict[str, object]], tonic: Fraction, *, equave: Fraction, closed: bool
) -> dict[str, object]:
    """Whether the cadence lands where its kind requires."""
    from app.harmony_dictionary.stability import _circular_distance_cents

    if not chords:
        return {"lands": False, "reason": "empty progression"}
    root, _ = _chord_ratios(chords[-1])
    distance = float(_circular_distance_cents(root, tonic, equave))
    if closed:
        lands = distance < 50.0
    else:
        # An open cadence must land on the dominant, not the tonic.
        dominant, _ = reduce_on_equave(tonic * FUNCTION_ROOTS["D"], equave)
        lands = float(_circular_distance_cents(root, dominant, equave)) < 50.0
    return {"lands": lands, "final_root": ratio_text(root), "distance_to_tonic_cents": round(distance, 5)}


def diagnose_root_motion(chords: list[dict[str, object]], *, equave: Fraction) -> list[dict[str, object]]:
    """Bass/root motion between consecutive chords."""
    from app.harmony_dictionary.stability import _circular_distance_cents

    motions = []
    for first, second in zip(chords, chords[1:]):
        first_root, _ = _chord_ratios(first)
        second_root, _ = _chord_ratios(second)
        distance = float(_circular_distance_cents(first_root, second_root, equave))
        motions.append(
            {
                "from": ratio_text(first_root),
                "to": ratio_text(second_root),
                "distance_cents": round(distance, 5),
                "description": _describe_motion(first_root, second_root, equave),
            }
        )
    return motions


def diagnose_voice_leading(
    chords: list[dict[str, object]], *, equave: Fraction
) -> list[dict[str, object]]:
    """Exact-cents voice leading and common tones between consecutive chords."""
    transitions = []
    for first, second in zip(chords, chords[1:]):
        first_root, first_ratios = _chord_ratios(first)
        second_root, second_ratios = _chord_ratios(second)
        total, mapping = _voice_leading((first_root, first_ratios), (second_root, second_ratios), equave)
        movement = float(total)
        # Common tones compare *actual* pitches (root * ratio), not the
        # root-relative ratios: a shared relative ratio on different roots
        # is not a shared pitch.
        common = sum(
            1
            for ratio in first_ratios
            if any(_is_same_pitch(first_root * ratio, second_root * other, equave) for other in second_ratios)
        )
        transitions.append(
            {
                "total_movement_cents": round(movement, 5),
                "common_tones": common,
                "voice_mapping": mapping,
                "within_cap": movement <= VOICE_LEADING_CAP_CENTS,
            }
        )
    return transitions


def _is_same_pitch(first: Fraction, second: Fraction, equave: Fraction) -> bool:
    from app.harmony_dictionary.stability import _circular_distance_cents

    return float(_circular_distance_cents(first, second, equave)) < 5.0


def diagnose_tendency_resolution(
    chords: list[dict[str, object]], *, equave: Fraction, tolerance_cents: float = 200.0
) -> dict[str, object]:
    """Whether each voice of a chord resolves (moves <= tolerance) in the next.

    A voice that cannot resolve within the tolerance is a dangling tendency
    tone; the final chord's unresolved voices are reported separately.
    """
    from app.harmony_dictionary.stability import _equave_cents

    equave_cents = _equave_cents(equave)
    transitions = []
    for first, second in zip(chords, chords[1:]):
        first_root, first_ratios = _chord_ratios(first)
        second_root, second_ratios = _chord_ratios(second)
        source = _actual_voice_cents(first_root, first_ratios)
        target = _actual_voice_cents(second_root, second_ratios)
        unresolved = 0
        for value in source:
            resolved = any(
                abs(value - (other + equave_cents * steps)) <= Decimal(str(tolerance_cents))
                for other in target
                for steps in (-1, 0, 1)
            )
            if not resolved:
                unresolved += 1
        transitions.append({"unresolved_voices": unresolved, "voice_count": len(source)})
    final_unresolved = transitions[-1]["unresolved_voices"] if transitions else 0
    return {
        "transitions": transitions,
        "final_unresolved_voices": final_unresolved,
        "all_resolved": all(item["unresolved_voices"] == 0 for item in transitions),
    }


def diagnose_beat_landing(beats: list[int], *, measure_length: int = 4) -> dict[str, object]:
    """Whether the final chord lands on a downbeat of its measure."""
    if not beats:
        return {"lands_on_downbeat": False, "reason": "no beats given"}
    final = beats[-1] % measure_length
    return {"lands_on_downbeat": final == 0, "final_beat": beats[-1], "final_beat_in_measure": final}


def generate_cadence(
    tonic_ratio: Fraction,
    *,
    equave: Fraction = OCTAVE,
    kind: str = "authentic",
    dictionaries: dict[tuple[int, int], dict[str, object]],
    profile: StabilityProfile = DEFAULT_PROFILE,
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS,
    seed: int = 0,
    max_chords: int = 4,
    beats: list[int] | None = None,
) -> dict[str, object]:
    """Assemble a cadence from the dictionaries and diagnose it independently."""
    if kind not in CADENCE_TEMPLATES:
        raise ValueError(f"unknown cadence kind {kind!r}; expected one of {sorted(CADENCE_TEMPLATES)}")
    if not 2 <= max_chords <= 4:
        raise ValueError("max_chords must be between 2 and 4")
    rng = random.Random(seed)

    template = CADENCE_TEMPLATES[kind]
    if kind == "lattice":
        length = rng.randint(2, max_chords)
        # A lattice cadence walks the dictionary: free slots pick their
        # function by seed, and the cadence closes on T.
        free = [rng.choice(("T", "S", "D")) for _ in range(length - 1)]
        template = (*free, "T")
    pool = _variant_pool(dictionaries, equave)

    chords: list[dict[str, object]] = []
    failure_reason: str | None = None
    previous: tuple[Fraction, list[Fraction]] | None = None
    for function in template:
        slot_function = function if function in FUNCTION_ROOTS else "T"
        chord = _select_chord(pool, slot_function, tonic_ratio, previous, equave=equave, profile=profile, thresholds=thresholds, rng=rng)
        if chord is None:
            failure_reason = f"no candidate for {function} slot (voice-leading cap {VOICE_LEADING_CAP_CENTS}c)"
            break
        chords.append(chord)
        previous = _chord_ratios(chord)

    closed = kind in ("authentic", "predominant_chain") or (kind == "lattice" and template[-1] == "T")
    code = "OK" if failure_reason is None else PROGRESSION_NO_PATH
    result: dict[str, object] = {
        "version": CADENCE_VERSION,
        "tonic": ratio_text(tonic_ratio),
        "equave": ratio_text(equave),
        "kind": kind,
        "seed": seed,
        "code": code,
        "failure_reason": failure_reason,
        "chords": chords,
    }
    if code == "OK":
        result["diagnostics"] = {
            "stability_contour": diagnose_stability_contour(chords, tonic_ratio, equave=equave, profile=profile),
            "final_landing": diagnose_final_landing(chords, tonic_ratio, equave=equave, closed=closed),
            "root_motion": diagnose_root_motion(chords, equave=equave),
            "voice_leading": diagnose_voice_leading(chords, equave=equave),
            "tendency_resolution": diagnose_tendency_resolution(chords, equave=equave),
        }
        if beats is not None:
            result["diagnostics"]["beat_landing"] = diagnose_beat_landing(beats)
        classifications = []
        for chord in chords:
            root, ratios = _chord_ratios(chord)
            classifications.append(
                classify_with_context(root, ratios, tonic_ratio, equave=equave, profile=profile, thresholds=thresholds)
            )
        result["classifications"] = classifications
    return result


FUNCTION_LABELS = {"T": "tonic", "D": "dominant", "S": "subdominant"}


def build_classification_report(
    cadences: list[dict[str, object]],
) -> dict[str, object]:
    """The §4 final report over generated cadences.

    Carries both the threshold-only three-way classification and the
    contextual final label, the confusion matrix against the known slot
    functions, coverage (the share of non-ambiguous chords), and the I/IV
    (tonic/subdominant) misclassification examples.

    The "truth" is the function slot assigned *at generation time*; it is
    not an independent musical ground truth.  The matrix therefore measures
    the classifier's self-consistency, not its accuracy against annotated
    music, and ``ambiguous`` is a first-class outcome, not an error.
    """
    rows = ("tonic", "dominant", "subdominant")
    columns = ("tonic", "dominant", "subdominant", "ambiguous")
    matrix = {row: {column: 0 for column in columns} for row in rows}
    threshold_only = {row: {column: 0 for column in columns} for row in rows}
    total = 0
    ambiguous = 0
    iv_examples: list[dict[str, object]] = []

    for cadence in cadences:
        if cadence.get("code") != "OK":
            continue
        chords = cadence.get("chords", [])  # type: ignore[arg-type]
        classifications = cadence.get("classifications", [])  # type: ignore[arg-type]
        for chord, classification in zip(chords, classifications):
            truth = FUNCTION_LABELS.get(str(chord.get("function")))  # type: ignore[arg-type]
            if truth is None:
                continue
            final = str(classification.get("final"))  # type: ignore[arg-type]
            candidate = str(classification.get("candidate"))  # type: ignore[arg-type]
            total += 1
            matrix[truth][final] += 1
            threshold_only[truth][candidate if candidate in columns else "ambiguous"] += 1
            if final == "ambiguous":
                ambiguous += 1
            if {truth, final} == {"tonic", "subdominant"}:
                iv_examples.append(
                    {
                        "tonic": cadence.get("tonic"),
                        "equave": cadence.get("equave"),
                        "kind": cadence.get("kind"),
                        "seed": cadence.get("seed"),
                        "function": chord.get("function"),  # type: ignore[arg-type]
                        "root": chord.get("root_ratio"),  # type: ignore[arg-type]
                        "stability_q": classification.get("stability_q"),  # type: ignore[arg-type]
                        "final": final,
                    }
                )

    return {
        "version": CADENCE_VERSION,
        "truth_source": "self_assigned_slot",
        "note": (
            "confusion_matrix rows are the function slots assigned at generation time, "
            "not an independent ground truth; it measures classifier self-consistency"
        ),
        "chord_count": total,
        "coverage": round(1 - ambiguous / total, 5) if total else 0.0,
        "confusion_matrix": matrix,
        "threshold_only_matrix": threshold_only,
        "iv_misclassification_examples": iv_examples[:16],
    }


