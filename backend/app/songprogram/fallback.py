"""Deterministic typed fallback proposals and broad-prior production lowering.

The conformance package deliberately has its own oracle.  This module is the
production implementation and consequently depends only on app primitives.
It has no ambient RNG, clock, process state, or fixture dependency.
"""

from __future__ import annotations

import base64
import copy
import hashlib
from fractions import Fraction
from typing import Any, Iterable

from .mutation import _apply_one, _roots, apply_mutation_request, program_hash
from .search import canonical_bytes


U64_MAX = (1 << 64) - 1
ROLES = ("drums", "bass", "harmony", "melody", "texture")
OPERATIONS = (
    "replace_bounded_scalar",
    "replace_distribution_choice",
    "transpose_material_vector",
    "rotate_rhythm",
    "replace_chord_intent_reference",
    "replace_root_anchor_item",
    "edit_section",
    "swap_track_catalog_entry",
)


class FallbackError(ValueError):
    """A stable error at a closed fallback/sampler boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.decision_trace: list[dict[str, Any]] = []


def _artifact_hash(domain: str, value: Any, *, omit: str | None = None) -> str:
    if omit is not None:
        if not isinstance(value, dict):
            raise FallbackError("FALLBACK_REQUEST_INVALID")
        value = {key: item for key, item in value.items() if key != omit}
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(value)).hexdigest()


def _canonical(value: Any) -> bytes:
    """Canonical JSON without the line framing owned by ``search`` artifacts."""
    return canonical_bytes(value)[:-1]


def _choice_u64(domain: str, seed: int, path: list[Any]) -> int:
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= U64_MAX:
        raise FallbackError("FALLBACK_REQUEST_INVALID")
    raw = domain.encode() + b"\0" + seed.to_bytes(8, "big") + _canonical(path)
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _weighted_table(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not table:
        raise FallbackError("FALLBACK_REQUEST_INVALID")
    ordered = sorted(table, key=lambda item: _canonical(item["value"]))
    if table != ordered:
        raise FallbackError("FALLBACK_REQUEST_INVALID")
    seen: set[bytes] = set()
    total = 0
    for item in table:
        key = _canonical(item["value"])
        weight = item.get("weight")
        if key in seen or not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= U64_MAX:
            raise FallbackError("FALLBACK_REQUEST_INVALID")
        seen.add(key)
        total += weight
        if total > U64_MAX:
            raise FallbackError("FALLBACK_REQUEST_INVALID")
    return ordered


def _choose(table: list[dict[str, Any]], draw: int) -> Any:
    ordered = _weighted_table(table)
    cursor, upper = draw % sum(item["weight"] for item in ordered), 0
    for item in ordered:
        upper += item["weight"]
        if cursor < upper:
            return copy.deepcopy(item["value"])
    raise AssertionError("weighted table exhausted")


def _ordered_roots(roots: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return sorted((dict(item) for item in roots), key=lambda item: (item["kind"].encode(), item["id"].encode()))


def fallback_mutation_id(request_hash: str, round_index: int, candidate: int,
                         attempt: int, ordinal: int, core: dict[str, Any]) -> str:
    raw = (b"cps.fallback-mutation-id/v1\0" + request_hash.encode() +
           round_index.to_bytes(8, "big") + candidate.to_bytes(8, "big") +
           attempt.to_bytes(8, "big") + ordinal.to_bytes(4, "big") + canonical_bytes(core))
    return "mut_" + base64.b32encode(hashlib.sha256(raw).digest()).decode().lower().rstrip("=")[:20]


def _validate_fallback_manifest(manifest: dict[str, Any], dimension: int) -> None:
    if manifest.get("stream_domain") != "cps.mutation-fallback/v1":
        raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    operations = [row.get("operation") for row in manifest.get("operation_table", [])]
    if operations != list(OPERATIONS):
        raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    for row in manifest["operation_table"]:
        weight = row.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= U64_MAX:
            raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    tables = manifest.get("parameter_tables")
    if not isinstance(tables, dict):
        raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    for name in ("distribution_choice_ids", "transpose_unit_vectors", "chord_references", "root_anchor_unit_vectors", "edit_actions", "instrument_entry_ids"):
        try:
            _weighted_table(tables[name])
        except (KeyError, TypeError, FallbackError) as exc:
            raise FallbackError("FALLBACK_MANIFEST_MISMATCH") from exc
    rotations = tables.get("rotate_ordinal_steps")
    if not isinstance(rotations, list) or [row.get("value") for row in rotations] != [-4, -3, -2, -1, 1, 2, 3, 4]:
        raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    if any(not isinstance(row.get("weight"), int) or isinstance(row["weight"], bool) or not 1 <= row["weight"] <= U64_MAX for row in rotations):
        raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    for name in ("transpose_unit_vectors", "root_anchor_unit_vectors"):
        for row in tables[name]:
            value = row["value"]
            if not isinstance(value, list) or len(value) != dimension or sum(item != 0 for item in value) != 1 or any(item not in (-1, 0, 1) for item in value):
                raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
    for scalar in tables.get("bounded_scalars", []):
        try:
            _weighted_table(scalar["choices"])
        except (KeyError, TypeError, FallbackError) as exc:
            raise FallbackError("FALLBACK_MANIFEST_MISMATCH") from exc


def _row(operation: str, owner_kind: str, owner_id: str, field: Any,
         parameter: dict[str, Any], weight: int, roots: list[dict[str, str]]) -> dict[str, Any]:
    return {"operation": operation, "owner_kind": owner_kind, "owner_id": owner_id,
            "field_or_index": field, "parameter": parameter, "parameter_weight": weight,
            "actual_roots": _ordered_roots(roots), "identity": False}


def _rhythm_quantum(material: dict[str, Any]) -> int:
    import math

    steps = material["steps"]
    onsets = sorted({item["at_tick"] for item in steps})
    gaps = [right - left for left, right in zip(onsets, onsets[1:])]
    gaps.append(material["length_ticks"] - onsets[-1] + onsets[0])
    return math.gcd(material["length_ticks"], *(item["duration_ticks"] for item in steps), *(gap for gap in gaps if gap))


def enumerate_fallback_rows(program: dict[str, Any], manifest: dict[str, Any],
                            choice_catalog: dict[str, Any], instrument_catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Enumerate the finite, non-identity mutation universe for one program.

    This intentionally does not select a row.  Rebuilding it after every
    private sequential mutation is what keeps later bases and locks exact.
    """
    dimension = len(program["lattice"]["generators"])
    _validate_fallback_manifest(manifest, dimension)
    tables = manifest["parameter_tables"]
    rows: list[dict[str, Any]] = []
    bounds = {"bars": (1, 32), "velocity_scale_q": (0, 10000), "gate_scale_q": (1, 10000), "gain_q": (0, 10000), "pan_q": (-10000, 10000)}
    owners = {
        "section": program["form"],
        "realization": program["realizations"],
        "production": [{"id": key, **value} for key, value in program["production"]["tracks"].items()],
    }
    for scalar in tables["bounded_scalars"]:
        owner_kind, field = scalar["owner_kind"], scalar["field"]
        if field not in bounds or (owner_kind, field) not in {("section", "bars"), ("realization", "velocity_scale_q"), ("realization", "gate_scale_q"), ("production", "gain_q"), ("production", "pan_q")}:
            continue
        for owner in owners[owner_kind]:
            for choice in scalar["choices"]:
                value = choice["value"]
                if value == owner[field] or not bounds[field][0] <= value <= bounds[field][1]:
                    continue
                parameter = {"kind": "replace_bounded_scalar", "owner_kind": owner_kind, "owner_id": owner["id"], "field": field, "value": value, "minimum": bounds[field][0], "maximum": bounds[field][1]}
                rows.append(_row("replace_bounded_scalar", owner_kind, owner["id"], field, parameter, choice["weight"], _roots(parameter, 0)))
    permitted_choices = {entry["value"]: entry["weight"] for entry in tables["distribution_choice_ids"]}
    for choice in choice_catalog.get("entries", []):
        choice_id, owner_kind, field = choice.get("choice_id"), choice.get("owner_kind"), choice.get("field")
        if choice_id not in permitted_choices:
            continue
        if owner_kind == "section" and field in {"role", "development_stage"}:
            targets = program["form"]
        elif owner_kind == "material" and field == "mapping":
            targets = [item for item in program["materials"] if item["kind"] in {"direct_vector_cell", "melody_intent", "harmony_intent_cell"}]
        elif owner_kind == "track" and field == "role":
            targets = program["tracks"]
        elif owner_kind == "production" and field == "profile_id":
            targets = [{"id": "production", **program["production"]}]
        else:
            continue
        for target in targets:
            if target[field] == choice["value"]:
                continue
            parameter = {"kind": "replace_distribution_choice", "owner_kind": owner_kind, "owner_id": target["id"], "field": field, "choice_id": choice_id}
            rows.append(_row("replace_distribution_choice", owner_kind, target["id"], field, parameter, permitted_choices[choice_id], _roots(parameter, 0)))
    for material in program["materials"]:
        if material["kind"] not in {"direct_vector_cell", "harmony_intent_cell"}:
            continue
        for choice in tables["transpose_unit_vectors"]:
            delta = choice["value"]
            vectors = material["vectors"] if material["kind"] == "direct_vector_cell" else material["root_anchors"]
            if any(any(not -32 <= value + offset <= 32 for value, offset in zip(vector, delta, strict=True)) for vector in vectors):
                continue
            parameter = {"kind": "transpose_material_vector", "material_id": material["id"], "vector_delta": delta}
            rows.append(_row("transpose_material_vector", "material", material["id"], "vector_delta", parameter, choice["weight"], _roots(parameter, 0)))
    for material in program["materials"]:
        if material["kind"] != "rhythm_cell":
            continue
        quantum = _rhythm_quantum(material)
        for choice in tables["rotate_ordinal_steps"]:
            if (choice["value"] * quantum) % material["length_ticks"] == 0:
                continue
            parameter = {"kind": "rotate_rhythm", "rhythm_id": material["id"], "steps": choice["value"]}
            rows.append(_row("rotate_rhythm", "rhythm", material["id"], "steps", parameter, choice["weight"], _roots(parameter, 0)))
    for chord in program["chord_intents"]:
        for choice in tables["chord_references"]:
            reference = choice["value"]
            if chord["reference"] == {"temperament": "edo", **reference}:
                continue
            parameter = {"kind": "replace_chord_intent_reference", "chord_intent_id": chord["id"], "reference_equave": reference["equave"], "divisions": reference["divisions"], "steps": reference["steps"]}
            rows.append(_row("replace_chord_intent_reference", "chord_intent", chord["id"], "reference", parameter, choice["weight"], _roots(parameter, 0)))
    for material in program["materials"]:
        if material["kind"] != "harmony_intent_cell":
            continue
        for index, vector in enumerate(material["root_anchors"]):
            for choice in tables["root_anchor_unit_vectors"]:
                candidate = [left + right for left, right in zip(vector, choice["value"], strict=True)]
                if any(not -32 <= value <= 32 for value in candidate):
                    continue
                parameter = {"kind": "replace_root_anchor_item", "material_id": material["id"], "index": index, "vector": candidate}
                rows.append(_row("replace_root_anchor_item", "material", material["id"], index, parameter, choice["weight"], _roots(parameter, 0)))
    for section in program["form"]:
        for choice in tables["edit_actions"]:
            if choice["value"] == "delete":
                if len(program["form"]) == 1:
                    continue
                parameter = {"kind": "edit_section", "action": "delete", "section_id": section["id"], "insert_after_section_id": None}
                rows.append(_row("edit_section", "section", section["id"], "delete", parameter, choice["weight"], _roots(parameter, 0)))
            else:
                for predecessor in program["form"]:
                    parameter = {"kind": "edit_section", "action": "duplicate", "section_id": section["id"], "insert_after_section_id": predecessor["id"]}
                    rows.append(_row("edit_section", "section", section["id"], predecessor["id"], parameter, choice["weight"], _roots(parameter, 0)))
    catalog = {entry.get("instrument_id"): entry for entry in instrument_catalog.get("entries", [])}
    for track in program["tracks"]:
        for choice in tables["instrument_entry_ids"]:
            entry = catalog.get(choice["value"])
            if entry is None or entry["instrument_id"] == track["instrument_id"]:
                continue
            is_drum = track["role"] == "drums"
            if (entry.get("kind") == "drum_kit") != is_drum:
                continue
            if is_drum and any(note not in {item["drum_note"] for item in entry.get("note_map", [])} for note in (track["drum_map"] or {}).values()):
                continue
            parameter = {"kind": "swap_track_catalog_entry", "track_id": track["id"], "instrument_id": entry["instrument_id"]}
            rows.append(_row("swap_track_catalog_entry", "track", track["id"], "instrument_id", parameter, choice["weight"], _roots(parameter, 0)))
    ordinal = {operation: index for index, operation in enumerate(OPERATIONS)}
    return sorted(rows, key=lambda row: (ordinal[row["operation"]], row["owner_kind"].encode(), row["owner_id"].encode(), _canonical(row["field_or_index"]), _canonical(row["parameter"])))


