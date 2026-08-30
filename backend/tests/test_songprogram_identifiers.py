from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from songprogram_conformance.identifiers import (
    budget_profile_digest,
    compiler_build_id,
    event_id,
    lattice_domain_hash,
    program_hash,
    project_artifact_hash,
    semantic_address,
)
from songprogram_conformance.canonical import canonical_bytes
from songprogram_conformance.build_project_goldens import build_triad


PACK = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "pack"


def _load(name: str) -> dict[str, Any]:
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def test_minimal_direct_identity_sidecar() -> None:
    program = _load("minimal_direct_song_program.json")
    project = _load("minimal_direct_project.json")
    expected = _load("minimal_direct_expected.json")
    address = semantic_address("sec_a", "real_a", 0, "pitch_a", 0, 0)
    assert address == expected["semantic_address"]
    assert program_hash(program) == expected["program_hash"]
    assert lattice_domain_hash(project["lattice"]) == expected["domain_hash"]
    assert event_id(project["events"][0]) == expected["event_id"]
    assert project_artifact_hash(project) == expected["artifact_hash"]


def test_compiler_manifest_identity_is_content_derived() -> None:
    manifest = _load("compiler_manifest_sp0.json")
    assert budget_profile_digest(manifest["budget_profile"]) == manifest["budget_profile"]["digest"]
    assert compiler_build_id(manifest) == manifest["build_id"]


def test_cache_entry_key_value_and_receipt_hashes_are_recomputable() -> None:
    entry = _load("cache_entry_major_no_solution.json")
    query_path = PACK.parents[1] / "goldens" / "adversarial_independent_nearest_query.json"
    query = json.loads(query_path.read_text(encoding="utf-8"))
    query_hash = "sha256:" + hashlib.sha256(canonical_bytes(query)).hexdigest()
    assert entry["key"]["canonical_query_hash"] == query_hash
    key_core = {key: value for key, value in entry["key"].items() if key != "cache_key_hash"}
    key_hash = "sha256:" + hashlib.sha256(
        b"cps.chord-cache-key/v1\0" + canonical_bytes(key_core)
    ).hexdigest()
    assert entry["key"]["cache_key_hash"] == key_hash
    value_core = {key: value for key, value in entry["value"].items() if key != "canonical_value_hash"}
    value_hash = "sha256:" + hashlib.sha256(canonical_bytes(value_core)).hexdigest()
    assert entry["value"]["canonical_value_hash"] == value_hash
    empty_stream_hash = "sha256:" + hashlib.sha256(canonical_bytes([])).hexdigest()
    assert entry["receipt"]["opcode_stream_hash"] == empty_stream_hash


def test_resolved_triad_project_is_reproducible_from_independent_oracle() -> None:
    project, expected = build_triad()
    stored_project = (PACK / "resolved_triad_project.json").read_bytes()
    stored_expected = (PACK / "resolved_triad_expected.json").read_bytes()
    assert canonical_bytes(project) + b"\n" == stored_project
    assert canonical_bytes(expected) + b"\n" == stored_expected
