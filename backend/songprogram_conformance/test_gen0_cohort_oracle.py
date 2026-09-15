from __future__ import annotations

from .gen0_cohort_oracle import (
    artifact_identity,
    build_report,
    derive_mode_keys,
    manifest_hash,
    record_hash,
)


def _manifest() -> dict:
    value = {
        "manifest_hash": "",
        "thresholds_bp": {
            "compile_success_ge": 9500,
            "initial_viability_ge": 7000,
            "planner_viability_ge": 8000,
            "exact_duplicate_lt": 100,
            "near_duplicate_lt": 1000,
            "transformed_recall_ge": 8000,
            "mode_prevalence_le": 3500,
        },
        "near_duplicate_policy": {"status": "audit_only"},
    }
    value["manifest_hash"] = manifest_hash(value)
    return value


def _record(ordinal: int) -> dict:
    modes = derive_mode_keys(
        {
            "root_anchor_deltas": [[ordinal], [ordinal + 1]],
            "chord_steps": [[ordinal], [ordinal + 2]],
            "role_time_grid": [["harmony", ordinal, 1]],
            "sounding_intervals": ["1/1"],
        }
    )
    value = {
        "candidate_ordinal": ordinal,
        "terminal_stage": "complete",
        "compile_success": True,
        "automatic_viable": ordinal < 800,
        "has_transformed_recall": ordinal < 800,
        "duplicate_classification": "distinct",
        "qd_cell": [ordinal % 5, 0],
        "mode_keys": modes,
    }
    value["record_hash"] = record_hash(value)
    return value


def test_oracle_uses_fixed_thousand_denominator_and_audit_policy() -> None:
    report = build_report(_manifest(), [_record(index) for index in range(1000)])
    assert report["rates_bp"]["compile_success"] == 10000
    assert report["rates_bp"]["automatic_viable"] == 8000
    assert report["gates"]["near_duplicate"]["status"] == "not_enforced"
    assert report["planner_eligible"] is False
    assert report["qd_occupied_cells"] == [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]


def test_mode_keys_are_deduplicated_and_digest_sorted() -> None:
    keys = derive_mode_keys(
        {
            "root_anchor_deltas": [[0], [1], [0], [1]],
            "chord_steps": [],
            "role_time_grid": [],
            "sounding_intervals": [],
        }
    )
    assert len(keys["root_anchor_ngram"]) == 2
    assert keys["root_anchor_ngram"] == sorted(
        keys["root_anchor_ngram"], key=lambda value: bytes.fromhex(value[7:])
    )


def test_closed_identity_rules_omit_only_their_normative_self_field() -> None:
    request = {
        "schema": "cps.structural-sampler-request",
        "schema_version": "1.1.0",
        "request_hash": "sha256:" + "0" * 64,
        "root_seed": 7,
    }
    first = artifact_identity("generic-cps-artifact-v1", request)
    request["request_hash"] = "sha256:" + "f" * 64
    assert artifact_identity("generic-cps-artifact-v1", request) == first
    request["root_seed"] = 8
    assert artifact_identity("generic-cps-artifact-v1", request) != first


def test_song_program_and_project_rules_bind_normative_domains() -> None:
    program = {
        "schema": "cps.song-program",
        "schema_version": "0.1.0",
        "program_id": "a",
        "seed": 1,
    }
    first = artifact_identity("song-program-v0.1", program)
    program["program_id"] = "b"
    assert artifact_identity("song-program-v0.1", program) == first
    project = {"compiler": {"build_id": "cb_fixture"}, "events": []}
    assert artifact_identity("arrangement-project-v1.2", project).startswith("sha256:")
