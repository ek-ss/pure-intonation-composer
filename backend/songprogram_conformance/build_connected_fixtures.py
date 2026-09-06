"""Build the minimal authoritative Connected Execution v1 fixture corpus."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .connected_oracle import (
    artifact_hash,
    build_cache_entry,
    build_runner_result,
    canonical_lf,
    connected_request_hash,
    executor_manifest_digest,
    json_pointer_replace,
    logical_output_hash,
    raw_hash,
    semantic_input_hash,
    semantic_runner_request_hash,
)
from .mutation_oracle import artifact_hash as mutation_artifact_hash
from .mutation_oracle import evaluate as apply_mutation
from .mutation_oracle import program_hash


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures"
OUT = FIXTURES / "connected"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_lf(value))


def _file(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(OUT).as_posix(), "sha256": raw_hash(path.read_bytes())}


def _raw_file_hash(path: Path) -> str:
    return raw_hash(path.read_bytes())


def _build_id(manifest: dict[str, Any]) -> str:
    core = deepcopy(manifest)
    core.pop("build_id", None)
    digest = hashlib.sha256(b"cps.compiler-build/v1\0" + canonical_bytes(core)).digest()
    return "cb_" + base64.b32encode(digest).decode("ascii").lower().rstrip("=")[:26]


def _instrument_digest(catalog: dict[str, Any]) -> str:
    return artifact_hash("cps.instrument-catalog/v1", catalog)


def _compiler_manifest(catalog_digest: str) -> dict[str, Any]:
    base = _json(FIXTURES / "pack" / "compiler_manifest_sp0.json")
    manifest = deepcopy(base)
    manifest["schema_version"] = "1.1.0"
    manifest["instrument_catalog_digest"] = catalog_digest
    manifest["progression_resolver"] = {
        "build_id": "fixture-progression-exact-v1",
        "algorithm": "gen0-progression-exact/v1",
        "profile_hash": "sha256:" + "7" * 64,
        "search_completeness": "exact",
        "candidates_per_intent": 2,
        "maximum_voice_motion_millicents": 2_000_000,
        "crossing_policy": "allow",
    }
    profile = manifest["budget_profile"]
    profile["id"] = "gen0-progression-exact-v1"
    profile["root_ceilings"]["progression_states"] = 12_288
    profile["root_ceilings"]["progression_edges"] = 294_336
    profile["child_ceilings"]["progression_states"] = 12_288
    profile["child_ceilings"]["progression_edges"] = 294_336
    profile["shape_limits"]["progression_occurrences"] = 512
    profile["shape_limits"]["progression_candidates_per_occurrence"] = 24
    profile["digest"] = mutation_artifact_hash(
        "cps.budget-profile/v1", {key: value for key, value in profile.items() if key != "digest"}
    )
    manifest["build_id"] = _build_id(manifest)
    return manifest


def _executor_manifest() -> dict[str, Any]:
    contract_paths = {
        "mutation_application": REPO / "docs" / "song_program_mutation_application_contract.md",
        "gen0b_compiler_lowering": REPO / "docs" / "song_program_gen0b_compiler_lowering_contract.md",
        "chord_member_melody": REPO / "docs" / "song_program_chord_member_melody_contract.md",
        "connected_execution": REPO / "docs" / "song_program_connected_execution_contract.md",
    }
    schema_names = {
        "song_program": "song_program_0_1.schema.json",
        "mutation": "mutation.schema.json",
        "mutation_request": "mutation_application_request.schema.json",
        "mutation_impact": "mutation_impact_report.schema.json",
        "mutation_receipt": "mutation_application_receipt.schema.json",
        "compiler_manifest": "compiler_manifest_1_1.schema.json",
        "project": "arrangement_project_1_2.schema.json",
        "gen0b_evidence": "gen0b_compiler_evidence.schema.json",
        "melody_report": "chord_member_melody_report.schema.json",
        "compile_report": "compile_report_1_1.schema.json",
        "charge_receipt": "charge_receipt_1_1.schema.json",
        "opcode_stream": "logical_opcode_stream.schema.json",
        "opcode_bundle": "opcode_stream_bundle.schema.json",
        "connected_request": "connected_request.schema.json",
        "connected_output": "connected_logical_output.schema.json",
        "connected_cache_entry": "connected_cache_entry.schema.json",
    }
    return {
        "schema": "cps.connected-executor-manifest",
        "schema_version": "1.0.0",
        "pipeline_order": "mutation-then-gen0b-compile-then-melody/v1",
        "canonical_json_contract": "cps-canonical-json/v1",
        "contract_hashes": {key: _raw_file_hash(path) for key, path in contract_paths.items()},
        "schema_hashes": {key: _raw_file_hash(SCHEMAS / name) for key, name in schema_names.items()},
    }


def _mutation_request(
    program: dict[str, Any], compiler: dict[str, Any], catalog: dict[str, Any], mutation: dict[str, Any]
) -> dict[str, Any]:
    run = _json(FIXTURES / "search" / "run_manifest.json")
    choices = _json(FIXTURES / "search" / "mutation_choice_catalog.json")
    run["compiler_manifest_hash"] = raw_hash(canonical_lf(compiler))
    run["mutation_schema_hash"] = _raw_file_hash(SCHEMAS / "mutation.schema.json")
    run_hash = artifact_hash("cps.search-run-manifest/v1", run)
    choice_hash = artifact_hash("cps.mutation-choice-catalog/v1", choices)
    return {
        "schema": "cps.mutation-application-request",
        "schema_version": "1.0.0",
        "contract": "cps-mutation-application/v1",
        "contract_sha256": _raw_file_hash(REPO / "docs" / "song_program_mutation_application_contract.md"),
        "mutation_schema_sha256": _raw_file_hash(SCHEMAS / "mutation.schema.json"),
        "request_schema_sha256": _raw_file_hash(SCHEMAS / "mutation_application_request.schema.json"),
        "impact_schema_sha256": _raw_file_hash(SCHEMAS / "mutation_impact_report.schema.json"),
        "receipt_schema_sha256": _raw_file_hash(SCHEMAS / "mutation_application_receipt.schema.json"),
        "action_id": "act_aaaaaaaaaaaaaaaaaaaaaaaaaa",
        "run_manifest_hash": run_hash,
        "run_manifest": run,
        "base_program_hash": program_hash(program),
        "base_program": program,
        "mutation_choice_catalog_hash": choice_hash,
        "mutation_choice_catalog": choices,
        "instrument_catalog_digest": _instrument_digest(catalog),
        "instrument_catalog": catalog,
        "locked_roots": [],
        "mutations": [mutation],
    }


def build() -> None:
    catalog = _json(FIXTURES / "render" / "catalog.json")
    catalog_digest = _instrument_digest(catalog)
    program = _json(FIXTURES / "pack" / "minimal_direct_song_program.json")
    program["production"]["catalog_digest"] = catalog_digest
    compiler = _compiler_manifest(catalog_digest)
    executor = _executor_manifest()
    failure_mutation = {
        "schema": "cps.mutation", "schema_version": "1.0.0",
        "mutation_id": "mut_aaaaaaaaaaaaaaaaaaaa", "base_program_hash": program_hash(program),
        "operation": "rotate_rhythm", "declared_scope": [{"kind": "rhythm", "id": "rhythm_a"}],
        "parameters": {"kind": "transpose_material_vector", "material_id": "pitch_a", "vector_delta": [1, 0]},
    }
    mutation_request = _mutation_request(program, compiler, catalog, failure_mutation)
    request = {
        "schema": "cps.connected-request",
        "schema_version": "1.0.0",
        "executor_manifest_digest": executor_manifest_digest(executor),
        "executor_manifest": executor,
        "mutation_request": mutation_request,
        "compiler_manifest": compiler,
    }
    request_hash = connected_request_hash(request)
    applied = apply_mutation(
        program,
        mutation_request["mutations"][0],
        mutation_request["locked_roots"],
        mutation_request["mutation_choice_catalog"],
        catalog,
        artifact_hash("cps.mutation-application-request/v1", mutation_request),
    )
    if applied["status"] != "failure":
        raise AssertionError("connected minimal case must be a mutation failure")
    projected_error = {key: applied["error"][key] for key in ("code", "stage", "pointer")}
    output = {
        "schema": "cps.connected-logical-output",
        "schema_version": "1.0.0",
        "request_hash": request_hash,
        "status": "mutation_failure",
        "resulting_program": None,
        "mutation_impact": None,
        "mutation_receipt": applied["receipt"],
        "project": None,
        "compiler_evidence": None,
        "melody_report": None,
        "compile_report": None,
        "lineage_index": None,
        "error": projected_error,
    }
    output["logical_output_hash"] = logical_output_hash(output)
    entry = build_cache_entry(request, output, None)
    corrupted = json_pointer_replace(entry, "/entry_hash", "sha256:" + "0" * 64)

    request_path = OUT / "mutation_failure_request.json"
    output_path = OUT / "mutation_failure_cold_output.json"
    entry_path = OUT / "mutation_failure_cache_entry.json"
    corrupt_path = OUT / "mutation_failure_corrupt_entry.json"
    for path, value in ((request_path, request), (output_path, output), (entry_path, entry), (corrupt_path, corrupted)):
        _write(path, value)

    failure_case = {
        "case_id": "mutation_operation_mismatch",
        "pipeline": "connected_candidate",
        "connected_request_hash": request_hash,
        "request": _file(request_path),
        "cold_output": _file(output_path),
        "opcode_stream_bundle": None,
        "valid_cache_entry": _file(entry_path),
        "corruption": {
            "id": "entry_hash_zero",
            "kind": "raw_fixture",
            "corrupted_entry": _file(corrupt_path),
            "expected_first_failed_check": "entry_hash",
        },
    }
    # Connect an identity mutation to the separately generated authoritative
    # GEN0-B/melody cold artifacts without regenerating any of their contents.
    compiler_dir = FIXTURES / "compiler"
    success_program = _json(compiler_dir / "gen0b_melody_song_program.json")
    success_compiler = _json(compiler_dir / "gen0b_compiler_manifest.json")
    if success_program["production"]["catalog_digest"] != catalog_digest:
        raise AssertionError("compiler fixture is not bound to the immutable instrument catalog")
    success_mutation = {
        "schema": "cps.mutation", "schema_version": "1.0.0",
        "mutation_id": "mut_bbbbbbbbbbbbbbbbbbbb", "base_program_hash": program_hash(success_program),
        "operation": "rotate_rhythm", "declared_scope": [{"kind": "rhythm", "id": "rhythm_chord"}],
        "parameters": {"kind": "rotate_rhythm", "rhythm_id": "rhythm_chord", "steps": 3},
    }
    success_mutation_request = _mutation_request(success_program, success_compiler, catalog, success_mutation)
    success_request = {
        "schema": "cps.connected-request", "schema_version": "1.0.0",
        "executor_manifest_digest": executor_manifest_digest(executor), "executor_manifest": executor,
        "mutation_request": success_mutation_request, "compiler_manifest": success_compiler,
    }
    success_request_hash = connected_request_hash(success_request)
    success_applied = apply_mutation(
        success_program, success_mutation, [], success_mutation_request["mutation_choice_catalog"], catalog,
        artifact_hash("cps.mutation-application-request/v1", success_mutation_request),
    )
    if success_applied["status"] != "success" or success_applied["program"] != success_program:
        raise AssertionError("the connected compiler adapter mutation must be canonical identity")
    project = _json(compiler_dir / "gen0b_melody_project.json")
    evidence = _json(compiler_dir / "gen0b_compiler_evidence.json")
    melody = _json(compiler_dir / "chord_member_melody_report.json")
    report = _json(compiler_dir / "gen0b_compile_report.json")
    receipt = _json(compiler_dir / "gen0b_charge_receipt.json")
    if report["receipt"] != receipt:
        raise AssertionError("compiler report receipt differs from its authority file")
    success_output = {
        "schema": "cps.connected-logical-output", "schema_version": "1.0.0",
        "request_hash": success_request_hash, "status": "success",
        "resulting_program": success_program, "mutation_impact": success_applied["impact"],
        "mutation_receipt": success_applied["receipt"], "project": project,
        "compiler_evidence": evidence, "melody_report": melody, "compile_report": report,
        "lineage_index": None, "error": None,
    }
    success_output["logical_output_hash"] = logical_output_hash(success_output)
    root_stream = _json(compiler_dir / "gen0b_root_opcode_stream.json")
    child_streams = {
        "chord_query": _json(compiler_dir / "gen0b_chord_opcode_stream.json"),
        "progression_query": _json(compiler_dir / "gen0b_progression_opcode_stream.json"),
    }
    bundle = {
        "schema": "cps.opcode-stream-bundle", "schema_version": "1.0.0", "root": root_stream,
        "children": [
            {"kind": child["kind"], "query_id": child["query_id"], "stream": child_streams[child["kind"]]}
            for child in receipt["children"]
        ],
    }
    from .connected_oracle import opcode_bundle_hash
    bundle["bundle_hash"] = opcode_bundle_hash(bundle)
    success_entry = build_cache_entry(success_request, success_output, bundle)
    success_corrupt = deepcopy(success_entry)
    success_corrupt["opcode_stream_bundle"]["children"][0]["stream"]["stream_hash"] = "sha256:" + "0" * 64
    success_corrupt["opcode_stream_bundle"]["bundle_hash"] = opcode_bundle_hash(success_corrupt["opcode_stream_bundle"])
    success_corrupt["opcode_stream_bundle_hash"] = success_corrupt["opcode_stream_bundle"]["bundle_hash"]
    from .connected_oracle import cache_entry_hash
    success_corrupt["entry_hash"] = cache_entry_hash(success_corrupt)
    success_paths = {
        "request": OUT / "gen0b_identity_request.json", "output": OUT / "gen0b_identity_cold_output.json",
        "bundle": OUT / "gen0b_identity_opcode_bundle.json", "entry": OUT / "gen0b_identity_cache_entry.json",
        "corrupt": OUT / "gen0b_identity_corrupt_entry.json",
    }
    for key, value in (("request", success_request), ("output", success_output), ("bundle", bundle),
                       ("entry", success_entry), ("corrupt", success_corrupt)):
        _write(success_paths[key], value)
    success_case = {
        "case_id": "gen0b_identity_success", "pipeline": "connected_candidate",
        "connected_request_hash": success_request_hash, "request": _file(success_paths["request"]),
        "cold_output": _file(success_paths["output"]), "opcode_stream_bundle": _file(success_paths["bundle"]),
        "valid_cache_entry": _file(success_paths["entry"]),
        "corruption": {"id": "child_opcode_hash_zero", "kind": "raw_fixture",
                       "corrupted_entry": _file(success_paths["corrupt"]), "expected_first_failed_check": "opcode_hash"},
    }

    cases = sorted([failure_case, success_case], key=lambda item: item["case_id"].encode())
    manifest = {
        "schema": "cps.connected-fixture-manifest",
        "schema_version": "1.0.0",
        "cases": cases,
        "independent_generator": "songprogram_conformance.build_connected_fixtures/v1",
        "independent_verifier": "songprogram_conformance.connected_oracle/v1",
    }
    manifest["manifest_hash"] = artifact_hash("cps.connected-fixture-manifest/v1", manifest)
    manifest_path = OUT / "manifest.json"
    _write(manifest_path, manifest)

    output_by_id = {failure_case["case_id"]: output, success_case["case_id"]: success_output}
    request_hash_by_id = {failure_case["case_id"]: request_hash, success_case["case_id"]: success_request_hash}
    total_charge = receipt["usage"]["total_logical_units"]
    matrix_cases = []
    for scenario, ceiling in (("global_budget_exact", total_charge), ("global_budget_short_by_one", total_charge - 1)):
        case_ids = [item["case_id"] for item in cases]
        pairs = [{"case_id": cid, "connected_request_hash": request_hash_by_id[cid]} for cid in case_ids]
        input_hash = semantic_input_hash(pairs, ceiling)
        request_core = {"schema": "cps.connected-runner-request", "schema_version": "1.0.0",
                        "contract": "cps-connected-runner/v1", "fixture_set_hash": manifest["manifest_hash"],
                        "case_ids": case_ids, "semantic_input_hash": input_hash,
                        "global_compile_logical_ceiling": ceiling}
        request_core_path = OUT / f"{scenario}_request_core.json"; _write(request_core_path, request_core)
        cells=[]; expected_result=None; expected_stdout=None
        outputs=[(cid,output_by_id[cid]) for cid in case_ids]
        for workers in (1,2,4,8):
            for mode in ("cold","hit","corrupt"):
                # A batch-wide corrupt cell selects the success corruption; the
                # failure case has no compile bundle and remains semantically identical.
                corruption_id="child_opcode_hash_zero" if mode=="corrupt" else None
                wire={**request_core,"execution":{"worker_count":workers,"cache_mode":mode,"corruption_id":corruption_id}}
                wire_path=OUT/"runner_requests"/f"{scenario}_w{workers}_{mode}.json"; _write(wire_path,wire)
                result=build_runner_result(wire,outputs); stdout=canonical_lf(result)
                if expected_result is None:
                    expected_result,expected_stdout=result["result_hash"],raw_hash(stdout)
                    _write(OUT/f"{scenario}_expected.json",result)
                if result["result_hash"]!=expected_result or raw_hash(stdout)!=expected_stdout: raise AssertionError("matrix parity")
                cells.append({"worker_count":workers,"cache_mode":mode,"corruption_id":corruption_id,
                              "request":_file(wire_path),"expected_exit_code":0})
        matrix_cases.append({"case_id":scenario,"pipeline":"connected_candidate","request_core":_file(request_core_path),
                             "semantic_input_hash":input_hash,"semantic_request_hash":semantic_runner_request_hash({**request_core,"execution":{}}),
                             "expected_result_hash":expected_result,"expected_stdout_sha256":expected_stdout,"cells":cells})
    matrix = {
        "schema": "cps.connected-runner-matrix",
        "schema_version": "1.0.0",
        "fixture_set_hash": manifest["manifest_hash"],
        "cases": sorted(matrix_cases, key=lambda item: item["case_id"].encode()),
    }
    matrix["matrix_hash"] = artifact_hash("cps.connected-runner-matrix/v1", matrix)
    _write(OUT / "matrix.json", matrix)


if __name__ == "__main__":
    build()
