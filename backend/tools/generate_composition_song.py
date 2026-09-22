"""Generate one WAV through CompositionPlan 2.0 and the reference renderer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.composition_generation import generate_composition_plan  # noqa: E402
from app.songprogram.composition_lowering import (  # noqa: E402
    CompositionLoweringError,
    lower_composition_plan,
)
from app.songprogram.composition_viability import extract_composition_viability  # noqa: E402
from app.songprogram.composition_realization import (  # noqa: E402
    realization_profile_hash,
    validate_realization_profile,
)
from app.songprogram.fallback import execute_broad_prior_production  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.song_validity import assess_completed_song  # noqa: E402
from app.songprogram.structural_sampler import execute_structural_sampler  # noqa: E402
from tools.run_fixture_generation_cohort import (  # noqa: E402
    DEFAULT_GENERATION_MANIFEST,
    RENDER_FIXTURE,
    _exploration_authorities,
    _production_authorities,
    _trial_catalog,
    pcm_continuity,
)


DEFAULT_PROFILE = (
    BACKEND / "songprogram_conformance" / "profiles" / "composition_generation_v2.json"
)
DEFAULT_REALIZATION_PROFILE = (
    BACKEND / "songprogram_conformance" / "profiles" / "composition_realization_v2_1.json"
)


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--realization-profile", type=Path, default=DEFAULT_REALIZATION_PROFILE)
    parser.add_argument("--generation-manifest", type=Path, default=DEFAULT_GENERATION_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not 0 <= arguments.seed < 2**64:
        parser.error("--seed must fit uint64")
    for option in ("profile", "realization_profile", "generation_manifest"):
        path = getattr(arguments, option)
        if not path.is_file():
            parser.error(f"--{option.replace('_', '-')} is not a file: {path}")
    try:
        profile = _object(arguments.profile)
        realization_profile = _object(arguments.realization_profile)
        validate_realization_profile(realization_profile)
        generation_manifest = _object(arguments.generation_manifest)
        plan = generate_composition_plan(profile, arguments.seed)
        structural = None
        for structural_rejection_ordinal in range(64):
            structural_seed = (arguments.seed + structural_rejection_ordinal) % (2**64)
            request, sampler, structural_manifest = _exploration_authorities(
                structural_seed, None, generation_manifest
            )
            sampled = execute_structural_sampler(request, sampler, structural_manifest)
            if sampled["result"]["status"] != "success":
                continue
            try:
                structural = lower_composition_plan(
                    sampled["structural_program"], plan, realization_profile
                )
                break
            except CompositionLoweringError as error:
                if error.code != "COMPOSITION_LOWERING_CORE_ROLE_UNAVAILABLE":
                    raise
        if structural is None:
            raise ValueError("COMPOSITION_STRUCTURAL_REJECTIONS_EXHAUSTED")
        production_request, production_manifest, production_catalog = _production_authorities(
            arguments.seed,
            structural,
            structural_manifest,
            sampler["manifest_hash"],
            generation_manifest,
        )
        produced = execute_broad_prior_production(
            production_request,
            production_manifest,
            production_catalog,
            structural_manifest,
        )
        if produced["status"] != "success":
            raise ValueError(produced["error"])
        program = produced["output"]["program"]
        catalog, catalog_bytes, catalog_digest, assets = _trial_catalog(generation_manifest)
        program["production"]["catalog_digest"] = catalog_digest
        for track in program["tracks"]:
            track["instrument_id"] = (
                "drum_fixture_kit" if track["role"] == "drums" else f"trial_{track['role']}"
            )
        identity = CompilerIdentity(
            "composition-generation-v2/v1",
            "fixture-resolver",
            "sha256:" + "10" * 32,
            "sha256:" + "11" * 32,
            catalog_digest,
        )
        project = compile_sp0(program, identity)
        render_manifest = _object(RENDER_FIXTURE / "render_manifest.json")
        rendered = render_reference(
            project,
            catalog_bytes,
            assets.__getitem__,
            render_manifest_digest=render_manifest["render_manifest_digest"],
            project_artifact_hash=project_hash(project),
        )
        roles_by_track = {track["id"]: track["role"] for track in project["tracks"]}
        masks = {
            tuple(
                sorted(
                    {
                        roles_by_track[event["track_id"]]
                        for event in project["events"]
                        if event["section_id"] == section["id"]
                    }
                )
            )
            for section in project["form"]
        }
        validity = assess_completed_song(
            program,
            project,
            symbolic_coverage={"overall_coverage_basis_points": 10000},
            arrangement={"status": "passed", "distinct_role_mask_count": len(masks)},
            pcm_continuity=pcm_continuity(rendered.wav),
        )
        g1_features = extract_composition_viability(program, project)
        evaluation_midi, evaluation_midi_manifest = export_evaluation_midi(project)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))

    arguments.output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "composition_plan.json": canonical_bytes(plan),
        "structural_program.json": canonical_bytes(structural),
        "program.json": canonical_bytes(program),
        "project.json": canonical_bytes(project),
        "reference.wav": rendered.wav,
        "perceptual_preview.wav": rendered.wav,
        "evaluation_reference.mid": evaluation_midi,
        "evaluation_reference_midi.json": canonical_bytes(evaluation_midi_manifest),
        "song_validity.json": canonical_bytes(validity),
        "g1_features.json": canonical_bytes(g1_features),
    }
    for name, payload in artifacts.items():
        (arguments.output / name).write_bytes(payload)
    receipt = {
        "schema": "cps.composition-song-generation-receipt",
        "schema_version": "1.2.0",
        "seed": arguments.seed,
        "structural_seed": structural_seed,
        "structural_rejection_ordinal": structural_rejection_ordinal,
        "profile_hash": profile["profile_hash"],
        "realization_profile_hash": realization_profile_hash(realization_profile),
        "plan_hash": plan["plan_hash"],
        "program_hash": program_hash(program),
        "project_hash": project_hash(project),
        "wav_hash": rendered.report["wav_hash"],
        "midi_hash": evaluation_midi_manifest["midi_hash"],
        "midi_manifest_hash": evaluation_midi_manifest["manifest_hash"],
        "song_validity_hash": validity["assessment_hash"],
        "g1_feature_report_hash": g1_features["report_hash"],
        "archive_eligible": validity["archive_eligible"],
        "artifact_names": sorted(artifacts),
        "non_authoritative": True,
    }
    (arguments.output / "receipt.json").write_bytes(canonical_bytes(receipt))
    sys.stdout.buffer.write(canonical_bytes(receipt) + b"\n")


if __name__ == "__main__":
    main()
