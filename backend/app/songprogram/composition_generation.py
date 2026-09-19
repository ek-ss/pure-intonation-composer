"""Deterministic ordered-form and phrase planning for composition profile 2.0."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Mapping

from .search import canonical_bytes


_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_SECTION_FUNCTIONS = {
    "opening",
    "statement",
    "preparation",
    "arrival",
    "contrast",
    "return",
    "closure",
}
_CADENCE_TARGETS = {"none", "continuation", "arrival", "home", "open"}
_FOREGROUND_STATES = {"absent", "introduce", "present", "develop", "recall", "release"}
_PHRASE_SLOTS = {"pickup", "body", "answer", "cadence"}
_HARMONIC_FUNCTIONS = {"home", "departure", "preparation", "arrival", "return"}
_MOTIF_OPERATIONS = {
    "rest",
    "statement",
    "recall",
    "answer",
    "rhythmic_displacement",
    "fragmentation",
    "cadential_release",
}
_FORM_TRANSITIONS = {
    "opening": {"statement", "arrival"},
    "statement": {"preparation", "arrival"},
    "preparation": {"arrival", "return"},
    "arrival": {"statement", "contrast", "return", "closure"},
    "contrast": {"preparation", "return"},
    "return": {"preparation", "closure"},
    "closure": set(),
}


class CompositionGenerationError(ValueError):
    """A stable composition profile or generation failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _hash(domain: str, value: Mapping[str, Any], *, omit: str | None = None) -> str:
    payload = dict(value)
    if omit is not None:
        payload.pop(omit, None)
    return "sha256:" + hashlib.sha256(
        domain.encode("utf-8") + b"\0" + canonical_bytes(payload)
    ).hexdigest()


def composition_profile_hash(profile: Mapping[str, Any]) -> str:
    return _hash("cps.composition-generation-profile/2.0", profile, omit="profile_hash")


def composition_plan_hash(plan: Mapping[str, Any]) -> str:
    return _hash("cps.composition-plan/2.0", plan, omit="plan_hash")


