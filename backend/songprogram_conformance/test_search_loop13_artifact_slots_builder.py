from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from .search_loop13_artifact_slots_builder import build_slot_index, write_slot_index
from .search_loop13_fixture_oracle import artifact_hash
from .search_loop13_shared_authority_builder import NON_NULL_ARTIFACTS, NULL_ARTIFACTS


FIXTURE = (
    Path(__file__).with_name("fixtures")
    / "search_loop_13"
    / "shared_authority"
    / "artifact_slot_index.json"
)


def test_all_32_artifact_slots_are_materialized_and_authenticated() -> None:
    index = build_slot_index()
    slots = index["artifacts"]
    assert len(slots) == 32
    assert index["non_null_slot_count"] == 27
    assert index["null_slot_count"] == 5
    assert {name for name, value in slots.items() if value is not None} == set(NON_NULL_ARTIFACTS)
    assert {name for name, value in slots.items() if value is None} == set(NULL_ARTIFACTS)
    for name in NON_NULL_ARTIFACTS:
        binding = slots[name]
        artifact_bytes = base64.b64decode(binding["artifact_bytes_base64"])
        assert json.loads(artifact_bytes) == binding["document"]
        schema_bytes = base64.b64decode(binding["schema_bytes_base64"])
        assert binding["schema_hash"] == "sha256:" + hashlib.sha256(schema_bytes).hexdigest()
        assert binding["kind"] == name
    assert index["index_hash"] == artifact_hash(index, "index_hash")


def test_checked_in_slot_index_matches_builder(tmp_path) -> None:
    generated = tmp_path / "index.json"
    write_slot_index(generated)
    assert FIXTURE.read_bytes() == generated.read_bytes()
