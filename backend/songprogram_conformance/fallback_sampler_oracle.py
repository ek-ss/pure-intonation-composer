"""Independent oracle for fallback and broad-prior production decisions.

This module intentionally imports only the Python standard library and the
conformance canonical encoder.  In particular it never imports ``app.*``.
"""
from __future__ import annotations

import hashlib
import base64
from copy import deepcopy
from fractions import Fraction
from typing import Any

from .canonical import canonical_bytes
from .reference import ratio_mc

U64_MAX = (1 << 64) - 1
ROLES = ("drums", "bass", "harmony", "melody", "texture")
FIELDS = ("instrument", "register", "maximum_polyphony", "drum_map", "gain_q", "pan_q")


class SemanticError(ValueError):
    pass


def artifact_hash(domain: str, value: dict[str, Any], hash_field: str | None = None) -> str:
    core = {k: v for k, v in value.items() if k != hash_field}
    digest = hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(core) + b"\n").hexdigest()
    return "sha256:" + digest


def choice_u64(domain: str, root_seed: int, path: list[Any]) -> int:
    if not 0 <= root_seed <= U64_MAX:
        raise SemanticError("seed outside u64")
    raw = domain.encode() + b"\0" + root_seed.to_bytes(8, "big") + canonical_bytes(path)
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def validate_table(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not table:
        raise SemanticError("empty weighted table")
    ordered = sorted(table, key=lambda row: canonical_bytes(row["value"]))
    if table != ordered:
        raise SemanticError("table not in canonical value order")
    seen: set[bytes] = set()
    total = 0
    for row in table:
        key = canonical_bytes(row["value"])
        if key in seen:
            raise SemanticError("duplicate table value")
        seen.add(key)
        weight = row.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= U64_MAX:
            raise SemanticError("weight outside positive u64")
        total += weight
        if total > U64_MAX:
            raise SemanticError("weight sum overflow")
    return ordered


def weighted_choice(table: list[dict[str, Any]], draw: int) -> Any:
    rows = validate_table(table)
    total = sum(row["weight"] for row in rows)
    cursor = draw % total
    upper = 0
    for row in rows:
        upper += row["weight"]
        if cursor < upper:
            return deepcopy(row["value"])
    raise AssertionError("unreachable")


def _choose_presorted(table: list[dict[str, Any]], draw: int) -> Any:
    total = sum(row["weight"] for row in table)
    cursor, upper = draw % total, 0
    for row in table:
        upper += row["weight"]
        if cursor < upper:
            return deepcopy(row["value"])
    raise AssertionError("unreachable")


def fallback_mutation_id(request_hash: str, round_: int, candidate: int, attempt: int,
                         ordinal: int, core: dict[str, Any]) -> str:
    raw = (b"cps.fallback-mutation-id/v1\0" + request_hash.encode() +
           round_.to_bytes(8, "big") + candidate.to_bytes(8, "big") +
           attempt.to_bytes(8, "big") + ordinal.to_bytes(4, "big") + canonical_bytes(core) + b"\n")
    return "mut_" + base64.b32encode(hashlib.sha256(raw).digest()).decode().lower().rstrip("=")[:20]


def select_fallback(request: dict[str, Any], manifest: dict[str, Any],
                    eligible_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve authoritative hierarchical choices from independently enumerated rows.

    Each row contains operation/owner_kind/owner_id/field_or_index/parameter,
    parameter_weight, actual_roots, and optional identity. Eligibility enumeration
    remains independently testable from selection.
    """
    d = len(request["program"]["lattice"]["generators"])
    validate_fallback_manifest(manifest, d)
    locks = {(x["kind"], x["id"]) for x in request["locked_roots"]}
    rows = [deepcopy(r) for r in eligible_rows if not any((x["kind"], x["id"]) in locks for x in r["actual_roots"])]
    op_weights = {x["operation"]: x["weight"] for x in manifest["operation_table"]}
    attempt = 0; emitted=[]; trace=[]; seen=set()
    for ordinal in range(request["requested_mutation_count"]):
        while attempt < manifest["maximum_attempts_per_candidate"]:
            pool = rows
            if not pool: raise SemanticError("FALLBACK_NO_ELIGIBLE_OPERATION")
            prefix=[]; selected={}
            stages=("operation","owner_kind","owner_id","field_or_index","parameter")
            for stage in stages:
                values={canonical_bytes(r[stage]):r[stage] for r in pool}
                ordered=[values[k] for k in sorted(values)]
                table=[]
                for value in ordered:
                    if stage=="operation": weight=op_weights[value]
                    elif stage=="parameter":
                        weights={r["parameter_weight"] for r in pool if r[stage]==value}
                        if len(weights)!=1: raise SemanticError("ambiguous parameter weight")
                        weight=weights.pop()
                    else: weight=1
                    table.append({"value":value,"weight":weight})
                path=[request["run_manifest_hash"],request["action_coordinate"]["round"],request["action_coordinate"]["candidate"],attempt,ordinal,stage,*prefix]
                draw=choice_u64(manifest["stream_domain"],request["root_seed"],path)
                value=_choose_presorted(table,draw)
                trace.append({"fallback_attempt_ordinal":attempt,"mutation_ordinal":ordinal,"decision_kind":stage,"counter":0,"path":path,"eligible_table_hash":artifact_hash("cps.fallback-eligible-table/v1",{"table":table}),"selected_value_hash":artifact_hash("cps.fallback-selected-value/v1",{"value":value})})
                selected[stage]=value; prefix.append(value); pool=[r for r in pool if r[stage]==value]
            row=pool[0]
            core={"schema":"cps.mutation","schema_version":"1.0.0","base_program_hash":request["program_hash"],"operation":selected["operation"],"declared_scope":row["actual_roots"],"parameters":selected["parameter"]}
            duplicate_core={k:v for k,v in core.items() if k!="base_program_hash"}
            duplicate_key=canonical_bytes(duplicate_core)
            consumed=attempt; attempt+=1
            if row.get("identity",False) or duplicate_key in seen: continue
            core["mutation_id"]=fallback_mutation_id(request["request_hash"],request["action_coordinate"]["round"],request["action_coordinate"]["candidate"],consumed,ordinal,core)
            seen.add(duplicate_key); emitted.append(core); break
        else: raise SemanticError("FALLBACK_ATTEMPTS_EXHAUSTED")
    return {"mutations":emitted,"attempts_consumed":attempt,"decision_trace":trace}


def register_endpoint_mc(frequency_millihz: int, base_frequency_millihz: int) -> int:
    if frequency_millihz <= 0 or base_frequency_millihz <= 0:
        raise SemanticError("SAMPLER_PRODUCTION_VALUE_INVALID")
    try: return ratio_mc(Fraction(frequency_millihz, base_frequency_millihz))
    except (ArithmeticError, ValueError, OverflowError) as exc:
        raise SemanticError("SAMPLER_PRODUCTION_VALUE_INVALID") from exc


def validate_unit_vector(value: list[int], dimension: int) -> None:
    if len(value) != dimension or sum(component != 0 for component in value) != 1:
        raise SemanticError("not a signed unit vector")
    if any(component not in (-1, 0, 1) for component in value):
        raise SemanticError("not a signed unit vector")


def validate_fallback_manifest(manifest: dict[str, Any], dimension: int) -> None:
    expected_ops = [
        "replace_bounded_scalar", "replace_distribution_choice",
        "transpose_material_vector", "rotate_rhythm",
        "replace_chord_intent_reference", "replace_root_anchor_item",
        "edit_section", "swap_track_catalog_entry",
    ]
    if [x.get("operation") for x in manifest["operation_table"]] != expected_ops:
        raise SemanticError("operation order/content mismatch")
    operation_total = 0
    for row in manifest["operation_table"]:
        weight = row.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= U64_MAX:
            raise SemanticError("weight outside positive u64")
        operation_total += weight
        if operation_total > U64_MAX:
            raise SemanticError("weight sum overflow")
    tables = manifest["parameter_tables"]
    for name, table in tables.items():
        if name == "bounded_scalars":
            for scalar in table:
                validate_table(scalar["choices"])
        elif name == "rotate_ordinal_steps":
            if any(not isinstance(row.get("weight"), int) or not 1 <= row["weight"] <= U64_MAX for row in table):
                raise SemanticError("weight outside positive u64")
            if sum(row["weight"] for row in table) > U64_MAX:
                raise SemanticError("weight sum overflow")
        else:
            validate_table(table)
    for name in ("transpose_unit_vectors", "root_anchor_unit_vectors"):
        for row in tables[name]:
            validate_unit_vector(row["value"], dimension)
    rotations = [row["value"] for row in tables["rotate_ordinal_steps"]]
    if rotations != [-4, -3, -2, -1, 1, 2, 3, 4]:
        raise SemanticError("rotation ordinal table mismatch")
    for row in tables["chord_references"]:
        chord = row["value"]
        if chord["steps"] != sorted(set(chord["steps"])) or any(s >= chord["divisions"] for s in chord["steps"]):
            raise SemanticError("noncanonical chord steps")


def lower_production(request: dict[str, Any], manifest: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if request["sampler_manifest_hash"] != manifest["sampler_manifest_hash"]:
        raise SemanticError("SAMPLER_PRODUCTION_MANIFEST_INVALID")
    if request["instrument_catalog_digest"] != manifest["instrument_catalog_digest"]:
        raise SemanticError("SAMPLER_CATALOG_MISMATCH")
    active = request["active_roles"]
    if active != [role for role in ROLES if role in active]:
        raise SemanticError("SAMPLER_ACTIVE_ROLE_INVALID")
    index = {item["instrument_id"]: item for item in catalog["entries"]}
    rejection = request["production_rejection_ordinal"]
    seed = request["root_seed"]
    trace: list[dict[str, Any]] = []
    profile = _draw(manifest["profile_ids"], seed, manifest, rejection, "global", "profile", trace)
    decisions = []
    for role in active:
        instrument_id = _draw(manifest["instrument_entries_by_role"][role], seed, manifest, rejection, role, "instrument", trace)
        instrument = index.get(instrument_id)
        if instrument is None or instrument["role"] != role:
            raise SemanticError("SAMPLER_NO_COMPATIBLE_INSTRUMENT")
        register = None
        if role != "drums":
            register = _draw(manifest["register_presets_by_role"][role], seed, manifest, rejection, role, "register", trace)
            if "allowed_frequency_millihz" in instrument:
                base = request["program"]["lattice"]["base_frequency_millihz"]
                allowed = [register_endpoint_mc(x, base) for x in instrument["allowed_frequency_millihz"]]
            else:  # retained only for legacy semantic fixtures
                allowed = instrument["allowed_register_millicents"]
            if not (allowed[0] <= register[0] <= register[1] <= allowed[1]):
                raise SemanticError("SAMPLER_NO_COMPATIBLE_REGISTER")
        poly = _draw(manifest["polyphony_by_role"][role], seed, manifest, rejection, role, "maximum_polyphony", trace)
        if not 1 <= poly <= instrument["maximum_polyphony"]:
            raise SemanticError("SAMPLER_NO_COMPATIBLE_POLYPHONY")
        drum = None
        if role == "drums":
            drum = _draw(manifest["drum_map_profiles"], seed, manifest, rejection, role, "drum_map", trace)
        gain = _draw(manifest["gain_q_by_role"][role], seed, manifest, rejection, role, "gain_q", trace)
        pan = _draw(manifest["pan_q_by_role"][role], seed, manifest, rejection, role, "pan_q", trace)
        decisions.append({"role": role, "instrument_id": instrument_id, "register_millicents": register,
                          "maximum_polyphony": poly, "drum_map": drum, "gain_q": gain, "pan_q": pan})
    return {"profile": profile, "role_decisions": decisions, "decision_trace": trace}


def _draw(table: list[dict[str, Any]], seed: int, manifest: dict[str, Any], rejection: int,
          role: str, field: str, trace: list[dict[str, Any]]) -> Any:
    path = [manifest["sampler_manifest_hash"], rejection, "production", role, field]
    draw = choice_u64(manifest["stream_domain"], seed, path)
    value = weighted_choice(table, draw)
    trace.append({"production_rejection_ordinal": rejection, "role": role, "field": field,
                  "counter": 0, "draw_u64": draw,
                  "eligible_table_hash": artifact_hash("cps.fallback-eligible-table/v1", {"table": table}),
                  "selected_value_hash": artifact_hash("cps.fallback-selected-value/v1", {"value": value})})
    return value
