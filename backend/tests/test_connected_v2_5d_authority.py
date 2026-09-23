from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from app.songprogram.connected import (
    ConnectedCache, ConnectedExecutionError, cache_key, execute_connected,
    validate_connected_request,
)
from songprogram_conformance.connected_oracle import (
    cache_key as oracle_cache_key, connected_request_hash, executor_manifest_digest,
    validate_cache_entry,
)
from songprogram_conformance.verify_connected_v2_5d_fixtures import verify

FIXTURES = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "connected_v2_5d"
SCHEMAS = FIXTURES.parents[1] / "schemas"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_sealed_authority_and_production_cold_hit_corrupt_parity() -> None:
    verify()
    request, output, bundle, entry = (load(name) for name in (
        "connected_request.json", "connected_output.json", "opcode_bundle.json", "cache_entry.json"))
    assert cache_key(request) == oracle_cache_key(connected_request_hash(request), executor_manifest_digest(request["executor_manifest"]))
    assert validate_cache_entry(entry, request) == (output, bundle)
    cache = ConnectedCache()
    cold = execute_connected(request, None, cache)
    hit = execute_connected(request, None, cache)
    assert (cold.output, cold.opcode_stream_bundle) == (output, bundle)
    assert (hit.output, hit.opcode_stream_bundle) == (output, bundle)
    assert cold.telemetry["recomputations"] == 1 and hit.telemetry["hits"] == 1
    corrupted = deepcopy(entry)
    corrupted["entry_hash"] = "sha256:" + "0" * 64
    corrupt_cache = ConnectedCache()
    corrupt_cache.preseed_raw(request, corrupted)
    recomputed = execute_connected(request, None, corrupt_cache)
    assert (recomputed.output, recomputed.opcode_stream_bundle) == (output, bundle)
    assert recomputed.telemetry["corrupt_entries"] == 1


def test_version_mismatch_fails_closed_and_v1_cache_cannot_cross_domains() -> None:
    request = load("connected_request.json")
    legacy = json.loads((FIXTURES.parent / "connected" / "gen0b_identity_request.json").read_text())
    assert cache_key(request) != cache_key(legacy)
    mismatched = deepcopy(request)
    mismatched["schema_version"] = "1.0.0"
    with pytest.raises(ConnectedExecutionError, match="EXECUTOR_MANIFEST_VERSION_MISMATCH"):
        validate_connected_request(mismatched)
    unsupported = deepcopy(request)
    unsupported["schema_version"] = "3.0.0"
    with pytest.raises(ConnectedExecutionError, match="CONNECTED_REQUEST_INVALID"):
        validate_connected_request(unsupported)
    wrong_digest = deepcopy(request)
    wrong_digest["executor_manifest_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ConnectedExecutionError, match="EXECUTOR_MANIFEST_DIGEST_MISMATCH"):
        validate_connected_request(wrong_digest)


def test_5d_schemas_accept_sealed_artifacts_and_reject_invalid_pointers_and_profiles() -> None:
    def schema(name: str) -> dict:
        return json.loads((SCHEMAS / name).read_text())

    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for path in SCHEMAS.glob("*.schema.json")
        if (document := json.loads(path.read_text()))
    )
    output = load("connected_output.json")
    project = deepcopy(output["project"])
    project_schema = Draft202012Validator(schema("arrangement_project_1_3_5d.schema.json"), registry=registry)
    assert project_schema.is_valid(project)
    project["material_instances"][0]["source_program_path"] = "/realizations/~2"
    assert not project_schema.is_valid(project)

    report = deepcopy(output["compile_report"])
    report_schema = Draft202012Validator(schema("compile_report_1_1_5d.schema.json"), registry=registry)
    assert report_schema.is_valid(report)
    report["receipt"]["budget_profile_id"] = "gen0-progression-exact-v1"
    assert not report_schema.is_valid(report)
    legacy_receipt = schema("charge_receipt_1_1.schema.json")
    assert legacy_receipt["properties"]["budget_profile_id"]["const"] == "gen0-progression-exact-v1"
