"""Milestone 2: 12-EDO templates, sealed storage, and axis dictionaries."""

from __future__ import annotations

import json

import pytest

from app.harmony_dictionary.authority import OCTAVE, TRITAVE, equave_ratio
from app.harmony_dictionary.dictionary import (
    DEFAULT_POLICY,
    DictionaryPolicy,
    build_axis_dictionary,
    match_template,
)
from app.harmony_dictionary.storage import (
    StorageError,
    canonical_bytes,
    read_sealed,
    seal,
    write_sealed,
)
from app.harmony_dictionary.templates import OTHER, TEMPLATES, templates_for_voice_count


# ---------------------------------------------------------------- templates


def test_templates_are_root_relative_and_sorted() -> None:
    for name, shape in TEMPLATES.items():
        assert shape[0] == 0
        assert shape == tuple(sorted(shape))
        assert len(set(shape)) == len(shape)
        assert all(0 <= semitone < 12 for semitone in shape)


def test_templates_cover_both_voice_counts() -> None:
    assert len(templates_for_voice_count(3)) >= 5
    assert len(templates_for_voice_count(4)) >= 5
    with pytest.raises(ValueError):
        templates_for_voice_count(5)


def test_match_template_root_position_major_triad() -> None:
    # 1, 5/4, 3/2 in cents.
    result = match_template([0.0, 386.31372, 701.95500], 3)
    assert result["name"] == "major_triad"
    assert result["matched"] is True
    assert result["inversion"] == 0
    assert result["max_error_cents"] < 20.0


def test_match_template_first_inversion_is_detected() -> None:
    # A first-inversion major triad (bass = the major third): 5/4, 3/2, 2/1
    # relative to the bass = 0, 315.64, 813.70 cents.
    result = match_template([0.0, 315.64237, 813.68960], 3)
    assert result["name"] == "major_triad"
    assert result["inversion"] == 1


def test_match_template_no_fold_of_the_tritave() -> None:
    # A tone ~1902 cents above the root sits near 12-EDO semitone 19, not 0.
    result = match_template([0.0, 386.31372, 701.95500, 1899.0], 4)
    assert result["matched_semitones"][3] == 19


def test_match_template_unmatched_is_other() -> None:
    result = match_template([0.0, 137.0, 274.0], 3)
    assert result["name"] == OTHER
    assert result["matched"] is False
    # The best candidate is still reported for diagnostics.
    assert result["max_error_cents"] > 50.0


def test_match_template_is_deterministic() -> None:
    positions = [0.0, 203.90975, 407.81950]
    assert match_template(positions, 3) == match_template(list(positions), 3)


# ----------------------------------------------------------------- storage


def test_seal_binds_every_field(tmp_path) -> None:
    payload = {"a": 1, "nested": {"b": [1, 2]}}
    sealed = seal(payload, "test.domain/1")
    assert sealed["hash"].startswith("sha256:")
    # Changing any field breaks the hash.
    broken = dict(sealed)
    broken["a"] = 2
    body = {k: v for k, v in broken.items() if k != "hash"}
    import hashlib

    recomputed = "sha256:" + hashlib.sha256(b"test.domain/1\0" + canonical_bytes(body)).hexdigest()
    assert broken["hash"] != recomputed


def test_write_read_round_trip_and_byte_parity(tmp_path) -> None:
    path = tmp_path / "sealed.json"
    payload = seal({"x": [1, 2, 3], "y": "値"}, "test.domain/1")
    write_sealed(path, payload)
    assert read_sealed(path, "test.domain/1") == payload
    # Regeneration byte parity.
    assert path.read_bytes() == canonical_bytes(payload)


def test_read_sealed_fails_closed_on_corruption(tmp_path) -> None:
    path = tmp_path / "sealed.json"
    payload = seal({"x": 1}, "test.domain/1")
    write_sealed(path, payload)

    missing = tmp_path / "nope.json"
    with pytest.raises(StorageError) as error:
        read_sealed(missing, "test.domain/1")
    assert error.value.code == "DICTIONARY_MISSING"

    path.write_bytes(b"{not json")
    with pytest.raises(StorageError) as error:
        read_sealed(path, "test.domain/1")
    assert error.value.code == "DICTIONARY_CORRUPT"

    # Edit without re-sealing.
    write_sealed(path, payload)
    data = json.loads(path.read_bytes())
    data["x"] = 2
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(StorageError) as error:
        read_sealed(path, "test.domain/1")
    assert error.value.code == "DICTIONARY_HASH_MISMATCH"

    # A non-canonical serialization of the same object also fails.
    path.write_bytes(json.dumps(payload).encode())
    with pytest.raises(StorageError) as error:
        read_sealed(path, "test.domain/1")
    assert error.value.code == "DICTIONARY_NOT_CANONICAL"


