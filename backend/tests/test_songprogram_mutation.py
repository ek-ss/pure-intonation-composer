from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.mutation import (
    MutationError,
    apply_mutation_request,
    apply_mutations,
    program_hash,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "songprogram_conformance" / "fixtures"


def _program() -> dict:
    return json.loads((PACK / "pack" / "minimal_direct_song_program.json").read_text())


def _mutation(program: dict, operation: str, parameters: dict, scope: list[dict]) -> dict:
    return {"schema": "cps.mutation", "schema_version": "1.0.0", "mutation_id": "mut_aaaaaaaaaaaaaaaaaaaa", "base_program_hash": program_hash(program), "operation": operation, "declared_scope": scope, "parameters": parameters}


def test_rotate_is_atomic_and_inverse() -> None:
    program = _program()
    forward = _mutation(program, "rotate_rhythm", {"kind": "rotate_rhythm", "rhythm_id": "rhythm_a", "steps": 1}, [{"kind": "rhythm", "id": "rhythm_a"}])
    changed, _ = apply_mutations(program, [forward], [], {"entries": []}, {"entries": []}, "act_x")
    backward = copy.deepcopy(forward)
    backward["base_program_hash"] = program_hash(changed)
    backward["parameters"]["steps"] = -1
    restored, _ = apply_mutations(changed, [backward], [], {"entries": []}, {"entries": []}, "act_x")
    assert restored == program


def test_choice_and_lock_failures_are_typed() -> None:
    program = _program()
    mutation = _mutation(program, "replace_distribution_choice", {"kind": "replace_distribution_choice", "owner_kind": "material", "owner_id": "pitch_a", "field": "mapping", "choice_id": "choice_tnwjgh52rbcsot6geclq"}, [{"kind": "material", "id": "pitch_a"}])
    choices = json.loads((PACK / "search" / "mutation_choice_catalog.json").read_text())
    changed, _ = apply_mutations(program, [mutation], [], choices, {"entries": []}, "act_x")
    assert next(x for x in changed["materials"] if x["id"] == "pitch_a")["mapping"] == "cycle"
    with pytest.raises(MutationError, match="MUTATION_LOCKED"):
        apply_mutations(program, [mutation], [{"kind": "material", "id": "pitch_a"}], choices, {"entries": []}, "act_x")


def test_bad_second_mutation_keeps_caller_program_unchanged() -> None:
    program = _program()
    before = copy.deepcopy(program)
    mutation = _mutation(program, "rotate_rhythm", {"kind": "rotate_rhythm", "rhythm_id": "missing", "steps": 1}, [{"kind": "rhythm", "id": "missing"}])
    with pytest.raises(MutationError, match="MUTATION_REFERENCE_NOT_FOUND"):
        apply_mutations(program, [mutation], [], {"entries": []}, {"entries": []}, "act_x")
    assert program == before


def test_application_request_matches_every_checked_in_mutation_fixture() -> None:
    """The fixture suite is the read-only, byte-derived contract authority."""
    suite = json.loads((PACK / "mutation" / "cases.json").read_text())
    for case in suite["cases"]:
        assert apply_mutation_request(case["request"]) == case["expected"], case["case_id"]
