"""Build three reproducible composition-profile variants for paired G1 exploration."""

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

SOURCE = BACKEND / "songprogram_conformance/profiles/composition_generation_v2.json"
DESTINATION = BACKEND / "songprogram_conformance/profiles/g1_experiments"


def build_profiles(base: dict) -> dict[str, dict]:
    validate_composition_profile(base)
    profiles = {}

    contrast = copy.deepcopy(base)
    contrast["profile_id"] = "g1-experiment-contrast-arc-v1"
    contrast["form_templates"][0]["weight"] = 1
    contrast["form_templates"][1]["weight"] = 8
    for template in contrast["form_templates"]:
        for section in template["sections"]:
            if section["function"] == "contrast":
                section["energy_q"], section["density_q"] = 2000, 1500
            elif section["function"] == "arrival":
                section["energy_q"], section["density_q"] = 10000, 9500
            elif section["function"] == "closure":
                section["energy_q"], section["density_q"] = 1500, 1500
    profiles["contrast_arc"] = contrast

    recall = copy.deepcopy(base)
    recall["profile_id"] = "g1-experiment-motif-recall-v1"
    recall["motif_policy"]["templates"][0]["weight"] = 5
    recall["motif_policy"]["templates"][1]["weight"] = 1
    operations = recall["motif_policy"]["operation_choices_by_foreground_state"]
    operations["introduce"] = [{"operation": "statement", "weight": 5},
                               {"operation": "recall", "weight": 1}]
    operations["present"] = [{"operation": "recall", "weight": 5},
                             {"operation": "answer", "weight": 1}]
    for state in ("develop", "recall"):
        operations[state] = [{"operation": "answer", "weight": 5},
                             {"operation": "rhythmic_displacement", "weight": 1},
                             {"operation": "fragmentation", "weight": 1}]
    profiles["motif_recall"] = recall

    dialogue = copy.deepcopy(base)
    dialogue["profile_id"] = "g1-experiment-rhythm-dialogue-v1"
    coordination = dialogue["part_coordination_policy"]
    coordination["drum_onsets_q"] = [0, 1250, 2500, 3750, 5000, 6250, 7500, 8750]
    coordination["bass_onsets_q"] = [0, 2500, 5000, 7500]
    coordination["boundary_gesture_onset_q"] = 7500
    profiles["rhythm_dialogue"] = dialogue

    for profile in profiles.values():
        profile["profile_hash"] = composition_profile_hash(profile)
        validate_composition_profile(profile)
    return profiles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed profiles without writing")
    args = parser.parse_args()
    profiles = build_profiles(json.loads(SOURCE.read_text(encoding="utf-8")))
    if not args.check:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, profile in profiles.items():
        path = DESTINATION / f"{name}.json"
        payload = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.check:
            if path.read_bytes() != payload:
                parser.error(f"profile differs from builder: {path}")
        else:
            path.write_bytes(payload)
        print(f"{name}: {profile['profile_hash']}")


if __name__ == "__main__":
    main()
