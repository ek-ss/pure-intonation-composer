"""Deterministic musical-time lowering and symbolic coverage for exploration profiles."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter, defaultdict
from typing import Any, Mapping

from .search import canonical_bytes


class ExplorationProfileError(ValueError):
    """Raised when a profile or its lowering result is invalid."""


def profile_hash(profile: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in profile.items() if key != "profile_hash"}
    return (
        "sha256:"
        + hashlib.sha256(
            b"cps.song-preview-exploration-profile/v1\0" + canonical_bytes(payload)
        ).hexdigest()
    )


def _choice(seed: int, domain: str, values: list[Any]) -> Any:
    if not values:
        raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
    digest = hashlib.sha256(
        b"cps.song-preview-choice/v1\0" + seed.to_bytes(8, "big") + domain.encode("utf-8")
    ).digest()
    return copy.deepcopy(values[int.from_bytes(digest[:8], "big") % len(values)])


def validate_profile(profile: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "profile_id",
        "section_layouts",
        "role_order",
        "single_role_binding",
        "realization_policy",
        "coverage_gate",
        "profile_hash",
    }
    version = profile.get("schema_version") if isinstance(profile, Mapping) else None
    if version == "1.1.0":
        required.add("arrangement_policy")
    if (
        not isinstance(profile, Mapping)
        or set(profile) != required
        or profile.get("schema") != "cps.song-preview-exploration-profile"
        or version not in {"1.0.0", "1.1.0"}
        or profile.get("profile_hash") != profile_hash(profile)
    ):
        raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
    roles = profile.get("role_order")
    policies = profile.get("realization_policy")
    if (
        not isinstance(roles, list)
        or not isinstance(policies, Mapping)
        or set(policies) != set(roles)
    ):
        raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
    for role in roles:
        policy = policies[role]
        if set(policy) != {"entry_bar_choices", "period_bars", "duration_ticks", "gate_q"}:
            raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
        if policy["period_bars"] < 1 or not policy["entry_bar_choices"]:
            raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
    if version == "1.1.0":
        arrangement = profile["arrangement_policy"]
        section_roles = {"intro", "verse", "build", "drop", "break", "final", "outro"}
        if (
            set(arrangement)
            != {
                "algorithm",
                "role_count_choices_by_section_role",
                "role_priority_by_section_role",
                "velocity_scale_q_by_section_role",
                "minimum_distinct_role_masks",
            }
            or arrangement["algorithm"] != "section-role-mask-and-recall/v1"
            or set(arrangement["role_count_choices_by_section_role"]) != section_roles
            or set(arrangement["role_priority_by_section_role"]) != section_roles
            or set(arrangement["velocity_scale_q_by_section_role"]) != section_roles
            or any(
                set(arrangement["role_priority_by_section_role"][section_role]) != set(roles)
                for section_role in section_roles
            )
        ):
            raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")


def selected_layout(profile: Mapping[str, Any], seed: int) -> dict[str, int]:
    validate_profile(profile)
    layout = _choice(seed, "section-layout", list(profile["section_layouts"]))
    if set(layout) != {"section_count", "bars_per_section"}:
        raise ExplorationProfileError("EXPLORATION_PROFILE_INVALID")
    return layout


def apply_profile_with_arrangement(
    structural_program: Mapping[str, Any], profile: Mapping[str, Any], seed: int
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply ownership, section arrangement, and role schedules."""
    validate_profile(profile)
    result = copy.deepcopy(dict(structural_program))
    roles = list(profile["role_order"])
    role_index = {role: ordinal for ordinal, role in enumerate(roles)}
    by_material: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for realization in result["realizations"]:
        by_material[realization["material_id"]].append(realization)

    retained: list[dict[str, Any]] = []
    binding = profile["single_role_binding"]
    for material_id, rows in sorted(by_material.items()):
        available = sorted({row["role"] for row in rows}, key=role_index.__getitem__)
        weighted = [
            role
            for role in roles
            if role in available
            for _ in range(binding["role_weights"][role])
        ]
        owner = _choice(seed, f"material-owner/{material_id}", weighted)
        retained.extend(row for row in rows if row["role"] == owner)

    # A source material may be offered to several roles while a global
    # single-owner choice can collapse the result below the coverage floor.
    # Add deterministic role-specialized copies until the requested role floor
    # is met.  Every resulting material still belongs to exactly one role.
    materials = {material["id"]: material for material in result["materials"]}
    minimum_roles = profile["coverage_gate"]["minimum_sounding_roles"]
    sounding_roles = {row["role"] for row in retained}
    while len(sounding_roles) < minimum_roles:
        candidates = sorted(
            (
                material_id,
                role,
            )
            for material_id, rows in by_material.items()
            for role in {row["role"] for row in rows}
            if role not in sounding_roles
        )
        if not candidates:
            break
        source_id, role = _choice(
            seed,
            f"role-specialization/{len(sounding_roles)}",
            candidates,
        )
        suffix = f"_x{role_index[role]}"
        source = materials[source_id]
        specialized = copy.deepcopy(source)
        specialized["id"] = source_id + suffix
        if "rhythm_id" in specialized:
            rhythm_source = materials[specialized["rhythm_id"]]
            rhythm_copy = copy.deepcopy(rhythm_source)
            rhythm_copy["id"] = rhythm_source["id"] + suffix
            specialized["rhythm_id"] = rhythm_copy["id"]
            result["materials"].append(rhythm_copy)
            materials[rhythm_copy["id"]] = rhythm_copy
        result["materials"].append(specialized)
        materials[specialized["id"]] = specialized
        for row in by_material[source_id]:
            if row["role"] == role:
                clone = copy.deepcopy(row)
                clone["material_id"] = specialized["id"]
                retained.append(clone)
        sounding_roles.add(role)

    sections = {section["id"]: section for section in result["form"]}
    arrangement_report = None
    if "arrangement_policy" in profile:
        arrangement = profile["arrangement_policy"]
        global_roles = sorted({row["role"] for row in retained}, key=role_index.__getitem__)
        templates = {
            role: min(
                (row for row in retained if row["role"] == role),
                key=lambda row: (row["material_id"].encode(), row["id"].encode()),
            )
            for role in global_roles
        }
        existing = {(row["section_id"], row["role"]) for row in retained}
        for section_ordinal, section in enumerate(result["form"]):
            for role in global_roles:
                if (section["id"], role) in existing:
                    continue
                clone = copy.deepcopy(templates[role])
                clone["id"] = f"arr_{section_ordinal:02d}_{role_index[role]}"
                clone["section_id"] = section["id"]
                retained.append(clone)

        masks: dict[str, list[str]] = {}
        velocities: dict[str, int] = {}
        for section in result["form"]:
            section_role = section["role"]
            count = _choice(
                seed,
                f"arrangement-role-count/{section['id']}/{section_role}",
                arrangement["role_count_choices_by_section_role"][section_role],
            )
            count = max(1, min(count, len(global_roles)))
            priority = arrangement["role_priority_by_section_role"][section_role]
            mask = [role for role in priority if role in global_roles][:count]
            mask.sort(key=role_index.__getitem__)
            masks[section["id"]] = mask
            velocities[section["id"]] = _choice(
                seed,
                f"arrangement-velocity/{section['id']}/{section_role}",
                arrangement["velocity_scale_q_by_section_role"][section_role],
            )

        active_union = {role for mask in masks.values() for role in mask}
        missing_roles = [role for role in global_roles if role not in active_union]
        energetic_sections = sorted(
            result["form"],
            key=lambda section: (-velocities[section["id"]], section["id"].encode()),
        )
        for role in missing_roles[: max(0, minimum_roles - len(active_union))]:
            target = next(
                section["id"] for section in energetic_sections if role not in masks[section["id"]]
            )
            masks[target].append(role)
            masks[target].sort(key=role_index.__getitem__)
            active_union.add(role)

        minimum_masks = arrangement["minimum_distinct_role_masks"]
        distinct_masks = {tuple(mask) for mask in masks.values()}
        if len(result["form"]) > 1 and len(distinct_masks) < minimum_masks:
            last = result["form"][-1]["id"]
            current = masks[last]
            occurrences = Counter(role for mask in masks.values() for role in mask)
            last_section_role = result["form"][-1]["role"]
            protected = next(
                role
                for role in arrangement["role_priority_by_section_role"][last_section_role]
                if role in global_roles
            )
            removable = [role for role in reversed(current) if occurrences[role] > 1]
            removable = [role for role in removable if role != protected]
            if len(current) > 1 and removable:
                masks[last] = [role for role in current if role != removable[0]]
            elif len(global_roles) > 1:
                masks[last] = current + [role for role in global_roles if role not in current][:1]

        retained = [row for row in retained if row["role"] in masks[row["section_id"]]]
        for row in retained:
            row["velocity_scale_q"] = velocities[row["section_id"]]
        section_plans = [
            {
                "section_id": section["id"],
                "section_role": section["role"],
                "development_stage": section["development_stage"],
                "active_roles": masks[section["id"]],
                "velocity_scale_q": velocities[section["id"]],
            }
            for section in result["form"]
        ]
        arrangement_report = {
            "schema": "cps.section-arrangement-plan",
            "schema_version": "1.0.0",
            "profile_hash": profile["profile_hash"],
            "source_program_id": result["program_id"],
            "section_plans": section_plans,
            "distinct_role_mask_count": len(
                {tuple(plan["active_roles"]) for plan in section_plans}
            ),
            "sounding_role_count": len(
                {role for plan in section_plans for role in plan["active_roles"]}
            ),
            "status": "passed",
            "plan_hash": "",
        }
        if (
            arrangement_report["distinct_role_mask_count"] < minimum_masks
            or arrangement_report["sounding_role_count"] < minimum_roles
        ):
            arrangement_report["status"] = "rejected"
        arrangement_report["plan_hash"] = (
            "sha256:"
            + hashlib.sha256(
                b"cps.section-arrangement-plan/v1\0"
                + canonical_bytes(
                    {key: value for key, value in arrangement_report.items() if key != "plan_hash"}
                )
            ).hexdigest()
        )

    ticks_per_bar = result["clock"]["beats_per_bar"] * result["clock"]["ticks_per_beat"]
    helper_roles: dict[str, str] = {}
    helper_tail_ticks: dict[str, int] = {}
    for realization in retained:
        role = realization["role"]
        policy = profile["realization_policy"][role]
        # This profile is the sole owner of musical-time placement.  Structural
        # rotate transforms belong to the sparse cohort prior and would shift a
        # final repeated event beyond the tail used for the duration bound.
        realization["rhythm_transforms"] = []
        section_bars = sections[realization["section_id"]]["bars"]
        entry_bar = _choice(
            seed,
            f"entry-bar/{realization['section_id']}/{realization['material_id']}/{role}",
            [value for value in policy["entry_bar_choices"] if value < section_bars],
        )
        period = policy["period_bars"]
        realization["at_tick"] = entry_bar * ticks_per_bar
        realization["every_ticks"] = period * ticks_per_bar
        realization["repeat"] = 1 + (section_bars - entry_bar - 1) // period
        realization["gate_scale_q"] = _choice(
            seed, f"gate/{realization['id']}/{role}", policy["gate_q"]
        )
        material = materials[realization["material_id"]]
        helper_id = material.get("rhythm_id", material["id"])
        existing = helper_roles.setdefault(helper_id, role)
        if existing != role:
            raise ExplorationProfileError("EXPLORATION_MATERIAL_ROLE_CONFLICT")
        tail = (
            section_bars * ticks_per_bar
            - realization["at_tick"]
            - (realization["repeat"] - 1) * realization["every_ticks"]
        )
        helper_tail_ticks[helper_id] = min(helper_tail_ticks.get(helper_id, tail), tail)

    for helper_id, role in helper_roles.items():
        helper = materials[helper_id]
        if role in {"harmony", "texture"}:
            helper["steps"] = [{**helper["steps"][0], "at_tick": 0}]
        choices = profile["realization_policy"][role]["duration_ticks"]
        period_ticks = profile["realization_policy"][role]["period_bars"] * ticks_per_bar
        for ordinal, step in enumerate(helper["steps"]):
            maximum = min(period_ticks, helper_tail_ticks[helper_id]) - step["at_tick"]
            if maximum < 1:
                raise ExplorationProfileError("EXPLORATION_DURATION_NO_PLACEMENT")
            eligible = [value for value in choices if value <= maximum]
            step["duration_ticks"] = _choice(
                seed,
                f"duration/{helper_id}/{ordinal}/{role}",
                eligible or [maximum],
            )

    result["realizations"] = sorted(
        retained,
        key=lambda row: (
            row["section_id"].encode(),
            role_index[row["role"]],
            row["material_id"].encode(),
            row["id"].encode(),
        ),
    )
    return result, arrangement_report


