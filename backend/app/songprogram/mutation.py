"""Atomic typed SongProgram mutation application (MutationContract 1.0)."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from fractions import Fraction
from typing import Any


class MutationError(ValueError):
    """A typed mutation failure; ``code`` is the backwards-compatible API."""

    def __init__(self, code: str, stage: str = "mutation", ordinal: int = 0) -> None:
        super().__init__(code)
        self.code, self.stage, self.ordinal = code, stage, ordinal


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _lf(value: Any) -> bytes:
    return _canon(value) + b"\n"


def artifact_hash(domain: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + _lf(value)).hexdigest()


def program_hash(program: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        b"cps.song-program/0.1\0" + _canon({key: value for key, value in program.items() if key != "program_id"})
    ).hexdigest()


def _derived(prefix: bytes, mutation_id: str, source_id: str) -> str:
    raw = hashlib.sha256(prefix + mutation_id.encode() + b"\0" + source_id.encode()).digest()
    return base64.b32encode(raw).decode().lower().rstrip("=")[:20]


def _find(items: list[dict[str, Any]], ident: str, ordinal: int) -> dict[str, Any]:
    for item in items:
        if item["id"] == ident:
            return item
    raise MutationError("MUTATION_REFERENCE_NOT_FOUND", "mutation", ordinal)


def _ordered(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(items, key=lambda item: (item["kind"].encode(), item["id"].encode()))


def _roots(parameters: dict[str, Any], ordinal: int) -> list[dict[str, str]]:
    kind = parameters["kind"]
    if kind == "replace_bounded_scalar":
        if parameters["owner_kind"] == "section" and parameters["field"] == "bars":
            roots = [{"kind": "section", "id": parameters["owner_id"]}, {"kind": "global_form", "id": "global_form"}]
        elif parameters["owner_kind"] in {"realization", "production"}:
            roots = [{"kind": parameters["owner_kind"], "id": parameters["owner_id"]}]
        else:
            raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    elif kind == "replace_distribution_choice":
        roots = [{"kind": "production", "id": "production"}] if parameters["owner_kind"] == "production" else [{"kind": parameters["owner_kind"], "id": parameters["owner_id"]}]
    elif kind in {"transpose_material_vector", "replace_root_anchor_item"}:
        roots = [{"kind": "material", "id": parameters["material_id"]}]
    elif kind == "rotate_rhythm":
        roots = [{"kind": "rhythm", "id": parameters["rhythm_id"]}]
    elif kind == "replace_chord_intent_reference":
        roots = [{"kind": "chord_intent", "id": parameters["chord_intent_id"]}]
    elif kind == "edit_section":
        roots = [{"kind": "section", "id": parameters["section_id"]}, {"kind": "global_form", "id": "global_form"}]
    elif kind == "swap_track_catalog_entry":
        roots = [{"kind": "track", "id": parameters["track_id"]}]
    else:
        raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    return _ordered(roots)


def _closure(program: dict[str, Any], actual: list[dict[str, str]], mutation: dict[str, Any], after: bool) -> list[dict[str, str]]:
    found = {(item["kind"], item["id"]) for item in actual}
    changed = True
    while changed:
        changed = False
        for kind, ident in list(found):
            additions: list[tuple[str, str]] = []
            if kind == "rhythm":
                additions += [("material", item["id"]) for item in program["materials"] if item.get("rhythm_id") == ident]
            elif kind == "chord_intent":
                additions += [("material", item["id"]) for item in program["materials"] if ident in item.get("chord_intent_ids", [])]
            elif kind == "material":
                additions += [("realization", item["id"]) for item in program["realizations"] if item["material_id"] == ident]
            elif kind == "section":
                additions += [("realization", item["id"]) for item in program["realizations"] if item["section_id"] == ident]
            elif kind == "track":
                additions += [("realization", item["id"]) for item in program["realizations"] if item["track_id"] == ident]
                if ident in program["production"]["tracks"]:
                    additions.append(("production", ident))
            elif kind == "global_form":
                parameters = mutation["parameters"]
                if parameters["kind"] == "edit_section" and parameters["action"] == "duplicate":
                    marker = "sec_" + _derived(b"cps.mutation-section-id/v1\0", mutation["mutation_id"], parameters["section_id"])
                    start = next((i for i, item in enumerate(program["form"]) if item["id"] == marker), len(program["form"])) if after else next(i for i, item in enumerate(program["form"]) if item["id"] == parameters["insert_after_section_id"]) + 1
                else:
                    start = next((i for i, item in enumerate(program["form"]) if item["id"] == parameters.get("section_id", parameters.get("owner_id"))), len(program["form"]))
                additions += [("section", item["id"]) for item in program["form"][start:]]
            for addition in additions:
                if addition not in found:
                    found.add(addition)
                    changed = True
    return [{"kind": kind, "id": ident} for kind, ident in sorted(found, key=lambda item: (item[0].encode(), item[1].encode()))]


def _components(operation: str, parameters: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    song = [key for key in ["form", "tracks", "materials", "chord_intents", "realizations", "production"] if before[key] != after[key]]
    if not song:
        return [], [], []
    project, downstream = ["source_program_hash"], []
    if (operation == "replace_bounded_scalar" and parameters["field"] == "bars") or operation == "edit_section": project.append("form_clock")
    if (operation == "replace_distribution_choice" and parameters["owner_kind"] == "section") or operation == "edit_section": project.append("form_metadata")
    if (operation == "replace_distribution_choice" and parameters["owner_kind"] == "track") or operation == "swap_track_catalog_entry": project.append("track_records")
    if operation == "replace_bounded_scalar" and parameters["owner_kind"] == "production": project.append("mix")
    broad = operation in {"transpose_material_vector", "replace_root_anchor_item", "rotate_rhythm", "replace_chord_intent_reference", "edit_section"} or (operation == "replace_bounded_scalar" and parameters["owner_kind"] == "section") or (operation == "replace_distribution_choice" and parameters["owner_kind"] in {"material", "track"})
    if broad:
        project += ["material_instances", "resolved_chords", "harmony_occurrences", "events"]
        downstream.append("lineage_index")
    if operation == "replace_bounded_scalar" and parameters["owner_kind"] == "realization":
        project += ["harmony_occurrences", "events"]
        downstream.append("lineage_index")
    if not (operation == "replace_distribution_choice" and parameters["owner_kind"] == "section"):
        downstream += ["render_stems", "render_mix", "audio_evaluation"]
    if not ((operation == "replace_bounded_scalar" and parameters["owner_kind"] == "production") or (operation == "replace_distribution_choice" and parameters["owner_kind"] == "production") or operation == "swap_track_catalog_entry"):
        downstream.append("descriptors")
    project_order = ["source_program_hash", "form_clock", "form_metadata", "track_records", "mix", "material_instances", "resolved_chords", "harmony_occurrences", "events"]
    downstream_order = ["lineage_index", "render_stems", "render_mix", "audio_evaluation", "descriptors"]
    return song, [item for item in project_order if item in project], [item for item in downstream_order if item in downstream]


def _apply_one(program: dict[str, Any], mutation: dict[str, Any], choices: dict[str, Any], catalog: dict[str, Any], ordinal: int) -> dict[str, Any]:
    p, op, result = mutation["parameters"], mutation["operation"], copy.deepcopy(program)
    if op == "replace_bounded_scalar":
        bounds = {"bars": (1, 32), "velocity_scale_q": (0, 10000), "gate_scale_q": (1, 10000), "gain_q": (0, 10000), "pan_q": (-10000, 10000)}
        if p["field"] not in bounds or (p["minimum"], p["maximum"]) != bounds[p["field"]] or not p["minimum"] <= p["value"] <= p["maximum"]: raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        target = result["production"]["tracks"].get(p["owner_id"]) if p["owner_kind"] == "production" else _find(result["form"] if p["owner_kind"] == "section" else result["realizations"], p["owner_id"], ordinal)
        if target is None: raise MutationError("MUTATION_REFERENCE_NOT_FOUND", "mutation", ordinal)
        target[p["field"]] = p["value"]
    elif op == "replace_distribution_choice":
        choice = next((item for item in choices["entries"] if item["choice_id"] == p["choice_id"] and item["owner_kind"] == p["owner_kind"] and item["field"] == p["field"]), None)
        if choice is None: raise MutationError("MUTATION_CHOICE_UNRESOLVED", "mutation", ordinal)
        target = result["production"] if p["owner_kind"] == "production" else _find(result[{"section": "form", "material": "materials", "track": "tracks"}[p["owner_kind"]]], p["owner_id"], ordinal)
        target[p["field"]] = choice["value"]
    elif op == "transpose_material_vector":
        target = _find(result["materials"], p["material_id"], ordinal)
        field = "vectors" if target["kind"] == "direct_vector_cell" else "root_anchors" if target["kind"] == "harmony_intent_cell" else None
        if field is None or len(p["vector_delta"]) != len(result["lattice"]["generators"]): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        target[field] = [[a + b for a, b in zip(vector, p["vector_delta"], strict=True)] for vector in target[field]]
    elif op == "rotate_rhythm":
        target = _find(result["materials"], p["rhythm_id"], ordinal)
        if target["kind"] != "rhythm_cell": raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        onsets = sorted({item["at_tick"] for item in target["steps"]}); gaps = [b-a for a,b in zip(onsets,onsets[1:])] + [target["length_ticks"]-onsets[-1]+onsets[0]]
        quantum = math.gcd(target["length_ticks"], *(item["duration_ticks"] for item in target["steps"]), *(item for item in gaps if item))
        target["steps"] = [item for _, item in sorted(enumerate(({**item, "at_tick": (item["at_tick"] + p["steps"] * quantum) % target["length_ticks"]} for item in target["steps"])), key=lambda pair: (pair[1]["at_tick"], pair[0]))]
    elif op == "replace_chord_intent_reference":
        target = _find(result["chord_intents"], p["chord_intent_id"], ordinal); values = sorted(p["steps"])
        if len(values) != len(set(values)) or any(value < 0 or value >= p["divisions"] for value in values): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        ratio = Fraction(p["reference_equave"]); target["reference"] = {"temperament": "edo", "equave": f"{ratio.numerator}/{ratio.denominator}", "divisions": p["divisions"], "steps": values}
    elif op == "replace_root_anchor_item":
        target = _find(result["materials"], p["material_id"], ordinal)
        if target["kind"] != "harmony_intent_cell" or p["index"] >= len(target["root_anchors"]) or len(p["vector"]) != len(result["lattice"]["generators"]): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        target["root_anchors"][p["index"]] = p["vector"]
    elif op == "edit_section":
        source = _find(result["form"], p["section_id"], ordinal)
        if p["action"] == "delete":
            if p["insert_after_section_id"] is not None or len(result["form"]) == 1: raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
            result["form"] = [item for item in result["form"] if item["id"] != source["id"]]; result["realizations"] = [item for item in result["realizations"] if item["section_id"] != source["id"]]
        elif p["action"] == "duplicate":
            predecessor = _find(result["form"], p["insert_after_section_id"], ordinal); section_id = "sec_" + _derived(b"cps.mutation-section-id/v1\0", mutation["mutation_id"], source["id"])
            if any(item["id"] == section_id for item in result["form"]): raise MutationError("MUTATION_ID_COLLISION", "application", ordinal)
            result["form"].insert(result["form"].index(predecessor)+1, {**source, "id": section_id})
            rebuilt = []
            for item in result["realizations"]:
                rebuilt.append(item)
                if item["section_id"] == source["id"]: rebuilt.append({**item, "id": "real_" + _derived(b"cps.mutation-realization-id/v1\0", mutation["mutation_id"], item["id"]), "section_id": section_id})
            result["realizations"] = rebuilt
        else: raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    elif op == "swap_track_catalog_entry":
        track = _find(result["tracks"], p["track_id"], ordinal); entry = next((item for item in catalog["entries"] if item["instrument_id"] == p["instrument_id"]), None)
        if entry is None: raise MutationError("MUTATION_REFERENCE_NOT_FOUND", "mutation", ordinal)
        if (track["role"] == "drums") != (entry["kind"] == "drum_kit"): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        if track["role"] == "drums" and any(note not in {item["drum_note"] for item in entry["note_map"]} for note in track["drum_map"].values()): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        track["instrument_id"] = p["instrument_id"]
    else: raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    return result


def _error(exc: MutationError) -> dict[str, Any]:
    return {"code": exc.code, "stage": exc.stage, "pointer": "", "mutation_ordinal": exc.ordinal}


def _failed_step(mutation: dict[str, Any], ordinal: int, input_hash: str, actual: list[dict[str, str]] | None, error: dict[str, Any]) -> dict[str, Any]:
    return {"ordinal": ordinal, "mutation_id": mutation.get("mutation_id"), "mutation_hash": artifact_hash("cps.mutation/v1", mutation), "input_program_hash": input_hash, "status": "failed", "identity": None, "actual_roots": actual, "scope_hash": artifact_hash("cps.mutation-scope/v1", actual) if actual is not None else None, "closure_before": None, "closure_after": None, "closure_hash": None, "output_program_hash": None, "impact_hash": None, "error": error}


def apply_mutation_request(request: dict[str, Any]) -> dict[str, Any]:
    """Atomically apply a MutationApplicationRequest and return canonical artifacts."""
    request_hash = artifact_hash("cps.mutation-application-request/v1", request)
    base = copy.deepcopy(request["base_program"]); base_hash = program_hash(base); current = base
    entries: list[dict[str, Any]] = []; steps: list[dict[str, Any]] = []
    actual: list[dict[str, str]] | None = None
    try:
        for ordinal, mutation in enumerate(request["mutations"]):
            before = copy.deepcopy(current); before_hash = program_hash(before); actual = None
            if mutation.get("operation") != mutation.get("parameters", {}).get("kind"): raise MutationError("MUTATION_OPERATION_MISMATCH", "mutation", ordinal)
            if mutation.get("base_program_hash") != before_hash: raise MutationError("MUTATION_BASE_HASH_MISMATCH", "mutation", ordinal)
            try:
                trial = _apply_one(before, mutation, request["mutation_choice_catalog"], request["instrument_catalog"], ordinal)
                actual = _roots(mutation["parameters"], ordinal)
                if actual != _ordered(mutation.get("declared_scope", [])): raise MutationError("MUTATION_SCOPE_MISMATCH", "scope", ordinal)
                locks = {(item["kind"], item["id"]) for item in request["locked_roots"]}
                if any((item["kind"], item["id"]) in locks for item in actual): raise MutationError("MUTATION_LOCKED", "lock", ordinal)
            except MutationError: raise
            except (KeyError, IndexError, TypeError, ValueError): raise MutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal) from None
            after_hash = program_hash(trial); closure_before = _closure(before, actual, mutation, False); closure_after = _closure(trial, actual, mutation, True)
            song, project, downstream = _components(mutation["operation"], mutation["parameters"], before, trial)
            entry = {"ordinal": ordinal, "mutation_id": mutation["mutation_id"], "operation": mutation["operation"], "before_program_hash": before_hash, "after_program_hash": after_hash, "identity": before_hash == after_hash, "actual_roots": actual, "closure_before": closure_before, "closure_after": closure_after, "song_program_components": song, "project_components": project, "downstream_components": downstream}
            entries.append(entry)
            steps.append({"ordinal": ordinal, "mutation_id": mutation["mutation_id"], "mutation_hash": artifact_hash("cps.mutation/v1", mutation), "input_program_hash": before_hash, "status": "complete", "identity": before_hash == after_hash, "actual_roots": actual, "scope_hash": artifact_hash("cps.mutation-scope/v1", actual), "closure_before": closure_before, "closure_after": closure_after, "closure_hash": artifact_hash("cps.mutation-closure/v1", {"closure_before": closure_before, "closure_after": closure_after}), "output_program_hash": after_hash, "impact_hash": artifact_hash("cps.mutation-impact/v1", entry), "error": None})
            current = trial
    except MutationError as exc:
        error = _error(exc); steps.append(_failed_step(request["mutations"][exc.ordinal], exc.ordinal, program_hash(current), actual, error))
        receipt = {"schema": "cps.mutation-application-receipt", "schema_version": "1.0.0", "request_hash": request_hash, "status": "failed", "base_program_hash": base_hash, "result_program_hash": None, "impact_report_hash": None, "steps": steps, "error": error, "receipt_hash": ""}
        receipt["receipt_hash"] = artifact_hash("cps.mutation-application-receipt/v1", {key: value for key, value in receipt.items() if key != "receipt_hash"})
        return {"status": "failure", "program": None, "impact": None, "receipt": receipt, "error": error}
    result_hash = program_hash(current)
    impact = {"schema": "cps.mutation-impact-report", "schema_version": "1.0.0", "request_hash": request_hash, "base_program_hash": base_hash, "result_program_hash": result_hash, "identity": base_hash == result_hash, "entries": entries}
    receipt = {"schema": "cps.mutation-application-receipt", "schema_version": "1.0.0", "request_hash": request_hash, "status": "complete", "base_program_hash": base_hash, "result_program_hash": result_hash, "impact_report_hash": artifact_hash("cps.mutation-impact-report/v1", impact), "steps": steps, "error": None, "receipt_hash": ""}
    receipt["receipt_hash"] = artifact_hash("cps.mutation-application-receipt/v1", {key: value for key, value in receipt.items() if key != "receipt_hash"})
    return {"status": "success", "program": current, "impact": impact, "receipt": receipt, "error": None}


apply_mutation_application_request = apply_mutation_request


def apply_mutations(program: dict[str, Any], mutations: list[dict[str, Any]], locked_roots: list[dict[str, str]], choice_catalog: dict[str, Any], catalog: dict[str, Any], action_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Legacy program-only API, preserved for existing callers."""
    del action_id
    current, impacts = copy.deepcopy(program), []
    locks = {(item["kind"], item["id"]) for item in locked_roots}
    for ordinal, mutation in enumerate(mutations):
        if mutation.get("operation") != mutation.get("parameters", {}).get("kind"): raise MutationError("MUTATION_OPERATION_MISMATCH", "mutation", ordinal)
        if mutation.get("base_program_hash") != program_hash(current): raise MutationError("MUTATION_BASE_HASH_MISMATCH", "mutation", ordinal)
        trial = _apply_one(current, mutation, choice_catalog, catalog, ordinal); roots = _roots(mutation["parameters"], ordinal)
        if roots != _ordered(mutation.get("declared_scope", [])): raise MutationError("MUTATION_SCOPE_MISMATCH", "scope", ordinal)
        if any((item["kind"], item["id"]) in locks for item in roots): raise MutationError("MUTATION_LOCKED", "lock", ordinal)
        current = trial; impacts.append({"ordinal": ordinal, "roots": roots, "program_hash": program_hash(current)})
    return current, impacts
