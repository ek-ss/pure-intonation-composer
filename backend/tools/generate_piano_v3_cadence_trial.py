"""Generate CompositionPlan → CadencePlan → SongProgram 0.3 → Project trials.

This v3-only experimental CLI runs independently for each equave and seed. It
records every candidate outcome (including typed failures) and never removes a
failed seed from the cohort denominator. WAV rendering is optional; without
it PCM is recorded as ``not_evaluated``.

Example::

    python tools/generate_piano_v3_cadence_trial.py --equave 2/1 --seeds 0 1 \
        --output /path/to/new-directory --skip-wav
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

import jsonschema

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.harmony_dictionary.storage import read_sealed  # noqa: E402
from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.composition_generation import generate_composition_plan  # noqa: E402
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.piano_v3 import (  # noqa: E402
    PianoV3Error,
    PIANO_V3_DOMAINS,
    build_cadence_policy,
    cadence_impact_report,
    compare_navigation_coverage,
    generate_cadence_plan,
    lower_cadence_plan,
    validate_cadence_plan,
)
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from tools.generate_piano_solo import _object, _piano_catalog  # noqa: E402
from tools.run_fixture_generation_cohort import RENDER_FIXTURE  # noqa: E402

COMPOSITION_PROFILE = BACKEND / "songprogram_conformance/profiles/g1_experiments/piano_solo.json"
GENERATION_PROFILE = BACKEND / "songprogram_conformance/profiles/g1_experiments/piano_solo_generation.json"
FIXTURE = BACKEND / "songprogram_conformance/fixtures/compiler_v2_5d/gen0b_melody_song_program.json"
SCHEMAS = BACKEND / "songprogram_conformance/schemas"
DICTIONARY_DIR = BACKEND / "harmony_dictionary_data"
TICKS_PER_BAR = 1920


def _json_bytes(value: Any) -> bytes:
    """Stable artifact encoding for policy objects that intentionally use floats."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _dictionary(equave: str) -> dict[str, Any]:
    file = DICTIONARY_DIR / f"harmony_dictionary_{equave.replace('/', '-')}.json"
    return read_sealed(file, f"harmony-dictionary/{equave}")


def _base_program(plan: dict[str, Any], equave: str, catalog_digest: str) -> dict[str, Any]:
    """Create a v3 SongProgram skeleton whose form is driven by the Plan.

    The fixture contributes only the already-validated piano rhythm/melody
    materials and track envelope. Every section ID and bar count comes from
    the generated CompositionPlan; harmony is supplied exclusively by the
    subsequent CadencePlan lowering.
    """
    program = _object(FIXTURE)
    domain = copy.deepcopy(PIANO_V3_DOMAINS[equave])
    program["schema_version"] = "0.3.0"
    program["seed"] = plan["seed"]
    program["lattice"].update(domain)
    program["lattice"].pop("reduce_anchor_mod_equave", None)
    program["lattice"]["maximum_odd_limit"] = 4096
    program["lattice"]["pitch_exploration"]["maximum_domain_points"] = 1024
    program["lattice"]["pitch_exploration"]["maximum_reduced_complexity_bits"] = 4096
    program["limits"]["max_bars"] = 64
    program["production"]["catalog_digest"] = catalog_digest
    for track in program["tracks"]:
        track["instrument_id"] = f"piano_v3_{track['role']}"
        track["maximum_polyphony"] = 64

    melody = copy.deepcopy(next(m for m in program["materials"] if m["kind"] == "melody_intent"))
    program["materials"] = [
        item for item in program["materials"]
        if item["kind"] != "harmony_intent_cell"
    ]
    form: list[dict[str, Any]] = []
    realizations: list[dict[str, Any]] = []
    stages = ("introduce", "repeat", "develop", "contrast", "recall", "close")
    for ordinal, section in enumerate(plan["sections"]):
        form.append({
            "id": section["section_id"],
            "role": section["function"],
            "bars": section["bars"],
            "energy_q": [5000, 5000],
            "density_q": [4000, 4000],
            "tonal_center": [0] * 5,
            "development_stage": stages[min(ordinal, len(stages) - 1)],
        })
        realizations.append({
            "id": f"real_melody_{ordinal:03d}",
            "section_id": section["section_id"],
            "track_id": "melody",
            "material_id": melody["id"],
            "at_tick": 0,
            "repeat": section["bars"],
            "every_ticks": TICKS_PER_BAR,
            "rhythm_transforms": [],
            "pitch_transforms": [],
            "velocity_scale_q": 10_000,
            "gate_scale_q": 10_000,
        })
    program["form"] = form
    program["realizations"] = realizations
    program["chord_intents"] = []
    # Keep the existing rhythm helper; the lowering adds its own bar rhythm.
    program["program_id"] = f"sp_piano_v3_{equave.replace('/', '_')}_{plan['seed']}"
    return program


