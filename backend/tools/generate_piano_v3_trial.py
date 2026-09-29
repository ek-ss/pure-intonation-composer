"""Produce a 16-bar, five-axis piano trial with exact Project and checked PCM.

This is a fixture-derived *experimental* generator.  It deliberately does not
claim that a dictionary variant has been bound to a SongProgram chord intent:
SongProgram 0.2 accepts an EDO reference, not an exact-ratio dictionary key.
The receipt records that missing binding while proving the 5D song/render path.

Usage: python tools/generate_piano_v3_trial.py --seed 0 --output <new-directory>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import struct
import sys
import wave
from io import BytesIO
from pathlib import Path

import jsonschema

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from tools.generate_piano_solo import _piano_catalog, _object  # noqa: E402
from tools.run_fixture_generation_cohort import RENDER_FIXTURE  # noqa: E402

FIXTURE = BACKEND / "songprogram_conformance/fixtures/compiler_v2_5d/gen0b_melody_song_program.json"
GENERATION = BACKEND / "songprogram_conformance/profiles/g1_experiments/piano_solo_generation.json"
SCHEMAS = BACKEND / "songprogram_conformance/schemas"
TICKS_PER_BAR = 1920


def build_trial_program(seed: int, catalog_digest: str) -> dict:
    """Clone one proven 5D authority, then make section-local harmony cells."""
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("TRIAL_SEED_INVALID")
    program = _object(FIXTURE)
    lattice = program["lattice"]
    lattice["coordinate_bounds"] = [[-2, 2], [-2, 2], [-1, 1], [-1, 1], [-1, 1]]
    lattice["pitch_exploration"]["maximum_domain_points"] = 675
    lattice["maximum_odd_limit"] = 4096
    program["seed"] = seed
    program["limits"]["max_bars"] = 32
    program["production"]["catalog_digest"] = catalog_digest
    for track in program["tracks"]:
        track["instrument_id"] = "v3_trial_" + track["role"]
        # Adjacent piano strikes overlap during the sample release tail.
        track["maximum_polyphony"] = 64
    rhythm = [copy.deepcopy(material) for material in program["materials"] if material["kind"] == "rhythm_cell"]
    melody = copy.deepcopy(next(material for material in program["materials"] if material["kind"] == "melody_intent"))
    program["materials"] = rhythm + [melody]
    program["form"] = []
    program["realizations"] = []
    # The high-axis choice is seed-addressed, with exact tonic return.
    high_axes = (3, 4) if seed % 2 == 0 else (4, 3)
    roles = ("intro", "verse", "build", "final")
    for ordinal, role in enumerate(roles):
        section_id = f"sec_{ordinal:03d}"
        root = [0] * 5
        if ordinal in (1, 2):
            root[high_axes[ordinal - 1]] = 1
            # The exact root is 11/5 or 13/5, inside the fixture track's
            # frequency window.  No non-schema anchor-reduction flag is used.
            root[1] = -1
        program["form"].append({
            "id": section_id, "role": role, "bars": 4,
            "energy_q": [4000 + 1500 * ordinal] * 2,
            "density_q": [4000] * 2,
            "tonal_center": [0] * 5,
            "development_stage": ("introduce", "repeat", "develop", "close")[ordinal],
        })
        # No shared harmony material is edited in place.  Each section owns
        # its root anchor and EDO reference through a clone-on-write cell.
        material_id = f"harmony_{ordinal:03d}"
        program["materials"].append({
            "id": material_id, "kind": "harmony_intent_cell",
            "rhythm_id": "rhythm_chord", "root_anchors": [root],
            "chord_intent_ids": ["ci_major"], "mapping": "cycle",
        })
        for track_id, cell_id in (("harmony", material_id), ("melody", melody["id"])):
            program["realizations"].append({
                "id": f"real_{track_id}_{ordinal:03d}",
                "section_id": section_id, "track_id": track_id,
                "material_id": cell_id, "at_tick": 0, "repeat": 4,
                "every_ticks": TICKS_PER_BAR, "rhythm_transforms": [],
                "pitch_transforms": [], "velocity_scale_q": 10000,
                "gate_scale_q": 10000,
            })
    return program


def _pcm_check(wav: bytes) -> dict:
    with wave.open(BytesIO(wav)) as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        width = source.getsampwidth()
        count = source.getnframes()
        if channels not in (1, 2) or width not in (2, 4) or count == 0:
            raise ValueError("TRIAL_PCM_FORMAT_INVALID")
        raw = source.readframes(count)
    code = "h" if width == 2 else "i"
    samples = struct.unpack("<" + code * (len(raw) // width), raw)
    peak = max(abs(value) for value in samples)
    if not peak:
        raise ValueError("TRIAL_PCM_SILENT")
    return {
        "status": "checked", "channels": channels, "sample_rate_hz": rate,
        "frames": count, "peak_integer": peak,
        "nonzero_samples": sum(value != 0 for value in samples),
        "wav_sha256": "sha256:" + hashlib.sha256(wav).hexdigest(),
    }


def generate(seed: int) -> tuple[dict, dict, bytes, dict]:
    generation = _object(GENERATION)
    catalog, _, _, assets = _piano_catalog(generation)
    for entry in catalog["entries"]:
        if entry["instrument_id"] == "piano_solo_harmony":
            entry["instrument_id"] = "v3_trial_harmony"
        elif entry["instrument_id"] == "piano_solo_melody":
            entry["instrument_id"] = "v3_trial_melody"
        if entry.get("kind") == "pitched":
            entry["allowed_frequency_millihz"] = [110000, 1760000]
    catalog_bytes = canonical_bytes(catalog)
    digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
    program = build_trial_program(seed, digest)
    jsonschema.Draft202012Validator(
        _object(SCHEMAS / "song_program_0_2.schema.json")
    ).validate(program)
    identity = CompilerIdentity(
        "piano-v3-5d-trial/v1", "fixture-resolver",
        "sha256:" + "10" * 32, "sha256:" + "11" * 32, digest,
    )
    project = compile_sp0(program, identity, stochastic_realization=False)
    jsonschema.Draft202012Validator(
        _object(SCHEMAS / "arrangement_project_1_3_5d.schema.json")
    ).validate(project)
    render_manifest = _object(RENDER_FIXTURE / "render_manifest.json")
    rendered = render_reference(
        project, catalog_bytes, assets.__getitem__,
        render_manifest_digest=render_manifest["render_manifest_digest"],
        project_artifact_hash=project_hash(project),
    )
    pcm = _pcm_check(rendered.wav)
    roots = {tuple(chord["anchor_vector"]) for chord in project["resolved_chords"]}
    if not any(vector[3] for vector in roots) or not any(vector[4] for vector in roots):
        raise ValueError("TRIAL_HIGH_AXIS_NOT_RESOLVED")
    resolved_by_id = {chord["id"]: chord for chord in project["resolved_chords"]}
    material_by_id = {material["id"]: material for material in program["materials"]}
    expected_roots = {
        realization["section_id"]: material_by_id[realization["material_id"]]["root_anchors"][0]
        for realization in program["realizations"] if realization["track_id"] == "harmony"
    }
    section_reconciliation = []
    for section in program["form"]:
        section_id = section["id"]
        actual = sorted({
            occurrence["resolved_chord_id"]
            for occurrence in project["harmony_occurrences"]
            if occurrence["section_id"] == section_id
        })
        if not actual:
            raise ValueError("TRIAL_SECTION_HARMONY_MISSING")
        section_reconciliation.append({
            "section_id": section_id,
            "expected_root_vector": expected_roots[section_id],
            "resolved_chords": [
                {"id": chord_id, "root_vector": resolved_by_id[chord_id]["anchor_vector"],
                 "exact_ratios": resolved_by_id[chord_id]["exact_ratios"]}
                for chord_id in actual
            ],
            "root_matched": all(
                resolved_by_id[chord_id]["anchor_vector"] == expected_roots[section_id]
                for chord_id in actual
            ),
        })
    if not all(section["root_matched"] for section in section_reconciliation):
        raise ValueError("TRIAL_PROJECT_ROOT_MISMATCH")
    report = {
        "schema": "cps.piano-v3-trial-report", "schema_version": "1.0.0",
        "seed": seed, "program_hash": program_hash(program),
        "project_hash": project_hash(project),
        "source_fixture_sha256": "sha256:" + hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "catalog_digest": digest,
        "render_manifest_digest": render_manifest["render_manifest_digest"],
        "resolved_chords": [
            {"root_vector": chord["anchor_vector"], "exact_ratios": chord["exact_ratios"]}
            for chord in project["resolved_chords"]
        ],
        "event_count": len(project["events"]), "pcm": pcm,
        "section_root_reconciliation": section_reconciliation,
        "dictionary_variant_bound": False,
        "cadence_plan_project_match": "not_evaluated",
        "classification_threshold_calibrated": False,
        "production_status": "experimental_fixture_derived",
    }
    return program, project, rendered.wav, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("--output must be a new or empty directory")
    try:
        program, project, wav, report = generate(args.seed)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    midi, midi_manifest = export_evaluation_midi(
        project, program_by_track={"harmony": 0, "melody": 0}
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("program.json", program), ("project.json", project), ("report.json", report)):
        (args.output / name).write_bytes(canonical_bytes(value))
    (args.output / "reference.wav").write_bytes(wav)
    (args.output / "evaluation_reference.mid").write_bytes(midi)
    (args.output / "evaluation_reference_midi.json").write_bytes(canonical_bytes(midi_manifest))
    sys.stdout.buffer.write(canonical_bytes(report))


if __name__ == "__main__":
    main()
