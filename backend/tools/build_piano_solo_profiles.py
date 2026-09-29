"""Build reproducible piano-solo composition, realization, and generation profiles.

The piano-solo pipeline reuses the full-song plan/lowering/production machinery
but constrains it to two piano tracks (chord progression + main melody) on a
small 2D lattice.  This builder derives the three sealed authority files from
the frozen full-song bases so the hashes stay reproducible.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_generation import (  # noqa: E402
    composition_profile_hash, validate_composition_profile,
)
from app.songprogram.composition_realization import (  # noqa: E402
    realization_profile_hash, validate_realization_profile,
)
from app.songprogram.exploration_generation import (  # noqa: E402
    exploration_generation_manifest_hash, validate_exploration_generation_manifest,
)

PROFILES = BACKEND / "songprogram_conformance/profiles"
DESTINATION = PROFILES / "g1_experiments"

# The two piano roles.  Both map to the same piano instrument at production time.
PIANO_ROLES = ["harmony", "melody"]

# A 2D octave-equivalent lattice: fifths + major thirds generate the diatonic
# scale and triads.  Bounds [-4, 4]^2 give a full domain of 9^2 = 81 points
# (vs 9^3 = 729 for the full 3D lattice) while the centered navigation half
# domain [-2, 2]^2 still covers every 12-TET tonal center within 50 cents.
PIANO_DOMAIN = {
    "equave": "2/1",
    "generators": ["3/1", "5/1"],
    "coordinate_bounds": [[-4, 4], [-4, 4]],
    "register_bounds": [-8, 8],
    # The [3/1, 5/1] generators make tonal centers drift many octaves from the
    # reference; reducing the anchor mod equave pins each chord to the register.
    "reduce_anchor_mod_equave": True,
}

# v2 (spec §11): the lattice register is narrowed to the three octaves that
# contain the piano hard registers (C3–G5 relative to the 440 Hz base).
# Exponent band -2..0 covers ratios [1/4, 2) = A2–A5; the per-track hard
# registers (C3–C5 harmony, G3–G5 melody) are enforced by the compiler on top
# of this because the exponent band alone cannot bound the composite of
# generator coordinates, equave exponent, and re-octaving.
PIANO_DOMAIN_V2 = {
    **PIANO_DOMAIN,
    "register_bounds": [-2, 0],
}

# v2 register bounds in millicents relative to the lattice base (440 Hz = A4).
# 12-TET boundaries; the compiler compares exact-ratio millicents against them
# (never MIDI-rounded values).  The candidate main registers are the placement
# targets; the hard registers are the strict limits (phrase peaks and accents
# may reach the hard edge, nothing may cross it).
#   harmony C3–C5  = (-2100, +300) cents   melody G3–G5 = (-1400, +1000) cents
#   main    C3–G4  = (-2100, -200) cents   main    G3–E5 = (-1400, +700) cents
#   bass    C3–C4  = (-2100, -900) cents
PIANO_V2_REGISTER = {
    "harmony": {
        "main_millicents": [-2_100_000, -200_000],
        "hard_millicents": [-2_100_000, 300_000],
    },
    "melody": {
        "main_millicents": [-1_400_000, 700_000],
        "hard_millicents": [-1_400_000, 1_000_000],
    },
}
# The bass layer of the comping (lowest voice of each articulation) stays in
# C3–C4 so the chord's bass is stable.
PIANO_V2_BASS_MILLICENTS = [-2_100_000, -900_000]
# The catalog frequency window covering the union of the hard registers with
# margin (A2–A5); the renderer rejects any note outside it.
PIANO_V2_FREQUENCY_MILLIHZ = [110_000, 880_000]


def build_composition_profile(base: dict, profile_id: str = "piano-solo-v1") -> dict:
    validate_composition_profile(base)
    result = copy.deepcopy(base)
    result["profile_id"] = profile_id
    # The melody chord-member cycle drives the main-melody anchors.  Drum/bass
    # onsets are retained for schema shape but unused (those roles are inactive).
    result["part_coordination_policy"]["melody_chord_member_cycle"] = [0, 1, 2]
    result["profile_hash"] = composition_profile_hash(result)
    validate_composition_profile(result)
    return result


def build_realization_profile(base: dict, profile_id: str = "piano-solo-roles-v1") -> dict:
    validate_realization_profile(base)
    result = copy.deepcopy(base)
    result["profile_id"] = profile_id
    # Every section function realizes exactly the two piano roles.
    for function in result["role_masks_by_function"]:
        result["role_masks_by_function"][function] = [
            {"roles": list(PIANO_ROLES), "weight": 1},
        ]
    result["profile_hash"] = realization_profile_hash(result)
    validate_realization_profile(result)
    return result


def build_generation_manifest(
    base: dict,
    manifest_id: str = "piano-solo-generation-v1",
    domain: dict | None = None,
) -> dict:
    validate_exploration_generation_manifest(base)
    result = copy.deepcopy(base)
    result["manifest_id"] = manifest_id
    # Single 2D lattice domain.
    result["sampler_tables"]["equave_domain"] = [
        {"value": copy.deepcopy(domain or PIANO_DOMAIN), "weight": 1},
    ]
    # Keep only chord references that match the 2/1 equave domain.
    result["sampler_tables"]["chord_reference"] = [
        item for item in base["sampler_tables"]["chord_reference"]
        if item["value"].get("equave") == (domain or PIANO_DOMAIN)["equave"]
    ]
    # The 2D [3/1, 5/1] lattice needs only the 3 and 5 prime factors.
    result["lowering_choices"]["lattice_navigation"]["required_prime_factors"] = [3, 5]
    if domain is not None:
        # v2: per-role candidate main registers and the narrowed catalog
        # frequency window (the union of the hard registers, A2–A5).
        result["production_policy"]["register_millicents_by_role"] = {
            role: list(spec["main_millicents"])
            for role, spec in PIANO_V2_REGISTER.items()
        }
        result["production_policy"]["pitched_frequency_millihz"] = list(
            PIANO_V2_FREQUENCY_MILLIHZ
        )
    result["manifest_hash"] = exploration_generation_manifest_hash(result)
    validate_exploration_generation_manifest(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    composition_base = json.loads(
        (PROFILES / "composition_generation_v2.json").read_text())
    realization_base = json.loads(
        (PROFILES / "composition_realization_v2_1.json").read_text())
    generation_base = json.loads(
        (PROFILES / "full_song_generation_v1.json").read_text())
    pairs = (
        ("piano_solo", build_composition_profile(composition_base), "profile_hash"),
        ("piano_solo_roles", build_realization_profile(realization_base), "profile_hash"),
        ("piano_solo_generation", build_generation_manifest(generation_base), "manifest_hash"),
        # v2 (spec §11): new profile versions / digests so the sealed v1
        # receipts and WAVs still reproduce byte-for-byte.
        ("piano_solo_v2", build_composition_profile(composition_base, "piano-solo-v2"),
         "profile_hash"),
        ("piano_solo_roles_v2",
         build_realization_profile(realization_base, "piano-solo-roles-v2"),
         "profile_hash"),
        ("piano_solo_generation_v2",
         build_generation_manifest(generation_base, "piano-solo-generation-v2", PIANO_DOMAIN_V2),
         "manifest_hash"),
    )
    if not args.check:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, profile, hash_key in pairs:
        path = DESTINATION / f"{name}.json"
        payload = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode()
        if args.check:
            if path.read_bytes() != payload:
                parser.error(f"profile differs from builder: {path}")
        else:
            path.write_bytes(payload)
        print(f"{name}: {profile[hash_key]}")


if __name__ == "__main__":
    main()
