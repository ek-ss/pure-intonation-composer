"""Independent verifier for the authoritative five-dimensional GEN0-B suite.

This module deliberately imports no production ``app.songprogram`` module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .canonical import canonical_bytes
from .gen0b_melody_oracle import artifact_hash, progression_result
from .identifiers import (
    budget_profile_digest,
    compiler_build_id,
    program_hash,
    project_artifact_hash,
)

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures" / "compiler_v2_5d"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def verify() -> None:
    suite = _load("gen0b_melody_fixture_set.json")
    assert suite["authority_status"] == "authoritative"
    assert suite["generator_identity"] == "cps-independent-gen0b-5d-oracle/1.0.0"
    assert set(suite["files"]) == set(suite["file_sha256"])
    for name in suite["files"]:
        assert suite["file_sha256"][name] == "sha256:" + hashlib.sha256(
            (FIXTURES / name).read_bytes()
        ).hexdigest()
    for name, expected in suite["schema_sha256"].items():
        assert expected == "sha256:" + hashlib.sha256(
            (ROOT / "schemas" / name).read_bytes()
        ).hexdigest()
    core = {key: value for key, value in suite.items() if key != "suite_hash"}
    assert suite["suite_hash"] == artifact_hash(
        "cps.gen0b-5d-fixture-suite-index/v1", core
    )

    program = _load("gen0b_melody_song_program.json")
    project = _load("gen0b_melody_project.json")
    manifest = _load("gen0b_compiler_manifest.json")
    query = _load("gen0b_progression_query.json")
    result = _load("gen0b_progression_result.json")
    evidence = _load("gen0b_compiler_evidence.json")
    melody = _load("chord_member_melody_report.json")
    root = _load("gen0b_root_opcode_stream.json")
    assert program["schema_version"] == "0.2.0"
    assert project["schema_version"] == "1.3.0"
    assert manifest["schema_version"] == "2.0.0"
    assert query["schema_version"] == "2.0.0"
    assert evidence["schema_version"] == "2.0.0"
    assert melody["schema_version"] == "2.0.0"
    assert len(program["lattice"]["generators"]) == 5
    assert progression_result(query) == result
    assert evidence["source_program_hash"] == program_hash(program)
    assert evidence["project_hash"] == project_artifact_hash(project)
    assert manifest["budget_profile"]["digest"] == budget_profile_digest(
        manifest["budget_profile"]
    )
    assert manifest["build_id"] == compiler_build_id(manifest)
    assert suite["expected_hashes"] == {
        "project_hash": project_artifact_hash(project),
        "evidence_hash": evidence["evidence_hash"],
        "melody_report_hash": melody["report_hash"],
        "root_opcode_stream_hash": root["stream_hash"],
    }
    assert root["stream_hash"] == artifact_hash(
        "cps.logical-opcode-stream/v1",
        {key: value for key, value in root.items() if key != "stream_hash"},
    )
    assert hashlib.sha256(canonical_bytes(result)).digest()

    cases = _load("gen0b_5d_negative_cases.json")["cases"]
    assert [case["expected_error"] for case in cases] == [
        "VECTOR_DIMENSION_MISMATCH",
        "GEN0B_DOMAIN_LIMIT_EXCEEDED",
        "GEN0B_DOMAIN_LIMIT_EXCEEDED",
    ]
    limits = manifest["budget_profile"]["domain_limits"]
    assert cases[0]["domain"]["dimensions"] > limits["dimensions"]
    assert cases[1]["domain"]["coordinate_cardinality"] > limits["coordinate_cardinality"]
    assert cases[2]["domain"]["placed_cardinality"] > limits["placed_cardinality"]


if __name__ == "__main__":
    verify()
