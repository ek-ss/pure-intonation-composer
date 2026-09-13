"""Coverage for previously untested PIL failure codes and precedence.

All projects/manifests below are synthetic test inputs built in code; no
authoritative fixture, oracle, or golden is created or modified.
"""

from __future__ import annotations

import copy

import pytest

from app.songprogram import perceptual
from app.songprogram.perceptual import PilError
from test_perceptual_interpretation_phase1 import _manifest, _note, _project
from test_perceptual_segmentation_phase2 import (
    _bound_manifest,
    _phase2_project,
    _policy,
)


def test_schema_invalid_for_noncanonical_ratio() -> None:
    with pytest.raises(PilError) as caught:
        perceptual.compute_pitch_record(
            _note("ev_a", "2/2"),
            base_frequency_millihz=220_000,
            equave_period_mc=1_200_000,
            radius_millicents=100_000,
        )
    assert caught.value.code == "PIL_SCHEMA_INVALID"


def test_schema_invalid_run_creates_no_report() -> None:
    project = _project([_note("ev_a", "2/2")])
    with pytest.raises(PilError) as caught:
        perceptual.run_perceptual_interpretation(project, _manifest())
    assert caught.value.code == "PIL_SCHEMA_INVALID"


def test_numeric_overflow_for_sub_millihz_frequency() -> None:
    with pytest.raises(PilError) as caught:
        perceptual.compute_pitch_record(
            _note("ev_a", "1/4"),
            base_frequency_millihz=1,
            equave_period_mc=1_200_000,
            radius_millicents=100_000,
        )
    assert caught.value.code == "PIL_NUMERIC_OVERFLOW"


def test_segment_boundary_invalid_for_odd_ticks_per_beat() -> None:
    policy = _policy()
    project = _phase2_project()
    project["clock"] = {"ticks_per_beat": 481, "total_ticks": 962}
    report = perceptual.run_perceptual_interpretation(
        project, _bound_manifest(policy), segmentation_policy=policy
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_SEGMENT_BOUNDARY_INVALID"


def test_policy_invalid_precedes_boundary_invalid() -> None:
    # Contract section 4.3: PIL_SEGMENTATION_POLICY_INVALID (5) wins over
    # PIL_SEGMENT_BOUNDARY_INVALID (6) when both conditions are present.
    policy = _policy()
    project = _phase2_project()
    project["clock"] = {"ticks_per_beat": 481, "total_ticks": 962}
    project["tracks"] = [
        {"id": "harmony", "role": "harmony"},
        {"id": "harmony", "role": "bass"},
    ]
    report = perceptual.run_perceptual_interpretation(
        project, _bound_manifest(policy), segmentation_policy=policy
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_SEGMENTATION_POLICY_INVALID"


def test_pitch_support_empty_precedes_policy_invalid() -> None:
    # Contract section 4.3: PIL_PITCH_SUPPORT_EMPTY (4) wins over
    # PIL_SEGMENTATION_POLICY_INVALID (5).
    policy = _policy(grid_divisions_per_beat=3)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    manifest = _manifest(radius=1)
    manifest["segmentation_policy_hash"] = policy["policy_hash"]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    project = _phase2_project()
    # 7/6 sits at 266871 mc, over 1 mc away from every 100000-millicent bin
    # center, so the radius-1 kernel has empty support.
    project["events"] = [{**_note("ev_a", "7/6", 0), "velocity": 100}]
    report = perceptual.run_perceptual_interpretation(
        project, manifest, segmentation_policy=policy
    )
    assert report["status"] == "failure"
    assert report["error"] == "PIL_PITCH_SUPPORT_EMPTY"


def test_result_validation_rejects_corrupt_report() -> None:
    report = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "1/1")]), _manifest()
    )
    assert report["status"] == "success"
    corrupt = copy.deepcopy(report)
    corrupt["pitch_records"][0]["mapping_q31"][0]["weight_q31"] -= 1
    with pytest.raises(PilError) as caught:
        perceptual._validate_report_bounds(corrupt)
    assert caught.value.code == "PIL_RESULT_VALIDATION"


def test_result_validation_rejects_unknown_status() -> None:
    report = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "1/1")]), _manifest()
    )
    corrupt = copy.deepcopy(report)
    corrupt["status"] = "unknown"
    with pytest.raises(PilError) as caught:
        perceptual._validate_report_bounds(corrupt)
    assert caught.value.code == "PIL_RESULT_VALIDATION"
