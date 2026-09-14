from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .search_loop13_calibration_fixture_builder import (
    build_calibration_authority,
    write_calibration_authority,
)
from .search_loop13_fixture_oracle import artifact_hash


FIXTURE = Path(__file__).with_name("fixtures") / "search_loop_13" / "calibration_authority"
RENDERER_HASH = json.loads(
    (FIXTURE.parent / "shared_authority" / "artifacts" / "render_manifest.json").read_bytes()
)["render_manifest_digest"]


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
        "calibration_fixture_set": "fixture_set_hash",
        "calibration_decision": "decision_hash",
    }
    for name, field in hash_fields.items():
        assert authority[name][field] == artifact_hash(authority[name], field)
    for binding in authority["raw_authorities"].values():
        payload = bytes.fromhex(binding["bytes_hex"])
        assert binding["hash"] == "sha256:" + hashlib.sha256(payload).hexdigest()
    for provenance in authority["reference_source_provenances"].values():
        assert provenance["provenance_hash"] == artifact_hash(provenance, "provenance_hash")
    for feature in authority["genre_feature_records"].values():
        assert feature["record_hash"] == artifact_hash(feature, "record_hash")
    reference = authority["genre_reference_set_manifest"]
    assert {member["source_provenance_hash"] for member in reference["members"]} == {
        value["provenance_hash"] for value in authority["reference_source_provenances"].values()
    }
    assert authority["calibration_decision"]["schema_version"] == "1.1.0"
    assert authority["calibration_decision"]["status"] == "promoted"
    assert all(row["passed"] for row in authority["calibration_evidence_summary"]["criteria"])


def test_fixture_only_calibration_is_repeatable() -> None:
    renderer_hash = "sha256:" + "b" * 64
    assert build_calibration_authority(renderer_hash) == build_calibration_authority(renderer_hash)


def test_fixture_only_calibration_pack_materializes_every_entry(tmp_path) -> None:
    index = write_calibration_authority(tmp_path, "sha256:" + "c" * 64)
    assert index["index_hash"] == artifact_hash(index, "index_hash")
    for entry in index["entries"]:
        payload = (tmp_path / entry["path"]).read_bytes()
        assert entry["canonical_bytes_sha256"] == "sha256:" + hashlib.sha256(payload).hexdigest()


def test_checked_in_calibration_authority_matches_independent_builder(tmp_path) -> None:
    write_calibration_authority(tmp_path, RENDERER_HASH)
    expected = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    actual = {
        path.relative_to(FIXTURE): path.read_bytes()
        for path in FIXTURE.rglob("*")
        if path.is_file()
    }
    assert actual == expected
