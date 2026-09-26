"""Milestone 4: stability scoring, T/D/S classification, and cadences."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.harmony_dictionary.authority import OCTAVE, TRITAVE, AXES_BY_EQUAVE
from app.harmony_dictionary.cadence import (
    PROGRESSION_NO_PATH,
    build_classification_report,
    generate_cadence,
)
from app.harmony_dictionary.dictionary import DictionaryPolicy, build_axis_dictionary
from app.harmony_dictionary.stability import (
    DEFAULT_PROFILE,
    DEFAULT_THRESHOLDS,
    ClassificationThresholds,
    classify_threshold,
    classify_with_context,
    stability_components,
    stability_q,
)

I_CHORD = [Fraction(1), Fraction(5, 4), Fraction(3, 2)]
V7_CHORD = [Fraction(1), Fraction(5, 4), Fraction(3, 2), Fraction(7, 4)]


# ---------------------------------------------------------------- stability


def test_components_are_in_unit_range() -> None:
    components = stability_components(
        Fraction(1), I_CHORD, Fraction(1), equave=OCTAVE
    )
    assert set(components) == {"R", "C", "V", "F"}
    for value in components.values():
        assert 0.0 <= value <= 1.0


def test_tonic_is_stable_and_dominant_is_not() -> None:
    tonic = Fraction(1)
    i_value = stability_q(Fraction(1), I_CHORD, tonic, equave=OCTAVE)
    v7_value = stability_q(Fraction(3, 2), V7_CHORD, tonic, equave=OCTAVE)
    assert i_value > v7_value
    assert i_value >= DEFAULT_THRESHOLDS.T_high
    assert v7_value <= DEFAULT_THRESHOLDS.T_high


def test_stability_depends_on_the_specified_tonic() -> None:
    as_c = stability_q(Fraction(1), I_CHORD, Fraction(1), equave=OCTAVE)
    as_g = stability_q(Fraction(1), I_CHORD, Fraction(3, 2), equave=OCTAVE)
    assert as_c > as_g


def test_stability_q_is_a_bounded_integer() -> None:
    for root, chord in (
        (Fraction(1), I_CHORD),
        (Fraction(3, 2), V7_CHORD),
        (Fraction(4, 3), [Fraction(1), Fraction(5, 4), Fraction(3, 2)]),
    ):
        value = stability_q(root, chord, Fraction(1), equave=OCTAVE)
        assert isinstance(value, int)
        assert 0 <= value <= 10000


def test_threshold_classification() -> None:
    assert classify_threshold(9000, DEFAULT_THRESHOLDS) == "tonic"
    assert classify_threshold(2000, DEFAULT_THRESHOLDS) == "dominant"
    assert classify_threshold(5000, DEFAULT_THRESHOLDS) == "subdominant"
    with pytest.raises(ValueError):
        ClassificationThresholds(T_high=1000, D_low=2000)


def test_context_aware_classification_flags_mismatch() -> None:
    # A V7 has a low stability (threshold says subdominant) but its root sits
    # at the dominant position: the contextual label must be ambiguous, with
    # an explanation, not silently relabeled.
    result = classify_with_context(
        Fraction(3, 2), V7_CHORD, Fraction(1), equave=OCTAVE
    )
    assert result["candidate"] == "subdominant"
    assert result["final"] == "ambiguous"
    assert result["reasons"]


def test_context_aware_classification_confirms_the_tonic() -> None:
    result = classify_with_context(Fraction(1), I_CHORD, Fraction(1), equave=OCTAVE)
    assert result["candidate"] == "tonic"
    assert result["final"] == "tonic"
    assert result["reasons"] == []


def test_profile_is_versioned_and_sealable() -> None:
    payload = DEFAULT_PROFILE.as_dict()
    assert payload["version"] == "1.0.0"
    assert sum(payload["weights"]) == pytest.approx(1.0)
    assert DEFAULT_THRESHOLDS.as_dict()["D_low"] < DEFAULT_THRESHOLDS.as_dict()["T_high"]


def test_tritave_equave_stability() -> None:
    value = stability_q(Fraction(1), I_CHORD, Fraction(1), equave=TRITAVE)
    assert 0 <= value <= 10000


# ----------------------------------------------------------------- cadence


@pytest.fixture(scope="module")
def octave_dictionaries() -> dict:
    """A reduced-budget build keeps the test suite fast; the gate under test
    is the generator, not the dictionary's exhaustiveness."""
    policy = DictionaryPolicy(max_tuples_examined=2000)
    dictionaries = {}
    for generator in AXES_BY_EQUAVE["2/1"]:
        for voice_count in (3, 4):
            dictionaries[(generator, voice_count)] = build_axis_dictionary(
                OCTAVE, generator, voice_count, policy=policy
            )
    return dictionaries


