from __future__ import annotations

from .search_loop13_calibration_fixture_builder import build_calibration_authority
from .search_loop13_fixture_oracle import artifact_hash


def test_fixture_only_calibration_draft_has_closed_primary_hashes() -> None:
    authority = build_calibration_authority("sha256:" + "a" * 64)
    hash_fields = {
        "listener_cohort_manifest": "manifest_hash",
        "feature_extractor_manifest": "manifest_hash",
        "genre_reference_set_manifest": "manifest_hash",
        "calibration_statistic_operator": "operator_hash",
        "calibration_acceptance_policy": "policy_hash",
        "calibration_response_set": "response_hash",
        "blinded_assignment_manifest": "manifest_hash",
        "calibration_dataset_manifest": "manifest_hash",
        "calibration_bootstrap_trace": "trace_hash",
        "calibration_evidence_summary": "summary_hash",
        "calibration_decision": "decision_hash",
    }
    for name, field in hash_fields.items():
        assert authority[name][field] == artifact_hash(authority[name], field)
    assert authority["calibration_decision"]["schema_version"] == "1.1.0"
    assert authority["calibration_decision"]["status"] == "promoted"
    assert all(row["passed"] for row in authority["calibration_evidence_summary"]["criteria"])


def test_fixture_only_calibration_is_repeatable() -> None:
    renderer_hash = "sha256:" + "b" * 64
    assert build_calibration_authority(renderer_hash) == build_calibration_authority(renderer_hash)
