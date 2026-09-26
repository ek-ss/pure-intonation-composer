"""Milestone 1: equave/generator loop authority and 1D axis index."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.harmony_dictionary.authority import (
    AXES_BY_EQUAVE,
    OCTAVE,
    TRITAVE,
    AuthorityError,
    axes_for_equave,
    axis_index,
    axis_payload,
    equave_ratio,
    loop_steps,
    reduce_on_equave,
    resolve_axis_point,
)

# Reference table from docs/development_plan_5d_chord_cadence_dictionary.md §2.
REFERENCE_LOOPS = {
    ("2/1", 3): (53, 84),
    ("2/1", 5): (59, 137),
    ("2/1", 7): (109, 306),
    ("2/1", 11): (37, 128),
    ("2/1", 13): (10, 37),
    ("3/1", 2): (84, 53),
    ("3/1", 5): (157, 230),
    ("3/1", 7): (153, 271),
    ("3/1", 11): (104, 227),
    ("3/1", 13): (3, 7),
}


@pytest.mark.parametrize("equave_text,generator", sorted(REFERENCE_LOOPS))
def test_reference_loop_table(equave_text: str, generator: int) -> None:
    expected_n, expected_k = REFERENCE_LOOPS[(equave_text, generator)]
    result = loop_steps(equave_ratio(equave_text), generator)
    assert result.found is True
    assert result.code == "OK"
    assert result.n == expected_n
    assert result.k == expected_k
    assert 0 <= result.distance_mc <= 100  # 10 cents = 100 millicents


@pytest.mark.parametrize("equave_text,generator", sorted(REFERENCE_LOOPS))
def test_no_earlier_n_satisfies_the_tolerance(equave_text: str, generator: int) -> None:
    expected_n = REFERENCE_LOOPS[(equave_text, generator)][0]
    result = loop_steps(equave_ratio(equave_text), generator, limit=expected_n - 1)
    assert result.found is False
    assert result.code == "LOOP_NOT_FOUND_WITHIN_LIMIT"
    assert result.n is None and result.k is None and result.distance_mc is None


def test_trivial_loop_when_generator_is_the_equave() -> None:
    result = loop_steps(TRITAVE, 3)
    assert result.found is True
    assert (result.n, result.k, result.distance_mc) == (1, 1, 0)


def test_n_zero_is_excluded_as_trivial() -> None:
    # d_E(0, g) = 0 for every pair; the search must start at n = 1.
    result = loop_steps(OCTAVE, 3)
    assert result.n >= 1


def test_loop_limit_is_a_versioned_boundary() -> None:
    result = loop_steps(OCTAVE, 3, limit=1)
    assert result.code == "LOOP_NOT_FOUND_WITHIN_LIMIT"
    with pytest.raises(AuthorityError):
        loop_steps(OCTAVE, 3, limit=0)


def test_loop_is_reproducible() -> None:
    first = loop_steps(OCTAVE, 7)
    second = loop_steps(OCTAVE, 7)
    assert first == second


def test_axis_validation() -> None:
    with pytest.raises(AuthorityError):
        equave_ratio("1/2")  # inverse belongs to the same class but is not > 1
    with pytest.raises(AuthorityError):
        equave_ratio("abc")
    with pytest.raises(AuthorityError):
        loop_steps(OCTAVE, 1)
    with pytest.raises(AuthorityError):
        axes_for_equave("5/1")


def test_axes_never_contain_the_equave_itself() -> None:
    for text, axes in AXES_BY_EQUAVE.items():
        equave_prime = equave_ratio(text).numerator
        assert equave_prime not in axes
        assert len(axes) == 5


def test_reduce_on_equave_round_trips() -> None:
    for ratio in (Fraction(1), Fraction(3), Fraction(27, 8), Fraction(5, 64), Fraction(13**7)):
        for equave in (OCTAVE, TRITAVE):
            reduced, exponent = reduce_on_equave(ratio, equave)
            assert 1 <= reduced < equave
            assert reduced * equave**exponent == ratio
    with pytest.raises(AuthorityError):
        reduce_on_equave(Fraction(-3), OCTAVE)


@pytest.mark.parametrize("equave_text,generator", sorted(REFERENCE_LOOPS))
def test_axis_index_shape(equave_text: str, generator: int) -> None:
    equave = equave_ratio(equave_text)
    loop, points = axis_index(equave, generator)
    assert len(points) == loop.n
    assert [point.n for point in points] == list(range(loop.n))

    origin = points[0]
    assert origin.original_ratio == Fraction(1)
    assert origin.reduced_ratio == Fraction(1)
    assert (origin.equave_exponent, origin.absolute_cents) == (0, 0.0)
    assert (origin.nearest_12edo_semitone, origin.signed_12edo_error_cents) == (0, 0.0)
    assert origin.reduced_cents == 0.0

    for point in points:
        assert 1 <= point.reduced_ratio < equave
        # 12-EDO rounding happens on the absolute semitone grid.
        assert abs(point.signed_12edo_error_cents) <= 50.0
        assert point.absolute_cents - 100 * point.nearest_12edo_semitone == pytest.approx(
            point.signed_12edo_error_cents, abs=1e-4
        )
        # The equave phase stays inside one equave.
        assert 0.0 <= point.reduced_cents < 1200 * equave.numerator / equave.denominator + 1e-3

    # Distinct n give distinct reduced ratios (g and E are distinct primes).
    assert len({point.reduced_ratio for point in points}) == len(points)


def test_axis_index_fails_closed_when_the_loop_is_missing() -> None:
    with pytest.raises(AuthorityError, match="LOOP_NOT_FOUND_WITHIN_LIMIT"):
        axis_index(OCTAVE, 3, limit=1)


def test_negative_direction_resolves_with_provenance() -> None:
    point, provenance = resolve_axis_point(OCTAVE, 3, -1)
    assert point.n == 52  # 53 - 1
    assert provenance["requested_n"] == -1
    assert provenance["index_n"] == 52
    assert provenance["loop_period"] == 53


def test_axis_payload_is_sealable() -> None:
    payload = axis_payload(OCTAVE, 13)
    assert payload["equave"] == "2/1"
    assert payload["generator"] == 13
    assert payload["loop"]["n"] == 10
    assert len(payload["points"]) == 10
    assert payload["negative_direction"]["offset"] == -10


def test_higher_axes_are_nonzero() -> None:
    # The 11/13 axes must actually move: original ratios carry the prime.
    for equave_text in ("2/1", "3/1"):
        for generator in (11, 13):
            _, points = axis_index(equave_ratio(equave_text), generator)
            assert all(point.original_ratio.numerator % generator == 0 or point.n == 0 for point in points[1:])