def _is_int(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _weighted_rows(value: Any, *, kind: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    seen: set[bytes] = set()
    rows: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {kind, "weight"}:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        key = row[kind]
        key_bytes = canonical_bytes(key)
        if key_bytes in seen or not _is_int(row["weight"], 1, 2**31 - 1):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        seen.add(key_bytes)
        rows.append(dict(row))
    return rows


def validate_composition_profile(profile: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "profile_id",
        "generator",
        "choice_algorithm",
        "form_templates",
        "phrase_policy",
        "harmonic_trajectory_policy",
        "motif_policy",
        "part_coordination_policy",
        "profile_hash",
    }
    if (
        not isinstance(profile, Mapping)
        or set(profile) != required
        or profile.get("schema") != "cps.composition-generation-profile"
        or profile.get("schema_version") != "2.0.0"
        or profile.get("generator") != "ordered-form-phrase/v1"
        or profile.get("choice_algorithm") != "seed-domain-sha256-weighted/v1"
        or not isinstance(profile.get("profile_id"), str)
        or not profile["profile_id"]
        or _SHA256.fullmatch(str(profile.get("profile_hash"))) is None
        or profile["profile_hash"] != composition_profile_hash(profile)
    ):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")

    templates = profile.get("form_templates")
    if not isinstance(templates, list) or not templates:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    template_ids: set[str] = set()
    for template in templates:
        if not isinstance(template, Mapping) or set(template) != {"template_id", "weight", "sections"}:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        template_id = template["template_id"]
        sections = template["sections"]
        if (
            not isinstance(template_id, str)
            or not template_id
            or template_id in template_ids
            or not _is_int(template["weight"], 1, 2**31 - 1)
            or not isinstance(sections, list)
            or not 3 <= len(sections) <= 8
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        template_ids.add(template_id)
        section_keys: set[str] = set()
        total_bars = 0
        for section in sections:
            if not isinstance(section, Mapping) or set(section) != {
                "section_key",
                "function",
                "bars",
                "energy_q",
                "density_q",
                "cadence_target",
                "foreground_state",
            }:
                raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
            key = section["section_key"]
            if (
                not isinstance(key, str)
                or not key
                or key in section_keys
                or section["function"] not in _SECTION_FUNCTIONS
                or not _is_int(section["bars"], 2, 16)
                or not _is_int(section["energy_q"], 0, 10000)
                or not _is_int(section["density_q"], 0, 10000)
                or section["cadence_target"] not in _CADENCE_TARGETS
                or section["foreground_state"] not in _FOREGROUND_STATES
            ):
                raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
            section_keys.add(key)
            total_bars += section["bars"]
        if not 16 <= total_bars <= 64:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        functions = [section["function"] for section in sections]
        if (
            functions[0] != "opening"
            or functions[-1] != "closure"
            or any(right not in _FORM_TRANSITIONS[left] for left, right in zip(functions, functions[1:]))
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")

    policy = profile.get("phrase_policy")
    if not isinstance(policy, Mapping) or set(policy) != {
        "algorithm",
        "length_choices_by_function",
        "slots_by_length_bars",
    } or policy.get("algorithm") != "ordered-exact-section-partition/v1":
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    choices = policy["length_choices_by_function"]
    if not isinstance(choices, Mapping) or set(choices) != _SECTION_FUNCTIONS:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    for function, rows in choices.items():
        parsed = _weighted_rows(rows, kind="length_bars")
        if any(not _is_int(row["length_bars"], 2, 8) for row in parsed):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    slots = policy["slots_by_length_bars"]
    if not isinstance(slots, Mapping) or not slots:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    declared_lengths = {row["length_bars"] for rows in choices.values() for row in rows}
    if set(slots) != {str(length) for length in declared_lengths}:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    for raw_length, sequence in slots.items():
        length = int(raw_length)
        if (
            not isinstance(sequence, list)
            or len(sequence) != length
            or any(slot not in _PHRASE_SLOTS for slot in sequence)
            or sequence[-1] != "cadence"
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")

    harmonic = profile.get("harmonic_trajectory_policy")
    if not isinstance(harmonic, Mapping) or set(harmonic) != {
        "algorithm",
        "home_state_id",
        "states",
        "eligible_state_ids_by_section_function",
        "terminal_state_ids_by_cadence_target",
        "transitions",
    } or harmonic.get("algorithm") != "seeded-function-constrained-state-path/v1":
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    states = harmonic["states"]
    if not isinstance(states, list) or not states:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    state_ids: set[str] = set()
    for state in states:
        if (
            not isinstance(state, Mapping)
            or set(state) != {"state_id", "harmonic_function", "root_degree_ordinal"}
            or not isinstance(state["state_id"], str)
            or not state["state_id"]
            or state["state_id"] in state_ids
            or state["harmonic_function"] not in _HARMONIC_FUNCTIONS
            or not _is_int(state["root_degree_ordinal"], -64, 64)
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        state_ids.add(state["state_id"])
    state_by_id = {state["state_id"]: state for state in states}
    if (
        harmonic["home_state_id"] not in state_ids
        or state_by_id[harmonic["home_state_id"]]["harmonic_function"] != "home"
        or state_by_id[harmonic["home_state_id"]]["root_degree_ordinal"] != 0
    ):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    eligible = harmonic["eligible_state_ids_by_section_function"]
    terminal = harmonic["terminal_state_ids_by_cadence_target"]
    if (
        not isinstance(eligible, Mapping)
        or set(eligible) != _SECTION_FUNCTIONS
        or not isinstance(terminal, Mapping)
        or set(terminal) != _CADENCE_TARGETS
    ):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    for values in [*eligible.values(), *terminal.values()]:
        if (
            not isinstance(values, list)
            or not values
            or len(values) != len(set(values))
            or any(value not in state_ids for value in values)
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    transitions = harmonic["transitions"]
    if not isinstance(transitions, list) or not transitions:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    transition_pairs: set[tuple[str, str]] = set()
    for transition in transitions:
        if (
            not isinstance(transition, Mapping)
            or set(transition) != {"from_state_id", "to_state_id", "weight"}
            or transition["from_state_id"] not in state_ids
            or transition["to_state_id"] not in state_ids
            or not _is_int(transition["weight"], 1, 2**31 - 1)
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        pair = (transition["from_state_id"], transition["to_state_id"])
        if pair in transition_pairs:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        transition_pairs.add(pair)

    motif = profile.get("motif_policy")
    if not isinstance(motif, Mapping) or set(motif) != {
        "algorithm",
        "templates",
        "operation_choices_by_foreground_state",
        "rhythmic_displacement_q_choices",
    } or motif.get("algorithm") != "seeded-normalized-motif-lineage/v1":
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    templates = motif["templates"]
    if not isinstance(templates, list) or not templates:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    template_ids: set[str] = set()
    for template in templates:
        if (
            not isinstance(template, Mapping)
            or set(template) != {"template_id", "weight", "events"}
            or not isinstance(template["template_id"], str)
            or not template["template_id"]
            or template["template_id"] in template_ids
            or not _is_int(template["weight"], 1, 2**31 - 1)
            or not isinstance(template["events"], list)
            or not 2 <= len(template["events"]) <= 16
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        template_ids.add(template["template_id"])
        positions = []
        for event in template["events"]:
            if (
                not isinstance(event, Mapping)
                or set(event) != {"position_q", "duration_q", "degree_delta"}
                or not _is_int(event["position_q"], 0, 9999)
                or not _is_int(event["duration_q"], 1, 10000)
                or event["position_q"] + event["duration_q"] > 10000
                or not _is_int(event["degree_delta"], -64, 64)
            ):
                raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
            positions.append(event["position_q"])
        if positions != sorted(set(positions)):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    operations = motif["operation_choices_by_foreground_state"]
    if not isinstance(operations, Mapping) or set(operations) != _FOREGROUND_STATES:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    expected = {
        "absent": {"rest"},
        "introduce": {"statement", "recall"},
        "present": {"recall", "answer"},
        "develop": {"answer", "rhythmic_displacement", "fragmentation"},
        "recall": {"answer", "rhythmic_displacement", "fragmentation"},
        "release": {"cadential_release"},
    }
    for state, rows in operations.items():
        parsed = _weighted_rows(rows, kind="operation")
        values = {row["operation"] for row in parsed}
        if not values <= _MOTIF_OPERATIONS or not values <= expected[state]:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
        if state == "absent" and values != {"rest"}:
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    displacements = motif["rhythmic_displacement_q_choices"]
    if (
        not isinstance(displacements, list)
        or not displacements
        or len(displacements) != len(set(displacements))
        or any(not _is_int(value, 1, 4999) for value in displacements)
    ):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")

    coordination = profile.get("part_coordination_policy")
    if not isinstance(coordination, Mapping) or set(coordination) != {
        "algorithm",
        "drum_onsets_q",
        "bass_onsets_q",
        "drum_duration_q",
        "bass_duration_q",
        "boundary_gesture_onset_q",
        "melody_chord_member_cycle",
    } or coordination.get("algorithm") != "kick-bass-harmony-foreground/v1":
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    for name in ("drum_onsets_q", "bass_onsets_q"):
        values = coordination[name]
        if (
            not isinstance(values, list)
            or not values
            or values != sorted(set(values))
            or any(not _is_int(value, 0, 9999) for value in values)
        ):
            raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    if not set(coordination["bass_onsets_q"]) <= set(coordination["drum_onsets_q"]):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    if (
        not _is_int(coordination["drum_duration_q"], 1, 10000)
        or not _is_int(coordination["bass_duration_q"], 1, 10000)
        or not _is_int(coordination["boundary_gesture_onset_q"], 0, 9999)
        or not isinstance(coordination["melody_chord_member_cycle"], list)
        or not coordination["melody_chord_member_cycle"]
        or len(coordination["melody_chord_member_cycle"])
        != len(set(coordination["melody_chord_member_cycle"]))
        or any(
            not _is_int(value, 0, 7)
            for value in coordination["melody_chord_member_cycle"]
        )
    ):
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")


def _draw(seed: int, domain: str) -> int:
    if not _is_int(seed, 0, 2**64 - 1):
        raise CompositionGenerationError("COMPOSITION_SEED_INVALID")
    digest = hashlib.sha256(
        b"cps.composition-choice/2.0\0" + seed.to_bytes(8, "big") + domain.encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _weighted_choice(seed: int, domain: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(row["weight"] for row in rows)
    point = _draw(seed, domain) % total
    cursor = 0
    for row in rows:
        cursor += row["weight"]
        if point < cursor:
            return copy.deepcopy(row)
    raise AssertionError("unreachable weighted choice")


def _choice(seed: int, domain: str, values: list[Any]) -> Any:
    if not values:
        raise CompositionGenerationError("COMPOSITION_PROFILE_INVALID")
    return copy.deepcopy(values[_draw(seed, domain) % len(values)])


def _partitionable(remaining: int, lengths: list[int]) -> bool:
    reachable = {0}
    for total in range(1, remaining + 1):
        if any(total - length in reachable for length in lengths if length <= total):
            reachable.add(total)
    return remaining in reachable


def generate_composition_plan(profile: Mapping[str, Any], seed: int) -> dict[str, Any]:
    """Select an ordered form and exactly partition every section into phrases."""
    validate_composition_profile(profile)
    if not _is_int(seed, 0, 2**64 - 1):
        raise CompositionGenerationError("COMPOSITION_SEED_INVALID")
    template = _weighted_choice(seed, "form-template", list(profile["form_templates"]))
    sections: list[dict[str, Any]] = []
    phrase_ordinal = 0
    for section_ordinal, source in enumerate(template["sections"]):
        rows = list(profile["phrase_policy"]["length_choices_by_function"][source["function"]])
        remaining = source["bars"]
        phrases = []
        local_ordinal = 0
        while remaining:
            eligible = [
                row
                for row in rows
                if row["length_bars"] <= remaining
                and _partitionable(
                    remaining - row["length_bars"],
                    [candidate["length_bars"] for candidate in rows],
                )
            ]
            if not eligible:
                raise CompositionGenerationError("COMPOSITION_PHRASE_PARTITION_UNAVAILABLE")
            selected = _weighted_choice(
                seed,
                f"phrase-length/{template['template_id']}/{section_ordinal}/{local_ordinal}",
                eligible,
            )
            length = selected["length_bars"]
            phrases.append(
                {
                    "phrase_id": f"phr_{phrase_ordinal:03d}",
                    "ordinal": local_ordinal,
                    "start_bar": source["bars"] - remaining,
                    "length_bars": length,
                    "slots": copy.deepcopy(
                        profile["phrase_policy"]["slots_by_length_bars"][str(length)]
                    ),
                    "cadence_target": source["cadence_target"] if remaining == length else "continuation",
                }
            )
            remaining -= length
            phrase_ordinal += 1
            local_ordinal += 1
        sections.append(
            {
                "section_id": f"sec_{section_ordinal:03d}",
                "ordinal": section_ordinal,
                **copy.deepcopy(dict(source)),
                "phrases": phrases,
            }
        )
    harmonic = profile["harmonic_trajectory_policy"]
    states = {state["state_id"]: state for state in harmonic["states"]}
    previous = harmonic["home_state_id"]
    trajectory = []
    flat_phrases = [
        (section, phrase)
        for section in sections
        for phrase in section["phrases"]
    ]
    for index, (section, phrase) in enumerate(flat_phrases):
        if index == 0:
            selected_id = harmonic["home_state_id"]
            if (
                selected_id not in harmonic["eligible_state_ids_by_section_function"][section["function"]]
                or selected_id not in harmonic["terminal_state_ids_by_cadence_target"][phrase["cadence_target"]]
            ):
                raise CompositionGenerationError("COMPOSITION_HARMONIC_PATH_UNAVAILABLE")
        else:
            eligible_ids = set(
                harmonic["eligible_state_ids_by_section_function"][section["function"]]
            ) & set(harmonic["terminal_state_ids_by_cadence_target"][phrase["cadence_target"]])
            edges = [
                {
                    "state_id": edge["to_state_id"],
                    "weight": edge["weight"],
                }
                for edge in harmonic["transitions"]
                if edge["from_state_id"] == previous and edge["to_state_id"] in eligible_ids
            ]
            if not edges:
                raise CompositionGenerationError("COMPOSITION_HARMONIC_PATH_UNAVAILABLE")
            selected_id = _weighted_choice(
                seed, f"harmonic-state/{phrase['phrase_id']}", edges
            )["state_id"]
        state = states[selected_id]
        trajectory.append(
            {
                "phrase_id": phrase["phrase_id"],
                "state_id": selected_id,
                "harmonic_function": state["harmonic_function"],
                "root_degree_ordinal": state["root_degree_ordinal"],
            }
        )
        previous = selected_id
    motif_policy = profile["motif_policy"]
    motif_template = _weighted_choice(seed, "motif-template", list(motif_policy["templates"]))
    root_events = [
        {
            "event_id": f"mte_{ordinal:03d}",
            "source_event_id": None,
            **copy.deepcopy(event),
        }
        for ordinal, event in enumerate(motif_template["events"])
    ]
    root_phrase_id: str | None = None
    motif_occurrences = []
    event_ordinal = len(root_events)
    for section, phrase in flat_phrases:
        foreground = section["foreground_state"]
        if foreground == "absent":
            operation = "rest"
        elif root_phrase_id is None:
            operation = "statement"
            root_phrase_id = phrase["phrase_id"]
        else:
            operation = _weighted_choice(
                seed,
                f"motif-operation/{phrase['phrase_id']}",
                list(motif_policy["operation_choices_by_foreground_state"][foreground]),
            )["operation"]
            if operation == "statement":
                operation = "recall"
        if operation == "rest":
            events = []
        elif operation == "statement":
            events = copy.deepcopy(root_events)
        else:
            selected = copy.deepcopy(root_events)
            for event in selected:
                event["source_event_id"] = event["event_id"]
                event["event_id"] = f"mte_{event_ordinal:03d}"
                event_ordinal += 1
            if operation == "answer":
                for event in selected:
                    event["degree_delta"] = -event["degree_delta"]
            elif operation == "rhythmic_displacement":
                minimum = min(event["position_q"] for event in selected)
                maximum = max(event["position_q"] + event["duration_q"] for event in selected)
                signed_offsets = []
                for offset in motif_policy["rhythmic_displacement_q_choices"]:
                    if maximum + offset <= 10000:
                        signed_offsets.append(offset)
                    if minimum - offset >= 0:
                        signed_offsets.append(-offset)
                if not signed_offsets:
                    raise CompositionGenerationError("COMPOSITION_MOTIF_TRANSFORM_UNAVAILABLE")
                signed = _choice(
                    seed,
                    f"motif-displacement/{phrase['phrase_id']}",
                    signed_offsets,
                )
                for event in selected:
                    event["position_q"] += signed
            elif operation == "fragmentation":
                selected = selected[: max(1, (len(selected) + 1) // 2)]
            elif operation == "cadential_release":
                selected = [selected[-1]]
                selected[0]["position_q"] = 10000 - selected[0]["duration_q"]
                selected[0]["degree_delta"] = 0
            elif operation != "recall":
                raise CompositionGenerationError("COMPOSITION_MOTIF_TRANSFORM_UNAVAILABLE")
            events = selected
        motif_occurrences.append(
            {
                "phrase_id": phrase["phrase_id"],
                "lineage_id": "motif_000" if operation != "rest" else None,
                "source_phrase_id": (
                    None if operation in {"rest", "statement"} else root_phrase_id
                ),
                "operation": operation,
                "events": events,
            }
        )
    result = {
        "schema": "cps.composition-plan",
        "schema_version": "2.0.0",
        "profile_id": profile["profile_id"],
        "profile_hash": profile["profile_hash"],
        "seed": seed,
        "form_template_id": template["template_id"],
        "total_bars": sum(section["bars"] for section in sections),
        "sections": sections,
        "harmonic_trajectory": trajectory,
        "motif_plan": {
            "template_id": motif_template["template_id"],
            "root_phrase_id": root_phrase_id,
            "occurrences": motif_occurrences,
        },
        "part_coordination": copy.deepcopy(profile["part_coordination_policy"]),
        "plan_hash": "",
    }
    result["plan_hash"] = composition_plan_hash(result)
    return result
