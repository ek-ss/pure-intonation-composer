"""Tests for the versioned experimental style profiles (piano v3 cadence).

Covers the fail-closed validation and hash of a style profile, the
clone-on-write application to a SongProgram, the clearly-contrasting built-in
profiles, and the float-free canonical encoding.  The full generation path
(styled rendering features, default stability) is covered in
``test_piano_v3_cadence_generation.py``; the cluster provenance separation is
covered in ``test_cluster_piano_v3_cadence.py``.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.songprogram.style_profile import (
    STYLE_PROFILES,
    StyleProfileError,
    apply_style_profile,
    build_style_profile,
    load_style_profile,
    style_profile_hash,
    validate_style_profile,
)


def _profile() -> dict:
    """A fresh copy of the restrained built-in profile (for tampering)."""
    return copy.deepcopy(STYLE_PROFILES["restrained"])


def _test_program() -> dict:
    """A minimal v3-like SongProgram for the apply tests."""
    return {
        "clock": {"beats_per_bar": 4, "tempo_milli_bpm": 120_000, "ticks_per_beat": 480},
        "tracks": [
            {"id": "harmony", "role": "harmony"},
            {"id": "melody", "role": "melody"},
        ],
        "materials": [
            {"id": "rhy_harmony", "kind": "rhythm_cell", "length_ticks": 1920,
             "steps": [{"at_tick": 0, "duration_ticks": 1920,
                        "accent_q": 10_000, "lane_id": None}]},
            {"id": "rhy_melody", "kind": "rhythm_cell", "length_ticks": 1920,
             "steps": [{"at_tick": 0, "duration_ticks": 240,
                        "accent_q": 8_000, "lane_id": None}]},
            {"id": "melody_a", "kind": "melody_intent", "rhythm_id": "rhy_melody",
             "mapping": "zip", "points": [0, 1, 2]},
            {"id": "cell_0", "kind": "harmony_intent_cell", "rhythm_id": "rhy_harmony",
             "mapping": "zip", "root_anchors": [[0, 0, 0, 0, 0]],
             "anchor_equave_exponent": 0, "chord_intent_ids": ["ci_0"]},
        ],
        "realizations": [
            {"id": "real_h", "track_id": "harmony", "material_id": "cell_0",
             "velocity_scale_q": 10_000, "gate_scale_q": 10_000},
            {"id": "real_m", "track_id": "melody", "material_id": "melody_a",
             "velocity_scale_q": 10_000, "gate_scale_q": 10_000},
        ],
        "chord_intents": [
            {"id": "ci_0", "dictionary_variant": {"variant_hash": "sha256:abc"}},
        ],
    }


# --- built-in profiles -------------------------------------------------------

def test_builtin_profiles_validate_and_are_contrasting() -> None:
    assert set(STYLE_PROFILES) == {"restrained", "driving"}
    for profile in STYLE_PROFILES.values():
        validate_style_profile(profile)
    restrained = STYLE_PROFILES["restrained"]
    driving = STYLE_PROFILES["driving"]
    # Clearly contrasting: different tempo, dynamics, and rhythm density.
    assert restrained["tempo_milli_bpm"] < driving["tempo_milli_bpm"]
    assert (restrained["harmony"]["velocity_scale_q"]
            < driving["harmony"]["velocity_scale_q"])
    assert (len(restrained["harmony"]["rhythm"]["steps"])
            < len(driving["harmony"]["rhythm"]["steps"]))
    # Distinct provenance hashes.
    assert style_profile_hash(restrained) != style_profile_hash(driving)


def test_builtin_profiles_are_float_free() -> None:
    def has_float(value):
        if isinstance(value, float):
            return True
        if isinstance(value, dict):
            return any(has_float(key) or has_float(item) for key, item in value.items())
        if isinstance(value, list):
            return any(has_float(item) for item in value)
        return False

    for profile in STYLE_PROFILES.values():
        assert not has_float(profile)


# --- hash --------------------------------------------------------------------

def test_hash_is_deterministic_and_tamper_sensitive() -> None:
    profile = _profile()
    first = style_profile_hash(profile)
    assert first == style_profile_hash(copy.deepcopy(profile))
    assert first.startswith("sha256:")
    tampered = copy.deepcopy(profile)
    tampered["tempo_milli_bpm"] += 1
    assert style_profile_hash(tampered) != first


def test_hash_excludes_the_profile_hash_field() -> None:
    profile = _profile()
    body = {key: value for key, value in profile.items() if key != "profile_hash"}
    assert style_profile_hash(profile) == style_profile_hash(body)


# --- validation (fail closed) ------------------------------------------------

def test_validation_rejects_wrong_schema() -> None:
    profile = _profile()
    profile["schema"] = "cps.other"
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_SCHEMA_INVALID"


def test_validation_rejects_wrong_version() -> None:
    profile = _profile()
    profile["schema_version"] = "9.9.9"
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_VERSION_UNSUPPORTED"


def test_validation_rejects_missing_or_extra_fields() -> None:
    profile = _profile()
    del profile["tempo_milli_bpm"]
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_FIELDS_INVALID"
    profile = _profile()
    profile["extra"] = 1
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_FIELDS_INVALID"


def test_validation_rejects_out_of_range_tempo() -> None:
    profile = _profile()
    profile["tempo_milli_bpm"] = 10_000  # below the 30_000 floor
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_TEMPO_INVALID"


def test_validation_rejects_out_of_range_velocity() -> None:
    profile = _profile()
    profile["harmony"]["velocity_scale_q"] = 10_001  # above the 10_000 ceiling
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_VELOCITY_INVALID"


def test_validation_rejects_zero_gate() -> None:
    profile = _profile()
    profile["melody"]["gate_scale_q"] = 0  # below the 1 floor
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_GATE_INVALID"


def test_validation_rejects_bad_rhythm_mapping() -> None:
    profile = _profile()
    profile["harmony"]["rhythm"]["mapping"] = "shuffle"
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_RHYTHM_MAPPING_INVALID"


def test_validation_rejects_empty_rhythm_steps() -> None:
    profile = _profile()
    profile["melody"]["rhythm"]["steps"] = []
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_STEPS_INVALID"


def test_validation_rejects_float_cap() -> None:
    profile = _profile()
    profile["cadence"]["voice_leading_cap_millicents"] = 250.0  # float, not int
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_CADENCE_CAP_INVALID"


def test_validation_rejects_out_of_range_cap() -> None:
    profile = _profile()
    profile["cadence"]["voice_leading_cap_millicents"] = 1_200_001
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_CADENCE_CAP_INVALID"


def test_validation_rejects_zero_cap() -> None:
    profile = _profile()
    profile["cadence"]["voice_leading_cap_millicents"] = 0  # must be strictly positive
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_CADENCE_CAP_INVALID"


def test_validation_rejects_out_of_range_budget() -> None:
    profile = _profile()
    profile["cadence"]["candidate_budget"] = 0
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_CADENCE_BUDGET_INVALID"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("two_zip_chords", "STYLE_PROFILE_HARMONY_ZIP_STEPS_INVALID"),
        ("overlapping_chords", "STYLE_PROFILE_HARMONY_OVERLAP"),
        ("melody_outside_chord", "STYLE_PROFILE_MELODY_OUTSIDE_HARMONY"),
        ("too_many_melody_steps", "STYLE_PROFILE_MELODY_STEPS_INVALID"),
    ],
)
def test_cross_field_profile_conflicts_fail_before_generation(change: str, code: str) -> None:
    profile = _profile()
    if change == "two_zip_chords":
        profile["harmony"]["rhythm"]["steps"].append(
            {"at_tick": 960, "duration_ticks": 480, "accent_q": 4000}
        )
    elif change == "overlapping_chords":
        profile["harmony"]["rhythm"]["mapping"] = "cycle"
        profile["harmony"]["rhythm"]["steps"].append(
            {"at_tick": 960, "duration_ticks": 960, "accent_q": 4000}
        )
    elif change == "melody_outside_chord":
        profile["melody"]["rhythm"]["steps"][0]["duration_ticks"] = 2400
    else:
        profile["melody"]["rhythm"]["steps"].append(
            {"at_tick": 1600, "duration_ticks": 160, "accent_q": 4000}
        )
    profile["profile_hash"] = style_profile_hash(profile)
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == code


def test_validation_rejects_tampered_hash() -> None:
    profile = _profile()
    profile["tempo_milli_bpm"] += 1  # body changed, hash stale
    with pytest.raises(StyleProfileError) as error:
        validate_style_profile(profile)
    assert error.value.code == "STYLE_PROFILE_HASH_MISMATCH"


def test_build_style_profile_stamps_a_valid_hash() -> None:
    profile = build_style_profile(
        "test/v1", tempo_milli_bpm=100_000,
        harmony_velocity_scale_q=5_000, harmony_gate_scale_q=8_000,
        harmony_mapping="zip",
        harmony_steps=[{"at_tick": 0, "duration_ticks": 1920, "accent_q": 5_000}],
        melody_velocity_scale_q=6_000, melody_gate_scale_q=8_000,
        melody_steps=[{"at_tick": 0, "duration_ticks": 640, "accent_q": 5_000}],
        voice_leading_cap_millicents=300_000, candidate_budget=8,
    )
    validate_style_profile(profile)
    assert profile["profile_hash"] == style_profile_hash(profile)


# --- apply (clone-on-write) --------------------------------------------------

def test_apply_is_clone_on_write() -> None:
    program = _test_program()
    snapshot = copy.deepcopy(program)
    apply_style_profile(program, STYLE_PROFILES["driving"])
    assert program == snapshot  # the input is not mutated


def test_apply_changes_tempo_velocity_gate_rhythm_and_mapping() -> None:
    program = _test_program()
    result = apply_style_profile(program, STYLE_PROFILES["driving"])
    profile = STYLE_PROFILES["driving"]
    # Clock tempo.
    assert result["clock"]["tempo_milli_bpm"] == profile["tempo_milli_bpm"]
    # Per-role velocity / gate on the realizations.
    by_track = {realization["track_id"]: realization for realization in result["realizations"]}
    assert by_track["harmony"]["velocity_scale_q"] == profile["harmony"]["velocity_scale_q"]
    assert by_track["harmony"]["gate_scale_q"] == profile["harmony"]["gate_scale_q"]
    assert by_track["melody"]["velocity_scale_q"] == profile["melody"]["velocity_scale_q"]
    assert by_track["melody"]["gate_scale_q"] == profile["melody"]["gate_scale_q"]
    # Per-role rhythm steps (with the structural lane_id injected).
    materials = {material["id"]: material for material in result["materials"]}
    assert materials["rhy_harmony"]["steps"] == [
        {"at_tick": step["at_tick"], "duration_ticks": step["duration_ticks"],
         "accent_q": step["accent_q"], "lane_id": None}
        for step in profile["harmony"]["rhythm"]["steps"]
    ]
    assert materials["rhy_melody"]["steps"] == [
        {"at_tick": step["at_tick"], "duration_ticks": step["duration_ticks"],
         "accent_q": step["accent_q"], "lane_id": None}
        for step in profile["melody"]["rhythm"]["steps"]
    ]
    # Harmony mapping.
    assert materials["cell_0"]["mapping"] == profile["harmony"]["rhythm"]["mapping"]


def test_apply_leaves_the_sealed_dictionary_binding_untouched() -> None:
    program = _test_program()
    result = apply_style_profile(program, STYLE_PROFILES["driving"])
    # The chord intent's sealed-dictionary binding is unchanged.
    assert result["chord_intents"] == program["chord_intents"]
    # The harmony cell's chord binding (which variant it realizes) is unchanged.
    source = next(m for m in program["materials"] if m["id"] == "cell_0")
    applied = next(m for m in result["materials"] if m["id"] == "cell_0")
    assert applied["chord_intent_ids"] == source["chord_intent_ids"]
    assert applied["root_anchors"] == source["root_anchors"]
    assert applied["anchor_equave_exponent"] == source["anchor_equave_exponent"]


def test_apply_rejects_an_invalid_profile() -> None:
    program = _test_program()
    profile = _profile()
    profile["tempo_milli_bpm"] += 1  # stale hash
    with pytest.raises(StyleProfileError):
        apply_style_profile(program, profile)


def test_load_style_profile_round_trips(tmp_path) -> None:
    profile = STYLE_PROFILES["driving"]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    loaded = load_style_profile(path)
    assert loaded == profile
    validate_style_profile(loaded)


def test_load_style_profile_rejects_tampered_file(tmp_path) -> None:
    profile = copy.deepcopy(STYLE_PROFILES["driving"])
    profile["tempo_milli_bpm"] += 1  # body changed, hash stale
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    with pytest.raises(StyleProfileError):
        load_style_profile(path)
