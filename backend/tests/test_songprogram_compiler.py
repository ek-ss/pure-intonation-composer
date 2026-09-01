from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.compiler import CompileError, CompilerIdentity, compile_direct_sp0
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
    program["chord_intents"].append({"id": "unsupported"})
    with pytest.raises(CompileError, match="UNSUPPORTED_COMPILER_SLICE"):
        compile_direct_sp0(program, IDENTITY)


def test_canonical_project_bytes_are_stable() -> None:
    project = compile_direct_sp0(_load("minimal_direct_song_program.json"), IDENTITY)
    assert canonical_bytes(project).endswith(b"\n")
