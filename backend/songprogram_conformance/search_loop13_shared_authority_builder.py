"""Independent raw authority bindings for the SearchLoop13 shared context."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
DOCS = ROOT.parent / "docs"

CONTRACT_FILES = {
    "mutation_application": "song_program_mutation_application_contract.md",
    "connected_execution": "song_program_connected_execution_contract.md",
    "fallback_sampler": "song_program_fallback_sampler_contract.md",
    # Broad-prior production is normatively a section of this same contract.
    "broad_prior_production": "song_program_fallback_sampler_contract.md",
}

NULL_ARTIFACTS = (
    "planner_manifest",
    "planner_prompt_asset",
    "planner_invocation_policy",
    "tokenizer_manifest",
    "planner_tool_catalog",
)

NON_NULL_ARTIFACTS = (
    "sampler_manifest",
    "fallback_manifest",
    "broad_prior_production_manifest",
    "compiler_manifest",
    "evaluation_manifest",
    "genre_intent",
    "genre_reference_set_manifest",
    "feature_extractor_manifest",
    "genre_similarity_spec",
    "calibration_decision",
    "calibration_dataset_manifest",
    "calibration_response_set",
    "calibration_statistic_operator",
    "calibration_bootstrap_trace",
    "calibration_evidence_summary",
    "calibration_acceptance_policy",
    "qd_manifest",
    "mutation_choice_catalog",
    "fingerprint_spec",
    "archive_admission_policy",
    "challenger_acceptance_policy",
    "stopping_policy",
    "render_selection_policy",
    "render_manifest",
    "candidate_source_policy",
    "instrument_catalog",
    "executor_manifest",
)

SCHEMA_FILES = {
    "mutation": "mutation.schema.json",
    "mutation_request": "mutation_application_request_1_2.schema.json",
    "mutation_receipt": "mutation_application_receipt.schema.json",
    "mutation_impact": "mutation_impact_report.schema.json",
    "connected_request": "connected_request.schema.json",
    "connected_output": "connected_logical_output.schema.json",
    "compile_report": "compile_report_1_1.schema.json",
    "fingerprint_record": "fingerprint_record.schema.json",
    "evaluation_manifest": "evaluation_manifest_1_1.schema.json",
    "evaluation_request": "evaluation_request.schema.json",
    "evaluation_report": "evaluation_report_1_1.schema.json",
    "evaluation_manifest_1_1": "evaluation_manifest_1_1.schema.json",
    "evaluation_report_1_1": "evaluation_report_1_1.schema.json",
    "genre_intent": "genre_intent.schema.json",
    "genre_reference_set_manifest": "genre_reference_set_manifest.schema.json",
    "feature_extractor_manifest": "feature_extractor_manifest.schema.json",
    "genre_feature_record": "genre_feature_record.schema.json",
    "genre_similarity_spec": "genre_similarity_spec.schema.json",
    "calibration_decision": "calibration_decision_1_1.schema.json",
    "calibration_dataset_manifest": "calibration_dataset_manifest.schema.json",
    "calibration_response_set": "calibration_response_set.schema.json",
    "calibration_statistic_operator": "calibration_statistic_operator.schema.json",
    "calibration_bootstrap_trace": "calibration_bootstrap_trace.schema.json",
    "calibration_evidence_summary": "calibration_evidence_summary.schema.json",
    "calibration_acceptance_policy": "calibration_acceptance_policy.schema.json",
    "challenger_acceptance_policy_1_1": "challenger_acceptance_policy_1_1.schema.json",
    "challenger_acceptance_decision_1_1": "challenger_acceptance_decision_1_1.schema.json",
    "candidate_source_decision": "candidate_source_decision.schema.json",
    "sampler_request": "structural_sampler_request_1_1.schema.json",
    "sampler_result": "structural_sampler_result_1_1.schema.json",
    "planner_request": "planner_request.schema.json",
    "planner_response": "planner_response.schema.json",
    "planner_prompt_asset": "planner_prompt_asset.schema.json",
    "planner_invocation_policy": "planner_invocation_policy.schema.json",
    "tokenizer_manifest": "tokenizer_manifest.schema.json",
    "planner_tool_catalog": "planner_tool_catalog.schema.json",
    "conformance_violation_evidence": "conformance_violation_evidence.schema.json",
    "fixture_suite_index": "search_loop_13_fixture_suite_index.schema.json",
    "compile_only_request": "compile_only_request.schema.json",
    "compile_only_result": "compile_only_result.schema.json",
    "compile_only_cache_entry": "compile_only_cache_entry.schema.json",
    "cancellation_inbox_record": "cancellation_inbox_record_1_1.schema.json",
    "cancellation_decision": "cancellation_decision_1_1.schema.json",
    "archive_heads_snapshot": "archive_heads_snapshot.schema.json",
    "structural_sampler_trace": "structural_sampler_trace_1_1.schema.json",
    "structural_lowering_manifest": "structural_lowering_manifest.schema.json",
    "structural_program": "structural_song_program_1_0.schema.json",
    "structural_rejection_evidence": "structural_rejection_evidence_1_1.schema.json",
    "planner_proposal_preimage": "planner_proposal_preimage.schema.json",
    "event_payload": "search_loop_13_event_payload.schema.json",
    "run_record": "search_run_record_1_1.schema.json",
    "checkpoint": "search_checkpoint_1_1.schema.json",
    "fallback_manifest": "fallback_manifest_1_1.schema.json",
    "fallback_request": "fallback_request_1_1.schema.json",
    "production_request": "broad_prior_production_request_1_1.schema.json",
    "production_result": "broad_prior_production_result_1_1.schema.json",
    "fallback_result": "fallback_result_1_1.schema.json",
    "near_duplicate_decision": "near_duplicate_decision.schema.json",
    "render_request": "render_request.schema.json",
    "render_charge": "render_charge.schema.json",
    "render_dispatch_authorization": "render_dispatch_authorization.schema.json",
    "render_result": "render_result.schema.json",
    "render_failure": "render_failure.schema.json",
    "render_cache_entry": "render_cache_entry.schema.json",
    "render_cache_corruption_receipt": "render_cache_corruption_receipt.schema.json",
    "audio_artifact": "audio_artifact.schema.json",
    "cache_publication_index": "cache_publication_index.schema.json",
    "cas_index": "search_loop_13_cas_index.schema.json",
    "challenger_acceptance_decision": "challenger_acceptance_decision_1_1.schema.json",
    "archive_admission_decision": "archive_admission_decision.schema.json",
    "qd_archive_record": "qd_archive_record.schema.json",
    "round_decision": "round_decision.schema.json",
    "round_improvement_evidence": "round_improvement_evidence.schema.json",
}


def raw_binding(payload: bytes) -> dict[str, str]:
    return {
        "hash": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "bytes_base64": base64.b64encode(payload).decode("ascii"),
    }


def contract_bindings() -> dict[str, dict[str, str]]:
    return {key: raw_binding((DOCS / name).read_bytes()) for key, name in CONTRACT_FILES.items()}


def schema_bindings() -> dict[str, dict[str, str]]:
    return {key: raw_binding((SCHEMAS / name).read_bytes()) for key, name in SCHEMA_FILES.items()}
