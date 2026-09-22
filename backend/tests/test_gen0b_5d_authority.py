from __future__ import annotations

import json
import copy
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.songprogram.compiler import CompileError, _gen0b_melody_report, compile_gen0b
from songprogram_conformance.verify_gen0b_5d_fixtures import verify


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "songprogram_conformance"
    / "fixtures"
    / "compiler_v2_5d"
)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _compile_hashes() -> tuple[str, str, str, str]:
    artifacts = compile_gen0b(
        _load("gen0b_melody_song_program.json"), _load("gen0b_compiler_manifest.json")
    )
    assert artifacts.project is not None and artifacts.evidence is not None
    melody = _gen0b_melody_report(_load("gen0b_melody_song_program.json"), artifacts)
    return (
        artifacts.evidence["project_hash"],
        artifacts.evidence["evidence_hash"],
        melody["report_hash"],
        artifacts.root_opcode_stream["stream_hash"],
    )


def test_independent_authority_and_production_parity() -> None:
    verify()
    expected = _load("gen0b_melody_fixture_set.json")["expected_hashes"]
    assert _compile_hashes() == (
        expected["project_hash"],
        expected["evidence_hash"],
        expected["melody_report_hash"],
        expected["root_opcode_stream_hash"],
    )


def test_worker_matrix_is_identical() -> None:
    baseline = _compile_hashes()
    for workers in (1, 2, 4, 8):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            assert set(executor.map(lambda _: _compile_hashes(), range(workers))) == {baseline}


def test_cross_process_hash_seed_is_identical() -> None:
    source = (
        "import json; from pathlib import Path; "
        "from app.songprogram.compiler import compile_gen0b,_gen0b_melody_report; "
        f"p=Path({str(FIXTURES)!r}); "
        "program=json.loads((p/'gen0b_melody_song_program.json').read_text()); "
        "manifest=json.loads((p/'gen0b_compiler_manifest.json').read_text()); "
        "a=compile_gen0b(program,manifest); m=_gen0b_melody_report(program,a); "
        "print(json.dumps([a.evidence['project_hash'],a.evidence['evidence_hash'],m['report_hash'],a.root_opcode_stream['stream_hash']]))"
    )
    outputs = {
        subprocess.check_output(
            [sys.executable, "-c", source],
            cwd=FIXTURES.parents[2],
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        for seed in ("0", "1", "7", "42")
    }
    assert len(outputs) == 1


def test_authoritative_negative_domain_boundaries() -> None:
    base = _load("gen0b_melody_song_program.json")
    manifest = _load("gen0b_compiler_manifest.json")
    cases = _load("gen0b_5d_negative_cases.json")["cases"]
    for case in cases:
        program = copy.deepcopy(base)
        if case["id"] == "dimension_6_rejected":
            program["lattice"]["generators"].append("17/1")
            program["lattice"]["coordinate_bounds"].append([0, 0])
            for section in program["form"]:
                section["tonal_center"].append(0)
            for material in program["materials"]:
                for field in ("vectors", "root_anchors"):
                    for vector in material.get(field, []):
                        vector.append(0)
        else:
            widths = [7, 6, 5, 5, 1] if case["id"] == "coordinate_cardinality_1050_rejected" else [7, 5, 5, 4, 1]
            program["lattice"]["coordinate_bounds"] = [
                [0, width - 1] for width in widths
            ]
            program["lattice"]["register_bounds"] = [0, 0] if widths[1] == 6 else [0, 5]
            program["lattice"]["pitch_exploration"]["maximum_domain_points"] = 65535
        with pytest.raises(CompileError) as failure:
            compile_gen0b(program, manifest)
        assert failure.value.code == case["expected_error"]


def test_manifest_budget_digest_and_schema_version_cannot_be_swapped() -> None:
    program = _load("gen0b_melody_song_program.json")
    manifest = _load("gen0b_compiler_manifest.json")
    tampered = copy.deepcopy(manifest)
    tampered["budget_profile"]["domain_limits"]["dimensions"] = 4
    with pytest.raises(CompileError, match="COMPILER_MANIFEST_INVALID"):
        compile_gen0b(program, tampered)

    legacy_program = copy.deepcopy(program)
    legacy_program["schema_version"] = "0.1.0"
    with pytest.raises(CompileError, match="GEN0B_SCHEMA_VERSION_UNSUPPORTED"):
        compile_gen0b(legacy_program, manifest)
