"""Lower a CompositionPlan 2.0 onto a compiler-compatible structural program."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .composition_generation import composition_plan_hash


class CompositionLoweringError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_SECTION_ROLE = {
    "opening": "intro",
    "statement": "verse",
    "preparation": "build",
    "arrival": "drop",
    "contrast": "break",
    "return": "verse",
    "closure": "outro",
}

_DEVELOPMENT_STAGE = {
    "opening": "introduce",
    "statement": "statement",
    "preparation": "develop",
    "arrival": "contrast",
    "contrast": "contrast",
    "return": "recall",
    "closure": "release",
}

_FUNCTION_VECTOR = {
    "home": (0, 0),
    "departure": (1, 0),
    "preparation": (0, 1),
    "arrival": (0, 0),
    "return": (0, 0),
}


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if (
        not isinstance(plan, Mapping)
        or plan.get("schema") != "cps.composition-plan"
        or plan.get("schema_version") != "2.0.0"
        or plan.get("plan_hash") != composition_plan_hash(plan)
    ):
        raise CompositionLoweringError("COMPOSITION_PLAN_INVALID")


def _bounded_vector(function: str, bounds: list[list[int]]) -> list[int]:
    prototype = _FUNCTION_VECTOR[function]
    vector = [prototype[index] if index < len(prototype) else 0 for index in range(len(bounds))]
    return [max(low, min(high, value)) for value, (low, high) in zip(vector, bounds)]


def lower_composition_plan(
    structural_program: Mapping[str, Any], plan: Mapping[str, Any]
) -> dict[str, Any]:
    """Replace random form/placement while preserving sealed lattice/material authority."""
    _validate_plan(plan)
    if structural_program.get("schema") != "cps.structural-song-program":
        raise CompositionLoweringError("COMPOSITION_STRUCTURAL_PROGRAM_INVALID")
    result = copy.deepcopy(dict(structural_program))
    original_sections = {section["id"]: section for section in result["form"]}
    templates: dict[str, dict[str, Any]] = {}
    for realization in result["realizations"]:
        if realization["section_id"] not in original_sections:
            raise CompositionLoweringError("COMPOSITION_STRUCTURAL_PROGRAM_INVALID")
        templates.setdefault(realization["role"], realization)
    missing = sorted({"harmony"} - set(templates))
    if missing:
        raise CompositionLoweringError("COMPOSITION_LOWERING_CORE_ROLE_UNAVAILABLE")

    materials = {material["id"]: material for material in result["materials"]}
    harmony_primary = materials[templates["harmony"]["material_id"]]
    harmony_helper_id = harmony_primary.get("rhythm_id", harmony_primary["id"])
    harmony_helper = materials[harmony_helper_id]
    harmony_helper["steps"] = [
        {**harmony_helper["steps"][0], "at_tick": 0, "duration_ticks": harmony_helper["length_ticks"]}
    ]
    result["materials"] = [harmony_helper, harmony_primary]
    used_chords = set(harmony_primary.get("chord_intent_ids", []))
    result["chord_intents"] = [
        chord for chord in result["chord_intents"] if chord["id"] in used_chords
    ]

    trajectory = {row["phrase_id"]: row for row in plan["harmonic_trajectory"]}
    occurrences = {row["phrase_id"]: row for row in plan["motif_plan"]["occurrences"]}
    ticks_per_bar = result["clock"]["beats_per_bar"] * result["clock"]["ticks_per_beat"]
    bounds = result["lattice"]["coordinate_bounds"]
    coordination = plan["part_coordination"]
    fill_id = "rhy_cmp_fill_shared"
    result["materials"].append(
        {
            "id": fill_id,
            "kind": "rhythm_cell",
            "length_ticks": ticks_per_bar,
            "steps": [
                {
                    "at_tick": coordination["boundary_gesture_onset_q"]
                    * ticks_per_bar
                    // 10000,
                    "duration_ticks": max(
                        1, coordination["drum_duration_q"] * ticks_per_bar // 10000
                    ),
                    "accent_q": 10000,
                    "lane_id": None,
                }
            ],
        }
    )
    form = []
    realizations = []
    realization_ordinal = 0
    for section in plan["sections"]:
        first_phrase = section["phrases"][0]["phrase_id"]
        harmonic = trajectory[first_phrase]
        form.append(
            {
                "id": section["section_id"],
                "role": (
                    "final"
                    if section["function"] == "return" and section["section_key"] == "final"
                    else _SECTION_ROLE[section["function"]]
                ),
                "bars": section["bars"],
                "energy_q": [section["energy_q"], section["energy_q"]],
                "density_q": [section["density_q"], section["density_q"]],
                "tonal_center": _bounded_vector(harmonic["harmonic_function"], bounds),
                "development_stage": _DEVELOPMENT_STAGE[section["function"]],
            }
        )
        root_vector = _bounded_vector(harmonic["harmonic_function"], bounds)
        drum_id = f"rhy_cmp_drm_{section['ordinal']:03d}"
        bass_rhythm_id = f"rhy_cmp_bas_{section['ordinal']:03d}"
        bass_id = f"mat_cmp_bas_{section['ordinal']:03d}"
        result["materials"].extend(
            [
                {
                    "id": drum_id,
                    "kind": "rhythm_cell",
                    "length_ticks": ticks_per_bar,
                    "steps": [
                        {
                            "at_tick": onset * ticks_per_bar // 10000,
                            "duration_ticks": max(
                                1, coordination["drum_duration_q"] * ticks_per_bar // 10000
                            ),
                            "accent_q": max(1, section["energy_q"]),
                            "lane_id": None,
                        }
                        for onset in coordination["drum_onsets_q"]
                    ],
                },
                {
                    "id": bass_rhythm_id,
                    "kind": "rhythm_cell",
                    "length_ticks": ticks_per_bar,
                    "steps": [
                        {
                            "at_tick": onset * ticks_per_bar // 10000,
                            "duration_ticks": min(
                                coordination["bass_duration_q"] * ticks_per_bar // 10000,
                                ticks_per_bar - onset * ticks_per_bar // 10000,
                            ),
                            "accent_q": max(1, section["energy_q"]),
                            "lane_id": None,
                        }
                        for onset in coordination["bass_onsets_q"]
                    ],
                },
                {
                    "id": bass_id,
                    "kind": "direct_vector_cell",
                    "rhythm_id": bass_rhythm_id,
                    "vectors": [root_vector],
                    "register_delta": -1,
                    "mapping": "cycle",
                },
            ]
        )
        rows = [
            ("drums", drum_id, 0, section["bars"], []),
            (
                "bass",
                bass_id,
                0,
                section["bars"],
                [],
            ),
            ("harmony", harmony_primary["id"], 0, section["bars"], []),
            (
                "drums",
                fill_id,
                (section["bars"] - 1) * ticks_per_bar,
                1,
                ([{"op": "rotate", "ticks": ticks_per_bar // 4}]
                 if section["function"] == "return" else []),
            ),
        ]
        for role, material_id, at_tick, repeat, transforms in rows:
            realizations.append(
                {
                    "id": f"rea_cmp_{realization_ordinal:03d}",
                    "section_id": section["section_id"],
                    "role": role,
                    "material_id": material_id,
                    "at_tick": at_tick,
                    "repeat": repeat,
                    "every_ticks": ticks_per_bar,
                    "rhythm_transforms": transforms,
                    "pitch_transforms": [],
                    "velocity_scale_q": max(1, section["energy_q"]),
                    "gate_scale_q": 10000 if role == "harmony" else 9000,
                }
            )
            realization_ordinal += 1
        if section["foreground_state"] != "absent":
            for phrase in section["phrases"]:
                occurrence = occurrences[phrase["phrase_id"]]
                if occurrence["operation"] == "rest":
                    continue
                phrase_ticks = phrase["length_bars"] * ticks_per_bar
                helper_id = f"rhy_cmp_{phrase['phrase_id']}"
                material_id = f"mat_cmp_{phrase['phrase_id']}"
                steps = []
                points = []
                for event in occurrence["events"]:
                    at_tick = event["position_q"] * phrase_ticks // 10000
                    duration = max(1, event["duration_q"] * phrase_ticks // 10000)
                    duration = min(
                        duration,
                        phrase_ticks - at_tick,
                        ticks_per_bar - (at_tick % ticks_per_bar),
                    )
                    steps.append(
                        {
                            "at_tick": at_tick,
                            "duration_ticks": duration,
                            "accent_q": max(1, section["energy_q"]),
                            "lane_id": None,
                        }
                    )
                    member_cycle = coordination["melody_chord_member_cycle"]
                    points.append(
                        {
                            "relation": "chord_member",
                            "member": member_cycle[abs(event["degree_delta"]) % len(member_cycle)],
                            "contour": "hold",
                        }
                    )
                result["materials"].extend(
                    [
                        {
                            "id": helper_id,
                            "kind": "rhythm_cell",
                            "length_ticks": phrase_ticks,
                            "steps": steps,
                        },
                        {
                            "id": material_id,
                            "kind": "melody_intent",
                            "rhythm_id": helper_id,
                            "points": points,
                            "mapping": "zip",
                        },
                    ]
                )
                row = {
                    "id": f"rea_cmp_{realization_ordinal:03d}",
                    "section_id": section["section_id"],
                    "role": "melody",
                    "material_id": material_id,
                    "at_tick": phrase["start_bar"] * ticks_per_bar,
                    "repeat": 1,
                    "every_ticks": phrase_ticks,
                    "rhythm_transforms": [],
                    "pitch_transforms": [],
                    "velocity_scale_q": max(1, section["energy_q"]),
                    "gate_scale_q": 8500,
                }
                realizations.append(row)
                realization_ordinal += 1
    result["form"] = form
    result["realizations"] = realizations
    if (
        len(form) > result["limits"]["max_sections"]
        or len(result["materials"]) > result["limits"]["max_materials"]
        or len(realizations) > result["limits"]["max_realizations"]
    ):
        raise CompositionLoweringError("COMPOSITION_LOWERING_LIMIT_EXCEEDED")
    return result
