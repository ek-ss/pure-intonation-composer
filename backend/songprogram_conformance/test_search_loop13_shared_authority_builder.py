from __future__ import annotations

import json

from .search_loop13_shared_authority_builder import (
    CONTRACT_FILES,
    DOCS,
    SCHEMA_FILES,
    SCHEMAS,
    NON_NULL_ARTIFACTS,
    NULL_ARTIFACTS,
    contract_bindings,
    schema_bindings,
)


def test_shared_authority_binds_all_context_raw_schemas() -> None:
    context_schema = json.loads((SCHEMAS / "search_loop_13_context.schema.json").read_bytes())
    required = context_schema["properties"]["schema_hashes"]["required"]
    assert len(required) == 73
    assert set(SCHEMA_FILES) == set(required)
    assert all((SCHEMAS / name).is_file() for name in SCHEMA_FILES.values())
    bindings = schema_bindings()
    assert all(binding["hash"].startswith("sha256:") for binding in bindings.values())
    assert all("0000000000000000" not in binding["hash"] for binding in bindings.values())


def test_shared_authority_binds_exact_contract_bytes() -> None:
    assert set(CONTRACT_FILES) == {
        "mutation_application",
        "connected_execution",
        "fallback_sampler",
        "broad_prior_production",
    }
    assert all((DOCS / name).is_file() for name in CONTRACT_FILES.values())
    bindings = contract_bindings()
    assert bindings["fallback_sampler"] == bindings["broad_prior_production"]


def test_owner_artifact_nullability_partition_is_exact() -> None:
    context_schema = json.loads((SCHEMAS / "search_loop_13_context.schema.json").read_bytes())
    required = set(context_schema["$defs"]["artifacts"]["required"])
    assert len(NON_NULL_ARTIFACTS) == 27
    assert len(NULL_ARTIFACTS) == 5
    assert set(NON_NULL_ARTIFACTS).isdisjoint(NULL_ARTIFACTS)
    assert set(NON_NULL_ARTIFACTS) | set(NULL_ARTIFACTS) == required


def test_search_loop13_binds_noncyclic_calibration_decision_schema() -> None:
    assert SCHEMA_FILES["calibration_decision"] == "calibration_decision_1_1.schema.json"
    schema = json.loads((SCHEMAS / SCHEMA_FILES["calibration_decision"]).read_bytes())
    assert schema["properties"]["schema_version"]["const"] == "1.1.0"
    assert "genre_intent_hash" not in schema["properties"]
    assert "evaluation_manifest_hash" not in schema["properties"]
