"""Milestone 3: evaluation of arbitrary five-dimensional chords."""

from __future__ import annotations

import pytest

from app.harmony_dictionary.authority import OCTAVE, TRITAVE
from app.harmony_dictionary.dictionary import build_axis_dictionary
from app.harmony_dictionary.projection import (
    ON_DEMAND_BUDGET_EXHAUSTED,
    PROJECTION_UNRELIABLE,
    ProjectionPolicy,
    evaluate_chord,
    measure_recall,
)

# A just major triad expressed in the five-axis lattice [3, 5, 7, 11, 13]:
# 1/1, 3/2 (one fifth step down an octave), 5/4 (one major-third step down).
MAJOR_TRIAD_VECTORS = [[0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 0, 0, 0]]
MAJOR_TRIAD_REGISTERS = [0, -1, -2]


def test_axis_pure_chord_projects_with_zero_error() -> None:
    # A fifth stack lives exactly on the 3-axis.
    result = evaluate_chord(
        [[0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [2, 0, 0, 0, 0]],
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=[0, -1, -2],
    )
    assert result["code"] == "OK"
    assert result["selected_axis"] == 0
    selected = result["axes"][0]
    assert selected["max_error_cents"] == 0.0
    assert selected["rms_error_cents"] == 0.0
    assert selected["voice_loss"] == 0
    assert result["projection_status"] == "ok"


def test_two_axis_chord_selects_the_least_erroneous_axis() -> None:
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=MAJOR_TRIAD_REGISTERS,
    )
    assert result["code"] == "OK"
    axes = result["axes"]
    # The 3-axis carries the fifth exactly; only the 5/4 tone is approximate.
    assert result["selected_axis"] == 0
    assert axes[0]["max_error_cents"] < axes[1]["max_error_cents"]
    # The exact re-evaluation sees the true major triad.
    assert result["exact"]["template"] == "major_triad"


def test_discrepancy_between_approximate_and_exact_is_recorded() -> None:
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=MAJOR_TRIAD_REGISTERS,
    )
    # Without a dictionary the approximate side is "other"; the exact side
    # says major_triad, and the discrepancy must be reported.
    assert result["approximate"]["template"] == "other"
    assert result["exact"]["template"] == "major_triad"
    assert result["discrepancy"] is not None


def test_dictionary_lookup_hits_the_projected_key() -> None:
    dictionaries = {(3, 3): build_axis_dictionary(OCTAVE, 3, 3)}
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=MAJOR_TRIAD_REGISTERS,
        dictionaries=dictionaries,
    )
    assert result["approximate"]["key"] == "0,4,7"
    assert result["approximate"]["dictionary_hit"] is True
    assert result["approximate"]["template"] == "major_triad"
    assert result["discrepancy"] is None


def test_root_hypotheses_are_tried_and_reported() -> None:
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        registers=MAJOR_TRIAD_REGISTERS,
    )
    assert result["root"]["hypothesis"] == "tone_0"
    assert result["root"]["uncertain"] is True
    hypotheses = result["root_hypotheses"]
    assert [item["index"] for item in hypotheses] == [0, 1, 2]
    # The chosen hypothesis has the lowest RMS of the passing axes.
    best = min(item["rms_error_cents"] for item in hypotheses)
    assert best == min(
        item["rms_error_cents"] for item in hypotheses if item["index"] == 0
    )


def test_unreliable_projection_when_no_axis_passes_the_gate() -> None:
    policy = ProjectionPolicy(projection_error_limit_cents=0.001)
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=MAJOR_TRIAD_REGISTERS,
        policy=policy,
    )
    assert result["code"] == PROJECTION_UNRELIABLE
    assert result["selected_axis"] is None
    assert result["projection_status"] == PROJECTION_UNRELIABLE
    assert result["approximate"] is None
    # The bounded on-demand exact evaluation still runs.
    assert result["exact"]["template"] == "major_triad"


def test_on_demand_budget_exhaustion_is_a_failure() -> None:
    policy = ProjectionPolicy(projection_error_limit_cents=0.001, on_demand_budget=1)
    result = evaluate_chord(
        MAJOR_TRIAD_VECTORS,
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=MAJOR_TRIAD_REGISTERS,
        policy=policy,
    )
    assert result["code"] == ON_DEMAND_BUDGET_EXHAUSTED
    assert result["exact"] is None


def test_voice_loss_is_detected_for_doubled_tones() -> None:
    result = evaluate_chord(
        [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [1, 0, 0, 0, 0]],
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=[0, 0, -1],
    )
    for axis in result["axes"]:
        assert axis["voice_loss"] == 1
        assert axis["passes_gate"] is False
    assert result["code"] == PROJECTION_UNRELIABLE


