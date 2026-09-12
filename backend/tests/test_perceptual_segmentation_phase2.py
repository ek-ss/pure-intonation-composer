"""Synthetic conformance tests for PIL Phase 2 segmentation."""

from __future__ import annotations

import copy

import pytest

from app.songprogram import perceptual
from test_perceptual_interpretation_phase1 import _manifest, _note, _project


def _policy(**updates: object) -> dict:
    policy = {
        "schema": "cps.perceptual-segmentation-policy",
        "schema_version": "1.0.0",
        "algorithm": "pil-harmonic-segmentation-grid-events/v1",
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "policy_schema_hash": perceptual.SEGMENTATION_POLICY_SCHEMA_HASH,
        "grid_divisions_per_beat": 2,
        "minimum_segment_ticks": 240,
        "sustained_minimum_ticks": 480,
        "pitch_distribution_change_q": 1_000,
        "duration_coefficient_q": 10_000,
        "metrical_coefficient_q": 0,
        "persistence_coefficient_q": 0,
        "bass_coefficient_q": 0,
        "role_gain_q": {"drums": 0, "bass": 10_000, "harmony": 10_000,
                        "melody": 10_000, "texture": 10_000},
        "bass_role_order": ["bass", "harmony", "melody", "texture", "drums"],
        "boundary_priority": list(perceptual.BOUNDARY_PRIORITY),
        "boundary_confidence_q": {"endpoint": 10_000, "bass_change": 9_000,
                                  "sustained_change": 8_000,
                                  "pitch_distribution_change": 7_000,
                                  "metrical": 6_000},
    }
    policy.update(updates)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    return policy


def _bound_manifest(policy: dict) -> dict:
    manifest = _manifest()
    manifest["segmentation_policy_hash"] = policy["policy_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return manifest


def _phase2_project() -> dict:
    first = {**_note("ev_a", "1/1", 0), "velocity": 100}
    second = {**_note("ev_b", "3/2", 480), "track_id": "bass", "velocity": 100}
    project = _project([second, first])
    project["clock"] = {"ticks_per_beat": 480, "total_ticks": 960}
    project["tracks"] = [
        {"id": "harmony", "role": "harmony"},
        {"id": "bass", "role": "bass"},
    ]
    return project


def test_phase2_boundaries_weights_and_ids_are_deterministic() -> None:
    policy = _policy()
    report = perceptual.run_perceptual_interpretation(
        _phase2_project(), _bound_manifest(policy), segmentation_policy=policy
    )
    assert report["completed_phase"] == "harmonic_segmentation"
    assert [(row["start_tick"], row["end_tick"]) for row in report["segments"]] == [
        (0, 240), (240, 480), (480, 720), (720, 960)
    ]
    assert report["segments"][2]["boundary_reasons"] == [
        "bass_change", "sustained_change", "pitch_distribution_change", "metrical"
    ]
    assert report["segments"][2]["confidence_q"] == 9_000
    assert all(sum(item["weight_q31"] for item in row["weighted_pitch_distribution_q31"])
               == perceptual.Q31_TOTAL for row in report["segments"])
    assert all(row["segment_id"].startswith("seg_") and len(row["segment_id"]) == 36
               for row in report["segments"])


def test_global_boundary_merge_preserves_minimum_distance_from_endpoints() -> None:
    policy = _policy(minimum_segment_ticks=300)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    report = perceptual.run_perceptual_interpretation(
        _phase2_project(), _bound_manifest(policy), segmentation_policy=policy
    )
    assert [(row["start_tick"], row["end_tick"]) for row in report["segments"]] == [
        (0, 480), (480, 960)
    ]


def test_policy_hash_mismatch_has_stable_failure() -> None:
    policy = _policy()
    bad = copy.deepcopy(policy)
    bad["minimum_segment_ticks"] = 241
    report = perceptual.run_perceptual_interpretation(
        _phase2_project(), _bound_manifest(policy), segmentation_policy=bad
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_SEGMENTATION_POLICY_INVALID"


def test_phase_cache_entries_cannot_alias(tmp_path) -> None:
    policy = _policy()
    manifest = _bound_manifest(policy)
    project = _phase2_project()
    phase1 = perceptual.run_perceptual_interpretation(project, manifest, cache_dir=tmp_path)
    phase2 = perceptual.run_perceptual_interpretation(
        project, manifest, cache_dir=tmp_path, segmentation_policy=policy
    )
    assert phase1["completed_phase"] == "pitch_projection" and phase1["segments"] == []
    assert phase2["completed_phase"] == "harmonic_segmentation" and phase2["segments"]
    assert len(list(tmp_path.iterdir())) == 2


def test_zero_role_gain_produces_segment_empty_without_touching_project() -> None:
    project = _phase2_project()
    original = copy.deepcopy(project)
    policy = _policy(role_gain_q={role: 0 for role in perceptual.TRACK_ROLES})
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    report = perceptual.run_perceptual_interpretation(
        project, _bound_manifest(policy), segmentation_policy=policy
    )
    assert report["error"] == "PIL_SEGMENT_EMPTY"
    assert project == original


def test_unknown_policy_member_is_rejected() -> None:
    policy = _policy()
    policy["ambient_default"] = 1
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    with pytest.raises(perceptual.PilError, match="PIL_SEGMENTATION_POLICY_INVALID"):
        perceptual.validate_segmentation_policy(policy, _bound_manifest(policy))
