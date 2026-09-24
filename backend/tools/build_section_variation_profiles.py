"""Build reproducible wide-section composition and realization profiles."""

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

PROFILES = BACKEND / "songprogram_conformance/profiles"
DESTINATION = PROFILES / "g1_experiments"
OPENINGS = (
    ("ambient", 4, 1800, 1800, "absent"),
    ("pickup", 2, 3200, 4000, "introduce"),
    ("groove", 4, 5800, 5800, "introduce"),
    ("bloom", 6, 2600, 3000, "introduce"),
)
CLOSURES = (
    ("tail", 6, 1500, 1500, "release"),
    ("cut", 2, 3800, 2500, "release"),
    ("echo", 4, 2800, 3500, "recall"),
    ("full_circle", 4, 4800, 4500, "release"),
)


def build_composition_profile(base: dict) -> dict:
    validate_composition_profile(base)
    result = copy.deepcopy(base)
    result["profile_id"] = "g1-experiment-section-variation-v1"
    result["phrase_policy"]["length_choices_by_function"]["opening"] = [
        {"length_bars": 2, "weight": 3}, {"length_bars": 4, "weight": 1},
    ]
    result["phrase_policy"]["length_choices_by_function"]["closure"] = [
        {"length_bars": 2, "weight": 3}, {"length_bars": 4, "weight": 1},
    ]
    result["form_templates"] = []
    for form_index, form in enumerate(base["form_templates"]):
        for opening_index, opening in enumerate(OPENINGS):
            for closure_index, closure in enumerate(CLOSURES):
                sections = copy.deepcopy(form["sections"])
                for section_index, section in enumerate(sections):
                    if section_index == 0:
                        name, bars, energy, density, foreground = opening
                        section.update(bars=bars, energy_q=energy, density_q=density,
                                       foreground_state=foreground)
                    elif section_index == len(sections) - 1:
                        name, bars, energy, density, foreground = closure
                        section.update(bars=bars, energy_q=energy, density_q=density,
                                       foreground_state=foreground)
                    else:
                        # Different sections can change duration and intensity
                        # without changing the ordered functional arc or cadence.
                        variation = (opening_index + 2 * closure_index + form_index + section_index) % 3
                        section["bars"] = (2, 4, 6)[variation]
                        offset = (-700, 0, 700)[variation]
                        section["energy_q"] = max(1000, min(10000, section["energy_q"] + offset))
                        section["density_q"] = max(1000, min(10000, section["density_q"] - offset))
                result["form_templates"].append({
                    "template_id": f"{form_index}-{opening[0]}-{closure[0]}",
                    "weight": 1, "sections": sections,
                })
    result["profile_hash"] = composition_profile_hash(result)
    validate_composition_profile(result)
    return result


def build_realization_profile(base: dict) -> dict:
    validate_realization_profile(base)
    result = copy.deepcopy(base)
    result["profile_id"] = "g1-experiment-section-variation-roles-v1"
    masks = result["role_masks_by_function"]
    for function, candidates in {
        "opening": (("harmony", "texture"), ("bass", "harmony", "texture"),
                    ("drums", "bass", "harmony", "melody")),
        "statement": (("drums", "bass", "harmony", "melody", "texture"),),
        "preparation": (("bass", "harmony", "melody", "texture"),),
        "arrival": (("drums", "bass", "harmony", "melody"),),
        "contrast": (("bass", "harmony", "melody", "texture"),),
        "return": (("drums", "bass", "harmony", "melody", "texture"),),
        "closure": (("bass", "harmony", "texture"),
                    ("drums", "bass", "harmony", "melody"),
                    ("drums", "harmony", "melody", "texture")),
    }.items():
        existing = {tuple(row["roles"]) for row in masks[function]}
        for roles in candidates:
            if roles not in existing:
                masks[function].append({"roles": list(roles), "weight": 1})
    modes = result["texture_modes_by_function"]
    for function, candidates in {
        "opening": ("arp", "vocal_chop", "counterline"),
        "statement": ("pad", "arp"),
        "preparation": ("pad", "pluck"),
        "arrival": ("pad", "pluck"),
        "contrast": ("arp", "vocal_chop"),
        "return": ("pad", "counterline"),
        "closure": ("pluck", "arp", "counterline"),
    }.items():
        existing = {row["mode"] for row in modes[function]}
        modes[function].extend({"mode": mode, "weight": 1}
                               for mode in candidates if mode not in existing)
    result["profile_hash"] = realization_profile_hash(result)
    validate_realization_profile(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    pairs = (
        ("section_variation", build_composition_profile(json.loads(
            (PROFILES / "composition_generation_v2.json").read_text()))),
        ("section_variation_roles", build_realization_profile(json.loads(
            (PROFILES / "composition_realization_v2_1.json").read_text()))),
    )
    if not args.check:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, profile in pairs:
        path = DESTINATION / f"{name}.json"
        payload = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode()
        if args.check:
            if path.read_bytes() != payload:
                parser.error(f"profile differs from builder: {path}")
        else:
            path.write_bytes(payload)
        print(f"{name}: {profile['profile_hash']}")


if __name__ == "__main__":
    main()
