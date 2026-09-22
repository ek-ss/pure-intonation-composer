from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.compiler import (
    CompileError,
    CompilerIdentity,
    build_lineage_index,
    compile_connected_gen0b,
    compile_direct_sp0,
    compile_sp0,
    compile_gen0b,
    compile_gen0b_report,
    initial_material_lineage_seeds,
)
from app.songprogram.renderer import render_reference
from app.songprogram.search import canonical_bytes
from songprogram_conformance.identifiers import budget_profile_digest, compiler_build_id


PACK = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "pack"
COMPILER_FIXTURES = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "compiler"
IDENTITY = CompilerIdentity(
    build_id="fixture-build",
    resolver_build_id="fixture-resolver",
    resolver_profile_hash="sha256:" + "0" * 64,
    budget_profile_digest="sha256:" + "0" * 64,
    instrument_catalog_digest="sha256:" + "0" * 64,
)


def _load(name: str) -> dict[str, Any]:
    return json.loads((PACK / name).read_text())


def test_direct_compiler_matches_authoritative_project_golden() -> None:
    assert compile_direct_sp0(_load("minimal_direct_song_program.json"), IDENTITY) == _load(
        "minimal_direct_project.json"
    )


def test_texture_role_uses_direct_pitch_lowering_semantics() -> None:
    program = _load("minimal_direct_song_program.json")
    program["tracks"][0]["role"] = "texture"
    project = compile_sp0(program, IDENTITY)
    assert project["tracks"][0]["role"] == "texture"
    assert project["events"]


def test_song_program_0_2_compiles_a_five_dimension_variable_generator_domain() -> None:
    program = _load("minimal_direct_song_program.json")
    program["schema_version"] = "0.2.0"
    program["lattice"]["generators"] = ["3/1", "5/1", "7/1", "11/1", "13/1"]
    program["lattice"]["coordinate_bounds"] = [[0, 0]] * 5
    program["lattice"]["pitch_exploration"]["maximum_domain_points"] = 1
    program["form"][0]["tonal_center"] = [0] * 5
    program["materials"][1]["vectors"] = [[0] * 5]

    project = compile_sp0(program, IDENTITY)

    assert project["schema_version"] == "1.3.0"
    assert project["source_program"]["schema_version"] == "0.2.0"
    assert len(project["events"][0]["pitch_provenance"]["final_vector"]) == 5


def test_lineage_project_hash_is_version_separated() -> None:
    legacy = _load("minimal_direct_song_program.json")
    modern = json.loads(json.dumps(legacy))
    modern["schema_version"] = "0.2.0"
    legacy_project = compile_sp0(legacy, IDENTITY)
    modern_project = compile_sp0(modern, IDENTITY)

    assert build_lineage_index(legacy, legacy_project)["project_hash"] != build_lineage_index(
        modern, modern_project
    )["project_hash"]


def test_lattice_dimension_and_cardinality_fail_before_resolution() -> None:
    program = _load("minimal_direct_song_program.json")
    program["schema_version"] = "0.2.0"
    program["lattice"]["generators"] = ["3/1"] * 6
    program["lattice"]["coordinate_bounds"] = [[0, 0]] * 6
    program["form"][0]["tonal_center"] = [0] * 6
    program["materials"][1]["vectors"] = [[0] * 6]
    with pytest.raises(CompileError, match="VECTOR_DIMENSION_MISMATCH"):
        compile_sp0(program, IDENTITY)

    program = _load("minimal_direct_song_program.json")
    program["lattice"]["pitch_exploration"]["maximum_domain_points"] = 1
    with pytest.raises(CompileError, match="LATTICE_DOMAIN_TOO_LARGE"):
        compile_sp0(program, IDENTITY)


def test_direct_compiler_is_cross_process_and_hash_seed_invariant() -> None:
    source = (
        "import json; from pathlib import Path; "
        "from app.songprogram.compiler import CompilerIdentity,compile_direct_sp0; "
        f"p=json.loads(Path({str(PACK / 'minimal_direct_song_program.json')!r}).read_text()); "
        "i=CompilerIdentity('fixture-build','fixture-resolver','sha256:'+64*'0','sha256:'+64*'0','sha256:'+64*'0'); "
        "print(json.dumps(compile_direct_sp0(p,i),sort_keys=True,separators=(',',':')),end='')"
    )
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", source],
            cwd=PACK.parents[2],
            env=dict(os.environ, PYTHONHASHSEED=str(seed)),
        )
        for seed in range(4)
    ]
    assert len(set(outputs)) == 1


