"""End-to-end tests for the v3 lowering: cadence plan -> 0.3 program -> project.

Exercises ``lower_cadence_plan`` (bind the cadence plan's sealed-dictionary
variants to a SongProgram 0.3), compiles it through the exact sparse path, and
reconciles the result against ``cadence_impact_report`` (positional slot match).
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path

import jsonschema
import pytest

from app.songprogram.compiler import CompilerIdentity, compile_sp0
from app.songprogram.piano_v3 import (
    PianoV3Error,
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
TICKS_PER_BAR = 1920


def _base_program() -> dict:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for section in base["form"]:
        section["bars"] = 4
    base["lattice"]["maximum_odd_limit"] = 4096
    base["lattice"]["pitch_exploration"]["maximum_reduced_complexity_bits"] = 256
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


def _two_section_plan() -> dict:
    return {
        "seed": 19,
        "plan_hash": "sha256:" + "0" * 64,
        "sections": [
            {"section_id": "sec_a", "phrases": [{
                "section_id": "sec_a", "phrase_id": "phr_000", "start_bar": 0,
                "length_bars": 4, "cadence_target": "home",
            }]},
            {"section_id": "sec_b", "phrases": [{
                "section_id": "sec_b", "phrase_id": "phr_001", "start_bar": 0,
                "length_bars": 4, "cadence_target": "home",
            }]},
        ],
    }


def _two_section_base_program() -> dict:
    base = _base_program()
    section_b = copy.deepcopy(next(s for s in base["form"] if s["id"] == "sec_a"))
    section_b["id"] = "sec_b"
    base["form"].append(section_b)
    return base


def _pipeline() -> tuple[dict, dict, dict]:
    """Cadence plan, lowered 0.3 program, and compiled project (2 sections)."""
    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_two_section_plan(), dictionary, policy)
    program = lower_cadence_plan(_two_section_base_program(), cadence, dictionary)
    project = compile_sp0(
        program, _identity(), stochastic_realization=False,
        dictionary_authorities={dictionary["hash"]: dictionary},
    )
    return cadence, program, project


def _row(report: dict, section_id: str, bar: int) -> dict:
    return next(
        row for row in report["slots"]
        if row["section_id"] == section_id and row["bar"] == bar
    )


def _occurrence(project: dict, section_id: str, bar: int) -> dict:
    start = 4 * TICKS_PER_BAR if section_id == "sec_b" else 0
    return next(
        occurrence for occurrence in project["harmony_occurrences"]
        if occurrence["section_id"] == section_id
        and occurrence["start_tick"] == start + bar * TICKS_PER_BAR
    )


def _lift_voice(intent: dict, index: int) -> None:
    """Lift one placed voice by an equave (consistent vector/lift/ratio edit)."""
    voice = intent["dictionary_variant"]["voices"][index]
    voice["equave_exponent"] += 1
    ratio = Fraction(voice["exact_ratio"]) * 2
    voice["exact_ratio"] = f"{ratio.numerator}/{ratio.denominator}"


def _intent(program: dict, intent_id: str) -> dict:
    return next(i for i in program["chord_intents"] if i["id"] == intent_id)


def test_lower_cadence_plan_binds_variants_and_compiles() -> None:
    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_plan(), dictionary, policy)
    program = lower_cadence_plan(_base_program(), cadence, dictionary)
    schema = json.loads((BACKEND / "songprogram_conformance/schemas/song_program_0_3.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(program)

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
    project_schema = json.loads((BACKEND / "songprogram_conformance/schemas/arrangement_project_1_3_sparse.schema.json").read_text())
    jsonschema.Draft202012Validator(project_schema).validate(project)
    assert project["harmony_occurrences"]

    report = cadence_impact_report(cadence, program, project)
    assert report["program_checked"] and report["project_checked"]
    # Every slot is bound in the program and matched positionally in the project.
    for row, slot in zip(report["slots"], cadence["slots"]):
        assert row["program_bound"] is True
        assert row["status"] == "matched"
        assert row["section_id"] == slot["section_id"]
        assert row["bar"] == slot["bar"]

    shifted = json.loads(json.dumps(project))
    # Multiplying every resolved voice by the equave changes register, even
    # though the pitch classes remain identical. It cannot match the plan.
    for chord in shifted["resolved_chords"]:
        chord["exact_ratios"] = [
            f"{(2 * Fraction(value)).numerator}/{(2 * Fraction(value)).denominator}"
            for value in chord["exact_ratios"]
        ]
    assert all(row["status"] == "unmatched" for row in cadence_impact_report(cadence, program, shifted)["slots"])


def test_sparse_budget_receipt_rejects_negative_and_excess_counts() -> None:
    from app.songprogram.piano_v3 import PianoV3Error, sparse_charge_receipt

    accepted = sparse_charge_receipt(12, 675, 3375)
    assert accepted["accepted"]
    assert accepted["scope"] == "bounds_only_not_gen0b_opcode_receipt"
    assert not sparse_charge_receipt(65, 675, 3375)["accepted"]
    with pytest.raises(PianoV3Error, match="SPARSE_CHARGE_INVALID"):
        sparse_charge_receipt(-1, 675, 3375)


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


def test_lower_cadence_plan_rejects_missing_section() -> None:
    dictionary = _dictionary()
    policy = build_cadence_policy(
        "2/1", dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(_two_section_plan(), dictionary, policy)
    base = _two_section_base_program()
    base["form"] = base["form"][:1]  # drop sec_b; its slots would be silent
    with pytest.raises(PianoV3Error, match="LOWER_SECTION_MISSING"):
        lower_cadence_plan(base, cadence, dictionary)


def test_reconciliation_matches_all_slots_across_sections() -> None:
    cadence, program, project = _pipeline()
    report = cadence_impact_report(cadence, program, project)
    assert report["program_checked"] and report["project_checked"]
    for row in report["slots"]:
        assert row["program_bound"] is True
        assert row["status"] == "matched"
        assert row["mismatches"] == []
        for chord in row["project_chords"]:
            assert (chord["ratio_match"], chord["root_vector_match"],
                    chord["voice_vector_match"], chord["voice_lift_match"],
                    chord["intent_hash_match"]) == (True, True, True, True, True)


def test_reconciliation_rejects_occurrence_position_change() -> None:
    cadence, program, project = _pipeline()
    # Move the bar-1 occurrence into bar 2: the slot's own bar is empty.
    _occurrence(project, "sec_a", 1)["start_tick"] += TICKS_PER_BAR
    report = cadence_impact_report(cadence, program, project)
    row = _row(report, "sec_a", 1)
    assert row["status"] == "unmatched"
    assert "V3_RECON_NO_OCCURRENCE" in row["mismatches"]


def test_reconciliation_rejects_section_boundary_move() -> None:
    cadence, program, project = _pipeline()
    # Move the first bar of sec_b into the last bar of sec_a (boundary).
    occurrence = _occurrence(project, "sec_b", 0)
    occurrence["section_id"] = "sec_a"
    occurrence["start_tick"] = 3 * TICKS_PER_BAR
    report = cadence_impact_report(cadence, program, project)
    row = _row(report, "sec_b", 0)
    assert row["status"] == "unmatched"
    assert "V3_RECON_NO_OCCURRENCE" in row["mismatches"]


def test_reconciliation_rejects_same_chord_in_previous_section() -> None:
    cadence, program, project = _pipeline()
    # Sound sec_b bar 0's chord in sec_a's last bar, then remove the slot's
    # own occurrence: an identical ratio set elsewhere must not match.
    target = _occurrence(project, "sec_b", 0)
    chord_id = target["resolved_chord_id"]
    _occurrence(project, "sec_a", 3)["resolved_chord_id"] = chord_id
    project["harmony_occurrences"].remove(target)
    report = cadence_impact_report(cadence, program, project)
    row = _row(report, "sec_b", 0)
    assert row["status"] == "unmatched"
    assert "V3_RECON_NO_OCCURRENCE" in row["mismatches"]


def test_reconciliation_rejects_swapped_intent_ids() -> None:
    cadence, program, project = _pipeline()
    cells = {m["id"]: m for m in program["materials"] if m["kind"] == "harmony_intent_cell"}
    cell_a = cells["mat_v3_sec_a_00"]
    cell_b = cells["mat_v3_sec_b_00"]
    intent_a = _intent(program, cell_a["chord_intent_ids"][0])
    intent_b = _intent(program, cell_b["chord_intent_ids"][0])
    assert intent_a["dictionary_variant"]["source_chord_key"] != intent_b["dictionary_variant"]["source_chord_key"]
    cell_a["chord_intent_ids"], cell_b["chord_intent_ids"] = (
        cell_b["chord_intent_ids"], cell_a["chord_intent_ids"],
    )
    report = cadence_impact_report(cadence, program, project)
    for section_id in ("sec_a", "sec_b"):
        row = _row(report, section_id, 0)
        assert row["status"] == "unmatched"
        assert "V3_RECON_BINDING_SOURCE_KEY" in row["mismatches"]


def test_reconciliation_rejects_root_only_modification() -> None:
    cadence, program, project = _pipeline()
    # Lift only the root voice of one binding (consistent vector/lift/ratio).
    _lift_voice(_intent(program, "ci_v3_sec_a_01"), 0)
    report = cadence_impact_report(cadence, program, project)
    row = _row(report, "sec_a", 1)
    assert row["status"] == "unmatched"
    for code in ("V3_RECON_BINDING_VARIANT_HASH", "V3_RECON_PROVENANCE_INTENT_HASH",
                 "V3_RECON_VOICE_LIFT_MISMATCH"):
        assert code in row["mismatches"]


def test_reconciliation_rejects_single_voice_lift() -> None:
    cadence, program, project = _pipeline()
    # Lift one non-root voice: same pitch class, different absolute register.
    _lift_voice(_intent(program, "ci_v3_sec_a_01"), 1)
    report = cadence_impact_report(cadence, program, project)
    row = _row(report, "sec_a", 1)
    assert row["status"] == "unmatched"
    for code in ("V3_RECON_BINDING_VARIANT_HASH", "V3_RECON_PROVENANCE_INTENT_HASH",
                 "V3_RECON_VOICE_LIFT_MISMATCH"):
        assert code in row["mismatches"]
