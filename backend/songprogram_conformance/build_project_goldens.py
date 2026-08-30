"""Build complete Project goldens using only conformance references."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .identifiers import (
    chord_intent_hash,
    event_id,
    lattice_domain_hash,
    program_hash,
    project_artifact_hash,
    resolved_chord_id,
    semantic_address,
)
from .reference import resolve_exact

ROOT = Path(__file__).parent
PACK = ROOT / "fixtures" / "pack"


def build_triad() -> tuple[dict[str, Any], dict[str, Any]]:
    program = json.loads((PACK / "minimal_triad_song_program.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACK / "compiler_manifest_sp0.json").read_text(encoding="utf-8"))
    intent = program["chord_intents"][0]
    query = {
        "schema": "cps.sp0-oracle-query/v1",
        "numeric_contract": manifest["numeric_contract"],
        "domain": {
            "equave": program["lattice"]["equave"],
            "generators": program["lattice"]["generators"],
            "coordinate_bounds": program["lattice"]["coordinate_bounds"],
            "register_bounds": program["lattice"]["register_bounds"],
            "maximum_odd_limit": program["lattice"]["maximum_odd_limit"],
            "maximum_reduced_complexity_bits": program["lattice"]["pitch_exploration"]["maximum_reduced_complexity_bits"],
        },
        "intent": {
            "reference_equave": intent["reference"]["equave"],
            "reference_divisions": intent["reference"]["divisions"],
            "steps": intent["reference"]["steps"],
            **intent["voicing"],
            **intent["recognition"],
            "complexity_budget": intent["complexity_budget"],
        },
        "anchor": {"vector": [0, 0], "equave_exponent": 0},
    }
    result = resolve_exact(query)
    lattice = {
        "domain_hash": "",
        "base_frequency_millihz": program["lattice"]["base_frequency_millihz"],
        "equave": program["lattice"]["equave"],
        "generators": program["lattice"]["generators"],
        "coordinate_bounds": program["lattice"]["coordinate_bounds"],
        "register_bounds": program["lattice"]["register_bounds"],
        "maximum_odd_limit": program["lattice"]["maximum_odd_limit"],
        "maximum_reduced_complexity_bits": program["lattice"]["pitch_exploration"]["maximum_reduced_complexity_bits"],
    }
    lattice["domain_hash"] = lattice_domain_hash(lattice)
    eligibility = {**intent["voicing"], **intent["recognition"], "complexity_budget": intent["complexity_budget"]}
    chord = {
        "id": "",
        "domain_hash": lattice["domain_hash"],
        "intent_hash": chord_intent_hash(intent),
        "resolver_build_id": manifest["resolver"]["build_id"],
        "numeric_contract": manifest["numeric_contract"],
        "search_completeness": "exact",
        "reference_equave": intent["reference"]["equave"],
        "reference_divisions": intent["reference"]["divisions"],
        "canonical_steps": result["canonical_steps"],
        "eligibility_contract": eligibility,
        "anchor_vector": [0, 0],
        "voice_offsets": result["vectors"],
        "equave_exponents": result["equave_exponents"],
        "exact_ratios": result["exact_ratios"],
        "target_voice_ordinals": [0, 1, 2],
        "pair_errors_millicents": result["pair_errors_millicents"],
        "maximum_pair_error_millicents": result["pair_max_millicents"],
        "pair_rms_error_millicents": result["pair_rms_millicents"],
        "complexity_score": result["complexity_score"],
    }
    chord["id"] = resolved_chord_id(chord)
    project: dict[str, Any] = {
        "schema": "cps.arrangement-project",
        "schema_version": "1.2.0",
        "source_program": {"hash": program_hash(program), "schema": "cps.song-program", "schema_version": "0.1.0"},
        "compiler": {
            "build_id": manifest["build_id"],
            "numeric_contract": manifest["numeric_contract"],
            "resolver_build_id": manifest["resolver"]["build_id"],
            "resolver_profile_hash": manifest["resolver"]["profile_hash"],
            "budget_profile_digest": manifest["budget_profile"]["digest"],
            "instrument_catalog_digest": manifest["instrument_catalog_digest"],
        },
        "lattice": lattice,
        "clock": {"tempo_milli_bpm": 120000, "beats_per_bar": 4, "ticks_per_beat": 480, "bars": 1, "total_ticks": 1920},
        "tracks": [{"id": "harmony", "role": "harmony", "instrument_id": "pi18", "register_millicents": [-1200000, 3600000], "maximum_polyphony": 4, "drum_map": None}],
        "form": [{"id": "sec_a", "role": "study", "start_bar": 0, "bars": 1}],
        "material_instances": [{"id": "mi_harmony", "material_id": "harmony_a", "realization_id": "real_harmony", "section_id": "sec_a", "track_id": "harmony", "repeat_ordinal": 0, "at_tick": 0, "source_program_path": "/realizations/0"}],
        "resolved_chords": [chord],
        "harmony_occurrences": [{"chord_index": 0, "section_id": "sec_a", "start_tick": 0, "duration_ticks": 1920, "resolved_chord_id": chord["id"]}],
        "events": [],
        "mix": {"harmony": {"gain_q": 8000, "pan_q": 0}},
        "render_settings": {"sample_rate": 48000, "channel_layout": "stereo"},
    }
    for ordinal, (vector, exponent, ratio) in enumerate(zip(result["vectors"], result["equave_exponents"], result["exact_ratios"], strict=True)):
        address = semantic_address("sec_a", "real_harmony", 0, "harmony_a", 0, ordinal)
        event = {
            "id": "",
            "kind": "note",
            "track_id": "harmony",
            "section_id": "sec_a",
            "start_tick": 0,
            "duration_ticks": 1920,
            "velocity": 100,
            "articulation": "normal",
            "drum_note": None,
            "ratio": ratio,
            "chord_index": 0,
            "pitch_provenance": {"kind": "resolved_chord_voice", "resolved_chord_id": chord["id"], "target_voice_ordinal": ordinal, "shape_voice_ordinal": ordinal, "anchor_vector": [0, 0], "offset_vector": vector, "final_vector": vector, "equave_exponent": exponent, "final_ratio": ratio},
            "source": {"material_instance_id": "mi_harmony", "source_step_ordinal": 0, "emitted_voice_ordinal": ordinal, "semantic_address": address},
        }
        event["id"] = event_id(event)
        project["events"].append(event)
    project["events"].sort(key=lambda item: (item["start_tick"], item["track_id"], item["ratio"], item["source"]["semantic_address"], item["id"]))
    expected = {"schema": "cps.fixture-expected", "schema_version": "1.0.0", "fixture_id": "resolved_triad_2_1", "program_hash": program_hash(program), "domain_hash": lattice["domain_hash"], "resolved_chord_id": chord["id"], "event_ids": [event["id"] for event in project["events"]], "artifact_hash": project_artifact_hash(project)}
    return project, expected


def main() -> None:
    project, expected = build_triad()
    (PACK / "resolved_triad_project.json").write_bytes(canonical_bytes(project) + b"\n")
    (PACK / "resolved_triad_expected.json").write_bytes(canonical_bytes(expected) + b"\n")


if __name__ == "__main__":
    main()