def test_velocity_and_instance_id_boundaries_are_deterministic() -> None:
    program = _load("minimal_direct_song_program.json")
    program["materials"][0]["steps"][0]["accent_q"] = 0
    project = compile_direct_sp0(program, IDENTITY)
    assert project["events"][0]["velocity"] == 1
    program["realizations"][0]["repeat"] = 2
    program["realizations"][0]["every_ticks"] = 960
    project = compile_direct_sp0(program, IDENTITY)
    assert [item["id"] for item in project["material_instances"]] == ["mi_a", "mi_a_1"]


def test_unsupported_harmony_is_a_typed_failure() -> None:
    program = _load("minimal_direct_song_program.json")
    program["materials"][1]["kind"] = "melody_intent"
    with pytest.raises(CompileError, match="UNSUPPORTED_COMPILER_SLICE"):
        compile_direct_sp0(program, IDENTITY)


def test_canonical_project_bytes_are_stable() -> None:
    project = compile_direct_sp0(_load("minimal_direct_song_program.json"), IDENTITY)
    assert canonical_bytes(project).endswith(b"\n")


def test_mutated_material_core_retains_initial_lineage_seed() -> None:
    initial = _load("minimal_direct_song_program.json")
    seeds = initial_material_lineage_seeds(initial)
    mutated = _load("minimal_direct_song_program.json")
    mutated["materials"][1]["register_delta"] = 1
    project = compile_direct_sp0(mutated, IDENTITY)

    retained = build_lineage_index(mutated, project, seeds)
    recomputed = build_lineage_index(mutated, project)
    pitch_instance = next(item for item in project["material_instances"] if item["material_id"] == "pitch_a")
    retained_record = next(item for item in retained["instances"] if item["material_instance_id"] == pitch_instance["id"])
    recomputed_record = next(item for item in recomputed["instances"] if item["material_instance_id"] == pitch_instance["id"])

    assert retained_record["lineage_hash"] == seeds["pitch_a"]["lineage_hash"]
    assert retained_record["lineage_root_hash"] == seeds["pitch_a"]["lineage_root_hash"]
    assert recomputed_record["lineage_hash"] != retained_record["lineage_hash"]


def _drum_program() -> dict[str, Any]:
    program = _load("minimal_direct_song_program.json")
    program["tracks"] = [{"id": "drums", "role": "drums", "instrument_id": "drum_fixture_kit", "register_millicents": None, "maximum_polyphony": 8, "drum_map": {"kick": 36}}]
    program["materials"] = [program["materials"][0]]
    program["materials"][0]["steps"][0]["lane_id"] = "kick"
    program["realizations"][0]["id"] = "real_drums"
    program["realizations"][0]["track_id"] = "drums"
    program["realizations"][0]["material_id"] = "rhythm_a"
    program["production"]["tracks"] = {"drums": {"gain_q": 8000, "pan_q": 0}}
    return program


def test_drum_compiler_lowers_and_renders_checked_in_asset() -> None:
    render_root = PACK.parents[1] / "fixtures" / "render"
    catalog_bytes = (render_root / "catalog.json").read_bytes()
    catalog_digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
    identity = CompilerIdentity("fixture-build", "fixture-resolver", "sha256:" + "0" * 64, "sha256:" + "0" * 64, catalog_digest)
    project = compile_direct_sp0(_drum_program(), identity)
    event = project["events"][0]
    assert (event["kind"], event["drum_note"], event["ratio"], event["pitch_provenance"]) == ("drum", 36, None, None)
    result = render_reference(project, catalog_bytes, lambda uri: (render_root / "assets" / f"{uri.rsplit('/', 1)[1]}.wav").read_bytes(), render_manifest_digest="sha256:" + "0" * 64, project_artifact_hash="sha256:" + "1" * 64)
    assert result.report["frame_count"] == 264