def _select_row(request: dict[str, Any], manifest: dict[str, Any], rows: list[dict[str, Any]],
                attempt: int, ordinal: int, base_hash: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    locked = {(item["kind"], item["id"]) for item in request["locked_roots"]}
    pool = [copy.deepcopy(row) for row in rows if not any((root["kind"], root["id"]) in locked for root in row["actual_roots"])]
    if not pool:
        raise FallbackError("FALLBACK_NO_ELIGIBLE_OPERATION")
    op_weights = {row["operation"]: row["weight"] for row in manifest["operation_table"]}
    trace: list[dict[str, Any]] = []
    selected: dict[str, Any] = {}
    prefix: list[Any] = []
    for stage in ("operation", "owner_kind", "owner_id", "field_or_index", "parameter"):
        values = {_canonical(row[stage]): row[stage] for row in pool}
        table = []
        for key in sorted(values):
            value = values[key]
            if stage == "operation":
                weight = op_weights[value]
            elif stage == "parameter":
                weights = {row["parameter_weight"] for row in pool if row[stage] == value}
                if len(weights) != 1:
                    raise FallbackError("FALLBACK_MANIFEST_MISMATCH")
                weight = weights.pop()
            else:
                weight = 1
            table.append({"value": value, "weight": weight})
        path = [request["run_manifest_hash"], request["action_coordinate"]["round"], request["action_coordinate"]["candidate"], attempt, ordinal, stage, *prefix]
        value = _choose(table, _choice_u64(manifest["stream_domain"], request["root_seed"], path))
        trace.append({"fallback_attempt_ordinal": attempt, "mutation_ordinal": ordinal, "decision_kind": stage, "counter": 0, "path": path,
                      "eligible_table_hash": _artifact_hash("cps.fallback-eligible-table/v1", {"table": table}),
                      "selected_value_hash": _artifact_hash("cps.fallback-selected-value/v1", {"value": value})})
        selected[stage] = value
        prefix.append(value)
        pool = [row for row in pool if row[stage] == value]
    row = pool[0]
    core = {"schema": "cps.mutation", "schema_version": "1.0.0", "base_program_hash": base_hash,
            "operation": selected["operation"], "declared_scope": row["actual_roots"], "parameters": selected["parameter"]}
    return core, trace


def propose_fallback(request: dict[str, Any], *, choice_catalog: dict[str, Any],
                     instrument_catalog: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic typed sequence, without publishing an application.

    The public executor below is the only helper that submits the sequence to
    the mutation applicator.  Keeping proposal and submission split lets the
    search runner persist the typed request at its normal action boundary.
    """
    try:
        manifest, program = request["fallback_manifest"], request["program"]
        _validate_fallback_manifest(manifest, len(program["lattice"]["generators"]))
        if request["requested_mutation_count"] > manifest["maximum_mutations"]:
            raise FallbackError("FALLBACK_REQUEST_INVALID")
        if program_hash(program) != request["program_hash"]:
            raise FallbackError("FALLBACK_PROGRAM_HASH_MISMATCH")
    except (KeyError, TypeError, FallbackError):
        raise
    current = copy.deepcopy(program)
    base_hash = request["program_hash"]
    attempt, mutations, trace, seen = 0, [], [], set()
    while len(mutations) < request["requested_mutation_count"]:
        if attempt >= manifest["maximum_attempts_per_candidate"]:
            raise FallbackError("FALLBACK_ATTEMPTS_EXHAUSTED")
        ordinal = len(mutations)
        rows = enumerate_fallback_rows(current, manifest, choice_catalog, instrument_catalog)
        core, decision_trace = _select_row(request, manifest, rows, attempt, ordinal, base_hash)
        consumed = attempt
        attempt += 1
        duplicate_core = _canonical({key: value for key, value in core.items() if key != "base_program_hash"})
        if duplicate_core in seen:
            trace.extend(decision_trace)
            continue
        core["mutation_id"] = fallback_mutation_id(request["request_hash"], request["action_coordinate"]["round"], request["action_coordinate"]["candidate"], consumed, ordinal, core)
        trace.extend(decision_trace)
        try:
            next_program = _apply_one(current, core, choice_catalog, instrument_catalog, ordinal)
        except (KeyError, IndexError, TypeError, ValueError):
            raise FallbackError("FALLBACK_MUTATION_APPLICATION_FAILED")
        if program_hash(next_program) == base_hash:
            raise FallbackError("FALLBACK_MUTATION_APPLICATION_FAILED")
        seen.add(duplicate_core)
        mutations.append(core)
        current, base_hash = next_program, program_hash(next_program)
    return {"mutations": mutations, "attempts_consumed": attempt, "decision_trace": trace, "final_private_program": current}


def execute_fallback(request: dict[str, Any], application_request: dict[str, Any]) -> dict[str, Any]:
    """Propose and submit exactly one MutationApplicationRequest 1.1 batch."""
    try:
        proposal = propose_fallback(request, choice_catalog=application_request["mutation_choice_catalog"], instrument_catalog=application_request["instrument_catalog"])
    except FallbackError as error:
        result = {"schema": "cps.fallback-result", "schema_version": "1.0.0", "status": "failure", "error": error.code,
                  "attempts_consumed": 0, "partial_candidate": None, "request_hash": request.get("request_hash"),
                  "fallback_manifest_hash": request.get("fallback_manifest_hash"), "base_program_hash": request.get("program_hash"),
                  "action_coordinate": request.get("action_coordinate"), "requested_mutation_count": request.get("requested_mutation_count"),
                  "decision_trace": [], "result_hash": ""}
        result["result_hash"] = _artifact_hash("cps.fallback-result/v1", result, omit="result_hash")
        return {"result": result, "application": None}
    batch = copy.deepcopy(application_request)
    batch["base_program"] = copy.deepcopy(request["program"])
    batch["base_program_hash"] = request["program_hash"]
    batch["locked_roots"] = copy.deepcopy(request["locked_roots"])
    batch["mutations"] = proposal["mutations"]
    batch["request_hash"] = _artifact_hash("cps.mutation-application-request/v1", batch, omit="request_hash")
    applied = apply_mutation_request(batch)
    if applied["status"] != "success":
        result = {"schema": "cps.fallback-result", "schema_version": "1.0.0", "status": "failure", "error": "FALLBACK_MUTATION_APPLICATION_FAILED",
                  "attempts_consumed": proposal["attempts_consumed"], "partial_candidate": None, "request_hash": request["request_hash"],
                  "fallback_manifest_hash": request["fallback_manifest_hash"], "base_program_hash": request["program_hash"],
                  "action_coordinate": request["action_coordinate"], "requested_mutation_count": request["requested_mutation_count"],
                  "decision_trace": proposal["decision_trace"], "result_hash": ""}
        result["result_hash"] = _artifact_hash("cps.fallback-result/v1", result, omit="result_hash")
        return {"result": result, "application": applied}
    result = {"schema": "cps.fallback-result", "schema_version": "1.0.0", "status": "success", "mutations": proposal["mutations"],
              "application_receipt_hash": applied["receipt"]["receipt_hash"], "final_program_hash": program_hash(applied["program"]),
              "attempts_consumed": proposal["attempts_consumed"], "decision_trace": proposal["decision_trace"],
              "request_hash": request["request_hash"], "fallback_manifest_hash": request["fallback_manifest_hash"],
              "base_program_hash": request["program_hash"], "action_coordinate": request["action_coordinate"],
              "requested_mutation_count": request["requested_mutation_count"], "result_hash": ""}
    result["result_hash"] = _artifact_hash("cps.fallback-result/v1", result, omit="result_hash")
    return {"result": result, "application": applied}


def _ratio_millicents(value: Fraction) -> int:
    """The NumericContract's round-half-even logarithmic conversion."""
    from decimal import Decimal, ROUND_HALF_EVEN, localcontext

    if value <= 0:
        raise FallbackError("SAMPLER_PRODUCTION_VALUE_INVALID")
    with localcontext() as context:
        context.prec = 80
        cents = Decimal(1200000) * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln()) / Decimal(2).ln()
        return int(cents.to_integral_value(rounding=ROUND_HALF_EVEN))


def register_endpoint_millicents(frequency_millihz: int, base_frequency_millihz: int) -> int:
    if not isinstance(frequency_millihz, int) or not isinstance(base_frequency_millihz, int) or frequency_millihz <= 0 or base_frequency_millihz <= 0:
        raise FallbackError("SAMPLER_PRODUCTION_VALUE_INVALID")
    return _ratio_millicents(Fraction(frequency_millihz, base_frequency_millihz))


def _production_draw(table: list[dict[str, Any]], request: dict[str, Any], manifest: dict[str, Any],
                     role: str, field: str, trace: list[dict[str, Any]]) -> Any:
    rejection = request["production_rejection_ordinal"]
    path = [manifest["sampler_manifest_hash"], rejection, "production", role, field]
    value = _choose(table, _choice_u64(manifest["stream_domain"], request["root_seed"], path))
    trace.append({"production_rejection_ordinal": rejection, "role": role, "field": field, "counter": 0,
                  "draw_u64": _choice_u64(manifest["stream_domain"], request["root_seed"], path),
                  "eligible_table_hash": _artifact_hash("cps.fallback-eligible-table/v1", {"table": table}),
                  "selected_value_hash": _artifact_hash("cps.fallback-selected-value/v1", {"value": value})})
    return value


def _lower_broad_prior_choices(request: dict[str, Any], manifest: dict[str, Any], catalog: dict[str, Any],
                               trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve broad-prior role choices without altering a SongProgram."""
    if request.get("sampler_manifest_hash") != manifest.get("sampler_manifest_hash"):
        raise FallbackError("SAMPLER_PRODUCTION_MANIFEST_INVALID")
    if request.get("instrument_catalog_digest") != manifest.get("instrument_catalog_digest"):
        raise FallbackError("SAMPLER_CATALOG_MISMATCH")
    active = request.get("active_roles")
    if active != [role for role in ROLES if role in active]:
        raise FallbackError("SAMPLER_ACTIVE_ROLE_INVALID")
    index = {item.get("instrument_id"): item for item in catalog.get("entries", [])}
    profile = _production_draw(manifest["profile_ids"], request, manifest, "global", "profile", trace)
    decisions = []
    for role in active:
        instrument_id = _production_draw(manifest["instrument_entries_by_role"][role], request, manifest, role, "instrument", trace)
        instrument = index.get(instrument_id)
        # Full catalog instances carry ``kind``.  The frozen semantic fixture
        # predates that field, so absence is a fixture-level shorthand only.
        if instrument is None or instrument.get("role") != role or ("kind" in instrument and (instrument["kind"] == "drum_kit") != (role == "drums")):
            raise FallbackError("SAMPLER_NO_COMPATIBLE_INSTRUMENT")
        register = None
        if role != "drums":
            register = _production_draw(manifest["register_presets_by_role"][role], request, manifest, role, "register", trace)
            try:
                endpoints = [register_endpoint_millicents(value, request["program"]["lattice"]["base_frequency_millihz"]) for value in instrument["allowed_frequency_millihz"]]
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                raise FallbackError("SAMPLER_PRODUCTION_VALUE_INVALID") from exc
            if len(endpoints) != 2 or not endpoints[0] <= register[0] <= register[1] <= endpoints[1]:
                raise FallbackError("SAMPLER_NO_COMPATIBLE_REGISTER")
        polyphony = _production_draw(manifest["polyphony_by_role"][role], request, manifest, role, "maximum_polyphony", trace)
        if not isinstance(polyphony, int) or not 1 <= polyphony <= instrument.get("maximum_polyphony", 0):
            raise FallbackError("SAMPLER_NO_COMPATIBLE_POLYPHONY")
        drum = None
        if role == "drums":
            drum = _production_draw(manifest["drum_map_profiles"], request, manifest, role, "drum_map", trace)
            notes = {item["drum_note"] for item in instrument.get("note_map", [])}
            if not isinstance(drum, dict) or ("note_map" in instrument and not set(drum.get("drum_map", {}).values()) <= notes):
                raise FallbackError("SAMPLER_DRUM_MAP_INVALID")
        gain = _production_draw(manifest["gain_q_by_role"][role], request, manifest, role, "gain_q", trace)
        pan = _production_draw(manifest["pan_q_by_role"][role], request, manifest, role, "pan_q", trace)
        decisions.append({"role": role, "instrument_id": instrument_id, "register_millicents": register, "maximum_polyphony": polyphony,
                          "drum_map": drum, "gain_q": gain, "pan_q": pan})
    return {"profile": profile, "role_decisions": decisions, "decision_trace": trace}


def lower_broad_prior_choices(request: dict[str, Any], manifest: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Resolve one complete assignment and retain its trace on rejection."""
    trace: list[dict[str, Any]] = []
    try:
        return _lower_broad_prior_choices(request, manifest, catalog, trace)
    except FallbackError as error:
        error.decision_trace = trace
        raise


def apply_broad_prior_production(program: dict[str, Any], choices: dict[str, Any], *, catalog_digest: str,
                                 active_roles: list[str]) -> dict[str, Any]:
    """Lower resolved choices into pre-existing role track shells only."""
    active = [role for role in ROLES if role in active_roles]
    if active != active_roles:
        raise FallbackError("SAMPLER_ACTIVE_ROLE_INVALID")
    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    for track in program.get("tracks", []):
        by_role.setdefault(track.get("role"), []).append(track)
    if any(len(by_role[role]) != (1 if role in active else 0) for role in ROLES):
        raise FallbackError("SAMPLER_RESULT_INVALID")
    decisions = {item["role"]: item for item in choices["role_decisions"]}
    if set(decisions) != set(active):
        raise FallbackError("SAMPLER_RESULT_INVALID")
    result = copy.deepcopy(program)
    tracks = {track["role"]: track for track in result["tracks"]}
    mix: dict[str, dict[str, int]] = {}
    for role in active:
        decision, track = decisions[role], tracks[role]
        track.update({"instrument_id": decision["instrument_id"], "register_millicents": decision["register_millicents"], "maximum_polyphony": decision["maximum_polyphony"],
                      "drum_map": None if decision["drum_map"] is None else copy.deepcopy(decision["drum_map"]["drum_map"])})
        mix[track["id"]] = {"gain_q": decision["gain_q"], "pan_q": decision["pan_q"]}
    result["production"] = {"profile_id": choices["profile"]["profile_id"], "catalog_digest": catalog_digest, "tracks": mix, "envelopes": []}
    return result


def _public_production_trace(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    trace = []
    for row in rows:
        path = [manifest["sampler_manifest_hash"], row["production_rejection_ordinal"], "production", row["role"], row["field"]]
        trace.append({"production_rejection_ordinal": row["production_rejection_ordinal"], "role": row["role"], "field": row["field"], "counter": 0,
                      "path_hash": _artifact_hash("cps.choice-path/v1", {"path": path}),
                      "eligible_table_hash": row["eligible_table_hash"], "selected_value_hash": row["selected_value_hash"]})
    return trace


def _production_failure(request: dict[str, Any], manifest: dict[str, Any], code: str,
                        rejections: int, trace: list[dict[str, Any]]) -> dict[str, Any]:
    result = {"schema": "cps.broad-prior-production-result", "schema_version": "1.0.0", "status": "failure",
              "request_hash": request.get("request_hash"), "lowering_manifest_hash": request.get("lowering_manifest_hash"),
              "structural_program_hash": request.get("structural_program_hash"), "rejections_consumed": rejections,
              "role_decisions": [], "decision_trace": _public_production_trace(trace, manifest), "output": None,
              "error": code, "result_hash": ""}
    result["result_hash"] = _artifact_hash("cps.production-lowering-result/v1", result, omit="result_hash")
    return result


def execute_broad_prior_production(request: dict[str, Any], manifest: dict[str, Any],
                                   catalog: dict[str, Any]) -> dict[str, Any]:
    """Lower one broad-prior assignment into a schema-shaped result envelope.

    The structural sampler owns the existing track shells.  This lowering is
    deliberately incapable of adding tracks, rebinding realizations, creating
    events, or introducing automation.
    """
    start = request.get("production_rejection_ordinal")
    if not isinstance(start, int) or isinstance(start, bool) or not 0 <= start <= U64_MAX:
        return _production_failure(request, manifest, "SAMPLER_RESULT_INVALID", 0, [])
    try:
        if request.get("lowering_manifest_hash") != _artifact_hash("cps.production-lowering-manifest/v1", manifest):
            raise FallbackError("SAMPLER_PRODUCTION_MANIFEST_INVALID")
        catalog_digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)).hexdigest()
        if request.get("instrument_catalog_digest") != catalog_digest:
            raise FallbackError("SAMPLER_CATALOG_MISMATCH")
        # These are request/manifest errors, not completed assignments.  They
        # therefore have precedence and never consume a rejection ordinal.
        if request.get("sampler_manifest_hash") != manifest.get("sampler_manifest_hash"):
            raise FallbackError("SAMPLER_PRODUCTION_MANIFEST_INVALID")
        active = request.get("active_roles")
        if active != [role for role in ROLES if role in active]:
            raise FallbackError("SAMPLER_ACTIVE_ROLE_INVALID")
        if request.get("structural_program_hash") != program_hash(request["program"]):
            raise FallbackError("SAMPLER_RESULT_INVALID")
        ceiling = manifest["maximum_production_rejections"]
        if not isinstance(ceiling, int) or not 1 <= ceiling <= 256:
            raise FallbackError("SAMPLER_PRODUCTION_MANIFEST_INVALID")
    except FallbackError as error:
        return _production_failure(request, manifest, error.code, 0, [])
    except (KeyError, TypeError, ValueError):
        return _production_failure(request, manifest, "SAMPLER_PRODUCTION_MANIFEST_INVALID", 0, [])
    rejected_trace: list[dict[str, Any]] = []
    last_error = "SAMPLER_RESULT_INVALID"
    for rejection in range(start, ceiling):
        trial = copy.deepcopy(request)
        trial["production_rejection_ordinal"] = rejection
        try:
            choices = lower_broad_prior_choices(trial, manifest, catalog)
            output_program = apply_broad_prior_production(
                request["program"], choices, catalog_digest=catalog_digest, active_roles=request["active_roles"],
            )
        except FallbackError as error:
            rejected_trace.extend(error.decision_trace)
            last_error = error.code
            continue
        trace = _public_production_trace([*rejected_trace, *choices["decision_trace"]], manifest)
        break
    else:
        # The contract deliberately assigns no separate exhaustion code: the
        # first failing complete assignment remains the typed seed failure.
        return _production_failure(request, manifest, last_error, ceiling, rejected_trace)
    decisions = []
    for decision in choices["role_decisions"]:
        drum = decision["drum_map"]
        decisions.append({"role": decision["role"], "instrument_id": decision["instrument_id"], "register_millicents": decision["register_millicents"],
                          "maximum_polyphony": decision["maximum_polyphony"], "drum_map_id": None if drum is None else drum["drum_map_id"],
                          "drum_map": None if drum is None else drum["drum_map"], "drum_map_payload_hash": None if drum is None else drum["drum_map_payload_hash"],
                          "gain_q": decision["gain_q"], "pan_q": decision["pan_q"]})
    output = {"profile_id": choices["profile"]["profile_id"], "profile_payload_hash": choices["profile"]["profile_payload_hash"],
              "catalog_digest": catalog_digest, "program": output_program, "program_hash": program_hash(output_program)}
    result = {"schema": "cps.broad-prior-production-result", "schema_version": "1.0.0", "status": "success",
              "request_hash": request["request_hash"], "lowering_manifest_hash": request["lowering_manifest_hash"],
              "structural_program_hash": request["structural_program_hash"], "rejections_consumed": rejection,
              "role_decisions": decisions, "decision_trace": trace, "output": output, "error": None, "result_hash": ""}
    result["result_hash"] = _artifact_hash("cps.production-lowering-result/v1", result, omit="result_hash")
    return result
