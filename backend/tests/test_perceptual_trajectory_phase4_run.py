"""Run-level Phase 4 (functional_trajectory) integration tests.

Synthetic inputs only; no authoritative fixture, oracle, or golden is created
or modified.
"""

from __future__ import annotations

import copy

from app.songprogram import perceptual
from app.songprogram.perceptual import PIL_PHASE3_BUILD_ID
from test_perceptual_trajectory_phase4 import _phase4_inputs, _two_segment_project


def _run_phase4(cache_dir=None):
    policy, spec, vocabulary, manifest, _, vm_policy, template_set = _phase4_inputs()
    report = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        cache_dir=cache_dir,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
        voice_matching_policy=vm_policy,
        trajectory_template_set=template_set,
    )
    return report, policy, spec, vocabulary, manifest, vm_policy, template_set


def test_phase4_report_embeds_ordered_evidence() -> None:
    report, *_ = _run_phase4()
    assert report["status"] == "success"
    assert report["completed_phase"] == "functional_trajectory"
    assert len(report["segments"]) == 2
    assert len(report["voice_matching_records"]) == 1
    assert len(report["transition_feature_records"]) == 1
    assert len(report["trajectory_interpretations"]) == 1
    matching = report["voice_matching_records"][0]
    transition = report["transition_feature_records"][0]
    result = report["trajectory_interpretations"][0]
    assert transition["matching_record_hash"] == matching["record_hash"]
    assert result["transition_record_hashes"] == [transition["record_hash"]]
    assert result["similarity_q"] > 8_000
    assert report["report_hash"] == perceptual.report_hash(report)


def test_phase4_failure_reports_use_stable_codes() -> None:
    policy, spec, vocabulary, manifest, _, vm_policy, template_set = _phase4_inputs()
    bad_policy = copy.deepcopy(vm_policy)
    bad_policy["maximum_voices_per_segment"] = 99
    report = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
        voice_matching_policy=bad_policy,
        trajectory_template_set=template_set,
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_VOICE_MATCHING_FAILED"
    assert report["completed_phase"] == "functional_trajectory"

    bad_templates = copy.deepcopy(template_set)
    bad_templates["templates"][0]["steps"][0]["chord_targets"][0]["vocabulary_id"] = "unknown"
    report = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
        voice_matching_policy=vm_policy,
        trajectory_template_set=bad_templates,
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_TRAJECTORY_FAILED"


def test_voice_matching_failure_precedes_trajectory_validation() -> None:
    policy, spec, vocabulary, manifest, _, vm_policy, template_set = _phase4_inputs()
    bad_policy = copy.deepcopy(vm_policy)
    bad_policy["cost_weights"]["absolute_motion"] = -1
    bad_templates = copy.deepcopy(template_set)
    bad_templates["templates"] = []
    report = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
        voice_matching_policy=bad_policy,
        trajectory_template_set=bad_templates,
    )
    assert report["error"] == "PIL_VOICE_MATCHING_FAILED"


def test_phase4_requires_phase3_assets() -> None:
    policy, spec, _, manifest, _, vm_policy, template_set = _phase4_inputs()
    report = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        segmentation_policy=policy,
        voice_matching_policy=vm_policy,
        trajectory_template_set=template_set,
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_FEATURE_EXTRACTION_FAILED"


def test_phase3_build_manifest_is_not_silently_upgraded() -> None:
    policy, spec, vocabulary, manifest, _, vm_policy, template_set = _phase4_inputs()
    legacy = copy.deepcopy(manifest)
    legacy["implementation_build_id"] = PIL_PHASE3_BUILD_ID
    legacy["manifest_hash"] = perceptual.manifest_hash(legacy)
    # Phase 3 build still runs chord_similarity.
    phase3 = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        legacy,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert phase3["status"] == "success"
    assert phase3["completed_phase"] == "chord_similarity"
    # ...but is rejected for functional_trajectory before any draw.
    try:
        perceptual.run_perceptual_interpretation(
            _two_segment_project(),
            legacy,
            segmentation_policy=policy,
            feature_spec=spec,
            chord_vocabulary=vocabulary,
            voice_matching_policy=vm_policy,
            trajectory_template_set=template_set,
        )
    except perceptual.PilError as error:
        assert error.code == "PIL_BINDING_MISMATCH"
    else:  # pragma: no cover
        raise AssertionError("expected PIL_BINDING_MISMATCH")


def test_phase4_cache_cold_hit_corrupt_parity(tmp_path) -> None:
    cold, policy, spec, vocabulary, manifest, vm_policy, template_set = _run_phase4(tmp_path)
    cold_bytes = perceptual.canonical_report_bytes(cold)
    assert len(list(tmp_path.iterdir())) == 1

    hit, *_ = _run_phase4(tmp_path)
    assert perceptual.canonical_report_bytes(hit) == cold_bytes

    for path in tmp_path.iterdir():
        path.write_bytes(b'{"corrupt": true}')
    corrupt, *_ = _run_phase4(tmp_path)
    assert perceptual.canonical_report_bytes(corrupt) == cold_bytes

    # A Phase 3 run on the same cache directory cannot alias the Phase 4 entry.
    phase3 = perceptual.run_perceptual_interpretation(
        _two_segment_project(),
        manifest,
        cache_dir=tmp_path,
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
    )
    assert phase3["completed_phase"] == "chord_similarity"
    assert len(list(tmp_path.iterdir())) == 2


def test_phase4_report_is_byte_deterministic_across_runs() -> None:
    first, *_ = _run_phase4()
    second, *_ = _run_phase4()
    assert perceptual.canonical_report_bytes(first) == perceptual.canonical_report_bytes(second)
