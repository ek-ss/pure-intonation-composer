"""Read-only verification of the independent connected 5D authority corpus."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .canonical import canonical_bytes
from .connected_oracle import (
    artifact_hash, cache_entry_hash, connected_request_hash, executor_manifest_digest,
    logical_output_hash, opcode_bundle_hash, raw_hash, validate_cache_entry,
)
from .search_decision_oracle import artifact_hash as decision_hash
from .search_loop13_shared_authority_builder import SCHEMA_FILES
from .build_connected_v2_5d_fixtures import EXECUTOR_SCHEMAS, OVERRIDES
from .verify_gen0b_5d_fixtures import verify as verify_five_d

ROOT = Path(__file__).parent
OUT = ROOT / "fixtures" / "connected_v2_5d"
FIVE_D = ROOT / "fixtures" / "compiler_v2_5d"
SCHEMAS = ROOT / "schemas"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> None:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    verify_five_d()
    index = load(OUT / "suite_index.json")
    assert index["generator_identity"] == "cps-independent-connected-v2-5d-oracle/1.0.0"
    assert index["contract"] == "cps-connected-v2-5d-authoritative/v1"
    assert index["suite_hash"] == artifact_hash("cps.connected-v2-5d-fixture-suite-index/v1", index, omit="suite_hash")
    assert set(index["files"]) == set(index["file_sha256"])
    assert set(index["files"]) == {p.name for p in OUT.glob("*.json") if p.name != "suite_index.json"}
    for name, digest in index["file_sha256"].items():
        payload = (OUT / name).read_bytes()
        assert digest == raw_hash(payload)
        assert payload == canonical_bytes(json.loads(payload)) + b"\n"
    for name, digest in index["schema_sha256"].items():
        assert digest == raw_hash((SCHEMAS / name).read_bytes())

    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for path in SCHEMAS.glob("*.schema.json")
        if (schema := load(path))
    )
    artifacts = {
        "run_context.json": "search_loop_13_context_2_0.schema.json",
        "connected_request.json": "connected_request_2_0.schema.json",
        "connected_output.json": "connected_logical_output_2_0.schema.json",
        "opcode_bundle.json": "opcode_stream_bundle.schema.json",
        "cache_entry.json": "connected_cache_entry_2_0.schema.json",
    }
    for name, schema_name in artifacts.items():
        validator = Draft202012Validator(load(SCHEMAS / schema_name), registry=registry)
        errors = list(validator.iter_errors(load(OUT / name)))
        assert not errors, [(list(error.path), error.message) for error in errors]

    context, request, output, bundle, entry = (
        load(OUT / name) for name in artifacts
    )
    run = context["run_manifest"]
    assert context["run_hash"] == decision_hash(run)
    assert context["context_hash"] == decision_hash(context, "context_hash")
    assert set(context["schema_hashes"]) == set(SCHEMA_FILES)
    for key, name in {**SCHEMA_FILES, **OVERRIDES}.items():
        binding = context["schema_hashes"][key]
        assert base64.b64decode(binding["bytes_base64"]) == (SCHEMAS / name).read_bytes()
        assert binding["hash"] == raw_hash((SCHEMAS / name).read_bytes())
    for key in run:
        if key.endswith("_schema_hash"):
            slot = key.removesuffix("_schema_hash")
            expected = (raw_hash((SCHEMAS / "search_loop_13_context_2_0.schema.json").read_bytes())
                        if slot == "search_loop_context" else context["schema_hashes"][slot]["hash"])
            assert run[key] == expected
    for key, binding in context["schema_hashes"].items():
        assert binding["hash"] == raw_hash(base64.b64decode(binding["bytes_base64"]))
    for binding in context["contract_hashes"].values():
        assert binding["hash"] == raw_hash(base64.b64decode(binding["bytes_base64"]))
    for binding in context["artifacts"].values():
        if binding is not None:
            assert binding["schema_hash"] == raw_hash(base64.b64decode(binding["schema_bytes_base64"]))
            assert json.loads(base64.b64decode(binding["artifact_bytes_base64"])) == binding["document"]
    compiler = request["compiler_manifest"]
    executor = request["executor_manifest"]
    assert context["artifacts"]["executor_manifest"]["document"] == executor
    assert executor["schema_hashes"] == {key: raw_hash((SCHEMAS / name).read_bytes())
                                          for key, name in EXECUTOR_SCHEMAS.items()}
    assert context["artifacts"]["compiler_manifest"]["document"] == compiler
    assert run["compiler_manifest_hash"] == artifact_hash("cps.compiler-manifest/v2.0", compiler)
    assert run["mutation_schema_hash"] == context["schema_hashes"]["mutation"]["hash"]
    assert request["mutation_request"]["run_manifest_hash"] == context["run_hash"]
    assert request["mutation_request"]["context_hash"] == context["context_hash"]
    assert request["executor_manifest_digest"] == executor_manifest_digest(request["executor_manifest"])
    assert output["request_hash"] == connected_request_hash(request)
    assert output["logical_output_hash"] == logical_output_hash(output)
    assert bundle["bundle_hash"] == opcode_bundle_hash(bundle)
    assert entry["entry_hash"] == cache_entry_hash(entry)
    assert validate_cache_entry(entry, request) == (output, bundle)
    golden = {"project": "gen0b_melody_project.json", "compiler_evidence": "gen0b_compiler_evidence.json",
              "melody_report": "chord_member_melody_report.json", "compile_report": "gen0b_compile_report.json",
              "resulting_program": "gen0b_melody_song_program.json"}
    for key, name in golden.items():
        assert output[key] == load(FIVE_D / name)
    expected = {"run_hash": context["run_hash"], "context_hash": context["context_hash"],
                "compiler_manifest_hash": run["compiler_manifest_hash"],
                "executor_manifest_digest": request["executor_manifest_digest"],
                "connected_request_hash": output["request_hash"],
                "logical_output_hash": output["logical_output_hash"], "cache_entry_hash": entry["entry_hash"],
                "opcode_bundle_hash": bundle["bundle_hash"]}
    assert index["expected_hashes"] == expected


if __name__ == "__main__":
    verify()
