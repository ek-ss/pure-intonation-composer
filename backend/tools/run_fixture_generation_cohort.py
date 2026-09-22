"""Run a non-authoritative multi-seed sample/compile/render diversity trial."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import sys
import time
import wave
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.exploration_profile import (  # noqa: E402
    apply_profile_with_arrangement,
    selected_layout,
    symbolic_coverage,
    validate_profile,
)
from app.songprogram.exploration_generation import (  # noqa: E402
    derive_lattice_navigation,
    validate_exploration_generation_manifest,
)
from app.songprogram.fallback import (  # noqa: E402
    _artifact_hash,
    _search_decision_hash,
    execute_broad_prior_production,
)
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.structural_sampler import (  # noqa: E402
    _hash,
    execute_structural_sampler,
    structural_lowering_manifest_hash,
    structural_program_hash,
)

RENDER_FIXTURE = BACKEND / "songprogram_conformance" / "fixtures" / "render"
ROLE_ORDER = ("drums", "bass", "harmony", "melody", "texture")
SEARCH_MANIFEST = (
    BACKEND / "songprogram_conformance" / "fixtures" / "search" / "sampler_manifest.json"
)
SHARED_AUTHORITY = (
    BACKEND
    / "songprogram_conformance"
    / "fixtures"
    / "search_loop_13"
    / "shared_authority"
    / "artifacts"
)
PROFILE_DIRECTORY = BACKEND / "songprogram_conformance" / "profiles"
PROFILE_FILES = {
    "song-preview": PROFILE_DIRECTORY / "song_preview_exploration_v2.json",
    "full-song": PROFILE_DIRECTORY / "full_song_exploration_v2.json",
}
DEFAULT_GENERATION_MANIFEST = PROFILE_DIRECTORY / "full_song_generation_v1.json"


def _seed_choice(seed: int, domain: str, values: list[Any]) -> Any:
    digest = hashlib.sha256(f"cps.exploration-authority/v1\0{seed}\0{domain}".encode()).digest()
    return json.loads(json.dumps(values[int.from_bytes(digest[:8], "big") % len(values)]))


def _exploration_authorities(
    seed: int,
    profile: dict[str, Any] | None = None,
    generation_manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build a sealed, seed-addressed authority independent of golden fixtures."""
    sampler = json.loads((SHARED_AUTHORITY / "sampler_manifest.json").read_text())
    lowering = json.loads((SHARED_AUTHORITY / "structural_lowering_manifest.json").read_text())
    broad = json.loads(SEARCH_MANIFEST.read_text())
    for name in sampler["tables"]:
        sampler["tables"][name] = json.loads(json.dumps(broad["tables"][name]))
    if generation_manifest is None:
        generation_manifest = json.loads(DEFAULT_GENERATION_MANIFEST.read_text())
    validate_exploration_generation_manifest(generation_manifest)
    configured_tables = generation_manifest["sampler_tables"]
    lowering_choices = generation_manifest["lowering_choices"]
    weighted_domains = [
        item["value"]
        for item in configured_tables["equave_domain"]
        for _ in range(item["weight"])
    ]
    selected_domain = _seed_choice(seed, "equave-domain", weighted_domains)
    matching_chords = [
        item
        for item in configured_tables["chord_reference"]
        if item["value"]["equave"] == selected_domain["equave"]
    ]
    navigation = derive_lattice_navigation(
        selected_domain, lowering_choices["lattice_navigation"]
    )
    sampler["tables"].update(
        section_count=[{"value": 3, "weight": 1}],
        section_bars=[{"value": 8, "weight": 1}],
        total_bars=[{"value": 24, "weight": 1}],
        recall_decision=[{"value": True, "weight": 1}],
        transform_count=[{"value": 1, "weight": 1}],
        transform_type=[{"value": "rotate", "weight": 1}],
        **json.loads(json.dumps(configured_tables)),
    )
    sampler["tables"]["equave_domain"] = [{"value": selected_domain, "weight": 1}]
    sampler["tables"]["chord_reference"] = matching_chords
    if profile is not None:
        layout = selected_layout(profile, seed)
        sampler["tables"].update(
            section_count=[{"value": layout["section_count"], "weight": 1}],
            section_bars=[{"value": layout["bars_per_section"], "weight": 1}],
            total_bars=[
                {
                    "value": layout["section_count"] * layout["bars_per_section"],
                    "weight": 1,
                }
            ],
        )
    specs = [
        ("section_count", "once", ["form", "section_count"]),
        ("total_bars", "once", ["form", "total_bars"]),
        ("section_role", "per_section", ["form", "{section}", "role"]),
        ("section_bars", "per_section", ["form", "{section}", "bars"]),
        ("material_count", "once", ["materials", "count"]),
        ("material_kind", "per_material", ["materials", "{material}", "kind"]),
        ("active_roles", "once", ["roles"]),
        ("equave_domain", "once", ["lattice"]),
        ("rhythm_grid", "per_material", ["materials", "{material}", "grid"]),
        ("rhythm_density", "per_material", ["materials", "{material}", "density"]),
        ("chord_reference", "per_material", ["materials", "{material}", "chord"]),
        ("recall_decision", "per_recall", ["recall", "{section}", "{material}"]),
        ("transform_count", "per_recall", ["recall", "{recall}", "count"]),
        (
            "transform_type",
            "per_transform",
            ["recall", "{recall}", "{transform}", "type"],
        ),
        (
            "rotate_amount",
            "per_transform",
            ["recall", "{recall}", "{transform}", "amount"],
        ),
    ]
    sampler["decision_program"] = [
        {
            "ordinal": ordinal,
            "stage": "realizations" if ordinal >= 11 else "materials" if ordinal >= 4 else "form",
            "path": path,
            "table": table,
            "repeat": repeat,
        }
        for ordinal, (table, repeat, path) in enumerate(specs)
    ]
    sampler["maximum_rejections_per_seed"] = 256
    lowering["clock"]["tempo_milli_bpm"] = _seed_choice(
        seed, "tempo", lowering_choices["tempo_milli_bpm"]
    )
    lowering["lattice_constants"]["maximum_odd_limit"] = lowering_choices["maximum_odd_limit"]
    lowering["lattice_constants"]["pitch_exploration"]["maximum_domain_points"] = lowering_choices["maximum_domain_points"]
    lowering["chord_constants"]["complexity_budget"] = lowering_choices["chord_complexity_budget"]
    lowering["section_templates"]["tonal_center"] = _seed_choice(seed, "tonal-center", navigation["tonal_centers"])
    walk = _seed_choice(
        seed,
        "vector-walk",
        navigation["vector_walks"],
    )
    lowering["material_builders"]["direct_vectors"] = walk
    lowering["material_builders"]["harmony_root_anchors"] = navigation["harmony_root_anchors"]
    lowering["material_builders"]["melody_members"] = [0, 1]
    lowering["material_builders"]["rhythm_duration_ticks"] = _seed_choice(
        seed, "rhythm-duration", lowering_choices["rhythm_duration_ticks"]
    )
    lowering["material_builders"]["rhythm_accent_q"] = _seed_choice(
        seed, "rhythm-accent", lowering_choices["rhythm_accent_q"]
    )
    lowering["manifest_hash"] = structural_lowering_manifest_hash(lowering)
    sampler["structural_lowering_manifest_hash"] = lowering["manifest_hash"]
    sampler["manifest_hash"] = _hash(
        "cps.exploration-sampler-manifest/v1", sampler, omit="manifest_hash"
    )
    request = {
        "schema": "cps.structural-sampler-request",
        "schema_version": "1.1.0",
        "run_hash": _hash("cps.exploration-run/v1", {"seed": seed}),
        "context_hash": _hash("cps.exploration-context/v1", {"seed": seed}),
        "source_decision_hash": _hash("cps.exploration-source/v1", {"seed": seed}),
        "sampler_manifest_hash": sampler["manifest_hash"],
        "structural_lowering_manifest_hash": lowering["manifest_hash"],
        "structural_program_schema_hash": sampler["structural_program_schema_hash"],
        "structural_rejection_evidence_schema_hash": sampler[
            "structural_rejection_evidence_schema_hash"
        ],
        "root_seed": seed,
        "cohort_index": seed,
        "request_hash": "",
    }
    request["request_hash"] = _hash(
        "cps.structural-sampler-request/v1.1", request, omit="request_hash"
    )
    return request, sampler, lowering


