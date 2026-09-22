"""Lower a CompositionPlan 2.0 onto a compiler-compatible structural program."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .composition_generation import composition_plan_hash
from .composition_realization import (
    choose_density_positions,
    choose_role_mask,
    choose_texture_mode,
    thin_phrase_events,
    validate_realization_profile,
)


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

_DRUM_LANE_BY_POSITION = {
    0: "kick", 1250: "closed_hat", 2500: "snare", 3750: "closed_hat",
    5000: "kick", 6250: "open_hat", 7500: "clap", 8750: "closed_hat",
}

_TEXTURE_PATTERN_Q = {
    "pad": [(0, 10000, 0)],
    "noise_riser": [(5000, 1250, 0), (6250, 1250, 1), (7500, 1250, 1), (8750, 1250, 2)],
    "fx_impact": [(0, 2500, 0)],
    "transition_tail": [(0, 10000, 1)],
    "arp": [(0, 1800, 0), (2500, 1800, 1), (5000, 1800, 2), (7500, 1800, 1)],
    "vocal_chop": [(1250, 1000, 0), (3750, 1000, 2), (6250, 1000, 1), (8125, 1500, 2)],
    "counterline": [(0, 4000, 2), (5000, 4000, 1)],
    "pluck": [(0, 1500, 0), (5000, 1500, 1)],
}


def _audible_velocity_q(energy_q: int) -> int:
    """Keep section loudness changes subtle; energy still drives arrangement."""
    return 8500 + round(energy_q * 1500 / 10000)


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
    structural_program: Mapping[str, Any],
    plan: Mapping[str, Any],
    realization_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replace random form/placement while preserving sealed lattice/material authority."""
    _validate_plan(plan)
    if realization_profile is not None:
        validate_realization_profile(realization_profile)
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
    result["materials"] = (
        [] if realization_profile is not None else [harmony_helper, harmony_primary]
    )
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
                    "lane_id": "fill" if realization_profile is not None else None,
                }
            ],
        }
    )
    form = []
    realizations = []
    realization_ordinal = 0
    emitted_texture_modes: set[str] = set()
    emitted_harmony_patterns: set[tuple[int, ...]] = set()
    composition_seed = plan["seed"]
    for section in plan["sections"]:
        first_phrase = section["phrases"][0]["phrase_id"]
        harmonic = trajectory[first_phrase]
        active_roles = (
            set(choose_role_mask(
                realization_profile,
                composition_seed,
                section["section_id"],
                section["function"],
            ))
            if realization_profile is not None
            else {"drums", "bass", "harmony", "melody"}
        )
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
        audible_velocity_q = _audible_velocity_q(section["energy_q"])
        drum_id = f"rhy_cmp_drm_{section['ordinal']:03d}"
        bass_rhythm_id = f"rhy_cmp_bas_{section['ordinal']:03d}"
        bass_id = f"mat_cmp_bas_{section['ordinal']:03d}"
        texture_mode = (
            choose_texture_mode(
                realization_profile,
                composition_seed,
                section["section_id"],
                section["function"],
            )
            if realization_profile is not None and "texture" in active_roles
            else None
        )
        texture_rhythm_id = f"rhy_cmp_tex_{texture_mode}"
        texture_id = f"mat_cmp_tex_{texture_mode}"
        drum_onsets = (
            choose_density_positions(
                realization_profile,
                "drums",
                section["density_q"],
                composition_seed,
                f"density/{section['section_id']}/drums",
            )
            if realization_profile is not None
            else coordination["drum_onsets_q"]
        )
        bass_onsets = (
            choose_density_positions(
                realization_profile,
                "bass",
                section["density_q"],
                composition_seed,
                f"density/{section['section_id']}/bass",
            )
            if realization_profile is not None
            else coordination["bass_onsets_q"]
        )
        section_materials = []
        if "drums" in active_roles:
            section_materials.append(
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
                            "accent_q": audible_velocity_q,
                            "lane_id": (
                                _DRUM_LANE_BY_POSITION[onset]
                                if realization_profile is not None else None
                            ),
                        }
                        for onset in drum_onsets
                    ],
                }
            )
        if "bass" in active_roles:
            section_materials.extend(
                [
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
                            "accent_q": audible_velocity_q,
                            "lane_id": None,
                        }
                        for onset in bass_onsets
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
        if texture_mode is not None and texture_mode not in emitted_texture_modes:
            texture_pattern = _TEXTURE_PATTERN_Q[texture_mode]
            section_materials.extend(
                [
                    {
                        "id": texture_rhythm_id,
                        "kind": "rhythm_cell",
                        "length_ticks": ticks_per_bar,
                        "steps": [
                            {
                                "at_tick": onset_q * ticks_per_bar // 10000,
                                "duration_ticks": max(
                                    1,
                                    min(
                                        duration_q * ticks_per_bar // 10000,
                                        ticks_per_bar - onset_q * ticks_per_bar // 10000,
                                    ),
                                ),
                                "accent_q": 10000,
                                "lane_id": None,
                            }
                            for onset_q, duration_q, _ in texture_pattern
                        ],
                    },
                    {
                        "id": texture_id,
                        "kind": "direct_vector_cell",
                        "rhythm_id": texture_rhythm_id,
                        "vectors": [root_vector],
                        "register_delta": max(
                            register_delta for _, _, register_delta in texture_pattern
                        ),
                        "mapping": "cycle",
                    },
                ]
            )
            emitted_texture_modes.add(texture_mode)
        result["materials"].extend(section_materials)
        harmony_material_id = harmony_primary["id"]
        harmony_positions = [0]
        if realization_profile is not None and "harmony" in active_roles:
            harmony_positions = choose_density_positions(
                realization_profile,
                "harmony",
                section["density_q"],
                composition_seed,
                f"density/{section['section_id']}/harmony",
            )
            section_harmony_rhythm = copy.deepcopy(harmony_helper)
            harmony_pattern = tuple(harmony_positions)
            pattern_suffix = "_".join(str(position) for position in harmony_pattern)
            section_harmony_rhythm["id"] = f"rhy_cmp_har_{pattern_suffix}"
            section_harmony_rhythm["length_ticks"] = ticks_per_bar
            section_harmony_rhythm["steps"] = [
                {
                    **harmony_helper["steps"][0],
                    "at_tick": position * ticks_per_bar // 10000,
                    "duration_ticks": max(1, ticks_per_bar // len(harmony_positions)),
                    "accent_q": 10000,
                }
                for position in harmony_positions
            ]
            section_harmony = copy.deepcopy(harmony_primary)
            section_harmony["id"] = f"mat_cmp_har_{pattern_suffix}"
            section_harmony["rhythm_id"] = section_harmony_rhythm["id"]
            harmony_material_id = section_harmony["id"]
            if harmony_pattern not in emitted_harmony_patterns:
                result["materials"].extend([section_harmony_rhythm, section_harmony])
                emitted_harmony_patterns.add(harmony_pattern)
        rows = [
            ("drums", drum_id, 0, section["bars"], []),
            (
                "bass",
                bass_id,
                0,
                section["bars"],
                [],
            ),
            ("harmony", harmony_material_id, 0, section["bars"], []),
            ("texture", texture_id, 0, section["bars"], []),
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
            if role not in active_roles:
                continue
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
                    "velocity_scale_q": audible_velocity_q,
                    "gate_scale_q": (
                        10000 if role in {"harmony", "texture"} else 9000
                    ),
                }
            )
            realization_ordinal += 1
        if section["foreground_state"] != "absent" and "melody" in active_roles:
            for phrase in section["phrases"]:
                occurrence = occurrences[phrase["phrase_id"]]
                if occurrence["operation"] == "rest":
                    continue
                phrase_ticks = phrase["length_bars"] * ticks_per_bar
                helper_id = f"rhy_cmp_{phrase['phrase_id']}"
                material_id = f"mat_cmp_{phrase['phrase_id']}"
                steps = []
                points = []
                phrase_events = (
                    thin_phrase_events(
                        occurrence["events"],
                        section["density_q"],
                        composition_seed,
                        f"density/{section['section_id']}/{phrase['phrase_id']}/melody",
                    )
                    if realization_profile is not None
                    else occurrence["events"]
                )
                for event_ordinal_in_phrase, event in enumerate(phrase_events):
                    at_tick = event["position_q"] * phrase_ticks // 10000
                    duration = max(1, event["duration_q"] * phrase_ticks // 10000)
                    within_bar = at_tick % ticks_per_bar
                    harmony_boundaries = [
                        position * ticks_per_bar // 10000
                        for position in harmony_positions
                        if position * ticks_per_bar // 10000 > within_bar
                    ]
                    next_harmony_boundary = (
                        min(harmony_boundaries) if harmony_boundaries else ticks_per_bar
                    )
                    duration = min(
                        duration,
                        phrase_ticks - at_tick,
                        next_harmony_boundary - within_bar,
                    )
                    steps.append(
                        {
                            "at_tick": at_tick,
                            "duration_ticks": duration,
                            "accent_q": audible_velocity_q,
                            "lane_id": None,
                        }
                    )
                    member_cycle = coordination["melody_chord_member_cycle"]
                    points.append(
                        {
                            "relation": "chord_member",
                            "member": member_cycle[
                                (abs(event["degree_delta"]) + event_ordinal_in_phrase)
                                % len(member_cycle)
                            ],
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
                    "velocity_scale_q": audible_velocity_q,
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
