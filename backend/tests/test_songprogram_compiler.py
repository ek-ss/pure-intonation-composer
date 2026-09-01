from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.compiler import CompileError, CompilerIdentity, build_lineage_index, compile_direct_sp0
from app.songprogram.renderer import render_reference
from app.songprogram.search import canonical_bytes


PACK = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "pack"
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
