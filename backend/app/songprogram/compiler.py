"""Deterministic SP0 direct-vector compiler vertical slice."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any

from .resolver import resolve_joint_bnb


class CompileError(ValueError):
    def __init__(self, code: str, pointer: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.pointer = pointer


@dataclass(frozen=True)
class CompilerIdentity:
    build_id: str
    resolver_build_id: str
    resolver_profile_hash: str
    budget_profile_digest: str
    instrument_catalog_digest: str
    numeric_contract: str = "cps-numeric/decimal-log2-rhe-v1"


def resolve_single_harmony(program: dict[str, Any], intent: dict[str, Any], anchor: list[int]) -> dict[str, Any]:
    """Build the frozen GEN0-A query and return its sole canonical winner.

    Lowering deliberately stays separate so no caller can substitute a
    per-note nearest fallback for the exact joint result.
    """
    lattice = program["lattice"]
    query = {
        "schema": "cps.sp0-oracle-query/v1",
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "domain": {
            "equave": lattice["equave"],
            "generators": lattice["generators"],
            "coordinate_bounds": lattice["coordinate_bounds"],
            "register_bounds": lattice["register_bounds"],
            "maximum_odd_limit": lattice["maximum_odd_limit"],
            "maximum_reduced_complexity_bits": lattice["pitch_exploration"]["maximum_reduced_complexity_bits"],
        },
        "intent": {
            "reference_equave": intent["reference"]["equave"],
            "reference_divisions": intent["reference"]["divisions"],
            "steps": intent["reference"]["steps"],
            "bass_policy": intent["voicing"]["bass_policy"],
            "bass_target_ordinal": intent["voicing"]["bass_target_ordinal"],
            "minimum_spacing_millicents": intent["voicing"]["minimum_spacing_millicents"],
            "maximum_span_millicents": intent["voicing"]["maximum_span_millicents"],
            "maximum_pair_error_millicents": intent["recognition"]["maximum_pair_error_millicents"],
            "maximum_pair_rms_millicents": intent["recognition"]["maximum_pair_rms_millicents"],
            "complexity_budget": intent["complexity_budget"],
        },
        "anchor": {"vector": anchor, "equave_exponent": 0},
    }
    results = resolve_joint_bnb(query, 1)
    if not results:
        raise CompileError("NO_JOINT_CHORD_SOLUTION")
    return results[0]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(prefix: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(prefix + _canonical(value)).hexdigest()


def _b32(payload: bytes, length: int) -> str:
    return base64.b32encode(hashlib.sha256(payload).digest()).decode().lower().rstrip("=")[:length]


def _rhe(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    return sign * (
        quotient
        + int(
            remainder * 2 > value.denominator
            or (remainder * 2 == value.denominator and quotient % 2 == 1)
        )
    )


def _ratio(text: str) -> Fraction:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise CompileError("RATIO_INVALID") from error
    if value <= 0 or text != f"{value.numerator}/{value.denominator}":
        raise CompileError("RATIO_NOT_REDUCED")
    return value


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _mc(value: Fraction) -> int:
    with localcontext() as context:
        context.prec = 112
        result = (
            Decimal(1_200_000)
            * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln())
            / Decimal(2).ln()
        )
        return int(result.to_integral_value(rounding=ROUND_HALF_EVEN))


def _vector_ratio(
    generators: list[Fraction], vector: list[int], equave: Fraction, exponent: int
) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector, strict=True):
        value *= generator**power
    return value * equave**exponent


def _semantic_address(
    section: str,
    realization: str,
    repeat: int,
    material: str,
    step: int,
    voice: int = 0,
) -> str:
    core = ["cps.semantic-address", 1, section, realization, repeat, material, step, voice]
    return "sa_" + _b32(_canonical(core), 26)


def _event_id(event: dict[str, Any]) -> str:
    source = event["source"]
    core = {
        key: event[key]
        for key in (
            "kind",
            "track_id",
            "section_id",
            "start_tick",
            "duration_ticks",
            "velocity",
            "articulation",
            "drum_note",
            "ratio",
            "chord_index",
            "pitch_provenance",
        )
    }
    core["source"] = {
        key: source[key]
        for key in ("material_instance_id", "source_step_ordinal", "emitted_voice_ordinal")
    }
    payload = b"cps.event-id/v1\0" + source["semantic_address"].encode() + b"\0" + _canonical(core)
    return "ev_" + _b32(payload, 20)


def _resolved_chord_id(chord: dict[str, Any]) -> str:
    fields = (
        "domain_hash", "intent_hash", "resolver_build_id", "numeric_contract",
        "search_completeness", "reference_equave", "reference_divisions",
        "canonical_steps", "eligibility_contract", "anchor_vector", "voice_offsets",
        "equave_exponents", "exact_ratios", "target_voice_ordinals",
        "pair_errors_millicents", "maximum_pair_error_millicents",
        "pair_rms_error_millicents", "complexity_score",
    )
    return "rc_" + _b32(b"cps.resolved-chord/v1\0" + _canonical({field: chord[field] for field in fields}), 26)


def _instance_id(realization_id: str, repeat: int) -> str:
    stem = realization_id[5:] if realization_id.startswith("real_") else realization_id
    value = "mi_" + stem + ("" if repeat == 0 else f"_{repeat}")
    if (
        not value
        or len(value) > 40
        or not value[0].islower()
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in value)
    ):
        raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
    return value


def _place_exponent(
    base_ratio: Fraction, equave: Fraction, requested: int, bounds: list[int], register: list[int]
) -> int:
    candidates = [
        exponent
        for exponent in range(bounds[0], bounds[1] + 1)
        if register[0] <= _mc(base_ratio * equave**exponent) <= register[1]
    ]
    if not candidates:
        raise CompileError("REGISTER_NO_PLACEMENT")
    return min(candidates, key=lambda exponent: (abs(exponent - requested), exponent))


def compile_direct_sp0(program: dict[str, Any], identity: CompilerIdentity) -> dict[str, Any]:
    """Compile the strict direct-vector subset of SongProgram 0.1 to Project 1.2."""
    if program.get("schema") != "cps.song-program" or program.get("schema_version") != "0.1.0":
        raise CompileError("SCHEMA_VERSION_UNSUPPORTED")
    if any(
        material.get("kind") not in {"rhythm_cell", "direct_vector_cell", "harmony_intent_cell"}
        for material in program["materials"]
    ):
        raise CompileError("UNSUPPORTED_COMPILER_SLICE")
    if any(realization["pitch_transforms"] for realization in program["realizations"]):
        raise CompileError("UNSUPPORTED_SP0_TRANSFORM")
    sections = {section["id"]: section for section in program["form"]}
    tracks = {track["id"]: track for track in program["tracks"]}
    materials = {material["id"]: material for material in program["materials"]}
    if (
        len(sections) != len(program["form"])
        or len(tracks) != len(program["tracks"])
        or len(materials) != len(program["materials"])
    ):
        raise CompileError("SYMBOL_DUPLICATE")
    ticks_per_bar = program["clock"]["beats_per_bar"] * program["clock"]["ticks_per_beat"]
    form = []
    start_bar = 0
    for section in program["form"]:
        form.append(
            {
                "id": section["id"],
                "role": section["role"],
                "start_bar": start_bar,
                "bars": section["bars"],
            }
        )
        start_bar += section["bars"]
    lattice_source = program["lattice"]
    lattice = {
        "domain_hash": "",
        "base_frequency_millihz": lattice_source["base_frequency_millihz"],
        "equave": lattice_source["equave"],
        "generators": lattice_source["generators"],
        "coordinate_bounds": lattice_source["coordinate_bounds"],
        "register_bounds": lattice_source["register_bounds"],
        "maximum_odd_limit": lattice_source["maximum_odd_limit"],
        "maximum_reduced_complexity_bits": lattice_source["pitch_exploration"][
            "maximum_reduced_complexity_bits"
        ],
    }
    lattice["domain_hash"] = _sha(
        b"cps.lattice-domain/v1\0",
        {key: value for key, value in lattice.items() if key != "domain_hash"},
    )
    project: dict[str, Any] = {
        "schema": "cps.arrangement-project",
        "schema_version": "1.2.0",
        "source_program": {
            "hash": _sha(
                b"cps.song-program/0.1\0",
                {key: value for key, value in program.items() if key != "program_id"},
            ),
            "schema": "cps.song-program",
            "schema_version": "0.1.0",
        },
        "compiler": {
            "build_id": identity.build_id,
            "numeric_contract": identity.numeric_contract,
            "resolver_build_id": identity.resolver_build_id,
            "resolver_profile_hash": identity.resolver_profile_hash,
            "budget_profile_digest": identity.budget_profile_digest,
            "instrument_catalog_digest": identity.instrument_catalog_digest,
        },
        "lattice": lattice,
        "clock": {**program["clock"], "bars": start_bar, "total_ticks": start_bar * ticks_per_bar},
        "tracks": sorted(deepcopy(program["tracks"]), key=lambda item: item["id"].encode()),
        "form": form,
        "material_instances": [],
        "resolved_chords": [],
        "harmony_occurrences": [],
        "events": [],
        "mix": deepcopy(program["production"]["tracks"]),
        "render_settings": {"sample_rate": 48_000, "channel_layout": "stereo"},
    }
    equave = _ratio(lattice["equave"])
    generators = [_ratio(item) for item in lattice["generators"]]
    section_starts = {item["id"]: item["start_bar"] * ticks_per_bar for item in form}
    used_instances: set[str] = set()
    for realization_index, realization in enumerate(program["realizations"]):
        try:
            section, track, material = (
                sections[realization["section_id"]],
                tracks[realization["track_id"]],
                materials[realization["material_id"]],
            )
            rhythm = (
                material if material["kind"] == "rhythm_cell" else materials[material["rhythm_id"]]
            )
        except KeyError as error:
            raise CompileError("REFERENCE_NOT_FOUND") from error
        if rhythm["kind"] != "rhythm_cell":
            raise CompileError("UNSUPPORTED_COMPILER_SLICE")
        if track["role"] == "drums" and material["kind"] == "rhythm_cell":
            rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
            for repeat in range(realization["repeat"]):
                instance_id = _instance_id(realization["id"], repeat)
                if instance_id in used_instances:
                    raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
                used_instances.add(instance_id)
                instance_tick = (
                    section_starts[section["id"]]
                    + realization["at_tick"]
                    + repeat * realization["every_ticks"]
                )
                project["material_instances"].append(
                    {
                        "id": instance_id,
                        "material_id": material["id"],
                        "realization_id": realization["id"],
                        "section_id": section["id"],
                        "track_id": track["id"],
                        "repeat_ordinal": repeat,
                        "at_tick": instance_tick,
                        "source_program_path": f"/realizations/{realization_index}",
                    }
                )
                for step_index, step in enumerate(rhythm["steps"]):
                    lane = step.get("lane_id")
                    if lane is None or lane not in track["drum_map"]:
                        raise CompileError(
                            "UNKNOWN_DRUM_LANE",
                            f"/materials/{program['materials'].index(material)}/steps/{step_index}/lane_id",
                        )
                    onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                    duration = max(
                        1,
                        _rhe(
                            Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)
                        ),
                    )
                    if (
                        onset + duration
                        > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                    ):
                        raise CompileError("EVENT_SECTION_OVERFLOW")
                    address = _semantic_address(
                        section["id"], realization["id"], repeat, material["id"], step_index
                    )
                    event = {
                        "id": "",
                        "kind": "drum",
                        "track_id": track["id"],
                        "section_id": section["id"],
                        "start_tick": onset,
                        "duration_ticks": duration,
                        "velocity": min(
                            127,
                            max(
                                1,
                                _rhe(
                                    Fraction(
                                        125 * step["accent_q"] * realization["velocity_scale_q"],
                                        100_000_000,
                                    )
                                ),
                            ),
                        ),
                        "articulation": "normal",
                        "drum_note": track["drum_map"][lane],
                        "ratio": None,
                        "chord_index": None,
                        "pitch_provenance": None,
                        "source": {
                            "material_instance_id": instance_id,
                            "source_step_ordinal": step_index,
                            "emitted_voice_ordinal": 0,
                            "semantic_address": address,
                        },
                    }
                    event["id"] = _event_id(event)
                    project["events"].append(event)
            continue
        if material["kind"] == "harmony_intent_cell" and track["role"] == "harmony":
            rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
            intents = {intent["id"]: intent for intent in program["chord_intents"]}
            for repeat in range(realization["repeat"]):
                instance_id = _instance_id(realization["id"], repeat)
                if instance_id in used_instances:
                    raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
                used_instances.add(instance_id)
                instance_tick = section_starts[section["id"]] + realization["at_tick"] + repeat * realization["every_ticks"]
                project["material_instances"].append({"id": instance_id, "material_id": material["id"], "realization_id": realization["id"], "section_id": section["id"], "track_id": track["id"], "repeat_ordinal": repeat, "at_tick": instance_tick, "source_program_path": f"/realizations/{realization_index}"})
                for step_index, step in enumerate(rhythm["steps"]):
                    if material["mapping"] == "zip" and (step_index >= len(material["root_anchors"]) or step_index >= len(material["chord_intent_ids"])):
                        raise CompileError("MAPPING_LENGTH_MISMATCH")
                    item_index = step_index % len(material["root_anchors"])
                    intent_index = step_index % len(material["chord_intent_ids"])
                    try:
                        intent = intents[material["chord_intent_ids"][intent_index]]
                    except KeyError as error:
                        raise CompileError("REFERENCE_NOT_FOUND") from error
                    anchor = [left + right for left, right in zip(material["root_anchors"][item_index], section["tonal_center"], strict=True)]
                    core = resolve_single_harmony(program, intent, anchor)
                    offsets = [[coordinate - origin for coordinate, origin in zip(vector, anchor, strict=True)] for vector in core["vectors"]]
                    eligibility = {**intent["voicing"], **intent["recognition"], "complexity_budget": intent["complexity_budget"]}
                    chord = {"id": "", "domain_hash": lattice["domain_hash"], "intent_hash": _sha(b"cps.chord-intent/v1\0", intent), "resolver_build_id": identity.resolver_build_id, "numeric_contract": identity.numeric_contract, "search_completeness": "exact", "reference_equave": intent["reference"]["equave"], "reference_divisions": intent["reference"]["divisions"], "canonical_steps": core["canonical_steps"], "eligibility_contract": eligibility, "anchor_vector": anchor, "voice_offsets": offsets, "equave_exponents": core["equave_exponents"], "exact_ratios": core["exact_ratios"], "target_voice_ordinals": list(range(len(core["vectors"]))), "pair_errors_millicents": core["pair_errors_millicents"], "maximum_pair_error_millicents": core["pair_max_millicents"], "pair_rms_error_millicents": core["pair_rms_millicents"], "complexity_score": core["complexity_score"]}
                    chord["id"] = _resolved_chord_id(chord)
                    if all(existing["id"] != chord["id"] for existing in project["resolved_chords"]):
                        project["resolved_chords"].append(chord)
                    onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                    duration = max(1, _rhe(Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)))
                    if onset + duration > section_starts[section["id"]] + section["bars"] * ticks_per_bar:
                        raise CompileError("EVENT_SECTION_OVERFLOW")
                    chord_index = len(project["harmony_occurrences"])
                    project["harmony_occurrences"].append({"chord_index": chord_index, "section_id": section["id"], "start_tick": onset, "duration_ticks": duration, "resolved_chord_id": chord["id"]})
                    velocity = min(127, max(1, _rhe(Fraction(125 * step["accent_q"] * realization["velocity_scale_q"], 100_000_000))))
                    for ordinal, (vector, offset, exponent, ratio) in enumerate(zip(core["vectors"], offsets, core["equave_exponents"], core["exact_ratios"], strict=True)):
                        address = _semantic_address(section["id"], realization["id"], repeat, material["id"], step_index, ordinal)
                        event = {"id": "", "kind": "note", "track_id": track["id"], "section_id": section["id"], "start_tick": onset, "duration_ticks": duration, "velocity": velocity, "articulation": "normal", "drum_note": None, "ratio": ratio, "chord_index": chord_index, "pitch_provenance": {"kind": "resolved_chord_voice", "resolved_chord_id": chord["id"], "target_voice_ordinal": ordinal, "shape_voice_ordinal": ordinal, "anchor_vector": anchor, "offset_vector": offset, "final_vector": vector, "equave_exponent": exponent, "final_ratio": ratio}, "source": {"material_instance_id": instance_id, "source_step_ordinal": step_index, "emitted_voice_ordinal": ordinal, "semantic_address": address}}
                        event["id"] = _event_id(event)
                        project["events"].append(event)
            continue
        if material["kind"] != "direct_vector_cell" or track["role"] == "drums":
            raise CompileError("UNSUPPORTED_COMPILER_SLICE")
        rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
        for repeat in range(realization["repeat"]):
            instance_id = _instance_id(realization["id"], repeat)
            if instance_id in used_instances:
                raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
            used_instances.add(instance_id)
            instance_tick = (
                section_starts[section["id"]]
                + realization["at_tick"]
                + repeat * realization["every_ticks"]
            )
            project["material_instances"].append(
                {
                    "id": instance_id,
                    "material_id": material["id"],
                    "realization_id": realization["id"],
                    "section_id": section["id"],
                    "track_id": track["id"],
                    "repeat_ordinal": repeat,
                    "at_tick": instance_tick,
                    "source_program_path": f"/realizations/{realization_index}",
                }
            )
            for step_index, step in enumerate(rhythm["steps"]):
                if material["mapping"] == "zip" and step_index >= len(material["vectors"]):
                    raise CompileError("MAPPING_LENGTH_MISMATCH")
                vector = material["vectors"][step_index % len(material["vectors"])]
                final_vector = [
                    left + right
                    for left, right in zip(vector, section["tonal_center"], strict=True)
                ]
                if any(
                    not bound[0] <= coordinate <= bound[1]
                    for coordinate, bound in zip(
                        final_vector, lattice["coordinate_bounds"], strict=True
                    )
                ):
                    raise CompileError("LATTICE_COORDINATE_OUT_OF_RANGE")
                base_ratio = _vector_ratio(generators, final_vector, equave, 0)
                exponent = _place_exponent(
                    base_ratio,
                    equave,
                    material["register_delta"],
                    lattice["register_bounds"],
                    track["register_millicents"],
                )
                ratio = _ratio_text(base_ratio * equave**exponent)
                onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                duration = max(
                    1, _rhe(Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000))
                )
                if (
                    onset + duration
                    > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                ):
                    raise CompileError("EVENT_SECTION_OVERFLOW")
                velocity = min(
                    127,
                    max(
                        1,
                        _rhe(
                            Fraction(
                                125 * step["accent_q"] * realization["velocity_scale_q"],
                                100_000_000,
                            )
                        ),
                    ),
                )
                address = _semantic_address(
                    section["id"], realization["id"], repeat, material["id"], step_index
                )
                event = {
                    "id": "",
                    "kind": "note",
                    "track_id": track["id"],
                    "section_id": section["id"],
                    "start_tick": onset,
                    "duration_ticks": duration,
                    "velocity": velocity,
                    "articulation": "normal",
                    "drum_note": None,
                    "ratio": ratio,
                    "chord_index": None,
                    "pitch_provenance": {
                        "kind": "direct_vector",
                        "material_vector": vector,
                        "tonal_center": section["tonal_center"],
                        "register_delta": material["register_delta"],
                        "register_shift_equaves": 0,
                        "placed_equave_exponent": exponent - material["register_delta"],
                        "final_vector": final_vector,
                        "equave_exponent": exponent,
                        "final_ratio": ratio,
                    },
                    "source": {
                        "material_instance_id": instance_id,
                        "source_step_ordinal": step_index,
                        "emitted_voice_ordinal": 0,
                        "semantic_address": address,
                    },
                }
                event["id"] = _event_id(event)
                project["events"].append(event)
    if not project["events"] or len(project["events"]) > program["limits"]["max_events"]:
        raise CompileError("EVENT_LIMIT_EXCEEDED")
    project["material_instances"].sort(key=lambda item: item["id"].encode())
    project["resolved_chords"].sort(key=lambda item: item["id"].encode())
    project["events"].sort(
        key=lambda item: (
            item["start_tick"],
            item["track_id"].encode(),
            0 if item["kind"] == "drum" else 1,
            item["drum_note"] if item["kind"] == "drum" else item["ratio"],
            item["source"]["semantic_address"],
            item["id"],
        )
    )
    return project


def build_lineage_index(program: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical compiler-origin LineageIndex for a compiled Project."""
    materials = {material["id"]: material for material in program["materials"]}
    realizations = {realization["id"]: realization for realization in program["realizations"]}
    lineage_by_material = {
        material_id: _sha(
            b"cps.material-lineage/v1\0",
            {key: value for key, value in material.items() if key != "id"},
        )
        for material_id, material in materials.items()
    }
    instances = []
    by_lineage: dict[str, list[dict[str, Any]]] = {}
    for instance in project["material_instances"]:
        try:
            lineage_hash = lineage_by_material[instance["material_id"]]
        except KeyError as error:
            raise CompileError("REFERENCE_NOT_FOUND") from error
        record = {
            "material_instance_id": instance["id"],
            "lineage_hash": lineage_hash,
            "lineage_root_hash": lineage_hash,
        }
        instances.append(record)
        by_lineage.setdefault(lineage_hash, []).append(instance)
    instances.sort(key=lambda item: item["material_instance_id"].encode())
    edges = []
    for lineage_hash in sorted(by_lineage):
        ordered = sorted(by_lineage[lineage_hash], key=lambda item: (item["at_tick"], item["id"].encode()))
        for previous, current in zip(ordered, ordered[1:]):
            try:
                transforms = realizations[current["realization_id"]]["rhythm_transforms"]
            except KeyError as error:
                raise CompileError("REFERENCE_NOT_FOUND") from error
            rotate_total = sum(transform["ticks"] for transform in transforms)
            edges.append({"from_instance_id": previous["id"], "to_instance_id": current["id"], "operation": "identity" if rotate_total == 0 else f"rotate_ticks:{rotate_total}", "identity": rotate_total == 0})
    roots = sorted(set(lineage_by_material.values()))
    project_bytes = _canonical(project)
    project_hash = "sha256:" + hashlib.sha256(project["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + project_bytes).hexdigest()
    return {
        "schema": "cps.lineage-index",
        "schema_version": "1.0.0",
        "project_hash": project_hash,
        "program_lineage_root_hash": _sha(b"cps.program-lineage-root/v1\0", roots),
        "instances": instances,
        "transform_edges": edges,
    }
