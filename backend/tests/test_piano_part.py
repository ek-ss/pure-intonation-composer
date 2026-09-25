from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.songprogram.piano_part import add_piano_part, piano_samples
from tools.run_composition_generation_cohort import _generate


def _inputs() -> tuple[dict, dict]:
    return ({
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "tracks": [{"id": "trk_harmony", "role": "harmony"}],
        "materials": [], "realizations": [],
        "limits": {"max_tracks": 8, "max_materials": 64, "max_realizations": 512},
        "production": {"tracks": {}},
    }, {"sections": [
        {"section_id": "sec_000", "function": "opening", "bars": 4},
        {"section_id": "sec_001", "function": "statement", "bars": 4},
        {"section_id": "sec_002", "function": "arrival", "bars": 4},
        {"section_id": "sec_003", "function": "closure", "bars": 4},
    ]})


@pytest.mark.parametrize("style, expected", [
    ("ostinato", ["ostinato"] * 4),
    ("obbligato", ["obbligato"] * 4),
    ("mixed", ["ostinato", "obbligato", "obbligato", "ostinato"]),
])
def test_piano_has_independent_track_and_chord_aware_patterns(style: str, expected: list[str]) -> None:
    program, plan = _inputs()
    original = deepcopy(program)
    result = add_piano_part(program, plan, style)
    assert program == original
    assert result == add_piano_part(program, plan, style)
    assert [track["id"] for track in result["tracks"]] == ["trk_harmony", "trk_piano"]
    assert result["tracks"][-1]["instrument_id"] == "trial_piano"
    assert len(result["materials"]) == 4
    assert [row["material_id"].removeprefix("mat_piano_") for row in result["realizations"]] == expected
    assert all(row["repeat"] * row["every_ticks"] == 4 * 1920
               and row["track_id"] == "trk_piano" for row in result["realizations"])
    materials = {row["id"]: row for row in result["materials"]}
    for name in ("ostinato", "obbligato"):
        melody = materials[f"mat_piano_{name}"]
        rhythm = materials[melody["rhythm_id"]]
        assert len(melody["points"]) == len(rhythm["steps"])
        assert {point["relation"] for point in melody["points"]} == {"chord_member"}
        assert all(step["at_tick"] + step["duration_ticks"] <= rhythm["length_ticks"]
                   for step in rhythm["steps"])
    assert all(step["at_tick"] >= 1920 for step in materials["rhy_piano_obbligato"]["steps"])


def test_piano_opt_out_and_limits_fail_closed() -> None:
    program, plan = _inputs()
    assert add_piano_part(program, plan, "none") == program
    with pytest.raises(ValueError, match="PIANO_STYLE_INVALID"):
        add_piano_part(program, plan, "invalid")
    program["limits"]["max_materials"] = 3
    with pytest.raises(ValueError, match="PIANO_PROGRAM_LIMIT_EXCEEDED"):
        add_piano_part(program, plan, "mixed")
    assert len(piano_samples()) == 654


def test_obbligato_rejects_odd_length_section() -> None:
    program, plan = _inputs()
    plan["sections"][1]["bars"] = 3
    with pytest.raises(ValueError, match="PIANO_OBBLIGATO_REQUIRES_EVEN_BARS"):
        add_piano_part(program, plan, "mixed")


def test_cohort_does_not_reuse_a_different_piano_style(tmp_path) -> None:
    directory = tmp_path / "seed-0000"
    directory.mkdir()
    (directory / "receipt.json").write_text(json.dumps({"seed": 0, "piano_style": "none"}))
    result = _generate(0, str(tmp_path), "unused", "unused", "mixed")
    assert result == {"seed": 0, "status": "failed", "error": "GENERATION_RECEIPT_MODE_MISMATCH"}
