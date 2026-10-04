"""Generate CompositionPlan → CadencePlan → SongProgram 0.3 → Project trials.

This v3-only experimental CLI runs independently for each equave and seed. It
records every candidate outcome (including typed failures) and never removes a
failed seed from the cohort denominator.  An artifact write failure after the
seed directory was created is likewise recorded as a failure rather than
aborting the run: each staged partial artifact is attempted independently,
only artifacts actually persisted are listed, and the failure record is
attempted regardless.  WAV rendering is optional; without it PCM is recorded
as ``not_evaluated``.

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
from app.songprogram.compiler import (  # noqa: E402
    CompileError,
    CompilerIdentity,
    compile_sp0,
)
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
from app.songprogram.sparse_variant import (  # noqa: E402
    RegisterLiftPolicyError,
    build_register_lift_policy,
    validate_register_lift_policy,
)
from app.songprogram.style_profile import (  # noqa: E402
    STYLE_PROFILES,
    StyleProfileError,
    apply_style_profile,
    load_style_profile,
    style_profile_hash,
    validate_style_profile,
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


def _write_artifact(path: Path, payload: bytes) -> None:
    """Write one artifact file (isolated so tests can inject write failures)."""
    path.write_bytes(payload)


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


class V3TrialFailure(PianoV3Error):
    """A staged trial failure: failing stage, typed code, partial artifacts."""

    def __init__(
        self, code: str, stage: str, detail: str = "",
        artifacts: dict[str, bytes] | None = None,
        progression_diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, detail)
        self.stage = stage
        self.artifacts = artifacts if artifacts is not None else {}
        self.progression_diagnostics = progression_diagnostics


def _failure_code(error: BaseException) -> str:
    return getattr(error, "code", None) or type(error).__name__


def generate_one(
    equave: str, seed: int, *, skip_wav: bool,
    register_lift_policy: dict[str, Any] | None = None,
    crossing_match: str = "canonical",
    style_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Run one seed through the full v3 path, staging every failure.

    Each stage records its artifacts as it completes; a failure raises
    ``V3TrialFailure`` carrying the failing stage, its typed code, and the
    partial artifacts produced so far.  A seed is a cohort success only when
    every stage completes: partial artifacts never count as success, and a
    skipped WAV leaves PCM ``not_evaluated`` rather than a PCM success.

    ``register_lift_policy`` is the versioned bounded register-lift policy
    (see ``sparse_variant.build_register_lift_policy``).  ``None`` normalizes
    to the disabled policy (``allow_lifts=False``), which reproduces the exact
    sparse path byte for byte; the resolved policy and its hash are recorded in
    every report and failure as provenance.

    ``crossing_match`` is the versioned, 0.3-only edge-matching policy
    (``"canonical"`` or ``"non_crossing"``).  When ``"non_crossing"``, the
    compiler emits a distinct, versioned progression query (2.1.0 /
    ``gen0-progression-noncrossing/v1``) that makes the resolver rank only
    non-crossing pairings; the default ``"canonical"`` keeps the original 2.0
    query without the field.  It is independent of the register-lift policy and
    is recorded in every report and failure as provenance.

    ``style_profile`` is a versioned experimental style profile (see
    ``style_profile``) that alters the *realized* sound — tempo, per-role
    velocity / gate, per-role rhythm, and the cadence policy's voice-leading
    cap / candidate budget (which sealed-dictionary variant is selected per
    slot).  ``None`` applies no style and reproduces the baseline Program /
    Project / WAV byte for byte.  The sealed dictionary and the cadence plan's
    dictionary binding are untouched; the profile and its hash are recorded in
    every report and failure as provenance.  It is an experimental, unsealed
    control configuration (no auditory T/D/S claim).
    """
    if register_lift_policy is None:
        register_lift_policy = build_register_lift_policy()
    validate_register_lift_policy(register_lift_policy)
    if crossing_match not in {"canonical", "non_crossing"}:
        raise ValueError("CROSSING_MATCH_POLICY_INVALID")
    if style_profile is not None:
        validate_style_profile(style_profile)
    artifacts: dict[str, bytes] = {}
    stage = "setup"
    progression_diagnostics: dict[str, Any] = {}
    try:
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

        stage = "plan"
        plan = generate_composition_plan(_object(COMPOSITION_PROFILE), seed)
        artifacts["composition_plan.json"] = canonical_bytes(plan)

        stage = "cadence"
        # A style profile may override the cadence policy's voice-leading cap
        # and candidate budget (which sealed-dictionary variant is selected per
        # slot — the harmony progression).  The defaults reproduce the baseline
        # policy byte for byte, so a ``None`` style leaves it unchanged.
        cadence_kwargs: dict[str, Any] = {}
        if style_profile is not None:
            # The profile stores the cap in integer millicents (float-free);
            # the cadence policy carries it in cents, so convert here.
            cadence_kwargs = {
                "voice_leading_cap_cents": (
                    style_profile["cadence"]["voice_leading_cap_millicents"] / 1000.0
                ),
                "candidate_budget": style_profile["cadence"]["candidate_budget"],
            }
        policy = build_cadence_policy(
            equave, dictionary["hash"], dictionary["stability_profile_hash"],
            dictionary["thresholds"]["version"], **cadence_kwargs,
        )
        artifacts["cadence_policy.json"] = _json_bytes(policy)
        cadence = generate_cadence_plan(plan, dictionary, policy)
        validate_cadence_plan(cadence)
        artifacts["cadence_plan.json"] = canonical_bytes(cadence)

        stage = "lowering"
        base = _base_program(plan, equave, catalog_digest)
        program = lower_cadence_plan(base, cadence, dictionary)
        if style_profile is not None:
            # Apply the profile's realized-sound alterations (tempo, per-role
            # velocity / gate, per-role rhythm, harmony mapping).  The sealed
            # dictionary binding and the cadence plan are untouched.
            program = apply_style_profile(program, style_profile)
        artifacts["program.json"] = canonical_bytes(program)

        stage = "program_schema"
        program_schema = _object(SCHEMAS / "song_program_0_3.schema.json")
        jsonschema.Draft202012Validator(program_schema).validate(program)

        stage = "compile"
        identity = CompilerIdentity(
            f"piano-v3-cadence-{equave.replace('/', '-')}/v1", "sparse-exact/v1",
            "sha256:" + "10" * 32, "sha256:" + "11" * 32, catalog_digest,
        )
        project = compile_sp0(
            program, identity, stochastic_realization=False,
            dictionary_authorities={dictionary["hash"]: dictionary},
            progression_diagnostics=progression_diagnostics,
            register_lift_policy=register_lift_policy,
            crossing_match=crossing_match,
        )
        artifacts["project.json"] = canonical_bytes(project)

        stage = "project_schema"
        project_schema = _object(SCHEMAS / "arrangement_project_1_3_sparse.schema.json")
        jsonschema.Draft202012Validator(project_schema).validate(project)

        stage = "reconciliation"
        impact = cadence_impact_report(
            cadence, program, project, dictionary_file=dictionary,
            register_lift_policy=register_lift_policy,
        )
        bad = [
            f"{row['section_id']}/{row['bar']}:{'+'.join(row['mismatches']) or 'NOT_MATCHED'}"
            for row in impact["slots"] if row["status"] != "matched"
        ]
        if not impact["slots"] or bad:
            raise PianoV3Error("V3_CADENCE_PROJECT_RECONCILIATION_FAILED", "; ".join(bad[:8]))
        artifacts["cadence_impact_report.json"] = canonical_bytes(impact)

        stage = "midi"
        midi, midi_manifest = export_evaluation_midi(
            project, program_by_track={"harmony": 0, "melody": 0}
        )
        artifacts["evaluation_reference.mid"] = midi
        artifacts["evaluation_reference_midi.json"] = canonical_bytes(midi_manifest)

        if skip_wav:
            pcm: dict[str, Any] = {"status": "not_evaluated"}
        else:
            stage = "render"
            render_manifest = _object(RENDER_FIXTURE / "render_manifest.json")
            rendered = render_reference(
                project, catalog_bytes, assets.__getitem__,
                render_manifest_digest=render_manifest["render_manifest_digest"],
                project_artifact_hash=project_hash(project),
            )
            artifacts["reference.wav"] = rendered.wav
            stage = "pcm"
            pcm = _pcm_check(rendered.wav)
    except (PianoV3Error, CompileError, ValueError, KeyError, OSError, jsonschema.ValidationError) as error:
        raise V3TrialFailure(
            _failure_code(error), stage, str(error), artifacts,
            progression_diagnostics or None,
        ) from error

    report = {
        "schema": "cps.piano-v3-cadence-trial-report",
        "schema_version": "1.2.0",
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
        "register_lift_policy": register_lift_policy,
        "register_lift_policy_hash": register_lift_policy["policy_hash"],
        "crossing_match": crossing_match,
        # Experimental, unsealed style provenance.  ``None`` (baseline) applies
        # no style and reproduces the baseline Program / Project / WAV byte for
        # byte; a profile records its full body and hash.  No auditory claim.
        "style_profile": style_profile,
        "style_profile_hash": (
            style_profile_hash(style_profile) if style_profile is not None else None
        ),
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
                "mismatches": row["mismatches"],
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
    parser.add_argument(
        "--register-lift", action="store_true",
        help="Enable the versioned bounded register-lift candidate policy "
             "(default: disabled, reproducing the exact sparse path).",
    )
    parser.add_argument("--max-lift", type=int, default=1,
                        help="Maximum equave shift per non-root voice (0-8).")
    parser.add_argument("--max-variants", type=int, default=8,
                        help="Maximum candidate variants per chord (1-64).")
    parser.add_argument(
        "--crossing", action="store_true",
        help="Enable the versioned 0.3-only non-crossing edge-matching policy "
             "(crossing_match=non_crossing; default: canonical, historical).",
    )
    parser.add_argument(
        "--style", choices=sorted(STYLE_PROFILES),
        help="Apply a built-in experimental style profile by ID "
             "(restrained / driving).  Mutually exclusive with --style-profile.",
    )
    parser.add_argument(
        "--style-profile", type=Path,
        help="Apply an experimental style profile from a JSON file "
             "(mutually exclusive with --style).  Default: no style (baseline).",
    )
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("--output must be a new or empty directory")
    if len(set(args.seeds)) != len(args.seeds) or any(not 0 <= seed < 2**64 for seed in args.seeds):
        parser.error("--seeds must be unique uint64 values")
    register_lift_policy = build_register_lift_policy(
        allow_lifts=args.register_lift, max_lift=args.max_lift,
        max_variants=args.max_variants,
    )
    try:
        validate_register_lift_policy(register_lift_policy)
    except RegisterLiftPolicyError as error:
        parser.error(f"invalid register-lift policy: {error}")
    crossing_match = "non_crossing" if args.crossing else "canonical"
    # Resolve the experimental style profile (built-in ID or JSON file).  The
    # two flags are mutually exclusive; neither selects a style (baseline).
    if args.style is not None and args.style_profile is not None:
        parser.error("--style and --style-profile are mutually exclusive")
    style_profile: dict[str, Any] | None = None
    if args.style is not None:
        style_profile = STYLE_PROFILES[args.style]
    elif args.style_profile is not None:
        try:
            style_profile = load_style_profile(args.style_profile)
        except (StyleProfileError, ValueError, OSError) as error:
            parser.error(f"invalid style profile: {error}")
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for seed in args.seeds:
        directory = args.output / f"seed-{seed}"
        written: list[str] = []
        try:
            artifacts, report = generate_one(
                args.equave, seed, skip_wav=args.skip_wav,
                register_lift_policy=register_lift_policy,
                crossing_match=crossing_match,
                style_profile=style_profile,
            )
            directory.mkdir()
            for name, payload in artifacts.items():
                _write_artifact(directory / name, payload)
                written.append(name)
            outcomes.append({
                "seed": seed,
                "status": "success",
                # The cluster tool binds this path exactly (resolved): it is
                # the output path as given on the command line (the documented
                # convention is a relative local_authority/... path; absolute
                # is equally valid) joined with seed-{seed}/report.json.
                "report": str(directory / "report.json"),
                "pcm_status": report["pcm"]["status"],
            })
        except (V3TrialFailure, ValueError, KeyError, OSError, jsonschema.ValidationError) as error:
            # Staged failures carry their stage and partial artifacts; any
            # other failure type (e.g. an artifact write error after the
            # directory was created) is recorded with stage "unknown" and the
            # artifacts that were actually written.  Partial artifacts are
            # written for inspection but never count the seed as a cohort
            # success.  Staged partials are persisted one attempt each below,
            # so a write failure on one cannot prevent the others or the
            # failure record, and only artifacts actually persisted are
            # listed.
            staged = isinstance(error, V3TrialFailure)
            stage = error.stage if staged else "unknown"
            partial = [] if staged else sorted(written)
            failure = {
                "schema": "cps.piano-v3-cadence-trial-failure",
                "schema_version": "1.2.0",
                "seed": seed,
                "equave": args.equave,
                "status": "failed",
                "stage": stage,
                "failure_code": _failure_code(error),
                "detail": str(error),
                "partial_artifacts": partial,
                "candidate_failures_counted": True,
                "register_lift_policy": register_lift_policy,
                "register_lift_policy_hash": register_lift_policy["policy_hash"],
                "crossing_match": crossing_match,
                "style_profile": style_profile,
                "style_profile_hash": (
                    style_profile_hash(style_profile) if style_profile is not None else None
                ),
                "navigation_comparison": _navigation_report(args.equave),
                "classification_threshold_calibrated": False,
                "profile_status": "unsealed",
            }
            try:
                # exist_ok: when an artifact write failed, the directory was
                # already created on the success path; a second mkdir() would
                # raise FileExistsError and abort the whole run before the
                # failure could be recorded.
                directory.mkdir(exist_ok=True)
            except OSError as persist_error:
                # Nothing could be persisted (the directory does not exist);
                # keep the outcome in the cohort report so the denominator is
                # maintained and the seed is never a false success.
                failure["detail"] = (
                    f"{failure['detail']}; record not persisted: {persist_error}"
                )
                failure["partial_artifacts"] = []
            else:
                if staged:
                    persisted = []
                    for name, payload in error.artifacts.items():
                        try:
                            _write_artifact(directory / name, payload)
                        except OSError:
                            continue
                        persisted.append(name)
                    failure["partial_artifacts"] = sorted(persisted)
                try:
                    _write_artifact(directory / "failure.json", canonical_bytes(failure))
                except OSError as persist_error:
                    # The per-seed record could not be persisted; keep the
                    # outcome in the cohort report so the denominator is
                    # maintained and the seed is never a false success.
                    failure["detail"] = (
                        f"{failure['detail']}; record not persisted: {persist_error}"
                    )
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