def test_authentic_cadence_lands_on_the_tonic(octave_dictionaries) -> None:
    result = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="authentic", dictionaries=octave_dictionaries, seed=7
    )
    assert result["code"] == "OK"
    functions = [chord["function"] for chord in result["chords"]]
    assert functions == ["T", "D", "T"]
    diagnostics = result["diagnostics"]
    assert diagnostics["final_landing"]["lands"] is True
    assert len(diagnostics["stability_contour"]) == 3
    # The stability contour must dip at the dominant and recover at the end.
    contour = diagnostics["stability_contour"]
    assert contour[1] < contour[0]
    assert contour[2] > contour[1]


def test_plagal_cadence_has_four_chords(octave_dictionaries) -> None:
    result = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="plagal", dictionaries=octave_dictionaries, seed=1
    )
    assert result["code"] == "OK"
    functions = [chord["function"] for chord in result["chords"]]
    assert functions == ["T", "S", "D", "T"]
    assert result["diagnostics"]["final_landing"]["lands"] is True


def test_open_cadence_ends_on_the_dominant(octave_dictionaries) -> None:
    result = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="open", dictionaries=octave_dictionaries, seed=3
    )
    assert result["code"] == "OK"
    assert result["chords"][-1]["function"] == "D"
    assert result["diagnostics"]["final_landing"]["lands"] is True


def test_lattice_cadence_is_two_to_four_chords(octave_dictionaries) -> None:
    result = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="lattice", dictionaries=octave_dictionaries, seed=11
    )
    assert result["code"] == "OK"
    assert 2 <= len(result["chords"]) <= 4
    assert result["chords"][-1]["function"] == "T"


def test_cadence_is_deterministic_per_seed(octave_dictionaries) -> None:
    first = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="authentic", dictionaries=octave_dictionaries, seed=42
    )
    second = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="authentic", dictionaries=octave_dictionaries, seed=42
    )
    assert first == second


def test_empty_dictionary_fails_with_no_path(octave_dictionaries) -> None:
    result = generate_cadence(
        Fraction(1), equave=OCTAVE, kind="authentic", dictionaries={}, seed=0
    )
    assert result["code"] == PROGRESSION_NO_PATH
    assert result["failure_reason"] is not None
    assert "diagnostics" not in result


def test_unknown_kind_is_rejected(octave_dictionaries) -> None:
    with pytest.raises(ValueError):
        generate_cadence(Fraction(1), equave=OCTAVE, kind="deceptive", dictionaries=octave_dictionaries)


def test_classification_report_shape(octave_dictionaries) -> None:
    cadences = [
        generate_cadence(
            Fraction(1), equave=OCTAVE, kind=kind, dictionaries=octave_dictionaries, seed=seed
        )
        for kind in ("authentic", "plagal", "open")
        for seed in (0, 1)
    ]
    report = build_classification_report(cadences)
    assert report["chord_count"] > 0
    assert 0.0 <= report["coverage"] <= 1.0
    matrix = report["confusion_matrix"]
    assert set(matrix) == {"tonic", "dominant", "subdominant"}
    for row in matrix.values():
        assert set(row) == {"tonic", "dominant", "subdominant", "ambiguous"}
    # Every generated chord lands in exactly one column.
    total = sum(sum(row.values()) for row in matrix.values())
    assert total == report["chord_count"]