def test_tetrad_evaluation() -> None:
    # A dominant seventh on the 3/5 axes: 1/1, 5/4, 3/2, 7/4.
    result = evaluate_chord(
        [[0, 0, 0, 0, 0], [0, 1, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 1, 0, 0]],
        equave=OCTAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=[0, -2, -1, -3],
    )
    assert result["code"] == "OK"
    assert result["exact"]["template"] == "dominant_seventh"
    assert len(result["exact"]["interval_vector"]) == 6


def test_tritave_equave_evaluation() -> None:
    # On the tritave lattice the basis is [2, 5, 7, 11, 13].
    result = evaluate_chord(
        [[0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 0, 0, 0]],
        equave=TRITAVE,
        root_vector=[0, 0, 0, 0, 0],
        registers=[0, -1, -2],
    )
    assert result["equave"] == "3/1"
    assert result["basis"][0] == 2
    assert result["code"] in ("OK", PROJECTION_UNRELIABLE)


def test_validation_errors() -> None:
    with pytest.raises(ValueError):
        evaluate_chord([[0, 0, 0, 0, 0], [1, 0, 0, 0, 0]], equave=OCTAVE)
    with pytest.raises(ValueError):
        evaluate_chord(MAJOR_TRIAD_VECTORS, equave=OCTAVE, registers=[0, 0])
    with pytest.raises(ValueError):
        evaluate_chord(MAJOR_TRIAD_VECTORS, equave=OCTAVE, root_vector=[0, 0])


def test_evaluation_is_deterministic() -> None:
    first = evaluate_chord(
        MAJOR_TRIAD_VECTORS, equave=OCTAVE, root_vector=[0, 0, 0, 0, 0], registers=MAJOR_TRIAD_REGISTERS
    )
    second = evaluate_chord(
        MAJOR_TRIAD_VECTORS, equave=OCTAVE, root_vector=[0, 0, 0, 0, 0], registers=MAJOR_TRIAD_REGISTERS
    )
    assert first == second


def test_measure_recall_against_the_full_product() -> None:
    result = measure_recall(equave=OCTAVE, bound=1, chord_count=8, seed=42)
    assert result["chord_count"] == 8
    assert 0.0 <= result["recall"] <= 1.0
    assert 0.0 <= result["misclassification_rate"] <= 1.0
    assert result["projectable"] == int(result["recall"] * 8)


# ------------------------------------------- equave-lift boundary (1.1.0)


def test_project_tone_uses_equave_lift_at_the_octave_boundary() -> None:
    from fractions import Fraction

    from app.harmony_dictionary.authority import AxisPoint
    from app.harmony_dictionary.projection import _equave_cents, _project_tone

    point = AxisPoint(
        n=1,
        original_ratio=Fraction(3, 2),
        reduced_ratio=Fraction(3, 2),
        equave_exponent=0,
        absolute_cents=701.955,
        nearest_12edo_semitone=7,
        signed_12edo_error_cents=1.955,
        reduced_cents=1198.0,
    )
    # A tone 5 cents from 0 reaches the point's octave-down copy (7c away);
    # with the old 2400c equave width that lift was 1207c away and unused.
    index, projected, error = _project_tone(5.0, [point], _equave_cents(OCTAVE), 1)
    assert index == 0
    assert projected == pytest.approx(-2.0, abs=1e-9)
    assert error == pytest.approx(7.0, abs=1e-9)


def test_project_tone_uses_equave_lift_at_the_tritave_boundary() -> None:
    from fractions import Fraction

    from app.harmony_dictionary.authority import AxisPoint
    from app.harmony_dictionary.projection import _equave_cents, _project_tone

    point = AxisPoint(
        n=1,
        original_ratio=Fraction(2, 1),
        reduced_ratio=Fraction(2, 1),
        equave_exponent=0,
        absolute_cents=1200.0,
        nearest_12edo_semitone=12,
        signed_12edo_error_cents=0.0,
        reduced_cents=5.0,
    )
    # Near the top of the ~1902c tritave circle, lift +1 is the nearest copy
    # (the old 3600c width would have kept the tone 1890c from the base).
    index, projected, error = _project_tone(1895.0, [point], _equave_cents(TRITAVE), 1)
    assert index == 0
    assert projected == pytest.approx(5.0 + 1901.955, abs=1e-3)
    assert error == pytest.approx(1895.0 - (5.0 + 1901.955), abs=1e-3)