def test_drum_unmapped_lane_and_section_boundary_are_typed() -> None:
    program = _drum_program()
    program["materials"][0]["steps"][0]["lane_id"] = "snare"
    with pytest.raises(CompileError) as missing:
        compile_direct_sp0(program, IDENTITY)
    assert (missing.value.code, missing.value.pointer) == ("UNKNOWN_DRUM_LANE", "/materials/0/steps/0/lane_id")
    program = _drum_program()
    program["realizations"][0]["at_tick"] = 1800
    with pytest.raises(CompileError, match="EVENT_SECTION_OVERFLOW"):
        compile_direct_sp0(program, IDENTITY)


def test_single_harmony_matches_authoritative_triad_golden() -> None:
    manifest = _load("compiler_manifest_sp0.json")
    identity = CompilerIdentity(manifest["build_id"], manifest["resolver"]["build_id"], manifest["resolver"]["profile_hash"], manifest["budget_profile"]["digest"], manifest["instrument_catalog_digest"])
    actual = compile_direct_sp0(_load("minimal_triad_song_program.json"), identity)
    assert actual == _load("resolved_triad_project.json")


def test_five_dimension_harmony_uses_project_1_3_progression_path() -> None:
    manifest = _load("compiler_manifest_sp0.json")
    identity = CompilerIdentity(manifest["build_id"], manifest["resolver"]["build_id"], manifest["resolver"]["profile_hash"], manifest["budget_profile"]["digest"], manifest["instrument_catalog_digest"])
    program = _load("minimal_triad_song_program.json")
    program["schema_version"] = "0.2.0"
    program["lattice"]["generators"] += ["7/1", "11/1", "13/1"]
    program["lattice"]["coordinate_bounds"] += [[0, 0], [0, 0], [0, 0]]
    program["form"][0]["tonal_center"] += [0, 0, 0]
    for material in program["materials"]:
        if "root_anchors" in material:
            material["root_anchors"] = [vector + [0, 0, 0] for vector in material["root_anchors"]]

    project = compile_sp0(program, identity)

    assert project["schema_version"] == "1.3.0"
    assert all(len(chord["anchor_vector"]) == 5 for chord in project["resolved_chords"])
    assert all(
        len(offset) == 5
        for chord in project["resolved_chords"]
        for offset in chord["voice_offsets"]
    )


def test_gen0b_lowers_top_k_progression_and_chord_member_melody() -> None:
    manifest = json.loads((COMPILER_FIXTURES / "gen0b_compiler_manifest.json").read_text())
    identity = CompilerIdentity(
        manifest["build_id"], manifest["resolver"]["build_id"], manifest["resolver"]["profile_hash"],
        manifest["budget_profile"]["digest"], manifest["instrument_catalog_digest"],
    )
    program = json.loads((COMPILER_FIXTURES / "gen0b_melody_song_program.json").read_text())
    expected = json.loads((COMPILER_FIXTURES / "gen0b_melody_project.json").read_text())
    assert compile_direct_sp0(program, identity) == expected


def _gen0b_v2_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((COMPILER_FIXTURES / "gen0b_compiler_manifest.json").read_text())
    program = json.loads((COMPILER_FIXTURES / "gen0b_melody_song_program.json").read_text())
    manifest.update(
        schema_version="2.0.0",
        song_program_schema_versions=["0.2.0"],
        project_schema_version="1.3.0",
        progression_query_schema_version="2.0.0",
        gen0b_evidence_schema_version="2.0.0",
        melody_report_schema_version="2.0.0",
    )
    manifest["budget_profile"]["id"] = "gen0-progression-exact-v2"
    manifest["budget_profile"]["domain_limits"]["dimensions"] = 5
    manifest["budget_profile"]["digest"] = budget_profile_digest(manifest["budget_profile"])
    manifest["build_id"] = compiler_build_id(manifest)
    program["schema_version"] = "0.2.0"
    program["lattice"]["generators"] += ["7/1", "11/1", "13/1"]
    program["lattice"]["coordinate_bounds"] += [[0, 0], [0, 0], [0, 0]]
    for section in program["form"]:
        section["tonal_center"] += [0, 0, 0]
    for material in program["materials"]:
        if "vectors" in material:
            material["vectors"] = [vector + [0, 0, 0] for vector in material["vectors"]]
        if "root_anchors" in material:
            material["root_anchors"] = [
                vector + [0, 0, 0] for vector in material["root_anchors"]
            ]
    return program, manifest


