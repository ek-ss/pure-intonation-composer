"""Synthetic Phase 4 operator tests: voice matching, transitions, trajectory.

All assets are synthetic test inputs built in code; no authoritative fixture,
oracle, or golden is created or modified.  The operators are tested directly
because run-level Phase 4 integration is blocked on the undeclared Phase 4
implementation build identity (see completion report).
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from app.songprogram import perceptual
from app.songprogram.perceptual import PilError
from test_perceptual_chord_similarity_phase3 import _assets
from test_perceptual_interpretation_phase1 import _note, _project
from test_perceptual_segmentation_phase2 import _policy


def _two_segment_project() -> dict:
    events = []
    for index, start in ((1, 0), (2, 480)):
        for name, ratio in (("r", "1/1"), ("t", "5/4"), ("f", "3/2")):
            events.append({**_note(f"ev_{name}{index}", ratio, start), "velocity": 100})
        bass_ratio = "1/1" if index == 1 else "3/2"
        events.append(
            {**_note(f"ev_b{index}", bass_ratio, start), "track_id": "bass", "velocity": 100}
        )
    project = _project(events)
    project["clock"] = {"ticks_per_beat": 480, "beats_per_bar": 4, "total_ticks": 960}
    project["tracks"] = [
        {"id": "harmony", "role": "harmony"},
        {"id": "bass", "role": "bass"},
    ]
    return project


def _phase3(policy: dict, project: dict):
    spec, vocabulary, manifest = _assets(policy)
    report = perceptual.run_perceptual_interpretation(
        project,
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert report["status"] == "success"
    return spec, vocabulary, manifest, report


def _vm_policy(spec: dict, manifest: dict, **updates: object) -> dict:
    policy = {
        "schema": "cps.perceptual-voice-matching-policy",
        "schema_version": "1.0.0",
        "algorithm": "pil-injective-voice-matching-dp/v1",
        "policy_schema_hash": perceptual.VOICE_MATCHING_POLICY_SCHEMA_HASH,
        "matching_record_schema_hash": perceptual.VOICE_MATCHING_RECORD_SCHEMA_HASH,
        "feature_spec_hash": spec["spec_hash"],
        "maximum_voices_per_segment": 4,
        "selection_algorithm": "event-weight-desc-absolute-mc-id/v1",
        "identity_constraint": "same-event-id-must-match/v1",
        "interpretation_period_millicents": 1_200_000,
        "half_period_tie": "negative",
        "absolute_motion_cap_millicents": 4_800_000,
        "cost_weights": {
            "absolute_motion": 4_000,
            "circular_motion": 3_000,
            "pitch_mapping_l1": 2_000,
            "role_mismatch": 1_000,
        },
        "bass_likeness_kernels": {
            "fifth_center_millicents": 700_000,
            "fourth_center_millicents": 500_000,
            "step_up_center_millicents": 100_000,
            "step_down_center_millicents": -100_000,
            "radius_millicents": 100_000,
        },
    }
    policy.update(updates)
    policy["policy_hash"] = perceptual.voice_matching_policy_hash(policy)
    manifest["voice_matching_policy_hash"] = policy["policy_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return policy


def _template_set(spec: dict, vocabulary: dict, vm_policy: dict, manifest: dict, **updates) -> dict:
    template_set = {
        "schema": "cps.perceptual-trajectory-template-set",
        "schema_version": "1.0.0",
        "algorithm": "pil-consecutive-trajectory-l1/v1",
        "template_set_schema_hash": perceptual.TRAJECTORY_TEMPLATE_SET_SCHEMA_HASH,
        "transition_record_schema_hash": perceptual.TRANSITION_FEATURE_RECORD_SCHEMA_HASH,
        "trajectory_result_schema_hash": perceptual.TRAJECTORY_RESULT_SCHEMA_HASH,
        "feature_spec_hash": spec["spec_hash"],
        "vocabulary_hash": vocabulary["vocabulary_hash"],
        "voice_matching_policy_hash": vm_policy["policy_hash"],
        "alignment": {
            "algorithm": "all-consecutive-windows/v1",
            "missing_component_policy": "omit-and-renormalize/v1",
            "maximum_results": 16,
        },
        "score_weights": {
            "chord": 4_000,
            "bass": 2_000,
            "common_tone": 1_000,
            "contrary_motion": 500,
            "resolution": 1_000,
            "tension": 500,
            "metrical": 1_000,
        },
        "templates": [
            {
                "id": "major_repeat",
                "ordinal": 0,
                "steps": [
                    {
                        "chord_targets": [
                            {"vocabulary_id": "major", "weight_q31": perceptual.Q31_TOTAL}
                        ]
                    },
                    {
                        "chord_targets": [
                            {"vocabulary_id": "major", "weight_q31": perceptual.Q31_TOTAL}
                        ]
                    },
                ],
                "transitions": [
                    {
                        "bass_motion_center_millicents": -500_000,
                        "bass_motion_radius_millicents": 100_000,
                        "common_tone_target_q": 9_000,
                        "contrary_motion_target_q": 0,
                        "resolution_kind": "step_up",
                        "resolution_target_q": 0,
                        "directed_tension_change_target_q": 0,
                        "metrical_target_q": 7_500,
                    }
                ],
            }
        ],
    }
    template_set.update(updates)
    template_set["template_set_hash"] = perceptual.trajectory_template_set_hash(template_set)
    manifest["trajectory_template_set_hash"] = template_set["template_set_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return template_set


def _phase4_inputs():
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    spec, vocabulary, manifest, report = _phase3(policy, _two_segment_project())
    vm_policy = _vm_policy(spec, manifest)
    template_set = _template_set(spec, vocabulary, vm_policy, manifest)
    return policy, spec, vocabulary, manifest, report, vm_policy, template_set


def test_voice_matching_policy_validation_and_binding() -> None:
    _, spec, _, manifest, _, vm_policy, _ = _phase4_inputs()
    perceptual.validate_voice_matching_policy(vm_policy, manifest, spec)
    tampered = copy.deepcopy(vm_policy)
    tampered["maximum_voices_per_segment"] = 3
    with pytest.raises(PilError, match="PIL_VOICE_MATCHING_FAILED"):
        perceptual.validate_voice_matching_policy(tampered, manifest, spec)
    zero_weights = _vm_policy(
        spec,
        manifest,
        cost_weights={
            "absolute_motion": 0,
            "circular_motion": 0,
            "pitch_mapping_l1": 0,
            "role_mismatch": 0,
        },
    )
    with pytest.raises(PilError, match="PIL_VOICE_MATCHING_FAILED"):
        perceptual.validate_voice_matching_policy(zero_weights, manifest, spec)


def test_match_voices_emits_canonical_record() -> None:
    policy, _, _, _, report, vm_policy, _ = _phase4_inputs()
    records = perceptual.match_voices(
        _two_segment_project(),
        report["pitch_records"],
        report["segments"],
        policy,
        vm_policy,
    )
    assert len(records) == 1
    record = records[0]
    assert record["transition_id"].startswith("trn_")
    assert record["record_hash"] == perceptual.voice_matching_record_hash(record)
    assert len(record["pairs"]) == 4
    pairing = {row["from_event_id"]: row["to_event_id"] for row in record["pairs"]}
    # Role-aware minimum-cost matching pairs each voice with its same-name
    # counterpart (bass with bass, harmony with harmony).
    assert pairing == {
        "ev_b1": "ev_b2",
        "ev_r1": "ev_r2",
        "ev_t1": "ev_t2",
        "ev_f1": "ev_f2",
    }
    key = record["canonical_matching_key"]
    assert key[:3] == [4, 4, 4]
    assert key[11:] == [0, 0]
    assert record["unmatched_from_event_ids"] == record["unmatched_to_event_ids"] == []
    # Harmony voices sustain; the bass moves 1/1 -> 3/2, all motions >= 0.
    motions = {row["from_event_id"]: row["absolute_motion_millicents"] for row in record["pairs"]}
    assert motions["ev_b1"] == 701_955
    assert all(motions[name] == 0 for name in ("ev_r1", "ev_t1", "ev_f1"))
    assert record["contrary_motion_q"] == 0


def test_identity_constraint_forces_self_pairing() -> None:
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    sustained = {**_note("ev_hold", "1/1", 0), "duration_ticks": 960, "velocity": 100}
    moving_a = {**_note("ev_a", "5/4", 0), "velocity": 100}
    moving_b = {**_note("ev_b", "3/2", 480), "velocity": 100}
    project = _project([moving_a, moving_b, sustained])
    project["clock"] = {"ticks_per_beat": 480, "beats_per_bar": 4, "total_ticks": 960}
    project["tracks"] = [{"id": "harmony", "role": "harmony"}]
    spec, _, manifest, report = _phase3(policy, project)
    vm_policy = _vm_policy(spec, manifest)
    (record,) = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    self_pairs = [
        row for row in record["pairs"] if row["from_event_id"] == row["to_event_id"] == "ev_hold"
    ]
    assert len(self_pairs) == 1
    assert self_pairs[0]["absolute_motion_millicents"] == 0


def test_decreasing_voice_count_reverses_injection_and_records_unmatched_from() -> None:
    project = _project(
        [
            {**_note("ev_a", "1/1", 0), "velocity": 100},
            {**_note("ev_b", "5/4", 0), "velocity": 100},
            {**_note("ev_c", "3/2", 0), "velocity": 100},
            {**_note("ev_d", "1/1", 480), "velocity": 100},
            {**_note("ev_e", "3/2", 480), "velocity": 100},
        ]
    )
    project["clock"] = {"ticks_per_beat": 480, "beats_per_bar": 4, "total_ticks": 960}
    project["tracks"] = [{"id": "harmony", "role": "harmony"}]
    seg_policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    spec, _, manifest, report = _phase3(seg_policy, project)
    vm_policy = _vm_policy(spec, manifest)
    (record,) = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], seg_policy, vm_policy
    )
    assert len(record["pairs"]) == 2
    assert len(record["unmatched_from_event_ids"]) == 1
    assert record["unmatched_to_event_ids"] == []
    assert record["canonical_matching_key"][:3] == [3, 2, 2]


def test_contrary_motion_is_detected() -> None:
    project = _project(
        [
            {**_note("ev_a", "1/1", 0), "velocity": 100},
            {**_note("ev_b", "3/2", 0), "velocity": 100},
            {**_note("ev_c", "9/8", 480), "velocity": 100},
            {**_note("ev_d", "16/15", 480), "velocity": 100},
        ]
    )
    project["clock"] = {"ticks_per_beat": 480, "beats_per_bar": 4, "total_ticks": 960}
    project["tracks"] = [{"id": "harmony", "role": "harmony"}]
    pitch_records = [
        perceptual.compute_pitch_record(
            event,
            base_frequency_millihz=220_000,
            equave_period_mc=1_200_000,
            radius_millicents=100_000,
        )
        for event in project["events"]
    ]
    segments = [
        {
            "segment_id": "seg_" + "0" * 32,
            "start_tick": 0,
            "end_tick": 480,
            "source_event_ids": ["ev_a", "ev_b"],
            "bass_event_id": None,
        },
        {
            "segment_id": "seg_" + "1" * 32,
            "start_tick": 480,
            "end_tick": 960,
            "source_event_ids": ["ev_c", "ev_d"],
            "bass_event_id": None,
        },
    ]
    seg_policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    spec, _, manifest = _assets(seg_policy)
    vm_policy = _vm_policy(
        spec,
        manifest,
        cost_weights={
            "absolute_motion": 10_000,
            "circular_motion": 0,
            "pitch_mapping_l1": 0,
            "role_mismatch": 0,
        },
    )
    (record,) = perceptual.match_voices(project, pitch_records, segments, seg_policy, vm_policy)
    motions = {row["from_event_id"]: row["absolute_motion_millicents"] for row in record["pairs"]}
    # Minimum absolute-motion matching pairs 1/1->16/15 (up) and 3/2->9/8 (down).
    assert set(motions) == {"ev_a", "ev_b"}
    assert motions["ev_a"] > 0 > motions["ev_b"]
    assert record["contrary_motion_q"] == 10_000


def test_transition_feature_record_bass_metrical_and_tension() -> None:
    policy, _, vocabulary, _, report, vm_policy, _ = _phase4_inputs()
    project = _two_segment_project()
    matching = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    (transition,) = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        matching,
        vocabulary,
        vm_policy,
    )
    assert transition["transition_id"] == matching[0]["transition_id"]
    assert transition["matching_record_hash"] == matching[0]["record_hash"]
    assert transition["record_hash"] == perceptual.transition_feature_record_hash(transition)
    # Bass moves 1/1 -> 3/2: absolute +701955 wraps to circular -498045, still
    # a near-perfect fifth likeness (wrapped distance 1955 from the center).
    assert transition["bass_absolute_motion_millicents"] == 701_955
    assert transition["bass_circular_motion_millicents"] == -498_045
    assert transition["bass_fifth_likeness_q"] == 9_804
    assert transition["bass_fourth_likeness_q"] is not None
    # Destination starts at tick 480: beat but not bar boundary.
    assert transition["destination_metrical_strength_q"] == 7_500
    # Near-identical segments: directed tension change stays small and signed.
    assert -10_000 <= transition["directed_tension_change_q"] <= 10_000
    assert abs(transition["directed_tension_change_q"]) < 100


def test_null_bass_nulls_all_bass_fields() -> None:
    policy = _policy(
        grid_divisions_per_beat=1, minimum_segment_ticks=480, bass_role_order=["drums"]
    )
    project = _two_segment_project()
    spec, vocabulary, manifest, report = _phase3(policy, project)
    assert all(segment["bass_event_id"] is None for segment in report["segments"])
    vm_policy = _vm_policy(spec, manifest)
    matching = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    (transition,) = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        matching,
        vocabulary,
        vm_policy,
    )
    for key in (
        "bass_absolute_motion_millicents",
        "bass_circular_motion_millicents",
        "bass_fifth_likeness_q",
        "bass_fourth_likeness_q",
        "bass_step_likeness_q",
    ):
        assert transition[key] is None


def test_zero_tension_denominator_is_trajectory_failure() -> None:
    _, _, vocabulary, _, report, vm_policy, _ = _phase4_inputs()
    interpretations = [
        {**row, "candidates": [{"id": "major", "similarity_q": 0}]}
        for row in report["segment_interpretations"]
    ]
    with pytest.raises(PilError, match="PIL_TRAJECTORY_FAILED"):
        perceptual.build_transition_feature_records(
            _two_segment_project(),
            report["pitch_records"],
            report["segments"],
            interpretations,
            [],
            vocabulary,
            vm_policy,
        )


def test_template_set_validation_negatives() -> None:
    _, spec, vocabulary, manifest, _, vm_policy, template_set = _phase4_inputs()
    perceptual.validate_trajectory_template_set(template_set, manifest, spec, vocabulary, vm_policy)

    unknown = copy.deepcopy(template_set)
    unknown["templates"][0]["steps"][0]["chord_targets"][0]["vocabulary_id"] = "unknown"
    unknown["template_set_hash"] = perceptual.trajectory_template_set_hash(unknown)
    manifest["trajectory_template_set_hash"] = unknown["template_set_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    with pytest.raises(PilError, match="PIL_TRAJECTORY_FAILED"):
        perceptual.validate_trajectory_template_set(unknown, manifest, spec, vocabulary, vm_policy)

    bad_sum = copy.deepcopy(template_set)
    bad_sum["templates"][0]["steps"][0]["chord_targets"][0]["weight_q31"] -= 1
    bad_sum["template_set_hash"] = perceptual.trajectory_template_set_hash(bad_sum)
    manifest["trajectory_template_set_hash"] = bad_sum["template_set_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    with pytest.raises(PilError, match="PIL_TRAJECTORY_FAILED"):
        perceptual.validate_trajectory_template_set(bad_sum, manifest, spec, vocabulary, vm_policy)

    bad_weights = copy.deepcopy(template_set)
    bad_weights["score_weights"]["chord"] = 0
    bad_weights["template_set_hash"] = perceptual.trajectory_template_set_hash(bad_weights)
    manifest["trajectory_template_set_hash"] = bad_weights["template_set_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    with pytest.raises(PilError, match="PIL_TRAJECTORY_FAILED"):
        perceptual.validate_trajectory_template_set(
            bad_weights, manifest, spec, vocabulary, vm_policy
        )


def test_alignment_scores_sorts_and_truncates() -> None:
    _, _, _, _, report, _, template_set = _phase4_inputs()
    policy = _policy(grid_divisions_per_beat=1, minimum_segment_ticks=480)
    project = _two_segment_project()
    spec, _, manifest = _assets(policy)
    vm_policy = _vm_policy(spec, manifest)
    matching = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    transitions = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        matching,
        _assets(policy)[1],
        vm_policy,
    )
    results = perceptual.align_trajectories(
        report["segments"], report["segment_interpretations"], transitions, template_set
    )
    assert len(results) == 1
    result = results[0]
    match_preimage = {
        "segment_ids": result["segment_ids"],
        "template_id": result["template_id"],
        "template_set_hash": template_set["template_set_hash"],
    }
    match_body = json.dumps(
        match_preimage, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    expected_match_id = (
        "tjm_" + hashlib.sha256(b"cps.pil-trajectory-match-id/v1\0" + match_body).hexdigest()[:32]
    )
    assert result["match_id"] == expected_match_id
    assert result["canonical_alignment_key"] == [0, 0]
    assert result["result_hash"] == perceptual.trajectory_result_hash(result)
    assert result["similarity_q"] > 8_000
    assert result["component_scores_q"]["bass"] == 9_804
    assert result["transition_record_hashes"] == [transitions[0]["record_hash"]]

    truncated = copy.deepcopy(template_set)
    truncated["alignment"]["maximum_results"] = 0
    with pytest.raises(PilError, match="PIL_TRAJECTORY_FAILED"):
        perceptual.validate_trajectory_template_set(
            truncated, manifest, spec, _assets(policy)[1], vm_policy
        )


def test_null_bass_removes_bass_weight_from_similarity() -> None:
    policy = _policy(
        grid_divisions_per_beat=1, minimum_segment_ticks=480, bass_role_order=["drums"]
    )
    project = _two_segment_project()
    spec, vocabulary, manifest, report = _phase3(policy, project)
    vm_policy = _vm_policy(spec, manifest)
    template_set = _template_set(spec, vocabulary, vm_policy, manifest)
    matching = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    transitions = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        matching,
        vocabulary,
        vm_policy,
    )
    (result,) = perceptual.align_trajectories(
        report["segments"], report["segment_interpretations"], transitions, template_set
    )
    assert result["component_scores_q"]["bass"] is None
    assert 0 <= result["similarity_q"] <= 10_000


def test_phase4_operators_are_deterministic() -> None:
    policy, _, vocabulary, _, report, vm_policy, template_set = _phase4_inputs()
    project = _two_segment_project()
    first = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    second = perceptual.match_voices(
        project, report["pitch_records"], report["segments"], policy, vm_policy
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    transitions_a = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        first,
        vocabulary,
        vm_policy,
    )
    transitions_b = perceptual.build_transition_feature_records(
        project,
        report["pitch_records"],
        report["segments"],
        report["segment_interpretations"],
        second,
        vocabulary,
        vm_policy,
    )
    assert transitions_a == transitions_b
    results_a = perceptual.align_trajectories(
        report["segments"], report["segment_interpretations"], transitions_a, template_set
    )
    results_b = perceptual.align_trajectories(
        report["segments"], report["segment_interpretations"], transitions_b, template_set
    )
    assert results_a == results_b
