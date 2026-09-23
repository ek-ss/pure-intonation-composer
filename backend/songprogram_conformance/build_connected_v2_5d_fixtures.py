"""Independently seal the five-dimensional connected execution authority."""

from __future__ import annotations

import base64
import json
from copy import deepcopy
from pathlib import Path

from .canonical import canonical_bytes
from .connected_oracle import (
    artifact_hash, build_cache_entry, canonical_lf, connected_request_hash,
    executor_manifest_digest, logical_output_hash, opcode_bundle_hash, raw_hash,
)
from .mutation_oracle import evaluate, program_hash
from .search_decision_oracle import artifact_hash as decision_hash
from .search_loop13_shared_authority_builder import SCHEMA_FILES, CONTRACT_FILES

ROOT = Path(__file__).parent
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures"
FIVE_D = FIXTURES / "compiler_v2_5d"
SHARED = FIXTURES / "search_loop_13" / "shared_authority"
OUT = FIXTURES / "connected_v2_5d"
DOCS = ROOT.parents[1] / "docs"

OVERRIDES = {
    "mutation": "mutation_2_0.schema.json",
    "mutation_request": "mutation_application_request_2_0.schema.json",
    "connected_request": "connected_request_2_0.schema.json",
    "connected_output": "connected_logical_output_2_0.schema.json",
    "candidate_source_decision": "candidate_source_decision_2_0.schema.json",
    "compile_only_request": "compile_only_request_2_0.schema.json",
    "compile_only_result": "compile_only_result_2_0.schema.json",
    "fallback_request": "fallback_request_2_0.schema.json",
    "archive_heads_snapshot": "archive_heads_snapshot_2_0.schema.json",
}
EXECUTOR_SCHEMAS = {
    "song_program": "song_program_0_2.schema.json", "mutation": OVERRIDES["mutation"],
    "mutation_request": OVERRIDES["mutation_request"],
    "mutation_impact": "mutation_impact_report.schema.json",
    "mutation_receipt": "mutation_application_receipt.schema.json",
    "compiler_manifest": "compiler_manifest_2_0.schema.json",
    "project": "arrangement_project_1_3_5d.schema.json",
    "gen0b_evidence": "gen0b_compiler_evidence_2_0.schema.json",
    "melody_report": "chord_member_melody_report_2_0.schema.json",
    "compile_report": "compile_report_1_1_5d.schema.json",
    "charge_receipt": "charge_receipt_1_1_5d.schema.json",
    "opcode_stream": "logical_opcode_stream.schema.json",
    "opcode_bundle": "opcode_stream_bundle.schema.json",
    "connected_request": OVERRIDES["connected_request"],
    "connected_output": OVERRIDES["connected_output"],
    "connected_cache_entry": "connected_cache_entry_2_0.schema.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seal(name: str, value: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(canonical_lf(value))


def schema_hash(name: str) -> str:
    return raw_hash((SCHEMAS / name).read_bytes())


def build() -> None:
    from .build_gen0b_5d_fixtures import build_5d_inputs, compile_pipeline

    program = load(FIVE_D / "gen0b_melody_song_program.json")
    compiler = load(FIVE_D / "gen0b_compiler_manifest.json")
    slots = deepcopy(load(SHARED / "artifact_slot_index.json")["artifacts"])
    catalog = load(FIXTURES / "render" / "catalog.json")
    choices = slots["mutation_choice_catalog"]["document"]
    assert program["production"]["catalog_digest"] == artifact_hash("cps.instrument-catalog/v1", catalog)
    executor = {
        "schema": "cps.connected-executor-manifest", "schema_version": "2.0.0",
        "pipeline_order": "mutation-then-gen0b-compile-then-melody/v1",
        "canonical_json_contract": "cps-canonical-json/v1",
        "contract_hashes": {key: raw_hash((DOCS / name).read_bytes()) for key, name in {
            "mutation_application": "song_program_mutation_application_contract.md",
            "gen0b_compiler_lowering": "song_program_gen0b_compiler_lowering_contract.md",
            "chord_member_melody": "song_program_chord_member_melody_contract.md",
            "connected_execution": "song_program_connected_execution_contract.md",
        }.items()},
        "schema_hashes": {key: schema_hash(name) for key, name in EXECUTOR_SCHEMAS.items()},
    }
    # Only the compiler slot changes in the shared artifact corpus; all other
    # base64-bound bytes are retained verbatim.
    compiler_slot = slots["compiler_manifest"]
    compiler_slot.update(document=compiler, artifact_bytes_base64=base64.b64encode(canonical_lf(compiler)).decode(),
                         artifact_hash=artifact_hash("cps.compiler-manifest/v2.0", compiler),
                         schema_bytes_base64=base64.b64encode((SCHEMAS / "compiler_manifest_2_0.schema.json").read_bytes()).decode(),
                         schema_hash=schema_hash("compiler_manifest_2_0.schema.json"))
    # The executor is the versioned authority bound by the new request and context.
    slots["executor_manifest"] = {
        **slots["executor_manifest"], "document": executor,
        "artifact_bytes_base64": base64.b64encode(canonical_lf(executor)).decode(),
        "artifact_hash": executor_manifest_digest(executor),
        "schema_bytes_base64": base64.b64encode((SCHEMAS / "connected_executor_manifest_2_0.schema.json").read_bytes()).decode(),
        "schema_hash": schema_hash("connected_executor_manifest_2_0.schema.json"),
    }
    schema_files = {**SCHEMA_FILES, **OVERRIDES}
    schema_hashes = {key: schema_hash(name) for key, name in schema_files.items()}
    contract_hashes = {key: raw_hash((DOCS / name).read_bytes()) for key, name in CONTRACT_FILES.items()}
    run_schema = load(SCHEMAS / "search_run_manifest_1_3.schema.json")
    run = {"schema": "cps.search-run-manifest", "schema_version": "1.3.0",
           "root_seed": 0, "population_size": 1, "candidates_per_round": 1,
           "planner_call_budget": 0, "compile_logical_budget": 2500000,
           "render_frame_budget": 0, "operational_deadline_seconds": None,
           "artifact_store": {"algorithm": "local-content-addressed/v1", "cas_root": "cas/sha256",
                              "run_root": "runs", "record_framing": "u64be-length-canonical-json/v1",
                              "atomic_write": "same-directory-create-if-absent-fsync/v1"}}
    component_hashes = load(SHARED / "artifacts" / "component_hashes.json")
    reusable_hashes = load(SHARED / "artifacts" / "reusable_component_hashes.json")
    for key in run_schema["required"]:
        if key in run:
            continue
        if key.endswith("_schema_hash"):
            schema_key = key.removesuffix("_schema_hash")
            run[key] = schema_hash("search_loop_13_context_2_0.schema.json") if schema_key == "search_loop_context" else schema_hashes[schema_key]
        elif key.endswith("_hash"):
            kind = key.removesuffix("_hash")
            slot = slots.get(kind)
            if kind == "compiler_manifest":
                run[key] = compiler_slot["artifact_hash"]
            elif kind == "executor_manifest":
                run[key] = slots[kind]["artifact_hash"]
            elif slot is None:
                run[key] = None
            else:
                document = slot["document"]
                run[key] = (document.get("manifest_hash") or document.get("intent_hash") or document.get("policy_hash")
                            or component_hashes.get(kind) or reusable_hashes.get(kind) or slot["artifact_hash"])
        else:
            raise AssertionError(key)
    run["structural_lowering_manifest_hash"] = slots["sampler_manifest"]["document"]["structural_lowering_manifest_hash"]
    run_hash = decision_hash(run)
    context = {"schema": "cps.search-loop-13-context", "schema_version": "2.0.0",
               "run_manifest": run, "run_hash": run_hash, "artifacts": slots,
               "contract_hashes": {key: {"hash": value, "bytes_base64": base64.b64encode((DOCS / CONTRACT_FILES[key]).read_bytes()).decode()}
                                   for key, value in contract_hashes.items()},
               "schema_hashes": {key: {"hash": value, "bytes_base64": base64.b64encode((SCHEMAS / schema_files[key]).read_bytes()).decode()}
                                 for key, value in schema_hashes.items()}}
    context["context_hash"] = decision_hash(context, "context_hash")
    mutation = {"schema": "cps.mutation", "schema_version": "2.0.0", "mutation_id": "mut_bbbbbbbbbbbbbbbbbbbb",
                "base_program_hash": program_hash(program), "operation": "rotate_rhythm",
                "declared_scope": [{"kind": "rhythm", "id": "rhythm_chord"}],
                "parameters": {"kind": "rotate_rhythm", "rhythm_id": "rhythm_chord", "steps": 3}}
    request_mutation = {
        "schema": "cps.mutation-application-request", "schema_version": "2.0.0",
        "contract": "cps-mutation-application/v2-batch",
        "contract_sha256": executor["contract_hashes"]["mutation_application"],
        "mutation_schema_sha256": schema_hashes["mutation"],
        "request_schema_sha256": schema_hashes["mutation_request"],
        "impact_schema_sha256": schema_hashes["mutation_impact"],
        "receipt_schema_sha256": schema_hashes["mutation_receipt"],
        "action_id": "act_aaaaaaaaaaaaaaaaaaaaaaaaaa", "run_manifest_hash": run_hash,
        "run_manifest": run, "context_hash": context["context_hash"],
        "source_decision_hash": raw_hash(b"cps.connected-v2-5d.source-decision/v1\0"),
        "base_program_hash": program_hash(program), "base_program": program,
        "mutation_choice_catalog_hash": run["mutation_choice_catalog_hash"],
        "mutation_choice_catalog": choices, "instrument_catalog_digest": compiler["instrument_catalog_digest"],
        "instrument_catalog": catalog, "locked_roots": [],
        "origin": {"kind": "planner", "response_hash": raw_hash(b"cps.connected-v2-5d.planner-response/v1\0"),
                   "proposal_hash": raw_hash(b"cps.connected-v2-5d.proposal/v1\0")},
        "mutations": [mutation],
    }
    request_mutation["request_hash"] = artifact_hash("cps.mutation-application-request/v1", request_mutation, omit="request_hash")
    request = {"schema": "cps.connected-request", "schema_version": "2.0.0",
               "executor_manifest_digest": executor_manifest_digest(executor),
               "executor_manifest": executor, "mutation_request": request_mutation, "compiler_manifest": compiler}
    applied = evaluate(program, mutation, [], choices, catalog, artifact_hash("cps.mutation-application-request/v1", request_mutation))
    assert applied["status"] == "success" and canonical_bytes(applied["program"]) == canonical_bytes(program)
    # Recompute through the independent compiler pipeline, then bind to the
    # already sealed five-dimensional golden rather than regenerating it.
    input_program, input_manifest, base_project, _ = build_5d_inputs()
    assert canonical_bytes(input_program) == canonical_bytes(program)
    assert canonical_bytes(input_manifest) == canonical_bytes(compiler)
    compiled = compile_pipeline(applied["program"], compiler, base_project)
    fields = {"project": "gen0b_melody_project.json", "evidence": "gen0b_compiler_evidence.json",
              "melody_report": "chord_member_melody_report.json", "compile_report": "gen0b_compile_report.json",
              "root_stream": "gen0b_root_opcode_stream.json", "chord_stream": "gen0b_chord_opcode_stream.json",
              "progression_stream": "gen0b_progression_opcode_stream.json"}
    for key, name in fields.items():
        assert canonical_lf(compiled[key]) == (FIVE_D / name).read_bytes(), name
    output = {"schema": "cps.connected-logical-output", "schema_version": "2.0.0",
              "request_hash": connected_request_hash(request), "status": "success",
              "resulting_program": applied["program"], "mutation_impact": applied["impact"],
              "mutation_receipt": applied["receipt"], "project": compiled["project"],
              "compiler_evidence": compiled["evidence"], "melody_report": compiled["melody_report"],
              "compile_report": compiled["compile_report"], "lineage_index": None, "error": None}
    output["logical_output_hash"] = logical_output_hash(output)
    receipt = compiled["receipt"]
    streams = {"chord_query": compiled["chord_stream"], "progression_query": compiled["progression_stream"]}
    bundle = {"schema": "cps.opcode-stream-bundle", "schema_version": "1.0.0",
              "root": compiled["root_stream"],
              "children": [{"kind": child["kind"], "query_id": child["query_id"], "stream": streams[child["kind"]]}
                           for child in receipt["children"]]}
    bundle["bundle_hash"] = opcode_bundle_hash(bundle)
    entry = build_cache_entry(request, output, bundle)
    for name, value in {"run_context.json": context, "connected_request.json": request,
                        "connected_output.json": output, "opcode_bundle.json": bundle,
                        "cache_entry.json": entry}.items():
        seal(name, value)
    files = sorted(p.name for p in OUT.glob("*.json") if p.name != "suite_index.json")
    referenced = set(schema_files.values()) | set(EXECUTOR_SCHEMAS.values()) | {
        "search_loop_13_context_2_0.schema.json", "search_run_manifest_1_3.schema.json",
        "connected_executor_manifest_2_0.schema.json"}
    index = {"schema": "cps.connected-v2-5d-fixture-suite-index", "schema_version": "1.0.0",
             "generator_identity": "cps-independent-connected-v2-5d-oracle/1.0.0",
             "contract": "cps-connected-v2-5d-authoritative/v1", "files": files,
             "file_sha256": {name: raw_hash((OUT / name).read_bytes()) for name in files},
             "schema_sha256": {name: schema_hash(name) for name in sorted(referenced)},
             "expected_hashes": {"run_hash": run_hash, "context_hash": context["context_hash"],
                                 "compiler_manifest_hash": compiler_slot["artifact_hash"],
                                 "executor_manifest_digest": executor_manifest_digest(executor),
                                 "connected_request_hash": connected_request_hash(request),
                                 "logical_output_hash": output["logical_output_hash"],
                                 "cache_entry_hash": entry["entry_hash"],
                                 "opcode_bundle_hash": bundle["bundle_hash"]}}
    index["suite_hash"] = artifact_hash("cps.connected-v2-5d-fixture-suite-index/v1", index)
    seal("suite_index.json", index)


if __name__ == "__main__":
    build()
