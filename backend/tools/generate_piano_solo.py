"""Generate a piano-solo (two-part) song: chord progression + main melody.

Both parts are realized on separate piano tracks (role ``harmony`` and role
``melody``) sharing one timbre.  The pipeline reuses the full-song plan /
lowering / production machinery but is constrained by the piano-solo profiles
to two tracks on a small 2D lattice.  ``--skip-wav`` produces symbolic / MIDI
artifacts only (G0 stays incomplete until a PCM render is checked).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.composition_generation import generate_composition_plan  # noqa: E402
from app.songprogram.composition_viability import extract_composition_viability  # noqa: E402
from app.songprogram.lattice_pitch_diagnostic import lattice_pitch_diagnostic  # noqa: E402
from app.songprogram.composition_lowering import (  # noqa: E402
    CompositionLoweringError,
    lower_composition_plan,
)
from app.songprogram.composition_realization import (  # noqa: E402
    realization_profile_hash,
    validate_realization_profile,
)
from app.songprogram.fallback import (  # noqa: E402
    _search_decision_hash,
    execute_broad_prior_production,
    structural_program_hash,
)
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.piano_part import piano_samples  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.song_validity import assess_piano_solo  # noqa: E402
from app.songprogram.structural_sampler import (  # noqa: E402
    _hash,
    execute_structural_sampler,
)
from tools.run_fixture_generation_cohort import (  # noqa: E402
    RENDER_FIXTURE,
    _exploration_authorities,
    _wav_asset,
)

PROFILES = BACKEND / "songprogram_conformance" / "profiles" / "g1_experiments"
DEFAULT_PROFILE = PROFILES / "piano_solo.json"
DEFAULT_REALIZATION_PROFILE = PROFILES / "piano_solo_roles.json"
DEFAULT_GENERATION_MANIFEST = PROFILES / "piano_solo_generation.json"
DEFAULT_PRODUCTION_MANIFEST = PROFILES / "piano_solo_production.json"
DEFAULT_CATALOG = PROFILES / "piano_solo_catalog.json"


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _piano_production_authorities(
    seed: int,
    structural: dict[str, Any],
    lowering: dict[str, Any],
    sampler_hash: str,
    generation_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the piano production request from the sealed piano authorities.

    Mirrors ``run_fixture_generation_cohort._production_authorities`` but reads
    the piano-solo manifest / catalog and skips the drum map (a piano song has
    no drum track).
    """
    from typing import Any

    manifest = _object(DEFAULT_PRODUCTION_MANIFEST)
    catalog = _object(DEFAULT_CATALOG)
    policy = generation_manifest["production_policy"]
    for entry in catalog["entries"]:
        entry["maximum_polyphony"] = policy["maximum_polyphony"]
        if entry.get("role") != "drums":
            entry["allowed_frequency_millihz"] = policy["pitched_frequency_millihz"]
    catalog_digest = (
        "sha256:"
        + hashlib.sha256(b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)).hexdigest()
    )
    manifest["instrument_catalog_digest"] = catalog_digest
    manifest["sampler_manifest_hash"] = sampler_hash
    role_order = ["drums", "bass", "harmony", "melody", "texture"]
    manifest["register_presets_by_role"] = {
        role: [{"value": policy["register_millicents"], "weight": 1}]
        for role in role_order
        if role != "drums"
    }
    manifest["polyphony_by_role"] = {
        role: [{"value": policy["maximum_polyphony"], "weight": 1}]
        for role in role_order
    }
    active_roles = sorted(
        {item["role"] for item in structural["realizations"]},
        key=["drums", "bass", "harmony", "melody", "texture"].index,
    )
    request = {
        "schema": "cps.broad-prior-production-request",
        "schema_version": "1.1.0",
        "run_hash": _hash("cps.exploration-run/v1", {"seed": seed}),
        "context_hash": _hash("cps.exploration-context/v1", {"seed": seed}),
        "source_decision_hash": _hash("cps.exploration-source/v1", {"seed": seed}),
        "root_seed": seed,
        "cohort_index": seed,
        "production_rejection_ordinal": 0,
        "sampler_manifest_hash": manifest["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": lowering["manifest_hash"],
        "production_lowering_manifest_hash": _hash(
            "cps.production-lowering-manifest/v1", manifest
        ),
        "instrument_catalog_digest": catalog_digest,
        "structural_program_hash": structural_program_hash(structural),
        "structural_program": structural,
        "active_roles": active_roles,
        "lattice_equave": structural["lattice"]["equave"],
        "request_hash": "",
    }
    request["request_hash"] = _search_decision_hash(request, "request_hash")
    return request, manifest, catalog


def _piano_catalog(
    generation_manifest: dict[str, Any],
) -> tuple[dict[str, Any], bytes, str, dict[str, bytes]]:
    """Build the piano instrument catalog with the shared piano timbre.

    Both the chord and melody entries use the same reference piano sample so
    the two tracks sound like one instrument.  The drum kit entry is retained
    for catalog shape but no drum track is realized in a piano song.
    """
    from typing import Any

    catalog = _object(DEFAULT_CATALOG)
    policy = generation_manifest["production_policy"]
    assets: dict[str, bytes] = {}
    descriptor, payload = _wav_asset(piano_samples())
    assets[descriptor["uri"]] = payload
    for entry in catalog["entries"]:
        if entry.get("kind") != "pitched":
            continue
        entry["asset"] = descriptor
        entry["allowed_frequency_millihz"] = policy["pitched_frequency_millihz"]
        entry["maximum_polyphony"] = policy["maximum_polyphony"]
    payload_bytes = canonical_bytes(catalog)
    digest = "sha256:" + hashlib.sha256(
        b"cps.instrument-catalog/v1\0" + payload_bytes
    ).hexdigest()
    return catalog, payload_bytes, digest, assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--realization-profile", type=Path, default=DEFAULT_REALIZATION_PROFILE)
    parser.add_argument("--generation-manifest", type=Path, default=DEFAULT_GENERATION_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-wav", action="store_true",
                        help="generate symbolic/MIDI diagnostics without rendering")
    arguments = parser.parse_args()
    if not 0 <= arguments.seed < 2**64:
        parser.error("--seed must fit uint64")
    if arguments.skip_wav and arguments.output.exists() and any(arguments.output.iterdir()):
        parser.error("--skip-wav requires a new or empty output directory")
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
        production_request, production_manifest, production_catalog = (
            _piano_production_authorities(
                arguments.seed, structural, structural_manifest,
                sampler["manifest_hash"], generation_manifest,
            )
        )
        produced = execute_broad_prior_production(
            production_request, production_manifest, production_catalog, structural_manifest,
        )
        if produced["status"] != "success":
            raise ValueError(produced["error"])
        program = produced["output"]["program"]
        # Both piano tracks share the piano timbre; point them at the catalog.
        for track in program["tracks"]:
            if track["role"] in ("harmony", "melody"):
                track["instrument_id"] = (
                    "piano_solo_harmony" if track["role"] == "harmony" else "piano_solo_melody"
                )
        catalog, catalog_bytes, catalog_digest, assets = _piano_catalog(generation_manifest)
        program["production"]["catalog_digest"] = catalog_digest
        identity = CompilerIdentity(
            "piano-solo-generation-v1/v1",
            "fixture-resolver",
            "sha256:" + "10" * 32,
            "sha256:" + "11" * 32,
            catalog_digest,
        )
        project = compile_sp0(program, identity)
        rendered = None
        if not arguments.skip_wav:
            render_manifest = _object(RENDER_FIXTURE / "render_manifest.json")
            rendered = render_reference(
                project,
                catalog_bytes,
                assets.__getitem__,
                render_manifest_digest=render_manifest["render_manifest_digest"],
                project_artifact_hash=project_hash(project),
            )
        validity = assess_piano_solo(program, project)
        g1_features = extract_composition_viability(program, project)
        evaluation_midi, evaluation_midi_manifest = export_evaluation_midi(
            project,
            program_by_track={
                "trk_harmony": 0,
                "trk_melody": 0,
            },
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))

    arguments.output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "composition_plan.json": canonical_bytes(plan),
        "structural_program.json": canonical_bytes(structural),
        "program.json": canonical_bytes(program),
        "project.json": canonical_bytes(project),
        "evaluation_reference.mid": evaluation_midi,
        "evaluation_reference_midi.json": canonical_bytes(evaluation_midi_manifest),
        "song_validity.json": canonical_bytes(validity),
        "g1_features.json": canonical_bytes(g1_features),
        "lattice_pitch.json": canonical_bytes(lattice_pitch_diagnostic(project)),
    }
    if rendered is not None:
        artifacts["reference.wav"] = rendered.wav
        artifacts["perceptual_preview.wav"] = rendered.wav
    for name, payload in artifacts.items():
        (arguments.output / name).write_bytes(payload)
    receipt = {
        "schema": "cps.piano-solo-generation-receipt",
        "schema_version": "1.0.0",
        "seed": arguments.seed,
        "structural_seed": structural_seed,
        "structural_rejection_ordinal": structural_rejection_ordinal,
        "profile_hash": profile["profile_hash"],
        "realization_profile_hash": realization_profile_hash(realization_profile),
        "plan_hash": plan["plan_hash"],
        "program_hash": program_hash(program),
        "project_hash": project_hash(project),
        "midi_hash": evaluation_midi_manifest["midi_hash"],
        "midi_manifest_hash": evaluation_midi_manifest["manifest_hash"],
        "song_validity_hash": validity["assessment_hash"],
        "g1_feature_report_hash": g1_features["report_hash"],
        "archive_eligible": validity["archive_eligible"],
        "artifact_names": sorted(artifacts),
        "non_authoritative": True,
    }
    if rendered is not None:
        receipt["wav_hash"] = rendered.report["wav_hash"]
    else:
        receipt["render_status"] = "skipped"
    (arguments.output / "receipt.json").write_bytes(canonical_bytes(receipt))
    sys.stdout.buffer.write(canonical_bytes(receipt) + b"\n")


if __name__ == "__main__":
    main()