def _production_authorities(
    seed: int,
    structural: dict[str, Any],
    lowering: dict[str, Any],
    sampler_hash: str,
    generation_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = json.loads((SHARED_AUTHORITY / "broad_prior_production_manifest.json").read_text())
    catalog = json.loads((SHARED_AUTHORITY / "instrument_catalog.json").read_text())
    policy = generation_manifest["production_policy"]
    for entry in catalog["entries"]:
        entry["maximum_polyphony"] = policy["maximum_polyphony"]
        if entry["role"] != "drums":
            entry["allowed_frequency_millihz"] = policy["pitched_frequency_millihz"]
    drum_map = {
        lane: row["drum_note"]
        for lane, row in generation_manifest["render_catalog_policy"]["drum_lanes"].items()
    }
    drum_entry = next(entry for entry in catalog["entries"] if entry["role"] == "drums")
    source_mapping = drum_entry["note_map"][0]
    drum_entry["note_map"] = [
        {**source_mapping, "drum_note": note} for note in sorted(drum_map.values())
    ]
    catalog_digest = (
        "sha256:"
        + hashlib.sha256(b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)).hexdigest()
    )
    manifest["instrument_catalog_digest"] = catalog_digest
    manifest["sampler_manifest_hash"] = sampler_hash
    manifest["register_presets_by_role"] = {
        role: [{"value": policy["register_millicents"], "weight": 1}] for role in ROLE_ORDER[1:]
    }
    manifest["polyphony_by_role"] = {
        role: [{"value": policy["maximum_polyphony"], "weight": 1}] for role in ROLE_ORDER
    }
    manifest["drum_map_profiles"] = [
        {
            "value": {
                "drum_map_id": "composition-multilane-v1",
                "drum_map": drum_map,
                "drum_map_payload_hash": _hash("cps.drum-map-profile/v1", drum_map),
            },
            "weight": 1,
        }
    ]
    active_roles = sorted(
        {item["role"] for item in structural["realizations"]}, key=ROLE_ORDER.index
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
        "production_lowering_manifest_hash": _artifact_hash(
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


def _wav_asset(samples: list[int]) -> tuple[dict[str, Any], bytes]:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 4, 48000, len(samples), "NONE", "not compressed"))
        output.writeframes(b"".join(struct.pack("<i", sample) for sample in samples))
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "uri": f"asset://sha256/{digest}",
        "sha256": f"sha256:{digest}",
        "byte_length": len(payload),
        "frames": len(samples),
        "channels": 1,
        "sample_rate": 48000,
    }, payload


