"""Standalone semantic validator for native ArrangementProject 1.2."""

from __future__ import annotations

import base64
import hashlib
import json
from fractions import Fraction
from typing import Any


class ProjectValidationError(ValueError):
    def __init__(self, code: str, stage: str, pointer: str) -> None:
        super().__init__(code)
        self.code, self.stage, self.pointer = code, stage, pointer


def _fail(code: str, stage: str, pointer: str) -> None:
    raise ProjectValidationError(code, stage, pointer)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(prefix: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(prefix + _canonical(value)).hexdigest()


def _b32(payload: bytes, length: int) -> str:
    return base64.b32encode(hashlib.sha256(payload).digest()).decode().lower().rstrip("=")[:length]


def _ratio(text: Any, pointer: str) -> Fraction:
    if not isinstance(text, str):
        _fail("SCHEMA_TYPE_MISMATCH", "schema", pointer)
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        _fail("RATIO_NOT_REDUCED", "numeric", pointer)
    if value <= 0 or text != f"{value.numerator}/{value.denominator}":
        _fail("RATIO_NOT_REDUCED", "numeric", pointer)
    return value


def _vector_ratio(generators: list[Fraction], vector: list[int], equave: Fraction, exponent: int) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector, strict=True):
        value *= generator**power
    return value * equave**exponent


def _semantic_address(instance: dict[str, Any], step: int, voice: int) -> str:
    core = ["cps.semantic-address", 1, instance["section_id"], instance["realization_id"], instance["repeat_ordinal"], instance["material_id"], step, voice]
    return "sa_" + _b32(_canonical(core), 26)


def _event_id(event: dict[str, Any]) -> str:
    source = event["source"]
    fields = ("kind", "track_id", "section_id", "start_tick", "duration_ticks", "velocity", "articulation", "drum_note", "ratio", "chord_index", "pitch_provenance")
    core = {field: event[field] for field in fields}
    core["source"] = {field: source[field] for field in ("material_instance_id", "source_step_ordinal", "emitted_voice_ordinal")}
    return "ev_" + _b32(b"cps.event-id/v1\0" + source["semantic_address"].encode() + b"\0" + _canonical(core), 20)


def _chord_id(chord: dict[str, Any]) -> str:
    fields = ("domain_hash", "intent_hash", "resolver_build_id", "numeric_contract", "search_completeness", "reference_equave", "reference_divisions", "canonical_steps", "eligibility_contract", "anchor_vector", "voice_offsets", "equave_exponents", "exact_ratios", "target_voice_ordinals", "pair_errors_millicents", "maximum_pair_error_millicents", "pair_rms_error_millicents", "complexity_score")
    return "rc_" + _b32(b"cps.resolved-chord/v1\0" + _canonical({field: chord[field] for field in fields}), 26)


