"""Debug: which v2 anchors fail the register filter?"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from fractions import Fraction

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import (
    _harmony_query, _reduced_anchor_exponent, _v2_bass_anchor_exponent,
    _piano_v2_chord_in_register, _mc, _ratio, _vector_ratio,
    _PIANO_V2_BASS_MILLICENTS, _PIANO_V2_HARD_REGISTER,
)
from app.songprogram.resolver import resolve_joint_bnb

PROFILES = BACKEND / "songprogram_conformance" / "profiles" / "g1_experiments"


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    # Rebuild the program like the smoke test.
    from tools._v2_smoke import _object
    import hashlib
    from app.songprogram.composition_generation import generate_composition_plan
    from app.songprogram.composition_lowering import lower_composition_plan
    from app.songprogram.fallback import (
        execute_broad_prior_production, structural_program_hash, _search_decision_hash,
    )
    from app.songprogram.search import canonical_bytes
    from app.songprogram.structural_sampler import _hash, execute_structural_sampler
    from tools.run_fixture_generation_cohort import _exploration_authorities

    profile = _object(PROFILES / "piano_solo_v2.json")
    realization_profile = _object(PROFILES / "piano_solo_roles_v2.json")
    generation_manifest = _object(PROFILES / "piano_solo_generation_v2.json")
    plan = generate_composition_plan(profile, seed)
    request, sampler, structural_manifest = _exploration_authorities(
        seed, None, generation_manifest
    )
    sampled = execute_structural_sampler(request, sampler, structural_manifest)
    structural = lower_composition_plan(
        sampled["structural_program"], plan, realization_profile, v2=True
    )
    manifest = _object(PROFILES / "piano_solo_production.json")
    catalog = _object(PROFILES / "piano_solo_catalog.json")
    policy = generation_manifest["production_policy"]
    for entry in catalog["entries"]:
        entry["maximum_polyphony"] = policy["maximum_polyphony"]
        if entry.get("role") != "drums":
            entry["allowed_frequency_millihz"] = policy["pitched_frequency_millihz"]
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
    req = {
        "schema": "cps.broad-prior-production-request",
        "schema_version": "1.1.0",
        "run_hash": _hash("cps.exploration-run/v1", {"seed": seed}),
        "context_hash": _hash("cps.exploration-context/v1", {"seed": seed}),
        "source_decision_hash": _hash("cps.exploration-source/v1", {"seed": seed}),
        "root_seed": seed, "cohort_index": seed,
        "production_rejection_ordinal": 0,
        "sampler_manifest_hash": manifest["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": structural_manifest["manifest_hash"],
        "production_lowering_manifest_hash": _hash(
            "cps.production-lowering-manifest/v1", manifest),
        "instrument_catalog_digest": catalog_digest,
        "structural_program_hash": structural_program_hash(structural),
        "structural_program": structural,
        "active_roles": active_roles,
        "lattice_equave": structural["lattice"]["equave"],
        "request_hash": "",
    }
    req["request_hash"] = _search_decision_hash(req, "request_hash")
    produced = execute_broad_prior_production(req, manifest, catalog, structural_manifest)
    program = produced["output"]["program"]

    lattice = dict(program["lattice"])
    lattice.setdefault("domain_hash", "sha256:" + "0" * 64)
    print("lattice register_bounds:", lattice["register_bounds"],
          "reduce_anchor_mod_equave:", lattice.get("reduce_anchor_mod_equave"))
    print("hard register harmony:", _PIANO_V2_HARD_REGISTER["piano_solo_harmony"])
    print("bass register:", _PIANO_V2_BASS_MILLICENTS)

    intents = {intent["id"]: intent for intent in program["chord_intents"]}
    seen = set()
    fail = 0
    for material in program["materials"]:
        if material["kind"] != "harmony_intent_cell":
            continue
        for anchor in material["root_anchors"]:
            key = (tuple(anchor), material["chord_intent_ids"][0])
            if key in seen:
                continue
            seen.add(key)
            intent = intents[material["chord_intent_ids"][0]]
            base_exp = _reduced_anchor_exponent(lattice, anchor)
            v2_exp = _v2_bass_anchor_exponent(lattice, anchor)
            reduced_ratio = None
            value = Fraction(1)
            for g, p in zip(lattice["generators"], anchor):
                value *= Fraction(g) ** p
            reduced_ratio = value * Fraction(2) ** base_exp
            v2_ratio = value * Fraction(2) ** (v2_exp if v2_exp is not None else base_exp)
            query = _harmony_query(program, intent, anchor,
                                    anchor_exponent=v2_exp)
            cores = resolve_joint_bnb(query, 24)
            from app.songprogram.compiler import _chord_from_core, CompilerIdentity
            identity = CompilerIdentity("x", "y", "z", "w", "v")
            chords = [_chord_from_core(c, lattice=lattice, intent=intent,
                                       anchor=anchor, identity=identity) for c in cores]
            in_reg = [c for c in chords if _piano_v2_chord_in_register(lattice, c)]
            status = "OK" if in_reg else "FAIL"
            if not in_reg:
                fail += 1
            # Show the anchor's reduced + v2 pitch and the chord voice range.
            if cores:
                c0 = chords[0]
                mcs = []
                for off, exp in zip(c0["voice_offsets"], c0["equave_exponents"]):
                    vec = [a + o for a, o in zip(c0["anchor_vector"], off)]
                    mcs.append(_mc(_vector_ratio(
                        [_ratio(g) for g in lattice["generators"]], vec,
                        _ratio(lattice["equave"]), exp)))
                mcs.sort()
                print(f"{status} anchor={anchor} base_exp={base_exp} v2_exp={v2_exp} "
                      f"reduced_mc={_mc(reduced_ratio)} v2_mc={_mc(v2_ratio)} "
                      f"cores={len(cores)} in_reg={len(in_reg)} "
                      f"voice_range=[{mcs[0]}, {mcs[-1]}]")
            else:
                print(f"{status} anchor={anchor} base_exp={base_exp} v2_exp={v2_exp} "
                      f"reduced_mc={_mc(reduced_ratio)} v2_mc={_mc(v2_ratio)} cores=0")
    print(f"\ntotal unique (anchor,intent): {len(seen)}, failures: {fail}")


if __name__ == "__main__":
    main()