def _trial_catalog(
    generation_manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bytes, str, dict[str, bytes]]:
    if generation_manifest is None:
        generation_manifest = json.loads(DEFAULT_GENERATION_MANIFEST.read_text())
    validate_exploration_generation_manifest(generation_manifest)
    policy = generation_manifest["render_catalog_policy"]
    assets: dict[str, bytes] = {}

    def asset(samples: list[int]) -> dict[str, Any]:
        descriptor, payload = _wav_asset(samples)
        assets[descriptor["uri"]] = payload
        return descriptor

    drum_assets = {
        lane: asset(row["samples_q31"])
        for lane, row in policy["drum_lanes"].items()
    }
    entries: list[dict[str, Any]] = [
        {
            "engine": "sample-linear-q31/v1",
            "gain_q14": 16384,
            "instrument_id": "drum_fixture_kit",
            "kind": "drum_kit",
            "maximum_polyphony": generation_manifest["production_policy"]["maximum_polyphony"],
            "note_map": [
                {
                    "asset": drum_assets[lane],
                    "drum_note": row["drum_note"],
                    "gain_q14": 16384,
                }
                for lane, row in sorted(
                    policy["drum_lanes"].items(), key=lambda item: item[1]["drum_note"]
                )
            ],
            "role": "drums",
        }
    ]
    for role in ROLE_ORDER[1:]:
        timbre = policy["pitched_roles"][role]
        samples = [
            round(
                sum(
                    gain * math.sin(2 * math.pi * partial * frame / 256)
                    for partial, gain in zip(timbre["partials"], timbre["partial_gains_q31"])
                )
            )
            for frame in range(256)
        ]
        entries.append(
            {
                "allowed_frequency_millihz": generation_manifest["production_policy"][
                    "pitched_frequency_millihz"
                ],
                "asset": asset(samples),
                "engine": "sample-linear-q31/v1",
                "gain_q14": timbre["gain_q14"],
                "instrument_id": f"trial_{role}",
                "kind": "pitched",
                "loop": {"end_frame": 256, "mode": "forward", "start_frame": 0},
                "maximum_polyphony": generation_manifest["production_policy"]["maximum_polyphony"],
                "release_frames": timbre["release_frames"],
                "role": role,
                "root_frequency_millihz": 220000,
            }
        )
    catalog = {
        "schema": "cps.instrument-catalog",
        "schema_version": "1.0.0",
        "engine": "sample-linear-q31/v1",
        "entries": entries,
    }
    payload = canonical_bytes(catalog)
    digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + payload).hexdigest()
    return catalog, payload, digest, assets