def apply_profile(
    structural_program: Mapping[str, Any], profile: Mapping[str, Any], seed: int
) -> dict[str, Any]:
    """Apply an exploration profile while preserving the v1 public return type."""
    return apply_profile_with_arrangement(structural_program, profile, seed)[0]


def symbolic_coverage(project: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    """Measure bar coverage from event intervals without using rendered PCM."""
    validate_profile(profile)
    ticks_per_bar = project["clock"]["beats_per_bar"] * project["clock"]["ticks_per_beat"]
    tracks = {track["id"]: track["role"] for track in project["tracks"]}
    sections = {section["id"]: section for section in project["form"]}
    per_section = []
    all_covered = 0
    all_bars = 0
    role_bars: dict[str, set[tuple[str, int]]] = defaultdict(set)
    passed = True
    for section_id, section in sections.items():
        bars = section["bars"]
        covered: set[int] = set()
        for event in project["events"]:
            if event["section_id"] != section_id:
                continue
            section_start = section["start_bar"] * ticks_per_bar
            relative_start = event["start_tick"] - section_start
            first = max(0, relative_start // ticks_per_bar)
            last = min(bars - 1, (relative_start + event["duration_ticks"] - 1) // ticks_per_bar)
            for bar in range(first, last + 1):
                covered.add(bar)
                role_bars[tracks[event["track_id"]]].add((section_id, bar))
        longest = current = 0
        for bar in range(bars):
            current = 0 if bar in covered else current + 1
            longest = max(longest, current)
        coverage_bp = round(10000 * len(covered) / bars)
        high_energy = section["role"] in profile["coverage_gate"]["continuous_section_roles"]
        maximum = (
            profile["coverage_gate"]["maximum_empty_bar_run_continuous"]
            if high_energy
            else profile["coverage_gate"]["maximum_empty_bar_run_other"]
        )
        section_passed = longest <= maximum
        passed = passed and section_passed
        all_covered += len(covered)
        all_bars += bars
        per_section.append(
            {
                "section_id": section_id,
                "section_role": section["role"],
                "bars": bars,
                "covered_bars": len(covered),
                "coverage_basis_points": coverage_bp,
                "maximum_empty_bar_run": longest,
                "passed": section_passed,
            }
        )
    overall = round(10000 * all_covered / all_bars) if all_bars else 0
    passed = passed and overall >= profile["coverage_gate"]["minimum_overall_coverage_bp"]
    sounding_roles = sum(bool(role_bars.get(role)) for role in profile["role_order"])
    passed = passed and sounding_roles >= profile["coverage_gate"]["minimum_sounding_roles"]
    return {
        "schema": "cps.symbolic-coverage-report",
        "schema_version": "1.0.0",
        "profile_hash": profile["profile_hash"],
        "overall_coverage_basis_points": overall,
        "maximum_empty_bar_run": max(
            (row["maximum_empty_bar_run"] for row in per_section), default=0
        ),
        "sounding_role_count": sounding_roles,
        "role_active_bar_count": {
            role: len(role_bars.get(role, set())) for role in profile["role_order"]
        },
        "sections": per_section,
        "status": "passed" if passed else "rejected",
    }
