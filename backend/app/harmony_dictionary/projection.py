"""Evaluation of an arbitrary five-dimensional chord.

Given ``m = 3/4`` tone vectors in the five-axis lattice, a root, and an
equave, the evaluator:

1. computes each tone's exact root-relative ratio and register (trying every
   tone as a root hypothesis when the root is unspecified, and reporting the
   uncertainty);
2. projects every tone onto *one common axis* (the nearest 1D point, with
   equave lifts) — never one axis per tone;
3. records the projection error (max / RMS / interval distortion / voice
   loss), gates it against ``projection_error_limit_cents`` (25 cents, a
   provisional value), and selects the axis deterministically: voice-loss /
   max-error gate first, then minimum RMS, ties by max error, axis order,
   and dictionary key;
4. looks up the projected chord in the axis dictionary (the approximate
   classification) and re-evaluates with the *original exact* chord (12-EDO
   similarity, interval vector, stability), returning both and recording any
   discrepancy;
5. when no axis passes the gate, attempts a bounded on-demand exact
   evaluation and reports budget exhaustion as a failure.

This is *not* a claim that the 5D chord is isomorphic to a single axis; the
recall of the single-axis index against a small full-product fixture is
measured separately (``measure_recall``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from itertools import product

from app.harmony_dictionary.authority import (
    AXES_BY_EQUAVE,
    OCTAVE,
    AxisPoint,
    axis_index,
    reduce_on_equave,
)
from app.harmony_dictionary.dictionary import (
    _cents_decimal,
    _interval_vector,
    _pure_interval_relation,
    match_template,
)
from app.harmony_dictionary.stability import (
    DEFAULT_PROFILE,
    StabilityProfile,
    stability_q,
)
from app.harmony_dictionary.templates import templates_for_voice_count
from app.tuning.ratios import ratio_text

PROJECTION_VERSION = "1.0.0"

PROJECTION_UNRELIABLE = "PROJECTION_UNRELIABLE"
ON_DEMAND_BUDGET_EXHAUSTED = "ON_DEMAND_BUDGET_EXHAUSTED"
ROOT_UNCERTAIN = "ROOT_UNCERTAIN"


@dataclass(frozen=True)
class ProjectionPolicy:
    """Versioned projection gates and budgets."""

    # Provisional gate: a projected tone farther than this from its axis
    # point makes the axis unreliable.
    projection_error_limit_cents: float = 25.0
    # Equave lifts searched when mapping a tone to an axis point.
    max_equave_lifts: int = 1
    # Bounded on-demand exact evaluation budget (template evaluations).
    on_demand_budget: int = 2000


DEFAULT_PROJECTION_POLICY = ProjectionPolicy()


def _evaluate_vector(basis: tuple[int, ...], vector: Sequence[int]) -> Fraction:
    result = Fraction(1)
    for generator, exponent in zip(basis, vector):
        result *= Fraction(generator) ** exponent
    return result


def _equave_cents(equave: Fraction) -> Decimal:
    return Decimal(1200) * equave.numerator / equave.denominator


def _circular_distance(first: float, second: float, equave_cents: Decimal) -> float:
    """Distance on the equave circle between two positions (float cents)."""
    difference = abs(Decimal(repr(first)) - Decimal(repr(second)))
    arc = min(difference, equave_cents - difference)
    return float(arc)


def _project_tone(
    position_cents: float, points: list[AxisPoint], equave_cents: Decimal, max_lifts: int
) -> tuple[int, float, float]:
    """Map one tone to the nearest axis point (with equave lifts).

    Returns ``(index, projected_position, signed_error)`` where the
    projected position is the nearest copy of the point on the absolute
    semitone grid and the signed error is in cents.
    """
    best_index, best_distance, best_projected = 0, float("inf"), 0.0
    for index, point in enumerate(points):
        base = point.reduced_cents
        for lift in range(-max_lifts, max_lifts + 1):
            candidate = base + float(equave_cents) * lift
            distance = abs(position_cents - candidate)
            if distance < best_distance:
                best_index, best_distance, best_projected = index, distance, candidate
    return best_index, best_projected, position_cents - best_projected


def _axis_projection(
    positions_cents: list[float], points: list[AxisPoint], equave: Fraction, policy: ProjectionPolicy
) -> dict[str, object]:
    """Project every tone onto one axis; record the versioned error metrics."""
    equave_cents = _equave_cents(equave)
    indices: list[int] = []
    projected: list[float] = []
    signed: list[float] = []
    for position in positions_cents:
        index, proj, error = _project_tone(position, points, equave_cents, policy.max_equave_lifts)
        indices.append(index)
        projected.append(proj)
        signed.append(error)

    # Voice loss: two tones projecting to the same pitch collapse.
    distinct = len({round(value, 3) for value in projected})
    voice_loss = len(projected) - distinct
    max_error = max(abs(error) for error in signed)
    rms = math.sqrt(sum(error * error for error in signed) / len(signed))
    interval_distortion = max(
        abs(signed[i] - signed[j]) for i in range(len(signed)) for j in range(i + 1, len(signed))
    ) if len(signed) > 1 else 0.0
    return {
        "mapping": indices,
        "projected_cents": [round(value, 5) for value in projected],
        "signed_errors_cents": [round(value, 5) for value in signed],
        "max_error_cents": round(max_error, 5),
        "rms_error_cents": round(rms, 5),
        "interval_distortion_cents": round(interval_distortion, 5),
        "voice_loss": voice_loss,
        "passes_gate": voice_loss == 0 and max_error <= policy.projection_error_limit_cents,
    }


def _exact_evaluation(
    root_ratio: Fraction,
    root_relative_ratios: list[Fraction],
    equave: Fraction,
    *,
    tonic: Fraction | None,
    profile: StabilityProfile,
) -> dict[str, object]:
    """Re-evaluate with the original exact chord (never the projection)."""
    reduced = [reduce_on_equave(ratio, equave)[0] for ratio in root_relative_ratios]
    cents = [round(float(_cents_decimal(ratio)), 5) for ratio in reduced]
    match = match_template(cents, len(cents))
    result: dict[str, object] = {
        "ratios": [ratio_text(ratio) for ratio in reduced],
        "cents": cents,
        "template": match["name"],
        "template_matched": match["matched"],
        "template_max_error_cents": match["max_error_cents"],
        "interval_vector": _interval_vector(cents, equave),
        "pure_intervals": [
            {"pair": [i, j], **_pure_interval_relation(reduced[i], reduced[j], equave, 5.0)}
            for i in range(len(reduced))
            for j in range(i + 1, len(reduced))
        ],
    }
    if tonic is not None:
        result["stability_q"] = stability_q(root_ratio, reduced, tonic, equave=equave, profile=profile)
    return result


def evaluate_chord(
    vectors: Sequence[Sequence[int]],
    *,
    basis: Sequence[int] | None = None,
    equave: Fraction = OCTAVE,
    root_vector: Sequence[int] | None = None,
    registers: Sequence[int] | None = None,
    axes: dict[int, list[AxisPoint]] | None = None,
    dictionaries: dict[tuple[int, int], dict[str, object]] | None = None,
    tonic: Fraction | None = None,
    profile: StabilityProfile = DEFAULT_PROFILE,
    policy: ProjectionPolicy = DEFAULT_PROJECTION_POLICY,
) -> dict[str, object]:
    """Evaluate an arbitrary 5D chord (3/4 tones) per the versioned design."""
    voice_count = len(vectors)
    if voice_count not in (3, 4):
        raise ValueError(f"a chord has 3 or 4 tones, got {voice_count}")
    if basis is None:
        basis = AXES_BY_EQUAVE[ratio_text(equave)]
    basis_tuple = tuple(basis)
    if len(basis_tuple) != 5:
        raise ValueError(f"the dictionary targets five dimensions, got {len(basis_tuple)}")
    for vector in vectors:
        if len(vector) != 5:
            raise ValueError(f"every tone vector needs five coordinates, got {len(vector)}")
    registers_list = list(registers) if registers is not None else [0] * voice_count
    if len(registers_list) != voice_count:
        raise ValueError("registers must have one entry per tone")

    absolute = [
        _evaluate_vector(basis_tuple, vector) * equave**register
        for vector, register in zip(vectors, registers_list)
    ]

    def evaluate_with_root(root_index: int | None) -> dict[str, object]:
        if root_index is None:
            assert root_vector is not None
            root_ratio = _evaluate_vector(basis_tuple, root_vector)
        else:
            root_ratio = absolute[root_index]
        relative = [ratio / root_ratio for ratio in absolute]
        reduced = [reduce_on_equave(ratio, equave)[0] for ratio in relative]
        positions = [float(_cents_decimal(ratio)) for ratio in reduced]

        axis_results: list[dict[str, object]] = []
        for j, generator in enumerate(basis_tuple):
            points = axes[generator] if axes is not None else axis_index(equave, generator)[1]
            axis_results.append(_axis_projection(positions, points, equave, policy))

        candidates = [
            (result["rms_error_cents"], result["max_error_cents"], j)
            for j, result in enumerate(axis_results)
            if result["passes_gate"]
        ]
        selected: int | None = None
        if candidates:
            # Minimum RMS, ties by max error, axis order (the dictionary key
            # is a further tie-breaker applied below when keys are equal).
            candidates.sort()
            selected = candidates[0][2]

        result: dict[str, object] = {
            "root_index": root_index if root_index is not None else "specified",
            "root_ratio": ratio_text(root_ratio),
            "relative_ratios": [ratio_text(ratio) for ratio in reduced],
            "positions_cents": [round(value, 5) for value in positions],
            "axes": [
                {"axis": j, "generator": basis_tuple[j], **axis_results[j]} for j in range(5)
            ],
        }
        if selected is None:
            result["selected_axis"] = None
            result["projection_status"] = PROJECTION_UNRELIABLE
            return result

        result["selected_axis"] = selected
        result["projection_status"] = "ok"
        return result

    if root_vector is not None:
        if len(root_vector) != 5:
            raise ValueError(f"root_vector needs five coordinates, got {len(root_vector)}")
        evaluated = evaluate_with_root(None)
    else:
        # Root unspecified: try every tone as a root hypothesis and keep the
        # best (lowest RMS); the uncertainty is reported, not hidden.
        hypotheses = [evaluate_with_root(index) for index in range(voice_count)]
        best = min(
            hypotheses,
            key=lambda item: min(
                (float(axis["rms_error_cents"]) for axis in item["axes"] if axis["passes_gate"]),
                default=float("inf"),
            ),
        )
        evaluated = best
        evaluated["root_hypotheses"] = [
            {
                "index": item["root_index"],
                "rms_error_cents": min(
                    (float(axis["rms_error_cents"]) for axis in item["axes"] if axis["passes_gate"]),
                    default=float("inf"),
                ),
            }
            for item in hypotheses
        ]
        evaluated["root_uncertain"] = len(
            {item["root_ratio"] for item in hypotheses}
        ) > 1

    selected = evaluated["selected_axis"]
    code = "OK" if selected is not None else PROJECTION_UNRELIABLE

    approximate: dict[str, object] | None = None
    if selected is not None:
        generator = basis_tuple[selected]
        projected = [float(value) for value in evaluated["axes"][selected]["projected_cents"]]
        # Re-root at the projection of the tone nearest the actual root (the
        # dictionary keys its variants at the minimum reduced position).
        positions = [float(value) for value in evaluated["positions_cents"]]
        anchor = projected[min(range(voice_count), key=lambda i: positions[i])]
        relative_projected = [value - anchor for value in projected]
        cells = [int((Decimal(repr(value)) / Decimal(100)).to_integral_value(rounding=ROUND_HALF_EVEN)) % 12 for value in relative_projected]
        key = ",".join(str(cell) for cell in sorted(cells))
        dictionary_hit = False
        template = "other"
        if dictionaries is not None:
            dictionary = dictionaries.get((generator, voice_count))
            for entry in dictionary.get("entries", []) if dictionary else []:
                if entry["key"] == key:
                    dictionary_hit = True
                    template = entry["variants"][0]["template"]
                    break
        approximate = {"key": key, "template": template, "dictionary_hit": dictionary_hit}

    exact = _exact_evaluation(
        Fraction(evaluated["root_ratio"]),  # type: ignore[arg-type]
        [Fraction(text) for text in evaluated["relative_ratios"]],  # type: ignore[arg-type]
        equave,
        tonic=tonic,
        profile=profile,
    )

    discrepancy: str | None = None
    if approximate is not None and approximate["template"] != exact["template"]:
        discrepancy = f"approximate {approximate['template']} != exact {exact['template']}"

    if selected is not None:
        code = "OK"
    else:
        # Bounded on-demand exact evaluation: the template search is bounded
        # by construction; report exhaustion when it exceeds the budget.
        evaluations = len(templates_for_voice_count(voice_count)) * voice_count * math.factorial(voice_count)
        if evaluations <= policy.on_demand_budget:
            code = PROJECTION_UNRELIABLE  # the exact fallback succeeded
        else:
            code = ON_DEMAND_BUDGET_EXHAUSTED
            exact = None  # type: ignore[assignment]

    root_index = evaluated["root_index"]
    result: dict[str, object] = {
        "version": PROJECTION_VERSION,
        "equave": ratio_text(equave),
        "basis": list(basis_tuple),
        "root": {
            "vector": list(root_vector) if root_vector is not None else list(vectors[root_index]),  # type: ignore[index]
            "ratio": evaluated["root_ratio"],
            "hypothesis": "specified" if root_vector is not None else f"tone_{root_index}",
            "uncertain": evaluated.get("root_uncertain", False),
        },
        "tones": [
            {
                "vector": list(vector),
                "register": register,
                "ratio": ratio_text(ratio),
            }
            for vector, register, ratio in zip(vectors, registers_list, absolute)
        ],
        "relative_ratios": evaluated["relative_ratios"],
        "positions_cents": evaluated["positions_cents"],
        "axes": evaluated["axes"],
        "selected_axis": selected,
        "projection_status": evaluated["projection_status"],
        "approximate": approximate,
        "exact": exact,
        "discrepancy": discrepancy,
        "code": code,
    }
    if root_vector is None:
        result["root_hypotheses"] = evaluated.get("root_hypotheses", [])
    return result


def measure_recall(
    *,
    equave: Fraction = OCTAVE,
    basis: Sequence[int] | None = None,
    bound: int = 1,
    chord_count: int = 64,
    voice_counts: tuple[int, ...] = (3, 4),
    seed: int = 0,
    axes: dict[int, list[AxisPoint]] | None = None,
    dictionaries: dict[tuple[int, int], dict[str, object]] | None = None,
    policy: ProjectionPolicy = DEFAULT_PROJECTION_POLICY,
) -> dict[str, object]:
    """Measure the single-axis index recall against a small full product.

    Chords are sampled from the bounded full Cartesian product
    (``[-bound, bound]**5``) and evaluated on-demand exactly; the recall is
    the share that the single-axis projection recovers (passes the gate),
    and the misclassification rate compares the approximate dictionary
    classification with the exact re-evaluation.  A low recall means the
    index must be revised (e.g. top-2 axis search) — not that the numbers
    should be massaged.
    """
    import random

    if basis is None:
        basis = AXES_BY_EQUAVE[ratio_text(equave)]
    rng = random.Random(seed)
    grid = list(range(-bound, bound + 1))
    points = [list(vector) for vector in product(grid, repeat=5)]
    projectable = 0
    classified = 0
    mismatched = 0
    examined = 0
    for _ in range(chord_count):
        voice_count = rng.choice(voice_counts)
        tones = rng.sample(points, voice_count)
        examined += 1
        result = evaluate_chord(
            tones,
            basis=basis,
            equave=equave,
            axes=axes,
            dictionaries=dictionaries,
            policy=policy,
        )
        if result["code"] == "OK":
            projectable += 1
            approximate = result["approximate"]
            exact = result["exact"]
            if approximate is not None and exact is not None:
                classified += 1
                if approximate["template"] != exact["template"]:
                    mismatched += 1
    return {
        "equave": ratio_text(equave),
        "basis": list(basis),
        "bound": bound,
        "chord_count": examined,
        "projectable": projectable,
        "recall": round(projectable / examined, 5) if examined else 0.0,
        "classified": classified,
        "misclassified": mismatched,
        "misclassification_rate": round(mismatched / classified, 5) if classified else 0.0,
    }


