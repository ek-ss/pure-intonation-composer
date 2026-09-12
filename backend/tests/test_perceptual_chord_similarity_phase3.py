"""Synthetic Phase 3 extractor and soft chord-similarity tests."""

from __future__ import annotations

import copy

from app.songprogram import perceptual
from test_perceptual_interpretation_phase1 import _manifest, _note, _project
from test_perceptual_segmentation_phase2 import _policy


def _distribution(ordinals: list[int]) -> list[dict[str, int]]:
    raw = [1 if index in ordinals else 0 for index in range(12)]
    values = perceptual._normalize(raw, perceptual.Q31_TOTAL)
    return [
        {"pitch_class_ordinal": index, "weight_q31": value}
        for index, value in enumerate(values)
        if value
    ]


def _interval(pitch_rows: list[dict[str, int]]) -> list[dict[str, int]]:
    pitch = perceptual._expand_distribution(pitch_rows)
    raw = [
        sum(pitch[index] * pitch[(index + offset) % 12] for index in range(12))
        for offset in range(12)
    ]
    values = perceptual._normalize(raw, perceptual.Q31_TOTAL)
    return [
        {"pitch_class_ordinal": index, "weight_q31": value}
        for index, value in enumerate(values)
        if value
    ]


def _assets(policy: dict, *, margin: int = 0) -> tuple[dict, dict, dict]:
    spec = {
        "schema": "cps.perceptual-chord-feature-spec",
        "schema_version": "1.0.0",
        "algorithm": "pil-chord-features-12pc/v1",
        "feature_spec_schema_hash": perceptual.CHORD_FEATURE_SPEC_SCHEMA_HASH,
        "feature_record_schema_hash": perceptual.CHORD_FEATURE_RECORD_SCHEMA_HASH,
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "segmentation_policy_hash": policy["policy_hash"],
        "pitch_distribution_algorithm": "soft-event-mapping-weighted-q31/v1",
        "interval_distribution_algorithm": "circular-ordered-autocorrelation-q31/v1",
        "bass_relative_algorithm": "soft-bass-circular-correlation-q31/v1",
        "register_profile_algorithm": "segment-event-weighted-absolute-millicents/v1",
        "common_tone_algorithm": "histogram-intersection-q10000/v1",
        "similarity": {
            "algorithm": "weighted-normalized-l1-q10000/v1",
            "pitch_weight": 5000,
            "interval_weight": 3000,
            "bass_relative_weight": 2000,
            "confidence_floor_q": 0,
            "winner_margin_floor_q": margin,
            "maximum_candidates": 8,
        },
    }
    spec["spec_hash"] = perceptual.chord_feature_spec_hash(spec)
    entries = []
    for ordinal, (entry_id, members) in enumerate((("major", [0, 4, 7]), ("minor", [0, 3, 7]))):
        pitch = _distribution(members)
        entries.append(
            {
                "id": entry_id,
                "ordinal": ordinal,
                "pitch_distribution_q31": pitch,
                "interval_distribution_q31": _interval(pitch),
                "bass_relative_distribution_q31": pitch,
            }
        )
    vocabulary = {
        "schema": "cps.perceptual-chord-vocabulary",
        "schema_version": "1.0.0",
        "algorithm": "pil-chord-vocabulary-q31/v1",
        "vocabulary_schema_hash": perceptual.CHORD_VOCABULARY_SCHEMA_HASH,
        "interpretation_period": "2/1",
        "feature_spec_hash": spec["spec_hash"],
        "entries": entries,
    }
    vocabulary["vocabulary_hash"] = perceptual.chord_vocabulary_hash(vocabulary)
    manifest = _manifest()
    manifest["segmentation_policy_hash"] = policy["policy_hash"]
    manifest["feature_spec_hash"] = spec["spec_hash"]
    manifest["vocabulary_hash"] = vocabulary["vocabulary_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return spec, vocabulary, manifest


def _major_project() -> dict:
    events = []
    for event_id, ratio in (("ev_root", "1/1"), ("ev_third", "5/4"), ("ev_fifth", "3/2")):
        events.append({**_note(event_id, ratio), "velocity": 100})
    project = _project(events)
    project["clock"] = {"ticks_per_beat": 480, "total_ticks": 480}
    project["tracks"] = [{"id": "harmony", "role": "harmony"}]
    return project


def test_ji_major_is_softly_interpreted_as_major() -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy)
    report = perceptual.run_perceptual_interpretation(
        _major_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert report["status"] == "success"
    assert report["completed_phase"] == "chord_similarity"
    assert len(report["feature_records"]) == len(report["segment_interpretations"]) == 1
    interpretation = report["segment_interpretations"][0]
    assert interpretation["candidates"][0]["id"] == "major"
    assert interpretation["best_label"] == "major"
    assert interpretation["feature_record_hash"] == report["feature_records"][0]["record_hash"]


def test_margin_can_keep_candidates_while_best_label_is_null() -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy, margin=10_000)
    report = perceptual.run_perceptual_interpretation(
        _major_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    interpretation = report["segment_interpretations"][0]
    assert len(interpretation["candidates"]) == 2
    assert interpretation["best_label"] is None


def test_feature_failure_precedes_vocabulary_failure() -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy)
    bad_spec = copy.deepcopy(spec)
    bad_spec["interval_distribution_algorithm"] = "invented"
    bad_vocabulary = copy.deepcopy(vocabulary)
    bad_vocabulary["entries"] = []
    report = perceptual.run_perceptual_interpretation(
        _major_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=bad_spec,
        chord_vocabulary=bad_vocabulary,
    )
    assert report["error"] == "PIL_FEATURE_EXTRACTION_FAILED"


def test_missing_bass_removes_component_instead_of_scoring_zero() -> None:
    policy = _policy(
        grid_divisions_per_beat=1,
        minimum_segment_ticks=480,
        bass_role_order=["bass"],
    )
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy)
    report = perceptual.run_perceptual_interpretation(
        _major_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert report["status"] == "success"
    assert report["segments"][0]["bass_event_id"] is None
    assert report["feature_records"][0]["bass_relative_distribution_q31"] is None
    assert report["segment_interpretations"][0]["candidates"]


def test_invalid_vocabulary_is_a_failed_report() -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy)
    vocabulary["entries"][1]["ordinal"] = 0
    vocabulary["vocabulary_hash"] = perceptual.chord_vocabulary_hash(vocabulary)
    manifest["vocabulary_hash"] = vocabulary["vocabulary_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    report = perceptual.run_perceptual_interpretation(
        _major_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert report["error"] == "PIL_VOCABULARY_FAILED"


def test_phase3_cache_cannot_alias_phase2(tmp_path) -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    spec, vocabulary, manifest = _assets(policy)
    project = _major_project()
    phase2 = perceptual.run_perceptual_interpretation(
        project, manifest, cache_dir=tmp_path, segmentation_policy=policy
    )
    phase3 = perceptual.run_perceptual_interpretation(
        project,
        manifest,
        cache_dir=tmp_path,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert phase2["completed_phase"] == "harmonic_segmentation"
    assert phase3["completed_phase"] == "chord_similarity"
    assert len(list(tmp_path.iterdir())) == 2