def _unique(items: list[dict[str, Any]], pointer: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if item["id"] in result:
            _fail("ID_DUPLICATE", "identity", f"{pointer}/{index}/id")
        result[item["id"]] = item
    return result


def validate_project(project: dict[str, Any]) -> None:
    required = {"schema", "schema_version", "source_program", "compiler", "lattice", "clock", "tracks", "form", "material_instances", "resolved_chords", "harmony_occurrences", "events", "mix", "render_settings"}
    for key in project:
        if key not in required:
            _fail("SCHEMA_UNKNOWN_FIELD", "schema", "/" + key)
    if not required <= set(project):
        _fail("SCHEMA_REQUIRED_FIELD", "schema", "")
    if project["schema"] != "cps.arrangement-project" or project["schema_version"] != "1.2.0":
        _fail("SCHEMA_VERSION_UNSUPPORTED", "schema", "/schema_version")
    lattice = project["lattice"]
    if lattice["domain_hash"] != _sha(b"cps.lattice-domain/v1\0", {key: value for key, value in lattice.items() if key != "domain_hash"}):
        _fail("HASH_MISMATCH", "hash", "/lattice/domain_hash")
    equave = _ratio(lattice["equave"], "/lattice/equave")
    generators = [_ratio(value, f"/lattice/generators/{index}") for index, value in enumerate(lattice["generators"])]
    if len(generators) != len(lattice["coordinate_bounds"]):
        _fail("VECTOR_DIMENSION_MISMATCH", "numeric", "/lattice/coordinate_bounds")
    tracks = _unique(project["tracks"], "/tracks")
    instances = _unique(project["material_instances"], "/material_instances")
    sections = _unique(project["form"], "/form")
    chords = _unique(project["resolved_chords"], "/resolved_chords")
    start_bar = 0
    for index, section in enumerate(project["form"]):
        if section["start_bar"] != start_bar:
            _fail("FORM_NOT_CONTIGUOUS", "timeline", f"/form/{index}/start_bar")
        start_bar += section["bars"]
    ticks_per_bar = project["clock"]["beats_per_bar"] * project["clock"]["ticks_per_beat"]
    if project["clock"]["bars"] != start_bar or project["clock"]["total_ticks"] != start_bar * ticks_per_bar:
        _fail("CLOCK_INCONSISTENT", "timeline", "/clock/total_ticks")
    for index, chord in enumerate(project["resolved_chords"]):
        pointer = f"/resolved_chords/{index}"
        if chord["domain_hash"] != lattice["domain_hash"] or chord["resolver_build_id"] != project["compiler"]["resolver_build_id"]:
            _fail("REFERENCE_MISMATCH", "references", pointer)
        if len({len(chord[field]) for field in ("voice_offsets", "equave_exponents", "exact_ratios", "target_voice_ordinals")}) != 1:
            _fail("CHORD_PARALLEL_LENGTH_MISMATCH", "provenance", pointer)
        for voice, (offset, exponent, ratio_text) in enumerate(zip(chord["voice_offsets"], chord["equave_exponents"], chord["exact_ratios"], strict=True)):
            vector = [left + right for left, right in zip(chord["anchor_vector"], offset, strict=True)]
            if _vector_ratio(generators, vector, equave, exponent) != _ratio(ratio_text, f"{pointer}/exact_ratios/{voice}"):
                _fail("PITCH_EQUATION_MISMATCH", "provenance", f"{pointer}/exact_ratios/{voice}")
        if chord["id"] != _chord_id(chord):
            _fail("HASH_MISMATCH", "hash", pointer + "/id")
    occurrences = project["harmony_occurrences"]
    for index, occurrence in enumerate(occurrences):
        if occurrence["chord_index"] != index:
            _fail("CHORD_INDEX_GAP", "references", f"/harmony_occurrences/{index}/chord_index")
        if occurrence["resolved_chord_id"] not in chords or occurrence["section_id"] not in sections:
            _fail("REFERENCE_NOT_FOUND", "references", f"/harmony_occurrences/{index}")
    event_ids: set[str] = set()
    referenced_chords: set[str] = set()
    for index, event in enumerate(project["events"]):
        pointer = f"/events/{index}"
        if not isinstance(event.get("velocity"), int) or isinstance(event.get("velocity"), bool):
            _fail("SCHEMA_TYPE_MISMATCH", "schema", pointer + "/velocity")
        if event["track_id"] not in tracks or event["section_id"] not in sections:
            _fail("REFERENCE_NOT_FOUND", "references", pointer)
        instance_id = event["source"]["material_instance_id"]
        if instance_id not in instances:
            _fail("REFERENCE_NOT_FOUND", "references", pointer + "/source/material_instance_id")
        instance, source = instances[instance_id], event["source"]
        if (instance["track_id"], instance["section_id"]) != (event["track_id"], event["section_id"]):
            _fail("REFERENCE_MISMATCH", "references", pointer + "/source")
        if source["semantic_address"] != _semantic_address(instance, source["source_step_ordinal"], source["emitted_voice_ordinal"]):
            _fail("HASH_MISMATCH", "hash", pointer + "/source/semantic_address")
        section = sections[event["section_id"]]
        section_start = section["start_bar"] * ticks_per_bar
        if event["start_tick"] < section_start or event["start_tick"] + event["duration_ticks"] > section_start + section["bars"] * ticks_per_bar:
            _fail("EVENT_SECTION_OVERFLOW", "timeline", pointer)
        if event["kind"] == "drum":
            if any(event[field] is not None for field in ("ratio", "chord_index", "pitch_provenance")):
                _fail("PROVENANCE_VARIANT_FIELD", "provenance", pointer)
            if tracks[event["track_id"]]["role"] != "drums" or source["emitted_voice_ordinal"] != 0:
                _fail("ROLE_SOURCE_MISMATCH", "provenance", pointer)
        elif event["kind"] == "note":
            ratio, provenance = _ratio(event["ratio"], pointer + "/ratio"), event["pitch_provenance"]
            if provenance["kind"] == "direct_vector":
                allowed = {"kind", "material_vector", "tonal_center", "register_delta", "register_shift_equaves", "placed_equave_exponent", "final_vector", "equave_exponent", "final_ratio"}
                for field in provenance:
                    if field not in allowed:
                        _fail("PROVENANCE_VARIANT_FIELD", "provenance", pointer + "/pitch_provenance/" + field)
                final_vector = [left + right for left, right in zip(provenance["material_vector"], provenance["tonal_center"], strict=True)]
                final_exponent = provenance["register_delta"] + provenance["register_shift_equaves"] + provenance["placed_equave_exponent"]
                actual = _vector_ratio(generators, final_vector, equave, final_exponent)
                if provenance["final_vector"] != final_vector or provenance["equave_exponent"] != final_exponent or _ratio(provenance["final_ratio"], pointer + "/pitch_provenance/final_ratio") != actual or ratio != actual or event["chord_index"] is not None:
                    _fail("PITCH_EQUATION_MISMATCH", "provenance", pointer + "/pitch_provenance")
                if source["emitted_voice_ordinal"] != 0:
                    _fail("ROLE_SOURCE_MISMATCH", "provenance", pointer + "/source/emitted_voice_ordinal")
            elif provenance["kind"] == "resolved_chord_voice":
                chord_id = provenance["resolved_chord_id"]
                if chord_id not in chords or event["chord_index"] is None or event["chord_index"] >= len(occurrences) or occurrences[event["chord_index"]]["resolved_chord_id"] != chord_id:
                    _fail("REFERENCE_NOT_FOUND", "references", pointer + "/pitch_provenance/resolved_chord_id")
                chord, ordinal = chords[chord_id], provenance["shape_voice_ordinal"]
                if ordinal >= len(chord["voice_offsets"]):
                    _fail("VOICE_ORDINAL_INVALID", "provenance", pointer + "/pitch_provenance/shape_voice_ordinal")
                expected_vector = [left + right for left, right in zip(chord["anchor_vector"], chord["voice_offsets"][ordinal], strict=True)]
                if provenance["anchor_vector"] != chord["anchor_vector"] or provenance["offset_vector"] != chord["voice_offsets"][ordinal] or provenance["final_vector"] != expected_vector or provenance["equave_exponent"] != chord["equave_exponents"][ordinal] or provenance["final_ratio"] != chord["exact_ratios"][ordinal] or ratio != _ratio(chord["exact_ratios"][ordinal], pointer + "/ratio"):
                    _fail("PITCH_EQUATION_MISMATCH", "provenance", pointer + "/pitch_provenance")
                referenced_chords.add(chord_id)
            else:
                _fail("UNSUPPORTED_SCHEMA_CAPABILITY", "capability", pointer + "/pitch_provenance/kind")
        else:
            _fail("SCHEMA_VARIANT_INVALID", "schema", pointer + "/kind")
        if event["id"] != _event_id(event):
            _fail("HASH_MISMATCH", "hash", pointer + "/id")
        if event["id"] in event_ids:
            _fail("ID_DUPLICATE", "identity", pointer + "/id")
        event_ids.add(event["id"])
    if referenced_chords != set(chords):
        _fail("UNUSED_RESOLVED_CHORD", "references", "/resolved_chords")