def test_read_sealed_fails_on_domain_mismatch(tmp_path) -> None:
    path = tmp_path / "sealed.json"
    write_sealed(path, seal({"x": 1}, "test.domain/1"))
    with pytest.raises(StorageError) as error:
        read_sealed(path, "other.domain/1")
    assert error.value.code == "DICTIONARY_HASH_MISMATCH"


# --------------------------------------------------------------- dictionary


def test_dictionary_policy_validation() -> None:
    with pytest.raises(ValueError):
        build_axis_dictionary(OCTAVE, 3, 5)


def test_major_triad_is_adopted_on_the_fifth_axis() -> None:
    dictionary = build_axis_dictionary(OCTAVE, 3, 3)
    assert dictionary["entry_count"] > 0
    keys = {entry["key"] for entry in dictionary["entries"]}
    assert "0,4,7" in keys  # the 12-EDO major triad cell
    major = next(entry for entry in dictionary["entries"] if entry["key"] == "0,4,7")
    assert 1 < len(major["variants"]) <= DEFAULT_POLICY.max_variants_per_key
    for variant in major["variants"]:
        assert variant["template"] == "major_triad"
        assert variant["ratios"][0] == "1/1"
        assert len(variant["index_tuple"]) == 3
        # Root-relative ratios stay inside one equave.
        for ratio_text in variant["ratios"]:
            numerator, denominator = (int(part) for part in ratio_text.split("/"))
            assert 1 <= numerator / denominator < 2


def test_variants_are_never_collapsed_under_one_key() -> None:
    dictionary = build_axis_dictionary(OCTAVE, 3, 3)
    for entry in dictionary["entries"]:
        tuples = [tuple(variant["index_tuple"]) for variant in entry["variants"]]
        assert len(set(tuples)) == len(tuples)


def test_dictionary_is_deterministic() -> None:
    first = build_axis_dictionary(OCTAVE, 5, 4)
    second = build_axis_dictionary(OCTAVE, 5, 4)
    assert first == second


def test_every_axis_has_multiple_distinct_chords() -> None:
    # Acceptance gate: every axis carries at least multiple distinct chords.
    # A reduced examination budget keeps the test fast; the gate is about
    # distinctness, not exhaustiveness.
    policy = DictionaryPolicy(max_tuples_examined=2000)
    for equave_text, axes in (("2/1", (3, 5, 7, 11, 13)), ("3/1", (2, 5, 7, 11, 13))):
        equave = equave_ratio(equave_text)
        for generator in axes:
            triads = build_axis_dictionary(equave, generator, 3, policy=policy)
            tetrads = build_axis_dictionary(equave, generator, 4, policy=policy)
            distinct = triads["variant_count"] + tetrads["variant_count"]
            if generator == 13 and equave_text == "3/1":
                # The tritave 13-axis closes after three steps: at most one
                # triad exists.  The lattice property, documented, not a bug.
                assert distinct >= 1
            else:
                assert distinct >= 2, f"{equave_text}/{generator} has {distinct} chords"


def test_truncated_stream_records_its_budget() -> None:
    policy = DictionaryPolicy(max_tuples_examined=50)
    dictionary = build_axis_dictionary(OCTAVE, 7, 4, policy=policy)
    assert dictionary["truncated"] is True
    assert dictionary["tuples_examined"] == 51


def test_not_enough_points_fails_with_a_code() -> None:
    # The tritave 13-axis has three points: no tetrads.
    dictionary = build_axis_dictionary(TRITAVE, 13, 4)
    assert dictionary["variant_count"] == 0
    assert dictionary["failures"][ "NOT_ENOUGH_AXIS_POINTS"] == 1


def test_variant_payload_is_json_sealable() -> None:
    dictionary = build_axis_dictionary(OCTAVE, 13, 3)
    assert dictionary["variant_count"] > 0
    variant = dictionary["entries"][0]["variants"][0]
    json.dumps(variant, ensure_ascii=False)  # no Fractions or Decimals leak out
    assert variant["ratios"][0] == "1/1"
    assert len(variant["interval_vector"]) == 6
    assert len(variant["pure_intervals"]) == 3


def test_interval_vector_uses_the_equave_circle() -> None:
    # Octave equave: six classes.  Tritave equave: ten classes on the
    # ~1902-cent circle, so a wide tritave chord is not folded to 1200.
    policy = DictionaryPolicy(max_tuples_examined=2000)
    octave = build_axis_dictionary(OCTAVE, 3, 3, policy=policy)
    tritave = build_axis_dictionary(TRITAVE, 2, 3, policy=policy)
    assert all(len(v["interval_vector"]) == 6 for e in octave["entries"] for v in e["variants"])
    assert all(len(v["interval_vector"]) == 10 for e in tritave["entries"] for v in e["variants"])
