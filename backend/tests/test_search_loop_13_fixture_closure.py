from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_fixture_case_binds_all_authority_roots() -> None:
    schema = load("search_loop_13_fixture_case.schema.json")
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "schema", "schema_version", "case_id", "root_seed", "inputs",
        "policies", "budgets", "stop_branch", "expected", "case_hash",
    ]
    expected = schema["$defs"]["expected"]
    assert expected["required"] == [
        "transcript_root_hash", "cas_index_hash", "cas_index_schema_hash",
        "cache_publication_index_hash", "final_checkpoint_hash",
        "audio_pcm_assets",
    ]
    assert schema["$defs"]["input"]["required"] == [
        "role", "path", "raw_file_sha256", "artifact_hash", "schema_hash",
    ]


def test_archive_snapshots_close_round_before_and_after() -> None:
    snapshot = load("archive_heads_snapshot.schema.json")
    assert "stage" in snapshot["required"]
    assert snapshot["properties"]["stage"]["enum"] == ["round_before", "round_after"]
    text = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "`stage=round_before`" in text
    assert "`stage=round_after`" in text
    assert "archive_heads_before_hash` and `archive_heads_after_hash` MUST" in text


def test_cache_publication_index_is_closed_ordered_root() -> None:
    index = load("cache_publication_index.schema.json")
    assert index["additionalProperties"] is False
    assert index["required"] == ["schema", "schema_version", "run_hash", "publications", "index_hash"]
    row = index["$defs"]["publication"]
    assert row["additionalProperties"] is False
    assert row["required"] == ["coordinate", "kind", "request_hash", "entry_hash"]
    run = load("search_run_manifest_1_3.schema.json")
    context = load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    assert "cache_publication_index_schema_hash" in run["required"]
    assert "cache_publication_index" in context["required"]


def test_cas_index_is_closed_runtime_bound_inventory() -> None:
    index = load("search_loop_13_cas_index.schema.json")
    assert index["additionalProperties"] is False
    assert index["required"] == ["schema", "schema_version", "run_hash", "entries", "index_hash"]
    entry = index["$defs"]["entry"]
    assert entry["required"] == ["locator", "content_kind", "artifact_hash", "schema_hash", "byte_length"]
    assert entry["properties"]["locator"]["oneOf"] == [
        {"$ref": "#/$defs/pathLocator"}, {"$ref": "#/$defs/roleLocator"}
    ]
    run = load("search_run_manifest_1_3.schema.json")
    context = load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    assert "cas_index_schema_hash" in run["required"]
    assert "cas_index" in context["required"]
    text = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "artifact_hash raw digest bytes" in text
    assert "reachable closure, not JSON Schema alone" in text
