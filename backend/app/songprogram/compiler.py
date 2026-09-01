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


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(prefix: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(prefix + _canonical(value)).hexdigest()


def _b32(payload: bytes, length: int) -> str:
    return base64.b32encode(hashlib.sha256(payload).digest()).decode().lower().rstrip("=")[:length]


def _rhe(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    return sign * (quotient + int(remainder * 2 > value.denominator or (remainder * 2 == value.denominator and quotient % 2 == 1)))


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
        result = Decimal(1_200_000) * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln()) / Decimal(2).ln()
        return int(result.to_integral_value(rounding=ROUND_HALF_EVEN))


def _vector_ratio(generators: list[Fraction], vector: list[int], equave: Fraction, exponent: int) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector, strict=True):
        value *= generator**power
    return value * equave**exponent


def _semantic_address(section: str, realization: str, repeat: int, material: str, step: int) -> str:
    core = ["cps.semantic-address", 1, section, realization, repeat, material, step, 0]
    return "sa_" + _b32(_canonical(core), 26)


def _event_id(event: dict[str, Any]) -> str:
    source = event["source"]
    core = {key: event[key] for key in ("kind", "track_id", "section_id", "start_tick", "duration_ticks", "velocity", "articulation", "drum_note", "ratio", "chord_index", "pitch_provenance")}
    core["source"] = {key: source[key] for key in ("material_instance_id", "source_step_ordinal", "emitted_voice_ordinal")}
    payload = b"cps.event-id/v1\0" + source["semantic_address"].encode() + b"\0" + _canonical(core)
    return "ev_" + _b32(payload, 20)


def _instance_id(realization_id: str, repeat: int) -> str:
    stem = realization_id[5:] if realization_id.startswith("real_") else realization_id
    value = "mi_" + stem + ("" if repeat == 0 else f"_{repeat}")
    if not value or len(value) > 40 or not value[0].islower() or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in value):
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
    if program.get("chord_intents") or any(material.get("kind") not in {"rhythm_cell", "direct_vector_cell"} for material in program["materials"]):
        raise CompileError("UNSUPPORTED_COMPILER_SLICE")
    if any(realization["pitch_transforms"] for realization in program["realizations"]):
        raise CompileError("UNSUPPORTED_SP0_TRANSFORM")
    sections = {section["id"]: section for section in program["form"]}
    tracks = {track["id"]: track for track in program["tracks"]}
    materials = {material["id"]: material for material in program["materials"]}
    if len(sections) != len(program["form"]) or len(tracks) != len(program["tracks"]) or len(materials) != len(program["materials"]):
        raise CompileError("SYMBOL_DUPLICATE")
    ticks_per_bar = program["clock"]["beats_per_bar"] * program["clock"]["ticks_per_beat"]
    form = []
    start_bar = 0
    for section in program["form"]:
        form.append({"id": section["id"], "role": section["role"], "start_bar": start_bar, "bars": section["bars"]})
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
        "maximum_reduced_complexity_bits": lattice_source["pitch_exploration"]["maximum_reduced_complexity_bits"],
    }
    lattice["domain_hash"] = _sha(b"cps.lattice-domain/v1\0", {key: value for key, value in lattice.items() if key != "domain_hash"})
    project: dict[str, Any] = {
        "schema": "cps.arrangement-project",
        "schema_version": "1.2.0",
        "source_program": {"hash": _sha(b"cps.song-program/0.1\0", {key: value for key, value in program.items() if key != "program_id"}), "schema": "cps.song-program", "schema_version": "0.1.0"},
        "compiler": {"build_id": identity.build_id, "numeric_contract": identity.numeric_contract, "resolver_build_id": identity.resolver_build_id, "resolver_profile_hash": identity.resolver_profile_hash, "budget_profile_digest": identity.budget_profile_digest, "instrument_catalog_digest": identity.instrument_catalog_digest},
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
            section, track, material = sections[realization["section_id"]], tracks[realization["track_id"]], materials[realization["material_id"]]
            rhythm = materials[material["rhythm_id"]]
        except KeyError as error:
            raise CompileError("REFERENCE_NOT_FOUND") from error
        if material["kind"] != "direct_vector_cell" or rhythm["kind"] != "rhythm_cell" or track["role"] == "drums":
            raise CompileError("UNSUPPORTED_COMPILER_SLICE")
        rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
        for repeat in range(realization["repeat"]):
            instance_id = _instance_id(realization["id"], repeat)
            if instance_id in used_instances:
                raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
            used_instances.add(instance_id)
            instance_tick = section_starts[section["id"]] + realization["at_tick"] + repeat * realization["every_ticks"]
            project["material_instances"].append({"id": instance_id, "material_id": material["id"], "realization_id": realization["id"], "section_id": section["id"], "track_id": track["id"], "repeat_ordinal": repeat, "at_tick": instance_tick, "source_program_path": f"/realizations/{realization_index}"})
            for step_index, step in enumerate(rhythm["steps"]):
                if material["mapping"] == "zip" and step_index >= len(material["vectors"]):
                    raise CompileError("MAPPING_LENGTH_MISMATCH")
                vector = material["vectors"][step_index % len(material["vectors"])]
                final_vector = [left + right for left, right in zip(vector, section["tonal_center"], strict=True)]
                if any(not bound[0] <= coordinate <= bound[1] for coordinate, bound in zip(final_vector, lattice["coordinate_bounds"], strict=True)):
                    raise CompileError("LATTICE_COORDINATE_OUT_OF_RANGE")
                base_ratio = _vector_ratio(generators, final_vector, equave, 0)
                exponent = _place_exponent(base_ratio, equave, material["register_delta"], lattice["register_bounds"], track["register_millicents"])
                ratio = _ratio_text(base_ratio * equave**exponent)
                onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                duration = max(1, _rhe(Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)))
                if onset + duration > section_starts[section["id"]] + section["bars"] * ticks_per_bar:
                    raise CompileError("EVENT_SECTION_OVERFLOW")
                velocity = min(127, max(1, _rhe(Fraction(125 * step["accent_q"] * realization["velocity_scale_q"], 100_000_000))))
                address = _semantic_address(section["id"], realization["id"], repeat, material["id"], step_index)
                event = {"id": "", "kind": "note", "track_id": track["id"], "section_id": section["id"], "start_tick": onset, "duration_ticks": duration, "velocity": velocity, "articulation": "normal", "drum_note": None, "ratio": ratio, "chord_index": None, "pitch_provenance": {"kind": "direct_vector", "material_vector": vector, "tonal_center": section["tonal_center"], "register_delta": material["register_delta"], "register_shift_equaves": 0, "placed_equave_exponent": exponent - material["register_delta"], "final_vector": final_vector, "equave_exponent": exponent, "final_ratio": ratio}, "source": {"material_instance_id": instance_id, "source_step_ordinal": step_index, "emitted_voice_ordinal": 0, "semantic_address": address}}
                event["id"] = _event_id(event)
                project["events"].append(event)
    if not project["events"] or len(project["events"]) > program["limits"]["max_events"]:
        raise CompileError("EVENT_LIMIT_EXCEEDED")
    project["material_instances"].sort(key=lambda item: item["id"].encode())
    project["events"].sort(key=lambda item: (item["start_tick"], item["track_id"].encode(), 1, item["ratio"], item["source"]["semantic_address"], item["id"]))
    return project