def _one(
    seed: int,
    output: str,
    profile_path: str | None = None,
    generation_manifest_path: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {"seed": seed, "status": "sampler_failed"}
    try:
        profile = None
        if profile_path is not None:
            profile = json.loads(Path(profile_path).read_text())
            validate_profile(profile)
            row.update(profile_id=profile["profile_id"], profile_hash=profile["profile_hash"])
        generation_manifest = json.loads(
            Path(generation_manifest_path or DEFAULT_GENERATION_MANIFEST).read_text()
        )
        validate_exploration_generation_manifest(generation_manifest)
        row["generation_manifest_hash"] = generation_manifest["manifest_hash"]
        request, sampler, structural_manifest = _exploration_authorities(
            seed, profile, generation_manifest
        )
        sampled = execute_structural_sampler(request, sampler, structural_manifest)
        if sampled["result"]["status"] != "success":
            row["error"] = sampled["result"]["error"]
            return row
        structural = sampled["structural_program"]
        arrangement = None
        if profile is not None:
            structural, arrangement = apply_profile_with_arrangement(structural, profile, seed)
        row.update(
            sampled_equave=structural["lattice"]["equave"],
            sampled_generators=structural["lattice"]["generators"],
            sampler_manifest_hash=sampler["manifest_hash"],
            lowering_manifest_hash=structural_manifest["manifest_hash"],
        )
        production_request, production_manifest, production_catalog = _production_authorities(
            seed, structural, structural_manifest, sampler["manifest_hash"], generation_manifest
        )
        active_roles = production_request["active_roles"]
        produced = execute_broad_prior_production(
            production_request,
            production_manifest,
            production_catalog,
            structural_manifest,
        )
        if produced["status"] != "success":
            row.update(status="production_failed", error=produced["error"])
            return row
        program = produced["output"]["program"]
        catalog, catalog_bytes, catalog_digest, assets = _trial_catalog(generation_manifest)
        program["production"]["catalog_digest"] = catalog_digest
        for track in program["tracks"]:
            track["instrument_id"] = (
                "drum_fixture_kit" if track["role"] == "drums" else f"trial_{track['role']}"
            )
        identity = CompilerIdentity(
            "fixture-cohort/v1",
            "fixture-resolver",
            "sha256:" + "10" * 32,
            "sha256:" + "11" * 32,
            catalog_digest,
        )
        compile_started = time.monotonic()
        project = compile_sp0(program, identity)
        compile_ms = round((time.monotonic() - compile_started) * 1000)
        coverage = symbolic_coverage(project, profile) if profile is not None else None
        manifest = json.loads((RENDER_FIXTURE / "render_manifest.json").read_text())

        def resolve(uri: str) -> bytes:
            return assets[uri]

        rendered = render_reference(
            project,
            catalog_bytes,
            resolve,
            render_manifest_digest=manifest["render_manifest_digest"],
            project_artifact_hash=project_hash(project),
        )
        destination = Path(output) / f"seed-{seed:04d}"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "sampler_manifest.json").write_bytes(canonical_bytes(sampler))
        (destination / "lowering_manifest.json").write_bytes(canonical_bytes(structural_manifest))
        (destination / "program.json").write_bytes(canonical_bytes(program))
        (destination / "project.json").write_bytes(canonical_bytes(project))
        (destination / "preview.wav").write_bytes(rendered.wav)
        if arrangement is not None:
            (destination / "arrangement_plan.json").write_bytes(canonical_bytes(arrangement))
        pitched = [event for event in project["events"] if event["kind"] == "note"]
        vectors = [
            tuple(event["pitch_provenance"]["final_vector"])
            for event in pitched
            if event["pitch_provenance"].get("final_vector") is not None
        ]
        vector_counts = Counter(vectors)
        row.update(
            status="success",
            program_hash=program_hash(program),
            project_hash=project_hash(project),
            audible_project_hash=audible_project_hash(project),
            wav_hash=rendered.report["wav_hash"],
            event_count=len(project["events"]),
            compile_ms=compile_ms,
            roles=active_roles,
            material_kinds=sorted(
                [item["kind"] for item in program["materials"] if item["kind"] != "rhythm_cell"]
            ),
            equave=program["lattice"]["equave"],
            generators=program["lattice"]["generators"],
            pitched_event_count=len(pitched),
            vector_observation_count=len(vectors),
            nonzero_vector_count=sum(any(value != 0 for value in vector) for vector in vectors),
            unique_vectors=[list(vector) for vector in sorted(set(vectors))],
            vector_event_count=[
                {"vector": list(vector), "event_count": count}
                for vector, count in sorted(vector_counts.items())
            ],
            pcm_continuity=pcm_continuity(rendered.wav),
        )
        if coverage is not None:
            row["symbolic_coverage"] = coverage
        if arrangement is not None:
            row["arrangement"] = {
                "plan_hash": arrangement["plan_hash"],
                "distinct_role_mask_count": arrangement["distinct_role_mask_count"],
                "sounding_role_count": arrangement["sounding_role_count"],
                "status": arrangement["status"],
                "section_role_counts": [
                    len(item["active_roles"]) for item in arrangement["section_plans"]
                ],
            }
        return row
    except Exception as error:  # trial ledger must retain every failed coordinate
        row.update(status="compile_or_render_failed", error=f"{type(error).__name__}:{error}")
        return row
    finally:
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)


