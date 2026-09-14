"""Materialize all 32 immutable RunContext artifact slots."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .search_loop13_fixture_oracle import artifact_hash
from .search_loop13_shared_authority_builder import NON_NULL_ARTIFACTS, NULL_ARTIFACTS


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
FIXTURE = ROOT / "songprogram_conformance" / "fixtures" / "search_loop_13"
SHARED = FIXTURE / "shared_authority" / "artifacts"
CALIBRATION = FIXTURE / "calibration_authority" / "artifacts"

SCHEMA_BY_SLOT = {
    "sampler_manifest": "sampler_manifest_1_1.schema.json",
    "fallback_manifest": "fallback_manifest_1_1.schema.json",
    "broad_prior_production_manifest": "broad_prior_production_manifest.schema.json",
    "compiler_manifest": "compiler_manifest_1_1.schema.json",
    "evaluation_manifest": "evaluation_manifest_1_1.schema.json",
    "genre_intent": "genre_intent.schema.json",
    "genre_reference_set_manifest": "genre_reference_set_manifest.schema.json",
    "feature_extractor_manifest": "feature_extractor_manifest.schema.json",
    "genre_similarity_spec": "genre_similarity_spec.schema.json",
    "calibration_decision": "calibration_decision_1_1.schema.json",
    "calibration_dataset_manifest": "calibration_dataset_manifest.schema.json",
    "calibration_response_set": "calibration_response_set.schema.json",
    "calibration_statistic_operator": "calibration_statistic_operator.schema.json",
    "calibration_bootstrap_trace": "calibration_bootstrap_trace.schema.json",
    "calibration_evidence_summary": "calibration_evidence_summary.schema.json",
    "calibration_acceptance_policy": "calibration_acceptance_policy.schema.json",
    "qd_manifest": "qd_manifest.schema.json",
    "mutation_choice_catalog": "mutation_choice_catalog.schema.json",
    "fingerprint_spec": "fingerprint_spec.schema.json",
    "archive_admission_policy": "archive_admission_policy.schema.json",
    "challenger_acceptance_policy": "challenger_acceptance_policy_1_1.schema.json",
    "stopping_policy": "stopping_policy.schema.json",
    "render_selection_policy": "render_selection_policy.schema.json",
    "render_manifest": "render_manifest.schema.json",
    "candidate_source_policy": "candidate_source_policy.schema.json",
    "instrument_catalog": "instrument_catalog.schema.json",
    "executor_manifest": "connected_executor_manifest.schema.json",
}

CALIBRATION_SLOTS = {
    "genre_reference_set_manifest",
    "feature_extractor_manifest",
    "calibration_decision",
    "calibration_dataset_manifest",
    "calibration_response_set",
    "calibration_statistic_operator",
    "calibration_bootstrap_trace",
    "calibration_evidence_summary",
    "calibration_acceptance_policy",
}

SELF_HASH_FIELDS = {
    "sampler_manifest": "manifest_hash",
    "evaluation_manifest": "manifest_hash",
    "genre_intent": "intent_hash",
    "genre_reference_set_manifest": "manifest_hash",
    "feature_extractor_manifest": "manifest_hash",
    "genre_similarity_spec": "spec_hash",
    "calibration_decision": "decision_hash",
    "calibration_dataset_manifest": "manifest_hash",
    "calibration_response_set": "response_hash",
    "calibration_statistic_operator": "operator_hash",
    "calibration_bootstrap_trace": "trace_hash",
    "calibration_evidence_summary": "summary_hash",
    "calibration_acceptance_policy": "policy_hash",
    "challenger_acceptance_policy": "policy_hash",
}


def _raw_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _component_hashes() -> dict[str, str]:
    hashes = json.loads((SHARED / "reusable_component_hashes.json").read_bytes())
    hashes.update(json.loads((SHARED / "component_hashes.json").read_bytes()))
    return hashes


def build_artifact_slots() -> dict[str, Any]:
    if set(SCHEMA_BY_SLOT) != set(NON_NULL_ARTIFACTS):
        raise AssertionError("slot/schema map does not match owner partition")
    component_hashes = _component_hashes()
    slots: dict[str, Any] = {}
    for slot in NON_NULL_ARTIFACTS:
        root = CALIBRATION if slot in CALIBRATION_SLOTS else SHARED
        artifact_path = root / f"{slot}.json"
        artifact_bytes = artifact_path.read_bytes()
        document = json.loads(artifact_bytes)
        schema_bytes = (SCHEMAS / SCHEMA_BY_SLOT[slot]).read_bytes()
        if slot in SELF_HASH_FIELDS:
            field = SELF_HASH_FIELDS[slot]
            expected_hash = artifact_hash(document, field)
            if document[field] != expected_hash:
                raise AssertionError(f"invalid self hash for {slot}")
            identity = expected_hash
        else:
            identity = component_hashes[slot]
        slots[slot] = {
            "kind": slot,
            "artifact_hash": identity,
            "schema_hash": _raw_hash(schema_bytes),
            "artifact_bytes_base64": base64.b64encode(artifact_bytes).decode("ascii"),
            "schema_bytes_base64": base64.b64encode(schema_bytes).decode("ascii"),
            "document": document,
        }
    slots.update({slot: None for slot in NULL_ARTIFACTS})
    return slots


def build_slot_index() -> dict[str, Any]:
    value = {
        "schema": "cps.search-loop-13-artifact-slot-index",
        "schema_version": "1.0.0",
        "non_null_slot_count": len(NON_NULL_ARTIFACTS),
        "null_slot_count": len(NULL_ARTIFACTS),
        "artifacts": build_artifact_slots(),
        "index_hash": "",
    }
    value["index_hash"] = artifact_hash(value, "index_hash")
    return value


def write_slot_index(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(build_slot_index()))
