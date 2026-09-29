"""Experimental 16-bar tritave song using exact sparse 24-step references.

Run: python tools/generate_piano_tritave_trial.py --seed 0 --output <empty-dir>
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from fractions import Fraction
from math import prod
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.harmony_dictionary.axis_search import axis_reference_coverage, build_sparse_axis_chord  # noqa: E402
from app.harmony_dictionary.storage import read_sealed  # noqa: E402
from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.sparse_variant import variant_hash  # noqa: E402
from app.songprogram.piano_v3 import sparse_charge_receipt  # noqa: E402
from app.songprogram.compiler import _mc  # noqa: E402
from tools.generate_piano_v3_trial import (  # noqa: E402
    GENERATION, RENDER_FIXTURE, SCHEMAS, _object, _pcm_check, _piano_catalog,
    build_trial_program,
)


def generate(seed: int) -> tuple[dict, dict, bytes, dict]:
    catalog, _, _, assets = _piano_catalog(_object(GENERATION))
    for entry in catalog["entries"]:
        if entry["instrument_id"] in ("piano_solo_harmony", "piano_solo_melody"):
            entry["instrument_id"] = "v3_trial_" + entry["role"]
        if entry.get("kind") == "pitched":
            entry["allowed_frequency_millihz"] = [110000, 1760000]
    catalog_bytes = canonical_bytes(catalog)
    digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
    program = build_trial_program(seed, digest)
    program["schema_version"] = "0.3.0"
    lattice = program["lattice"]
    lattice["equave"] = "3/1"
    lattice["generators"] = ["2/1", "5/1", "7/1", "11/1", "13/1"]
    # Each section owns an independently bound exact chord; these roots are
    # zero so the 3/1 crossing at reference step 19 stays an absolute lift.
    cells = [cell for cell in program["materials"] if cell["kind"] == "harmony_intent_cell"]
    dictionary = read_sealed(BACKEND / "harmony_dictionary_data/harmony_dictionary_3-1.json", "harmony-dictionary/3/1")
    generators = (2, 7, 11, 13) if seed % 2 == 0 else (2, 11, 7, 13)
    selections = {
        2: ("0,1,2", [12, 1, 9]),
        7: ("0,4,6", [2, 1, 5]),
        11: ("0,3,7", [0, 1, 2]),
        13: ("0,1,6", [0, 1, 2]),
    }
    coverage = {str(generator): axis_reference_coverage("3/1", generator) for generator in (2, 5, 7, 11, 13)}
    excluded = build_sparse_axis_chord("3/1", [0] * 5, 13, [0, 7, 19])
    for ordinal, (cell, generator) in enumerate(zip(cells, generators, strict=True)):
        cell["root_anchors"] = [[0] * 5]
        if ordinal == 0:
            # The sealed dictionary reduces every variant into a tritave;
            # an absolute 19-semitone boundary voice must therefore retain
            # its independent axis-search provenance rather than masquerade
            # as a dictionary variant.
            steps = [0, 7, 19]
            candidate = build_sparse_axis_chord("3/1", [0] * 5, generator, steps)
            variant = {
                "source_kind": "axis_search_candidate",
                "source_chord_key": f"axis-search/3-1/{generator}/0,7,19",
                "voices": [{"vector": voice["vector"], "equave_exponent": voice["equave_lift"],
                            "exact_ratio": voice["exact_ratio"]} for voice in candidate["voices"]],
            }
        else:
            entry_key, indices = selections[generator]
            entry = next(item for item in dictionary["dictionaries"][f"{generator}/3"]["entries"] if item["key"] == entry_key)
            chosen = next(item for item in entry["variants"] if item["index_tuple"] == indices)
            ratios = [Fraction(text) for text in chosen["ratios"]]
            steps = [round(_mc(ratio) / 100000) for ratio in ratios]
            if steps != sorted(steps) or any(not 0 <= step < 24 for step in steps):
                raise ValueError("TRITAVE_DICTIONARY_STEPS_INVALID")
            voices = []
            for ratio in ratios:
                places = [(n, lift) for n in range(-32, 33) for lift in range(-32, 33)
                          if Fraction(generator)**n * Fraction(3)**lift == ratio]
                if not places:
                    raise ValueError("TRITAVE_DICTIONARY_VOICE_UNPLACED")
                exponent, lift = min(places, key=lambda pair: (abs(pair[0]) + abs(pair[1]), pair))
                vector = [0] * 5
                vector[lattice["generators"].index(f"{generator}/1")] = exponent
                voices.append({"vector": vector, "equave_exponent": lift,
                               "exact_ratio": f"{ratio.numerator}/{ratio.denominator}"})
            variant = {
                "source_kind": "sealed_dictionary", "dictionary_hash": dictionary["hash"],
                "source_chord_key": f"{generator}/3/{entry_key}/" + ",".join(map(str, indices)),
                "voices": voices,
            }
        variant["variant_hash"] = variant_hash(variant)
        intent = program["chord_intents"][0].copy()
        intent["id"] = f"ci_axis_{ordinal}"
        intent["reference"] = {"temperament": "edo", "equave": "3/1", "divisions": 24, "steps": steps}
        intent["dictionary_variant"] = variant
        intent["recognition"] = {"maximum_pair_error_millicents": 120000,
                                 "maximum_pair_rms_millicents": 120000}
        intent["voicing"] = {**intent["voicing"], "maximum_span_millicents": 2500000}
        intent["complexity_budget"] = 256
        if ordinal == 0:
            program["chord_intents"] = []
        program["chord_intents"].append(intent)
        cell["chord_intent_ids"] = [intent["id"]]
    import jsonschema
    jsonschema.Draft202012Validator(_object(SCHEMAS / "song_program_0_3.schema.json")).validate(program)
    identity = CompilerIdentity("piano-tritave-sparse-trial/v1", "sparse-exact/v1",
                                "sha256:" + "10" * 32, "sha256:" + "11" * 32, digest)
    project = compile_sp0(program, identity, stochastic_realization=False,
                          dictionary_authorities={dictionary["hash"]: dictionary})
    jsonschema.Draft202012Validator(_object(SCHEMAS / "arrangement_project_1_3_sparse.schema.json")).validate(project)
    by_id = {chord["id"]: chord for chord in project["resolved_chords"]}
    sections = []
    for ordinal, section in enumerate(program["form"]):
        intent = program["chord_intents"][ordinal]
        chord_ids = {occurrence["resolved_chord_id"] for occurrence in project["harmony_occurrences"]
                     if occurrence["section_id"] == section["id"]}
        expected = [voice["exact_ratio"] for voice in intent["dictionary_variant"]["voices"]]
        if not chord_ids or any(by_id[chord_id]["exact_ratios"] != expected for chord_id in chord_ids):
            raise ValueError("TRITAVE_PROJECT_VARIANT_MISMATCH")
        sections.append({"section_id": section["id"], "source_chord_key": intent["dictionary_variant"]["source_chord_key"],
                         "source_kind": intent["dictionary_variant"]["source_kind"],
                         "dictionary_hash": intent["dictionary_variant"].get("dictionary_hash"),
                         "variant_hash": intent["dictionary_variant"]["variant_hash"],
                         "resolved_chord_ids": sorted(chord_ids), "exact_ratios": expected, "matched": True})
    manifest = _object(RENDER_FIXTURE / "render_manifest.json")
    rendered = render_reference(project, catalog_bytes, assets.__getitem__,
                                render_manifest_digest=manifest["render_manifest_digest"],
                                project_artifact_hash=project_hash(project))
    declared_voices = sum(
        len(intent["dictionary_variant"]["voices"]) for intent in program["chord_intents"]
    )
    rectangular_coordinate_points = prod(
        high - low + 1 for low, high in program["lattice"]["coordinate_bounds"]
    )
    low, high = program["lattice"]["register_bounds"]
    rectangular_placed_points = rectangular_coordinate_points * (high - low + 1)
    bounds_receipt = sparse_charge_receipt(
        declared_voices, rectangular_coordinate_points, rectangular_placed_points
    )
    report = {"schema": "cps.piano-tritave-trial-report", "schema_version": "1.0.0",
              "seed": seed, "equave": "3/1", "reference": "12-edo-absolute-24/v1",
              "dictionary_hash": dictionary["hash"],
              "coverage_by_axis": coverage,
              "excluded_axis_13": {"reference_covered": coverage["13"]["covered"],
                                   "candidate_filter": excluded["current_lattice_filter"],
                                   "reason": "candidate_unavailable_under_resource_limits"},
              "sections": sections, "program_hash": program_hash(program),
              "project_hash": project_hash(project), "pcm": _pcm_check(rendered.wav),
              "sparse_charge": bounds_receipt,
              "event_count": len(project["events"]), "classification_threshold_calibrated": False,
              "production_status": "experimental_sparse_trial"}
    return program, project, rendered.wav, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("output must be new or empty")
    program, project, wav, report = generate(args.seed)
    midi, midi_manifest = export_evaluation_midi(project, program_by_track={"harmony": 0, "melody": 0})
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("program.json", program), ("project.json", project), ("report.json", report),
                        ("evaluation_reference_midi.json", midi_manifest)):
        (args.output / name).write_bytes(canonical_bytes(value))
    (args.output / "reference.wav").write_bytes(wav)
    (args.output / "evaluation_reference.mid").write_bytes(midi)
    sys.stdout.buffer.write(canonical_bytes({
        "report": str(args.output / "report.json"), "program_hash": report["program_hash"],
        "project_hash": report["project_hash"], "wav_sha256": report["pcm"]["wav_sha256"],
        "matched_sections": len(report["sections"]), "event_count": report["event_count"],
    }))


if __name__ == "__main__":
    main()
