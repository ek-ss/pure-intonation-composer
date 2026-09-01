from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.compiler import CompilerIdentity, compile_direct_sp0
from app.songprogram.validator import ProjectValidationError, validate_project


PACK = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "pack"


def _load(name: str) -> dict[str, Any]:
    return json.loads((PACK / name).read_text())


def _mutate(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    parts = [part.replace("~1", "/").replace("~0", "~") for part in operation["pointer"].split("/")[1:]]
    target: Any = result
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    key = parts[-1]
    if isinstance(target, list):
        target[int(key)] = operation["value"]
    else:
        target[key] = operation["value"]
    return result


def test_direct_and_resolved_harmony_goldens_validate() -> None:
    validate_project(_load("minimal_direct_project.json"))
    validate_project(_load("resolved_triad_project.json"))


def test_compiled_drum_project_validates() -> None:
    program = _load("minimal_direct_song_program.json")
    program["tracks"] = [{"id": "drums", "role": "drums", "instrument_id": "drum_fixture_kit", "register_millicents": None, "maximum_polyphony": 8, "drum_map": {"kick": 36}}]
    program["materials"] = [program["materials"][0]]
    program["materials"][0]["steps"][0]["lane_id"] = "kick"
    program["realizations"][0].update({"id": "real_drums", "track_id": "drums", "material_id": "rhythm_a"})
    program["production"]["tracks"] = {"drums": {"gain_q": 8000, "pan_q": 0}}
    identity = CompilerIdentity("fixture-build", "fixture-resolver", "sha256:" + "0" * 64, "sha256:" + "0" * 64, "sha256:" + "0" * 64)
    validate_project(compile_direct_sp0(program, identity))


def test_all_declared_project_negative_cases_fail_exactly() -> None:
    fixture = _load("project_negative_cases.json")
    base = _load(fixture["base_path"])
    for case in fixture["cases"]:
        with pytest.raises(ProjectValidationError) as caught:
            validate_project(_mutate(base, case["mutation"]))
        expected = case["expected"]
        assert (caught.value.code, caught.value.stage, caught.value.pointer) == (expected["code"], expected["stage"], expected["pointer"]), case["id"]


def test_event_and_chord_identity_mutations_reject() -> None:
    direct = _load("minimal_direct_project.json")
    direct["events"][0]["id"] = "ev_aaaaaaaaaaaaaaaaaaaa"
    with pytest.raises(ProjectValidationError, match="HASH_MISMATCH"):
        validate_project(direct)
    triad = _load("resolved_triad_project.json")
    triad["resolved_chords"][0]["exact_ratios"][1] = "6/5"
    with pytest.raises(ProjectValidationError, match="PITCH_EQUATION_MISMATCH"):
        validate_project(triad)
