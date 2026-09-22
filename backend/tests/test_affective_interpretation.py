from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.affective import (
    AffectiveError,
    affective_report_hash,
    evaluate_affective,
)


ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return json.loads(
        (ROOT / "songprogram_conformance/profiles/affective_interpretation_v1.json").read_text()
    )


def _project() -> dict:
    return json.loads(
        (ROOT / "songprogram_conformance/fixtures/compiler/gen0b_melody_project.json").read_text()
    )


def test_affective_report_is_parallel_hash_bound_and_sectioned() -> None:
    report = evaluate_affective(_project(), _manifest())
    assert report["status"] == "success"
    assert report["audio_feature_status"] == "not_evaluated"
    assert report["whole_song"]["timbral_brightness_q"] is None
    assert report["sections"][0]["section_id"] == "sec_a"
    assert report["report_hash"] == affective_report_hash(report)


def test_major_like_third_is_brighter_than_minor_like_third() -> None:
    major = _project()
    minor = copy.deepcopy(major)
    for event in minor["events"]:
        if event["ratio"] == "5/2":
            event["ratio"] = "6/5"
    major_report = evaluate_affective(major, _manifest())
    minor_report = evaluate_affective(minor, _manifest())
    assert major_report["whole_song"]["harmonic_majorness_q"] > 0
    assert minor_report["whole_song"]["harmonic_majorness_q"] < 0
    assert major_report["whole_song"]["perceived_valence_q"] > minor_report["whole_song"]["perceived_valence_q"]


def test_affective_rejects_manifest_substitution_and_silence() -> None:
    manifest = _manifest()
    manifest["template_radius_millicents"] += 1
    with pytest.raises(AffectiveError, match="AFFECTIVE_MANIFEST_INVALID"):
        evaluate_affective(_project(), manifest)
    silent = _project()
    silent["events"] = []
    with pytest.raises(AffectiveError, match="AFFECTIVE_INSUFFICIENT_NOTES"):
        evaluate_affective(silent, _manifest())