def _duplicates(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values = [row[key] for row in rows if row["status"] == "success"]
    unique = len(set(values))
    duplicates = len(values) - unique
    return {
        "total": len(values),
        "unique": unique,
        "duplicates": duplicates,
        "duplicate_basis_points": round(10000 * duplicates / len(values)) if values else 0,
    }


def pcm_continuity(wav_payload: bytes) -> dict[str, int]:
    """Measure exact zero-valued frames and fully silent one-second windows."""
    with wave.open(io.BytesIO(wav_payload), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        frame_count = source.getnframes()
        if source.getsampwidth() != 4:
            raise ValueError("PCM_CONTINUITY_REQUIRES_PCM32")
        samples = struct.unpack(
            "<" + "i" * (frame_count * channels), source.readframes(frame_count)
        )
    active_frames = [
        any(samples[frame * channels + channel] != 0 for channel in range(channels))
        for frame in range(frame_count)
    ]
    windows = [
        any(active_frames[start : min(frame_count, start + rate)])
        for start in range(0, frame_count, rate)
    ]
    silent_frames = frame_count - sum(active_frames)
    return {
        "frame_count": frame_count,
        "silent_frame_count": silent_frames,
        "silent_frame_basis_points": round(10000 * silent_frames / frame_count)
        if frame_count
        else 10000,
        "one_second_window_count": len(windows),
        "fully_silent_one_second_window_count": windows.count(False),
    }


def audible_project_hash(project: dict[str, Any]) -> str:
    """Hash only fields that can alter reference-renderer PCM."""
    tracks = {track["id"]: track for track in project["tracks"]}
    payload = {
        "clock": project["clock"],
        "base_frequency_millihz": project["lattice"]["base_frequency_millihz"],
        "tracks": [
            {
                "role": track["role"],
                "instrument_id": track["instrument_id"],
                "maximum_polyphony": track["maximum_polyphony"],
                "mix": project["mix"][track["id"]],
            }
            for track in sorted(project["tracks"], key=lambda item: item["role"].encode())
        ],
        "events": [
            {
                key: value
                for key in (
                    "kind",
                    "role",
                    "start_tick",
                    "duration_ticks",
                    "velocity",
                    "ratio",
                    "drum_note",
                )
                if (value := ({**event, "role": tracks[event["track_id"]]["role"]}).get(key))
                is not None
            }
            for event in project["events"]
        ],
    }
    return (
        "sha256:"
        + hashlib.sha256(b"cps.audible-project/v1\0" + canonical_bytes(payload)).hexdigest()
    )


def _one_star(arguments: tuple[int, str, str | None, str]) -> dict[str, Any]:
    """Pickle-safe adapter for the multi-process execution path."""
    return _one(*arguments)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generation-manifest", type=Path, default=DEFAULT_GENERATION_MANIFEST)
    parser.add_argument(
        "--profile",
        choices=("cohort", "song-preview", "full-song"),
        default="cohort",
    )
    args = parser.parse_args()
    if (
        not 1 <= args.seeds <= 1000
        or not 0 <= args.seed_start <= (2**64 - args.seeds)
        or not 1 <= args.workers <= 32
    ):
        parser.error("seeds must be 1..1000, seed-start must fit uint64, and workers 1..32")
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.generation_manifest.is_file():
        parser.error(f"generation manifest does not exist: {args.generation_manifest}")
    try:
        generation_manifest = json.loads(args.generation_manifest.read_text())
        validate_exploration_generation_manifest(generation_manifest)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    (args.output / "generation_manifest.json").write_bytes(canonical_bytes(generation_manifest))
    profile_path = None if args.profile == "cohort" else PROFILE_FILES[args.profile]
    profile = None
    if profile_path is not None:
        profile = json.loads(profile_path.read_text())
        validate_profile(profile)
        (args.output / "exploration_profile.json").write_bytes(canonical_bytes(profile))
    _, catalog_bytes, catalog_digest, _ = _trial_catalog(generation_manifest)
    (args.output / "exploration_catalog.json").write_bytes(catalog_bytes)
    seed_values = list(range(args.seed_start, args.seed_start + args.seeds))
    worker_arguments = [
        (
            seed,
            str(args.output),
            None if profile_path is None else str(profile_path),
            str(args.generation_manifest),
        )
        for seed in seed_values
    ]
    if args.workers == 1:
        rows = [_one(*arguments) for arguments in worker_arguments]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            rows = list(pool.map(_one_star, worker_arguments))
    rows.sort(key=lambda row: row["seed"])
    successes = [row for row in rows if row["status"] == "success"]
    representatives: dict[str, int] = {}
    for row in successes:
        digest = row["audible_project_hash"]
        coverage_passed = row.get("symbolic_coverage", {}).get("status", "passed") == "passed"
        arrangement_passed = row.get("arrangement", {}).get("status", "passed") == "passed"
        maximum_silent_windows = (
            profile.get("coverage_gate", {}).get("maximum_fully_silent_one_second_windows")
            if profile is not None
            else None
        )
        pcm_passed = (
            maximum_silent_windows is None
            or row.get("pcm_continuity", {}).get("fully_silent_one_second_window_count", 0)
            <= maximum_silent_windows
        )
        if not arrangement_passed:
            row["semantic_admission"] = {
                "status": "rejected_arrangement",
                "representative_seed": None,
            }
        elif not pcm_passed:
            row["semantic_admission"] = {
                "status": "rejected_pcm_silence",
                "representative_seed": None,
            }
        elif not coverage_passed:
            row["semantic_admission"] = {
                "status": "rejected_coverage",
                "representative_seed": None,
            }
        elif digest in representatives:
            row["semantic_admission"] = {
                "status": "rejected_duplicate",
                "representative_seed": representatives[digest],
            }
        else:
            row["semantic_admission"] = {
                "status": "accepted",
                "representative_seed": row["seed"],
            }
            representatives[digest] = row["seed"]
    admission_counts = Counter(row["semantic_admission"]["status"] for row in successes)
    role_presence = Counter(role for row in successes for role in row["roles"])
    material_counts = Counter(kind for row in successes for kind in row["material_kinds"])
    failure_counts = Counter(
        row.get("error", "UNKNOWN") for row in rows if row["status"] != "success"
    )
    equaves = Counter(row["equave"] for row in successes)
    vectors = Counter(tuple(vector) for row in successes for vector in row["unique_vectors"])
    vector_events: Counter[tuple[int, ...]] = Counter()
    for row in successes:
        vector_events.update(
            {tuple(item["vector"]): item["event_count"] for item in row["vector_event_count"]}
        )
    report = {
        "schema": "cps.fixture-generation-cohort-report",
        "schema_version": "1.0.0",
        "non_authoritative": True,
        "profile_id": "cohort" if profile is None else profile["profile_id"],
        "profile_hash": None if profile is None else profile["profile_hash"],
        "generation_manifest_id": generation_manifest["manifest_id"],
        "generation_manifest_hash": generation_manifest["manifest_hash"],
        "seed_count": args.seeds,
        "seed_start": args.seed_start,
        "worker_count": args.workers,
        "exploration_catalog_digest": catalog_digest,
        "compile_survival": {
            "success": len(successes),
            "failed": args.seeds - len(successes),
            "basis_points": round(10000 * len(successes) / args.seeds),
        },
        "processing_time_ms": {
            "total": sum(row["elapsed_ms"] for row in rows),
            "minimum": min((row["elapsed_ms"] for row in rows), default=0),
            "maximum": max((row["elapsed_ms"] for row in rows), default=0),
            "mean": round(sum(row["elapsed_ms"] for row in rows) / len(rows)) if rows else 0,
            "compile_mean": round(
                sum(row.get("compile_ms", 0) for row in successes) / len(successes)
            )
            if successes
            else 0,
        },
        "failure_count": dict(sorted(failure_counts.items())),
        "duplicates": {
            key: _duplicates(rows, key)
            for key in (
                "program_hash",
                "project_hash",
                "audible_project_hash",
                "wav_hash",
            )
        },
        "semantic_duplicate_rejection": {
            "policy": "first-seed-wins-by-audible-project-hash/v1",
            "accepted": admission_counts["accepted"],
            "rejected_duplicate": admission_counts["rejected_duplicate"],
            "rejected_coverage": admission_counts["rejected_coverage"],
            "rejected_arrangement": admission_counts["rejected_arrangement"],
            "rejected_pcm_silence": admission_counts["rejected_pcm_silence"],
        },
        "symbolic_coverage": {
            "measured": sum("symbolic_coverage" in row for row in successes),
            "passed": sum(
                row.get("symbolic_coverage", {}).get("status") == "passed" for row in successes
            ),
            "rejected": sum(
                row.get("symbolic_coverage", {}).get("status") == "rejected" for row in successes
            ),
            "mean_coverage_basis_points": round(
                sum(
                    row.get("symbolic_coverage", {}).get("overall_coverage_basis_points", 0)
                    for row in successes
                )
                / max(1, sum("symbolic_coverage" in row for row in successes))
            ),
            "maximum_empty_bar_run": max(
                (
                    row.get("symbolic_coverage", {}).get("maximum_empty_bar_run", 0)
                    for row in successes
                ),
                default=0,
            ),
        },
        "pcm_continuity": {
            "measured": sum("pcm_continuity" in row for row in successes),
            "silent_frame_basis_points": round(
                10000
                * sum(
                    row.get("pcm_continuity", {}).get("silent_frame_count", 0) for row in successes
                )
                / max(
                    1,
                    sum(row.get("pcm_continuity", {}).get("frame_count", 0) for row in successes),
                )
            ),
            "fully_silent_one_second_window_count": sum(
                row.get("pcm_continuity", {}).get("fully_silent_one_second_window_count", 0)
                for row in successes
            ),
            "one_second_window_count": sum(
                row.get("pcm_continuity", {}).get("one_second_window_count", 0) for row in successes
            ),
        },
        "arrangement": {
            "measured": sum("arrangement" in row for row in successes),
            "passed": sum(
                row.get("arrangement", {}).get("status") == "passed" for row in successes
            ),
            "rejected": sum(
                row.get("arrangement", {}).get("status") == "rejected" for row in successes
            ),
            "minimum_distinct_role_mask_count": min(
                (
                    row["arrangement"]["distinct_role_mask_count"]
                    for row in successes
                    if "arrangement" in row
                ),
                default=0,
            ),
            "maximum_distinct_role_mask_count": max(
                (
                    row["arrangement"]["distinct_role_mask_count"]
                    for row in successes
                    if "arrangement" in row
                ),
                default=0,
            ),
        },
        "role_presence": dict(sorted(role_presence.items())),
        "role_presence_basis_points": {
            role: round(10000 * count / len(successes)) if successes else 0
            for role, count in sorted(role_presence.items())
        },
        "material_kind_count": dict(sorted(material_counts.items())),
        "lattice_exposure": {
            "equave_count": dict(sorted(equaves.items())),
            "unique_vector_count": len(vectors),
            "vector_candidate_presence": [
                {"vector": list(vector), "candidate_count": count}
                for vector, count in sorted(vectors.items())
            ],
            "vector_event_count": [
                {"vector": list(vector), "event_count": count}
                for vector, count in sorted(vector_events.items())
            ],
            "pitched_event_count": sum(row["pitched_event_count"] for row in successes),
            "nonzero_vector_count": sum(row["nonzero_vector_count"] for row in successes),
        },
        "rows": rows,
    }
    payload = canonical_bytes(report)
    (args.output / "cohort_report.json").write_bytes(payload)
    sys.stdout.buffer.write(payload)


if __name__ == "__main__":
    main()