def test_gen0b_v2_emits_five_dimension_evidence_and_melody_report() -> None:
    program, manifest = _gen0b_v2_inputs()

    connected = compile_connected_gen0b(program, manifest)

    assert connected["status"] == "success"
    assert connected["project"]["schema_version"] == "1.3.0"
    assert connected["compiler_evidence"]["schema_version"] == "2.0.0"
    assert connected["melody_report"]["schema_version"] == "2.0.0"
    assert all(
        run["query"]["schema_version"] == "2.0.0"
        for run in connected["compiler_evidence"]["progression_runs"]
    )
    assert all(
        len(binding["source_vector"]) == 5
        for binding in connected["melody_report"]["bindings"]
    )


def test_gen0b_chord_member_requires_one_active_member() -> None:
    manifest = json.loads((COMPILER_FIXTURES / "gen0b_compiler_manifest.json").read_text())
    identity = CompilerIdentity(
        manifest["build_id"], manifest["resolver"]["build_id"], manifest["resolver"]["profile_hash"],
        manifest["budget_profile"]["digest"], manifest["instrument_catalog_digest"],
    )
    program = json.loads((COMPILER_FIXTURES / "gen0b_melody_song_program.json").read_text())
    program["materials"][-1]["points"][0]["member"] = 7
    with pytest.raises(CompileError, match="MELODY_HARMONY_CONFLICT"):
        compile_direct_sp0(program, identity)


def test_gen0b_compile_report_receipt_evidence_and_opcode_streams_match_goldens() -> None:
    manifest = json.loads((COMPILER_FIXTURES / "gen0b_compiler_manifest.json").read_text())
    program = json.loads((COMPILER_FIXTURES / "gen0b_melody_song_program.json").read_text())
    artifacts = compile_gen0b(program, manifest)
    assert artifacts.project == json.loads((COMPILER_FIXTURES / "gen0b_melody_project.json").read_text())
    assert artifacts.report == json.loads((COMPILER_FIXTURES / "gen0b_compile_report.json").read_text())
    assert artifacts.evidence == json.loads((COMPILER_FIXTURES / "gen0b_compiler_evidence.json").read_text())
    assert artifacts.root_opcode_stream == json.loads((COMPILER_FIXTURES / "gen0b_root_opcode_stream.json").read_text())
    assert list(artifacts.child_opcode_streams) == [
        json.loads((COMPILER_FIXTURES / "gen0b_chord_opcode_stream.json").read_text()),
        json.loads((COMPILER_FIXTURES / "gen0b_progression_opcode_stream.json").read_text()),
    ]
    assert compile_gen0b_report(program, manifest) == artifacts.report


def test_compiler_lineage_index_records_identity_and_rotate_edges() -> None:
    program = _load("minimal_direct_song_program.json")
    program["realizations"][0]["repeat"] = 2
    program["realizations"][0]["every_ticks"] = 960
    project = compile_direct_sp0(program, IDENTITY)
    lineage = build_lineage_index(program, project)
    assert lineage["project_hash"] == "sha256:" + hashlib.sha256(b"fixture-build\0project/1.2.0\0" + json.dumps(project, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert [item["material_instance_id"] for item in lineage["instances"]] == ["mi_a", "mi_a_1"]
    assert lineage["transform_edges"] == [{"from_instance_id": "mi_a", "to_instance_id": "mi_a_1", "operation": "identity", "identity": True}]
    program["realizations"][0]["rhythm_transforms"] = [{"op": "rotate", "ticks": 120}]
    project = compile_direct_sp0(program, IDENTITY)
    assert build_lineage_index(program, project)["transform_edges"][0]["operation"] == "rotate_ticks:120"
