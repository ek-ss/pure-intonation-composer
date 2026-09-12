"""PIL Phase 1 (pitch projection) tests.

All projects/manifests below are synthetic test inputs built in code; no
authoritative fixture, oracle, or golden is created or modified.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.songprogram import perceptual
from app.songprogram.perceptual import (
    PIL_IMPLEMENTATION_BUILD_ID,
    NUMERIC_CONTRACT_HASH,
    PROJECT_SCHEMA_HASH,
    Q31_TOTAL,
    PilError,
)

BACKEND = Path(__file__).resolve().parents[1]


def _sha(byte: int) -> str:
    return "sha256:" + f"{byte:02x}" * 32


def _manifest(radius: int = 100_000) -> dict:
    manifest = {
        "schema": "cps.perceptual-interpretation-manifest",
        "schema_version": "1.0.0",
        "algorithm": "pil-parallel-interpretation/v1",
        "project_schema_hash": PROJECT_SCHEMA_HASH,
        "numeric_contract_hash": NUMERIC_CONTRACT_HASH,
        "implementation_build_id": PIL_IMPLEMENTATION_BUILD_ID,
        "interpretation_period": "2/1",
        "pitch_kernel": {
            "algorithm": "triangular-millicent-q31/v1",
            "radius_millicents": radius,
            "normalization_total": Q31_TOTAL,
        },
        "segmentation_policy_hash": _sha(0x03),
        "feature_spec_hash": _sha(0x04),
        "vocabulary_hash": _sha(0x05),
        "voice_matching_policy_hash": _sha(0x06),
        "trajectory_template_set_hash": _sha(0x07),
        "genre_model_hash": None,
    }
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return manifest


def _note(event_id: str, ratio: str, start: int = 0) -> dict:
    return {
        "id": event_id,
        "kind": "note",
        "track_id": "harmony",
        "start_tick": start,
        "duration_ticks": 480,
        "ratio": ratio,
    }


def _project(events: list[dict], equave: str = "2/1") -> dict:
    return {
        "schema": "cps.arrangement-project",
        "schema_version": "1.2.0",
        "compiler": {
            "build_id": "test.compiler.phase1",
            "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        },
        "lattice": {
            "base_frequency_millihz": 220_000,
            "equave": equave,
        },
        "events": events,
    }


def _record(report: dict, event_id: str) -> dict:
    (record,) = [row for row in report["pitch_records"] if row["source_event_id"] == event_id]
    return record


def test_unison_maps_max_weight_to_pitch_class_zero() -> None:
    report = perceptual.run_perceptual_interpretation(_project([_note("ev_a", "1/1")]), _manifest())
    assert report["status"] == "success"
    mapping = _record(report, "ev_a")["mapping_q31"]
    best = max(mapping, key=lambda row: row["weight_q31"])
    assert best["pitch_class_ordinal"] == 0
    assert sum(row["weight_q31"] for row in mapping) == Q31_TOTAL


def test_major_third_and_fifth_retain_multiple_candidates() -> None:
    report = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "5/4"), _note("ev_b", "3/2")]), _manifest()
    )
    third = _record(report, "ev_a")
    fifth = _record(report, "ev_b")
    assert third["absolute_millicents"] == 386_314
    assert fifth["absolute_millicents"] == 701_955
    # No hard nearest-note quantization: both neighbours keep nonzero weight.
    assert {row["pitch_class_ordinal"] for row in third["mapping_q31"]} == {3, 4}
    assert {row["pitch_class_ordinal"] for row in fifth["mapping_q31"]} == {7, 8}
    assert third["source_ratio"] == "5/4" and fifth["source_ratio"] == "3/2"


def test_q31_weights_always_sum_exactly() -> None:
    ratios = ["1/1", "5/4", "3/2", "6/5", "7/4", "9/8", "11/8", "13/8", "16/15", "45/32"]
    for radius in (100_000, 600_000):
        for ratio in ratios:
            report = perceptual.run_perceptual_interpretation(
                _project([_note("ev_a", ratio)]), _manifest(radius)
            )
            assert report["status"] == "success"
            mapping = report["pitch_records"][0]["mapping_q31"]
            assert sum(row["weight_q31"] for row in mapping) == Q31_TOTAL
            assert all(row["weight_q31"] >= 1 for row in mapping)
    # A minimal radius still normalizes exactly when support is non-empty.
    for radius in (1, 12_345):
        report = perceptual.run_perceptual_interpretation(
            _project([_note("ev_a", "1/1")]), _manifest(radius)
        )
        assert report["status"] == "success"
        mapping = report["pitch_records"][0]["mapping_q31"]
        assert sum(row["weight_q31"] for row in mapping) == Q31_TOTAL


def test_kernel_boundary_excludes_zero_raw_weight() -> None:
    # At distance exactly equal to the radius the raw weight max(0, R-d) is 0,
    # so the candidate is excluded from support.
    with pytest.raises(PilError, match="PIL_PITCH_SUPPORT_EMPTY"):
        perceptual.triangular_mapping_q31(50_000, 50_000)
    # One millicent inside the radius on both sides keeps both candidates.
    mapping = perceptual.triangular_mapping_q31(50_000, 50_001)
    assert [row["pitch_class_ordinal"] for row in mapping] == [0, 1]
    # Equal raw weights tie; the leftover unit goes to the lower ordinal.
    assert mapping[0]["weight_q31"] == mapping[1]["weight_q31"] + 1
    assert sum(row["weight_q31"] for row in mapping) == Q31_TOTAL


def test_kernel_tie_breaks_by_pitch_class_ordinal() -> None:
    # Exactly halfway between class 0 and class 1 with a wide radius: equal raw
    # weights, equal fractional remainders, ordinal 0 wins the extra unit.
    mapping = perceptual.triangular_mapping_q31(50_000, 600_000)
    by_ordinal = {row["pitch_class_ordinal"]: row["weight_q31"] for row in mapping}
    assert by_ordinal[0] >= by_ordinal[1]
    assert sum(by_ordinal.values()) == Q31_TOTAL


def test_empty_support_is_a_stable_failure_code() -> None:
    with pytest.raises(PilError, match="PIL_PITCH_SUPPORT_EMPTY"):
        perceptual.triangular_mapping_q31(50_000, 40_000)
    report = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "16/15")]), _manifest(10_000)
    )
    # 16/15 is 111728 mc: distance to class 1 is 88272 and to class 0 is
    # 111728, both beyond radius 10000 -> failed report, stable code.
    assert report["status"] == "failure"
    assert report["error"] == "PIL_PITCH_SUPPORT_EMPTY"
    assert report["pitch_records"] == []
    assert report["report_hash"] == perceptual.report_hash(report)


def test_native_phase_wraps_by_project_equave() -> None:
    octave = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "3/1")], equave="2/1"), _manifest()
    )
    tritave = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "3/1")], equave="3/1"), _manifest()
    )
    octave_record = octave["pitch_records"][0]
    tritave_record = tritave["pitch_records"][0]
    assert octave_record["native_phase_millicents"] == 701_955  # 1901955 mod 1200000
    assert tritave_record["native_phase_millicents"] == 0  # 1901955 mod 1901955
    # Interpretation phase is an independent explicit 2/1 wrap in both cases.
    assert octave_record["interpretation_phase_millicents"] == 701_955
    assert tritave_record["interpretation_phase_millicents"] == 701_955
    assert (
        octave_record["absolute_millicents"] == tritave_record["absolute_millicents"] == 1_901_955
    )


def test_frequency_millihz_is_exact_rhe_derivation() -> None:
    report = perceptual.run_perceptual_interpretation(
        _project([_note("ev_a", "3/2"), _note("ev_b", "5/4")]), _manifest()
    )
    assert _record(report, "ev_a")["frequency_millihz"] == 330_000
    assert _record(report, "ev_b")["frequency_millihz"] == 275_000


def test_event_and_input_order_invariance() -> None:
    events = [_note("ev_c", "3/2", 480), _note("ev_a", "1/1"), _note("ev_b", "5/4", 240)]
    forward = perceptual.run_perceptual_interpretation(_project(events), _manifest())
    shuffled = perceptual.run_perceptual_interpretation(
        _project(list(reversed(events))), _manifest()
    )
    # The events array order is part of the immutable Project hash, so the two
    # projects differ; the derived pitch records must not depend on that order.
    assert forward["pitch_records"] == shuffled["pitch_records"]
    assert [row["source_event_id"] for row in forward["pitch_records"]] == [
        "ev_a",
        "ev_b",
        "ev_c",
    ]


def test_cross_process_and_hashseed_parity(tmp_path: Path) -> None:
    script = (
        "import json,sys\n"
        "sys.path.insert(0, {!r})\n"
        "from app.songprogram import perceptual\n"
        "manifest = {{'schema': 'cps.perceptual-interpretation-manifest',\n"
        " 'schema_version': '1.0.0', 'algorithm': 'pil-parallel-interpretation/v1',\n"
        " 'project_schema_hash': {!r}, 'numeric_contract_hash': {!r},\n"
        " 'implementation_build_id': {!r}, 'interpretation_period': '2/1',\n"
        " 'pitch_kernel': {{'algorithm': 'triangular-millicent-q31/v1',\n"
        "   'radius_millicents': 100000, 'normalization_total': 2147483647}},\n"
        " 'segmentation_policy_hash': {!r}, 'feature_spec_hash': {!r},\n"
        " 'vocabulary_hash': {!r}, 'voice_matching_policy_hash': {!r},\n"
        " 'trajectory_template_set_hash': {!r}, 'genre_model_hash': None}}\n"
        "manifest['manifest_hash'] = perceptual.manifest_hash(manifest)\n"
        "project = {{'schema': 'cps.arrangement-project', 'schema_version': '1.2.0',\n"
        " 'compiler': {{'build_id': 'test.compiler.phase1',\n"
        "   'numeric_contract': 'cps-numeric/decimal-log2-rhe-v1'}},\n"
        " 'lattice': {{'base_frequency_millihz': 220000, 'equave': '2/1'}},\n"
        " 'events': [{{'id': 'ev_b', 'kind': 'note', 'ratio': '3/2'}},\n"
        "   {{'id': 'ev_a', 'kind': 'note', 'ratio': '5/4'}}]}}\n"
        "report = perceptual.run_perceptual_interpretation(project, manifest)\n"
        "sys.stdout.buffer.write(perceptual.canonical_report_bytes(report))\n"
    ).format(
        str(BACKEND),
        PROJECT_SCHEMA_HASH,
        NUMERIC_CONTRACT_HASH,
        PIL_IMPLEMENTATION_BUILD_ID,
        _sha(0x03),
        _sha(0x04),
        _sha(0x05),
        _sha(0x06),
        _sha(0x07),
    )
    outputs = []
    for seed in ("0", "1", "424242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            cwd=BACKEND,
            env=env,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_pil_failure_never_mutates_project_or_native_inputs() -> None:
    project = _project([_note("ev_a", "16/15")])
    before = copy.deepcopy(project)
    native_hash = _sha(0xAA)
    report = perceptual.run_perceptual_interpretation(
        project, _manifest(10_000), native_ji_report_hash=native_hash
    )
    assert report["status"] == "failure"
    assert project == before
    # Nullable correlation metadata is passed through, never computed from.
    assert report["native_ji_report_hash"] == native_hash


def test_binding_mismatch_negatives() -> None:
    project = _project([_note("ev_a", "1/1")])
    manifest = _manifest()

    tampered = copy.deepcopy(manifest)
    tampered["pitch_kernel"]["radius_millicents"] = 90_000
    with pytest.raises(PilError, match="PIL_BINDING_MISMATCH"):
        perceptual.run_perceptual_interpretation(project, tampered)

    wrong_build = _manifest()
    wrong_build["implementation_build_id"] = "pil.other.build"
    wrong_build["manifest_hash"] = perceptual.manifest_hash(wrong_build)
    with pytest.raises(PilError, match="PIL_BINDING_MISMATCH"):
        perceptual.run_perceptual_interpretation(project, wrong_build)

    wrong_contract = _project([_note("ev_a", "1/1")])
    wrong_contract["compiler"]["numeric_contract"] = "cps-numeric/other-v9"
    with pytest.raises(PilError, match="PIL_BINDING_MISMATCH"):
        perceptual.run_perceptual_interpretation(wrong_contract, manifest)

    with pytest.raises(PilError, match="PIL_BINDING_MISMATCH"):
        perceptual.run_perceptual_interpretation(
            project, manifest, expected_project_hash=_sha(0xFF)
        )

    ok = perceptual.run_perceptual_interpretation(
        project, manifest, expected_project_hash=perceptual.project_hash(project)
    )
    assert ok["status"] == "success"
    assert ok["project_hash"] == perceptual.project_hash(project)


def test_cache_cold_hit_corrupt_parity(tmp_path: Path) -> None:
    project = _project([_note("ev_a", "5/4"), _note("ev_b", "3/2")])
    manifest = _manifest()
    cache_dir = tmp_path / "pil-cache"

    cold = perceptual.run_perceptual_interpretation(project, manifest, cache_dir=cache_dir)
    cold_bytes = perceptual.canonical_report_bytes(cold)
    assert len(list(cache_dir.iterdir())) == 1

    hit = perceptual.run_perceptual_interpretation(project, manifest, cache_dir=cache_dir)
    assert perceptual.canonical_report_bytes(hit) == cold_bytes

    for path in cache_dir.iterdir():
        path.write_bytes(b'{"corrupt": true}')
    corrupt = perceptual.run_perceptual_interpretation(project, manifest, cache_dir=cache_dir)
    assert perceptual.canonical_report_bytes(corrupt) == cold_bytes

    key = perceptual.cache_key(perceptual.project_hash(project), manifest)
    canonical = json.loads(cold_bytes)
    stored = json.loads((cache_dir / f"{key.removeprefix('sha256:')}.json").read_bytes())
    assert stored == canonical
