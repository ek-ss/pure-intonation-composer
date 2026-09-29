"""End-to-end tests for the v3 lowering: cadence plan -> 0.3 program -> project.

Exercises ``lower_cadence_plan`` (bind the cadence plan's sealed-dictionary
variants to a SongProgram 0.3), compiles it through the exact sparse path, and
reconciles the result against ``cadence_impact_report`` (positional slot match).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from app.songprogram.compiler import CompilerIdentity, compile_sp0
from app.songprogram.piano_v3 import (
    build_cadence_policy,
    cadence_impact_report,
    generate_cadence_plan,
    lower_cadence_plan,
)

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = (
    BACKEND / "songprogram_conformance/fixtures/compiler_v2_5d/gen0b_melody_song_program.json"
)
DICT = BACKEND / "harmony_dictionary_data/harmony_dictionary_2-1.json"


def _base_program() -> dict:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for section in base["form"]:
        section["bars"] = 4
    # The sealed dictionary carries exact ratios with large odd parts; widen the
    # lattice filters and enable mod-equave anchor reduction so the sparse path
    # can place them and the placed root exponent matches the compiler's anchor.
    base["lattice"]["maximum_odd_limit"] = 10**18
    base["lattice"]["maximum_reduced_complexity_bits"] = 256
    base["lattice"]["reduce_anchor_mod_equave"] = True
    return base


def _dictionary() -> dict:
    return json.loads(DICT.read_text(encoding="utf-8"))


def _identity() -> CompilerIdentity:
    return CompilerIdentity(
        "piano-v3-cadence-e2e/v1", "fixture-resolver",
        "sha256:" + "10" * 32, "sha256:" + "11" * 32, "sha256:" + "12" * 32,
    )


def _plan() -> dict:
    return {
        "seed": 19,
        "plan_hash": "sha256:" + "0" * 64,
        "sections": [{"section_id": "sec_a", "phrases": [{
            "section_id": "sec_a", "phrase_id": "phr_000", "start_bar": 0,
            "length_bars": 4, "cadence_target": "home",
        }]}],
    }


def test_lower_cadence_plan_binds_variants_and_compiles() -> None:
    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_plan(), dictionary, policy)
    program = lower_cadence_plan(_base_program(), cadence, dictionary)

    assert program["schema_version"] == "0.3.0"
    # One chord intent + harmony cell per bar, plus the preserved melody.
    assert len(program["chord_intents"]) == len(cadence["slots"])
    harmony_cells = [m for m in program["materials"] if m["kind"] == "harmony_intent_cell"]
    assert len(harmony_cells) == len(cadence["slots"])
    # Every intent is bound to a sealed-dictionary variant.
    for intent in program["chord_intents"]:
        assert intent["dictionary_variant"]["source_kind"] == "sealed_dictionary"
        assert intent["dictionary_variant"]["dictionary_hash"] == dictionary["hash"]

    project = compile_sp0(
        program, _identity(), stochastic_realization=False,
        dictionary_authorities={dictionary["hash"]: dictionary},
    )
    assert project["harmony_occurrences"]

    report = cadence_impact_report(cadence, program, project)
    assert report["program_checked"] and report["project_checked"]
    # Every slot is bound in the program and matched positionally in the project.
    for row, slot in zip(report["slots"], cadence["slots"]):
        assert row["program_bound"] is True
        assert row["status"] == "matched"
        assert row["section_id"] == slot["section_id"]
        assert row["bar"] == slot["bar"]


def test_lower_cadence_plan_is_deterministic() -> None:
    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_plan(), dictionary, policy)
    first = lower_cadence_plan(_base_program(), cadence, dictionary)
    second = lower_cadence_plan(_base_program(), cadence, dictionary)
    assert first == second


def test_lower_cadence_plan_rejects_equave_mismatch() -> None:
    from app.songprogram.piano_v3 import PianoV3Error

    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_plan(), dictionary, policy)
    base = _base_program()
    # Force a lattice equave that disagrees with the cadence plan.
    base["lattice"]["equave"] = "3/1"
    try:
        lower_cadence_plan(base, cadence, dictionary)
        raised = False
    except PianoV3Error as error:
        raised = error.code == "LOWER_EQUAVE_MISMATCH"
    assert raised