def _pcm_check(wav_bytes: bytes) -> dict[str, Any]:
    with wave.open(BytesIO(wav_bytes), "rb") as wav:
        channels, rate, width, frames = (
            wav.getnchannels(), wav.getframerate(), wav.getsampwidth(), wav.getnframes()
        )
        samples = wav.readframes(frames)
    if channels not in (1, 2) or width not in (2, 4) or frames <= 0:
        raise PianoV3Error("V3_PCM_FORMAT_INVALID")
    code = "h" if width == 2 else "i"
    values = struct.unpack("<" + code * (len(samples) // width), samples)
    peak = max((abs(value) for value in values), default=0)
    if peak == 0:
        raise PianoV3Error("V3_PCM_SILENT")
    return {
        "status": "checked",
        "sample_rate_hz": rate,
        "channels": channels,
        "frames": frames,
        "nonzero_samples": sum(value != 0 for value in values),
        "peak_integer": peak,
        "wav_sha256": "sha256:" + hashlib.sha256(wav_bytes).hexdigest(),
    }


def _navigation_report(equave: str) -> dict[str, Any]:
    comparison = compare_navigation_coverage(PIANO_V3_DOMAINS[equave])
    comparison["measurement"]["steps"] = {
        str(step): result
        for step, result in comparison["measurement"]["steps"].items()
    }
    return comparison


def generate_one(equave: str, seed: int, *, skip_wav: bool) -> tuple[dict[str, bytes], dict[str, Any]]:
    dictionary = _dictionary(equave)
    generation = _object(GENERATION_PROFILE)
    catalog, catalog_bytes, catalog_digest, assets = _piano_catalog(generation)
    # Widen the piano sample window for both equaves; this digest is included
    # in Program/Project identity and therefore remains part of the receipt.
    for entry in catalog["entries"]:
        if entry.get("instrument_id") in ("piano_solo_harmony", "piano_solo_melody"):
            entry["instrument_id"] = f"piano_v3_{entry['role']}"
        if entry.get("kind") == "pitched":
            entry["allowed_frequency_millihz"] = [55_000, 1_760_000]
    catalog_bytes = canonical_bytes(catalog)
    catalog_digest = "sha256:" + hashlib.sha256(
        b"cps.instrument-catalog/v1\0" + catalog_bytes
    ).hexdigest()

    plan = generate_composition_plan(_object(COMPOSITION_PROFILE), seed)
    policy = build_cadence_policy(
        equave, dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"],
    )
    cadence = generate_cadence_plan(plan, dictionary, policy)
    validate_cadence_plan(cadence)
    base = _base_program(plan, equave, catalog_digest)
    program = lower_cadence_plan(base, cadence, dictionary)

    program_schema = _object(SCHEMAS / "song_program_0_3.schema.json")
    jsonschema.Draft202012Validator(program_schema).validate(program)
    identity = CompilerIdentity(
        f"piano-v3-cadence-{equave.replace('/', '-')}/v1", "sparse-exact/v1",
        "sha256:" + "10" * 32, "sha256:" + "11" * 32, catalog_digest,
    )
    project = compile_sp0(
        program, identity, stochastic_realization=False,
        dictionary_authorities={dictionary["hash"]: dictionary},
    )
    project_schema = _object(SCHEMAS / "arrangement_project_1_3_sparse.schema.json")
    jsonschema.Draft202012Validator(project_schema).validate(project)
    impact = cadence_impact_report(cadence, program, project)
    if not impact["slots"] or any(not row.get("program_bound") or row["status"] != "matched" for row in impact["slots"]):
        raise PianoV3Error("V3_CADENCE_PROJECT_RECONCILIATION_FAILED")

    midi, midi_manifest = export_evaluation_midi(
        project, program_by_track={"harmony": 0, "melody": 0}
    )
    artifacts = {
        "composition_plan.json": canonical_bytes(plan),
        "cadence_policy.json": _json_bytes(policy),
        "cadence_plan.json": canonical_bytes(cadence),
        "program.json": canonical_bytes(program),
        "project.json": canonical_bytes(project),
        "cadence_impact_report.json": canonical_bytes(impact),
        "evaluation_reference.mid": midi,
        "evaluation_reference_midi.json": canonical_bytes(midi_manifest),
    }
    if skip_wav:
        pcm: dict[str, Any] = {"status": "not_evaluated"}
    else:
        render_manifest = _object(RENDER_FIXTURE / "render_manifest.json")
        rendered = render_reference(
            project, catalog_bytes, assets.__getitem__,
            render_manifest_digest=render_manifest["render_manifest_digest"],
            project_artifact_hash=project_hash(project),
        )
        artifacts["reference.wav"] = rendered.wav
        pcm = _pcm_check(rendered.wav)
    report = {
        "schema": "cps.piano-v3-cadence-trial-report",
        "schema_version": "1.0.0",
        "status": "success",
        "seed": seed,
        "equave": equave,
        "composition_plan_hash": plan["plan_hash"],
        "cadence_plan_hash": cadence["cadence_plan_hash"],
        "program_hash": program_hash(program),
        "project_hash": project_hash(project),
        "dictionary_hash": dictionary["hash"],
        "stability_profile_hash": dictionary["stability_profile_hash"],
        "cadence_policy_hash": policy["policy_hash"],
        "compiler_identity": identity.__dict__,
        "catalog_digest": catalog_digest,
        "section_bars": [
            {"section_id": section["section_id"], "bars": section["bars"]}
            for section in plan["sections"]
        ],
        "candidate_slots": len(cadence["slots"]),
        "matched_slots": sum(row["status"] == "matched" for row in impact["slots"]),
        "slot_bindings": [
            {
                "section_id": row["section_id"],
                "bar": row["bar"],
                "source_chord_key": row["planned_variant"],
                "source_dictionary_hash": row["source_dictionary_hash"],
                "program_variant_hashes": row.get("program_variant_hashes", []),
                "absolute_exact_ratios": row["planned_absolute_ratios"],
                "project_chords": row.get("project_chords", []),
                "status": row["status"],
            }
            for row in impact["slots"]
        ],
        "candidate_failures": [],
        "receipt_status": "experimental_not_gen0b_opcode_receipt",
        "classification_threshold_calibrated": False,
        "navigation_comparison": _navigation_report(equave),
        "profile_status": "unsealed",
        "pcm": pcm,
    }
    artifacts["report.json"] = canonical_bytes(report)
    return artifacts, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equave", choices=tuple(PIANO_V3_DOMAINS), required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-wav", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("--output must be a new or empty directory")
    if len(set(args.seeds)) != len(args.seeds) or any(not 0 <= seed < 2**64 for seed in args.seeds):
        parser.error("--seeds must be unique uint64 values")
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for seed in args.seeds:
        directory = args.output / f"seed-{seed}"
        try:
            artifacts, report = generate_one(args.equave, seed, skip_wav=args.skip_wav)
            directory.mkdir()
            for name, payload in artifacts.items():
                (directory / name).write_bytes(payload)
            outcomes.append({
                "seed": seed,
                "status": "success",
                "report": str(directory / "report.json"),
                "pcm_status": report["pcm"]["status"],
            })
        except (PianoV3Error, ValueError, KeyError, OSError, jsonschema.ValidationError) as error:
            failure = {
                "schema": "cps.piano-v3-cadence-trial-failure",
                "schema_version": "1.0.0",
                "seed": seed,
                "equave": args.equave,
                "status": "failed",
                "failure_code": getattr(error, "code", None) or type(error).__name__,
                "detail": str(error),
                "candidate_failures_counted": True,
                "navigation_comparison": _navigation_report(args.equave),
                "classification_threshold_calibrated": False,
                "profile_status": "unsealed",
            }
            directory.mkdir()
            (directory / "failure.json").write_bytes(canonical_bytes(failure))
            outcomes.append(failure)
    cohort = {
        "schema": "cps.piano-v3-cadence-cohort-report",
        "schema_version": "1.0.0",
        "equave": args.equave,
        "seed_denominator": len(args.seeds),
        "successes": sum(item["status"] == "success" for item in outcomes),
        "failures": sum(item["status"] == "failed" for item in outcomes),
        "outcomes": outcomes,
        "classification_threshold_calibrated": False,
        "profile_status": "unsealed",
    }
    (args.output / "cohort_report.json").write_bytes(canonical_bytes(cohort))
    sys.stdout.buffer.write(canonical_bytes(cohort))


if __name__ == "__main__":
    main()
