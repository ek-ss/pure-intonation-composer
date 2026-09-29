"""An independent 1D coverage contract; no five-axis product is requested."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.harmony_dictionary.authority import AXES_BY_EQUAVE
from app.harmony_dictionary.axis_search import (
    AxisSearchError,
    axis_pitch_at_root,
    axis_reference_coverage,
    build_sparse_axis_chord,
    reference_steps,
)
from app.songprogram.compiler import _mc


@pytest.mark.parametrize("equave,expected", [("2/1", [6, 12, 10, 6, 21]), ("3/1", [9, 12, 10, 29, 96])])
def test_each_axis_covers_absolute_reference_with_exact_pitch(
    equave: str, expected: list[int]
) -> None:
    steps = reference_steps(equave)
    assert len(steps) == (12 if equave == "2/1" else 24)
    for g, radius in zip(AXES_BY_EQUAVE[equave], expected, strict=True):
        report = axis_reference_coverage(equave, g)
        assert report["covered"] and report["first_coverage_radius"] == radius
        assert report["examined_exponents"] == 2 * radius + 1
        assert report["target_steps"] == list(steps)
        for step, point in report["matches"].items():
            assert _mc(Fraction(point["ratio"])) - int(step) * 100_000 == point["signed_error_millicents"]
            assert abs(point["signed_error_millicents"]) <= 50_000


@pytest.mark.parametrize("equave,generator", [("2/1", 13), ("3/1", 13)])
def test_near_loop_does_not_silently_terminate_coverage(equave: str, generator: int) -> None:
    report = axis_reference_coverage(equave, generator)
    assert report["requires_beyond_first_loop"]
    too_short = axis_reference_coverage(equave, generator, radius_limit=report["loop_steps"] - 1)
    assert not too_short["covered"] and too_short["missing_steps"]


def test_tritave_reference_crosses_equave_without_octave_folding() -> None:
    report = axis_reference_coverage("3/1", 13)
    assert report["reference"] == "12-edo-absolute-24/v1"
    assert report["target_steps"][-1] == 23
    assert report["matches"]["19"]["absolute_millicents"] > 1_200_000
    assert "0" in report["matches"] and "12" in report["matches"]
    assert report["matches"]["0"]["absolute_millicents"] != report["matches"]["12"]["absolute_millicents"]


def test_axis_pitch_is_exact_root_plus_one_axis_and_register() -> None:
    result = axis_pitch_at_root("3/1", [1, 0, 0, 2, 0], 4, 1, -1)
    assert result["root_ratio"] == "242/1"  # 2 * 11**2
    assert result["vector"] == [1, 0, 0, 2, 1]
    assert result["exact_ratio"] == "3146/3"


def test_tritave_four_voice_candidate_uses_only_one_axis_and_exact_ratios() -> None:
    chord = build_sparse_axis_chord("3/1", [0, 0, 0, 0, 0], 13, [0, 6, 13, 19])
    assert chord["status"] == "sparse_candidate_not_compiled"
    assert chord["coverage_radius"] == 96 and chord["requires_beyond_first_loop"]
    assert len(chord["voices"]) == 4
    assert chord["root_relative_ratios"][0] == "1/1"
    assert all(voice["vector"][:4] == [0, 0, 0, 0] for voice in chord["voices"])
    assert len({voice["exact_ratio"] for voice in chord["voices"]}) == 4
    # Covering the reference is not equivalent to being admitted by the
    # current v3 lattice filter.  Record the failure instead of claiming that
    # this 13-axis candidate has been compiled into a SongProgram.
    assert not chord["current_lattice_filter"]["passes"]
    assert any(row["reason"] == "ODD_LIMIT_EXCEEDED" for row in chord["current_lattice_filter"]["reasons"])
    for voice in chord["voices"]:
        assert _mc(Fraction(voice["exact_ratio"])) - voice["reference_step"] * 100_000 == voice["signed_error_millicents"]


def test_caps_and_axes_reject_invalid_requests() -> None:
    with pytest.raises(AxisSearchError, match="AXIS_RADIUS_LIMIT_INVALID"):
        axis_reference_coverage("3/1", 13, radius_limit=257)
    with pytest.raises(AxisSearchError, match="AXIS_GENERATOR_UNSUPPORTED"):
        axis_reference_coverage("3/1", 3)
    with pytest.raises(AxisSearchError, match="AXIS_INDEX_INVALID"):
        axis_pitch_at_root("2/1", [0] * 5, 5, 0, 0)


def test_axis_search_api_reports_sparse_candidate_and_rejects_invalid_inputs() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    result = client.post("/api/harmony-dictionary/axis-search", json={
        "equave": "3/1", "generator": 13, "reference_steps": [0, 6, 13, 19],
    })
    assert result.status_code == 200
    body = result.json()
    assert body["coverage"]["first_coverage_radius"] == 96
    assert body["chord"]["status"] == "sparse_candidate_not_compiled"
    assert len(body["chord"]["voices"]) == 4
    assert client.post("/api/harmony-dictionary/axis-search", json={
        "equave": "3/1", "generator": 13, "radius_limit": 3,
        "reference_steps": [0, 6, 13, 19],
    }).status_code == 422
