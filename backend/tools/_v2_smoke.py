"""Throwaway smoke test: run the v2 piano pipeline for one seed, stop after compile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0
from app.songprogram.composition_generation import generate_composition_plan
from app.songprogram.composition_lowering import lower_composition_plan
from app.songprogram.fallback import execute_broad_prior_production, structural_program_hash
from app.songprogram.search import canonical_bytes
from app.songprogram.structural_sampler import _hash, execute_structural_sampler
from tools.run_fixture_generation_cohort import _exploration_authorities

PROFILES = BACKEND / "songprogram_conformance" / "profiles" / "g1_experiments"


def _object(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    profile = _object(PROFILES / "piano_solo_v2.json")
    realization_profile = _object(PROFILES / "piano_solo_roles_v2.json")
    generation_manifest = _object(PROFILES / "piano_solo_generation_v2.json")

    plan = generate_composition_plan(profile, seed)
    structural_seed = seed
    request, sampler, structural_manifest = _exploration_authorities(
        structural_seed, None, generation_manifest
    )
    sampled = execute_structural_sampler(request, sampler, structural_manifest)
    if sampled["result"]["status"] != "success":
        print("sampler failed:", sampled["result"].get("error"))
        return
    structural = lower_composition_plan(
        sampled["structural_program"], plan, realization_profile, v2=True
    )
    print("lowering OK: materials", len(structural["materials"]),
          "realizations", len(structural["realizations"]))

    # Production authorities (v2: per-role register presets).
    manifest = _object(PROFILES / "piano_solo_production.json")
    catalog = _object(PROFILES / "piano_solo_catalog.json")
    policy = generation_manifest["production_policy"]
    for entry in catalog["entries"]:
        entry["maximum_polyphony"] = policy["maximum_polyphony"]
        if entry.get("role") != "drums":
            entry["allowed_frequency_millihz"] = policy["pitched_frequency_millihz"]
    import hashlib
    catalog_digest = "sha256:" + hashlib.sha256(
        b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)
    ).hexdigest()
    manifest["instrument_catalog_digest"] = catalog_digest
    manifest["sampler_manifest_hash"] = sampler["manifest_hash"]
    role_order = ["drums", "bass", "harmony", "melody", "texture"]
    by_role = policy.get("register_millicents_by_role")
    manifest["register_presets_by_role"] = {
        role: [{"value": (by_role or {}).get(role, policy["register_millicents"]), "weight": 1}]
        for role in role_order if role != "drums"
    }
    manifest["polyphony_by_role"] = {
        role: [{"value": policy["maximum_polyphony"], "weight": 1}] for role in role_order
    }
    active_roles = sorted(
        {item["role"] for item in structural["realizations"]},
        key=["drums", "bass", "harmony", "melody", "texture"].index,
    )
    from app.songprogram.fallback import _search_decision_hash
    req = {
        "schema": "cps.broad-prior-production-request",
        "schema_version": "1.1.0",
        "run_hash": _hash("cps.exploration-run/v1", {"seed": seed}),
        "context_hash": _hash("cps.exploration-context/v1", {"seed": seed}),
        "source_decision_hash": _hash("cps.exploration-source/v1", {"seed": seed}),
        "root_seed": seed,
        "cohort_index": seed,
        "production_rejection_ordinal": 0,
        "sampler_manifest_hash": manifest["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": structural_manifest["manifest_hash"],
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
    req["request_hash"] = _search_decision_hash(req, "request_hash")
    produced = execute_broad_prior_production(
        req, manifest, catalog, structural_manifest
    )
    if produced["status"] != "success":
        print("production failed:", produced["error"])
        return
    program = produced["output"]["program"]
    for track in program["tracks"]:
        if track["role"] in ("harmony", "melody"):
            track["instrument_id"] = (
                "piano_solo_harmony" if track["role"] == "harmony" else "piano_solo_melody"
            )
    identity = CompilerIdentity(
        "piano-solo-generation-v2/v1",
        "fixture-resolver",
        "sha256:" + "10" * 32,
        "sha256:" + "11" * 32,
        catalog_digest,
    )
    project = compile_sp0(program, identity)
    print("compile OK: events", len(project["events"]),
          "resolved_chords", len(project["resolved_chords"]),
          "harmony_occurrences", len(project["harmony_occurrences"]))
    # Register sanity: count notes outside the v2 hard register.
    from app.songprogram.compiler import _mc, _ratio, _piano_v2_hard_register
    tracks_by_id = {t["id"]: t for t in project["tracks"]}
    outside = 0
    for event in project["events"]:
        if event["kind"] != "note":
            continue
        reg = _piano_v2_hard_register(tracks_by_id[event["track_id"]]["instrument_id"])
        if reg is None:
            continue
        mc = _mc(_ratio(event["ratio"]))
        if not reg[0] <= mc <= reg[1]:
            outside += 1
    print("notes outside hard register:", outside)


if __name__ == "__main__":
    main()
