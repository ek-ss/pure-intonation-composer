"""Deterministic Structural Sampler v1.1.

This is intentionally a manifest-driven producer.  It has no ambient random
source, fixture lookup, or production-lowering dependency: it creates only the
structural predecessor owned by ``broad-prior-v1.1``.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from .search import canonical_bytes


U64_MAX = (1 << 64) - 1
ROLES = ("drums", "bass", "harmony", "melody", "texture")
_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
_KINDS = ("rhythm", "direct_vector", "harmony_intent", "melody_intent")
_COMPATIBLE = {
    "rhythm": ("drums",),
    "direct_vector": ("bass", "texture"),
    "harmony_intent": ("harmony", "texture"),
    "melody_intent": ("melody", "texture"),
}


class StructuralSamplerError(ValueError):
    """Stable envelope error before an attempt is started."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _AttemptFailure(Exception):
    code: str
    pointers: list[str]
    actual: Any = None
    expected: Any = None
    candidate: bool = False


def _hash(domain: str, value: Any, *, omit: str | None = None) -> str:
    if omit is not None:
        if not isinstance(value, dict):
            raise StructuralSamplerError("SAMPLER_REQUEST_INVALID")
        value = {key: item for key, item in value.items() if key != omit}
    return (
        "sha256:"
        + hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_bytes(value)).hexdigest()
    )


def structural_program_hash(program: Mapping[str, Any]) -> str:
    return _hash("cps.structural-song-program/1.0", dict(program))


def structural_rejection_evidence_hash(evidence: Mapping[str, Any]) -> str:
    return _hash("cps.structural-rejection-evidence/v1", dict(evidence), omit="evidence_hash")


def structural_lowering_manifest_hash(manifest: Mapping[str, Any]) -> str:
    return _hash("cps.structural-lowering-manifest/v1", dict(manifest), omit="manifest_hash")


def _raw_sha(value: Any) -> bytes:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise StructuralSamplerError("SAMPLER_REQUEST_INVALID")
    return bytes.fromhex(value[7:])


def _u64(value: Any, *, code: str = "SAMPLER_REQUEST_INVALID") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= U64_MAX:
        raise StructuralSamplerError(code)
    return value


def _b32(raw: bytes, length: int) -> str:
    return base64.b32encode(raw).decode("ascii").lower().rstrip("=")[:length]


def _attempt_seed(request: Mapping[str, Any], ordinal: int) -> str:
    payload = (
        b"cps.structural-sampler-attempt-seed/v1\0"
        + _u64(request["root_seed"]).to_bytes(8, "big")
        + _u64(request["cohort_index"]).to_bytes(8, "big")
        + _u64(ordinal).to_bytes(8, "big")
        + _raw_sha(request["sampler_manifest_hash"])
    )
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _path_bytes(path: list[Any]) -> bytes:
    result = bytearray()
    for segment in path:
        if isinstance(segment, int) and not isinstance(segment, bool):
            if not 0 <= segment <= U64_MAX:
                raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", [""])
            result += b"\x00" + segment.to_bytes(8, "big")
        elif isinstance(segment, str) and unicodedata.normalize("NFC", segment) == segment:
            raw = segment.encode("utf-8")
            if len(raw) > 0xFFFFFFFF:
                raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", [""])
            result += b"\x01" + len(raw).to_bytes(4, "big") + raw
        else:
            raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", [""])
    return bytes(result)


def _draw(attempt_seed_hash: str, path: list[Any]) -> int:
    key = hashlib.sha256(
        b"cps.broad-prior/stream/v1.1\0" + _raw_sha(attempt_seed_hash) + _path_bytes(path)
    ).digest()
    return int.from_bytes(hashlib.sha256(key + (0).to_bytes(8, "big")).digest()[:8], "big")


def _choice_rows(table: Any, pointer: str) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(table, list):
        raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", [pointer])
    rows: list[dict[str, Any]] = []
    values: set[str] = set()
    total = 0
    for index, source in enumerate(table):
        if not isinstance(source, dict) or set(source) != {"value", "weight"}:
            raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", [f"{pointer}/{index}"])
        try:
            value_hash = _hash("cps.sampler-choice-value/v1.1", source["value"])
        except Exception:
            raise _AttemptFailure(
                "SAMPLER_DECISION_PROGRAM_INVALID", [f"{pointer}/{index}/value"]
            ) from None
        if value_hash in values:
            raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", [f"{pointer}/{index}/value"])
        values.add(value_hash)
        weight = source["weight"]
        if not isinstance(weight, int) or isinstance(weight, bool) or not 0 <= weight <= U64_MAX:
            raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", [f"{pointer}/{index}/weight"])
        if weight:
            if total > U64_MAX - weight:
                raise _AttemptFailure(
                    "SAMPLER_WEIGHT_SUM_OVERFLOW", [pointer], total + weight, U64_MAX
                )
            total += weight
            rows.append(
                {
                    "index": index,
                    "choice_id": "choice_" + _b32(bytes.fromhex(value_hash[7:]), 26),
                    "value_hash": value_hash,
                    "weight": weight,
                    "_value": copy.deepcopy(source["value"]),
                }
            )
    if not rows:
        raise _AttemptFailure("SAMPLER_TABLE_EMPTY", [pointer])
    return rows, total


def _trace_choice(
    ordinal: int, path: list[Any], table: Any, pointer: str, attempt_seed_hash: str
) -> tuple[Any, dict[str, Any]]:
    rows, total = _choice_rows(table, pointer)
    public = [
        {key: row[key] for key in ("index", "choice_id", "value_hash", "weight")} for row in rows
    ]
    table_hash = _hash("cps.structural-sampler-table/v1", public)
    point = _draw(attempt_seed_hash, path) % total
    cursor = 0
    selected = rows[-1]
    for row in rows:
        cursor += row["weight"]
        if point < cursor:
            selected = row
            break
    result = {
        "decision_ordinal": ordinal,
        "path": copy.deepcopy(path),
        "counter": 0,
        "table": public,
        "table_hash": table_hash,
        "selected_index": selected["index"],
        "selected_value_hash": selected["value_hash"],
        "row_hash": "",
    }
    result["row_hash"] = _hash("cps.structural-sampler-decision/v1", result, omit="row_hash")
    return selected["_value"], result


def _failure(
    ordinal: int, code: str, pointers: list[str], actual: Any, expected: Any
) -> dict[str, Any]:
    evidence = {
        "schema": "cps.structural-rejection-evidence",
        "schema_version": "1.1.0",
        "attempt_ordinal": ordinal,
        "code": code,
        "constraint_id": code.lower(),
        "pointers": sorted(set(pointers), key=lambda value: value.encode("utf-8")),
        "actual": actual,
        "expected": expected,
        "evidence_hash": "",
    }
    evidence["evidence_hash"] = structural_rejection_evidence_hash(evidence)
    return evidence


def _request_valid(request: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "run_hash",
        "context_hash",
        "source_decision_hash",
        "sampler_manifest_hash",
        "structural_lowering_manifest_hash",
        "structural_program_schema_hash",
        "structural_rejection_evidence_schema_hash",
        "root_seed",
        "cohort_index",
        "request_hash",
    }
    if not isinstance(request, Mapping) or set(request) != required:
        raise StructuralSamplerError("SAMPLER_REQUEST_INVALID")
    if (
        request.get("schema") != "cps.structural-sampler-request"
        or request.get("schema_version") != "1.1.0"
    ):
        raise StructuralSamplerError("SAMPLER_REQUEST_INVALID")
    for name in (
        "run_hash",
        "context_hash",
        "source_decision_hash",
        "sampler_manifest_hash",
        "structural_lowering_manifest_hash",
        "structural_program_schema_hash",
        "structural_rejection_evidence_schema_hash",
        "request_hash",
    ):
        _raw_sha(request[name])
    _u64(request["root_seed"])
    _u64(request["cohort_index"])
    if request["request_hash"] != _hash(
        "cps.structural-sampler-request/v1.1", dict(request), omit="request_hash"
    ):
        raise StructuralSamplerError("SAMPLER_REQUEST_INVALID")


def validate_structural_lowering_manifest(manifest: Mapping[str, Any], binding: str) -> None:
    """Check the sealed lowering identity and every field used by the builder."""
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "structural_program_schema_hash",
        "id_policy",
        "clock",
        "lattice_constants",
        "section_templates",
        "material_builders",
        "chord_constants",
        "realization_constants",
        "rhythm_position_policy",
        "compile_policy",
        "limits",
        "manifest_hash",
    }
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != required
        or manifest.get("schema") != "cps.structural-lowering-manifest"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("algorithm") != "structural-song-program-lowering/v1"
    ):
        raise StructuralSamplerError("SAMPLER_LOWERING_MANIFEST_MISMATCH")
    if (
        manifest.get("manifest_hash") != binding
        or structural_lowering_manifest_hash(manifest) != binding
    ):
        raise StructuralSamplerError("SAMPLER_LOWERING_MANIFEST_MISMATCH")
    ids = manifest.get("id_policy")
    if (
        not isinstance(ids, Mapping)
        or any(
            not isinstance(ids.get(name), str) or not ids[name]
            for name in (
                "program_prefix",
                "section_prefix",
                "material_prefix",
                "rhythm_prefix",
                "chord_prefix",
                "realization_prefix",
            )
        )
        or not isinstance(ids.get("ordinal_width"), int)
    ):
        raise StructuralSamplerError("SAMPLER_LOWERING_MANIFEST_MISMATCH")
    if manifest.get("rhythm_position_policy") != "ascending-even-grid-prefix/v1":
        raise StructuralSamplerError("SAMPLER_LOWERING_MANIFEST_MISMATCH")


def _validate_sampler_binding(
    request: Mapping[str, Any], sampler: Mapping[str, Any], lowering: Mapping[str, Any]
) -> None:
    if (
        not isinstance(sampler, Mapping)
        or sampler.get("schema") != "cps.sampler-manifest"
        or sampler.get("schema_version") != "1.1.0"
        or sampler.get("algorithm") != "broad-prior-v1.1"
        or sampler.get("choice_algorithm") != "sha256-u64-mod-cumulative/v1.1"
        or sampler.get("stream_algorithm") != "path-addressed-sha256-attempt/v1.1"
    ):
        raise StructuralSamplerError("SAMPLER_MANIFEST_MISMATCH")
    if sampler.get("manifest_hash") != request["sampler_manifest_hash"]:
        raise StructuralSamplerError("SAMPLER_MANIFEST_MISMATCH")
    if (
        sampler.get("structural_lowering_manifest_hash")
        != request["structural_lowering_manifest_hash"]
        or sampler.get("structural_program_schema_hash")
        != request["structural_program_schema_hash"]
        or sampler.get("structural_rejection_evidence_schema_hash")
        != request["structural_rejection_evidence_schema_hash"]
    ):
        raise StructuralSamplerError("SAMPLER_MANIFEST_MISMATCH")
    validate_structural_lowering_manifest(lowering, request["structural_lowering_manifest_hash"])
    if lowering.get("structural_program_schema_hash") != request["structural_program_schema_hash"]:
        raise StructuralSamplerError("SAMPLER_LOWERING_MANIFEST_MISMATCH")


def _decision_program(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    program, tables = manifest.get("decision_program"), manifest.get("tables")
    if not isinstance(program, list) or not isinstance(tables, Mapping):
        raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", ["/decision_program"])
    ordered: list[dict[str, Any]] = []
    for expected, decision in enumerate(program):
        if (
            not isinstance(decision, dict)
            or set(decision) != {"ordinal", "stage", "path", "table", "repeat"}
            or decision.get("ordinal") != expected
            or decision.get("table") not in tables
            or not isinstance(decision.get("path"), list)
            or not all(isinstance(part, str) for part in decision["path"])
        ):
            raise _AttemptFailure(
                "SAMPLER_DECISION_PROGRAM_INVALID", [f"/decision_program/{expected}"]
            )
        ordered.append(decision)
    if len(ordered) != 15:
        raise _AttemptFailure("SAMPLER_DECISION_PROGRAM_INVALID", ["/decision_program"])
    return ordered


def _expand(
    decision: Mapping[str, Any], selected: Mapping[str, Any], recalls: list[tuple[int, int]] | None
) -> list[tuple[dict[str, int], list[Any]]]:
    repeat, table = decision["repeat"], decision["table"]
    sections, materials = selected.get("section_count"), selected.get("material_count")
    active = selected.get("active_roles")
    if table == "recall_decision":
        if not isinstance(sections, int) or not isinstance(materials, int):
            raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/decision_program"])
        owners = [
            {"section": section, "material": material}
            for section in range(sections)
            for material in range(materials)
        ]
    elif repeat == "once":
        owners = [{}]
    elif repeat == "per_section" and isinstance(sections, int):
        owners = [{"section": value} for value in range(sections)]
    elif repeat == "per_material" and isinstance(materials, int):
        owners = [{"material": value} for value in range(materials)]
    elif repeat == "per_role" and isinstance(active, list):
        owners = [{"role": role} for role in ROLES if role in active]
    elif repeat == "per_recall" and recalls is not None:
        owners = [{"section": s, "material": m, "recall": n} for n, (s, m) in enumerate(recalls)]
    elif repeat == "per_transform":
        counts = selected.get("transform_count")
        if not isinstance(counts, Mapping) or recalls is None:
            raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/decision_program"])
        owners = [
            {"section": s, "material": m, "recall": n, "transform": transform}
            for n, (s, m) in enumerate(recalls)
            for transform in range(counts.get((s, m), -1))
        ]
    else:
        raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/decision_program"])
    output = []
    for owner in owners:
        path: list[Any] = []
        for part in decision["path"]:
            if part.startswith("{") and part.endswith("}"):
                key = part[1:-1]
                if key not in owner:
                    raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/decision_program"])
                path.append(owner[key])
            else:
                path.append(part)
        output.append((owner, path))
    return output


def _half_even(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    return quotient + (twice > denominator or (twice == denominator and quotient % 2 == 1))


def _ident(prefix: str, ordinal: int, width: int) -> str:
    return f"{prefix}{ordinal:0{width}d}"


def _lower(
    request: Mapping[str, Any],
    lowering: Mapping[str, Any],
    values: Mapping[str, Any],
    transforms: Mapping[tuple[int, int], list[tuple[str, int]]],
    attempt_seed_hash: str,
) -> dict[str, Any]:
    count, total = values["section_count"], values["total_bars"]
    bars, roles = values["section_bars"], values["section_role"]
    if sum(bars) != total:
        raise _AttemptFailure("SAMPLER_TOTAL_BARS_MISMATCH", ["/form"], sum(bars), total)
    ids, clock = lowering["id_policy"], lowering["clock"]
    width = ids["ordinal_width"]
    form = [
        {
            "id": _ident(ids["section_prefix"], ordinal, width),
            "role": roles[ordinal],
            "bars": bars[ordinal],
            "energy_q": copy.deepcopy(lowering["section_templates"]["energy_q"]),
            "density_q": copy.deepcopy(lowering["section_templates"]["density_q"]),
            "tonal_center": copy.deepcopy(lowering["section_templates"]["tonal_center"]),
            "development_stage": lowering["section_templates"]["development_stage_by_role"][
                roles[ordinal]
            ],
        }
        for ordinal in range(count)
    ]
    domain = values["equave_domain"]
    lattice = {
        "base_frequency_millihz": lowering["lattice_constants"]["base_frequency_millihz"],
        "equave": domain["equave"],
        "generators": copy.deepcopy(domain["generators"]),
        "coordinate_bounds": copy.deepcopy(domain["coordinate_bounds"]),
        "register_bounds": copy.deepcopy(domain["register_bounds"]),
        "maximum_odd_limit": lowering["lattice_constants"]["maximum_odd_limit"],
        "pitch_exploration": copy.deepcopy(lowering["lattice_constants"]["pitch_exploration"]),
    }
    helpers, primaries, primary_ids, quantum = [], [], [], []
    length = clock["beats_per_bar"] * clock["ticks_per_beat"]
    for ordinal, kind in enumerate(values["material_kind"]):
        grid, density = values["rhythm_grid"][ordinal], values["rhythm_density"][ordinal]
        if not isinstance(grid, int) or grid <= 0 or length % grid:
            raise _AttemptFailure("SAMPLER_STRUCTURAL_SEMANTIC_INVALID", [f"/materials/{ordinal}"])
        positions = length // grid
        chosen = max(1, _half_even(positions * density, 10000))
        if chosen > positions:
            raise _AttemptFailure("SAMPLER_STRUCTURAL_SEMANTIC_INVALID", [f"/materials/{ordinal}"])
        helper_id = _ident(ids["rhythm_prefix"], ordinal, width)
        steps = [
            {
                "at_tick": position * grid,
                "duration_ticks": lowering["material_builders"]["rhythm_duration_ticks"],
                "accent_q": lowering["material_builders"]["rhythm_accent_q"],
                "lane_id": None,
            }
            for position in range(chosen)
        ]
        helpers.append(
            {"id": helper_id, "kind": "rhythm_cell", "length_ticks": length, "steps": steps}
        )
        quantum.append(
            math.gcd(
                length,
                *(step["duration_ticks"] for step in steps),
                *(grid for _ in range(max(0, len(steps) - 1))),
            )
        )
        if kind == "rhythm":
            primary_ids.append(helper_id)
            continue
        material_id = _ident(ids["material_prefix"], ordinal, width)
        primary_ids.append(material_id)
        common = {
            "id": material_id,
            "rhythm_id": helper_id,
            "mapping": lowering["material_builders"]["mapping"],
        }
        if kind == "direct_vector":
            primaries.append(
                {
                    **common,
                    "kind": "direct_vector_cell",
                    "vectors": copy.deepcopy(lowering["material_builders"]["direct_vectors"]),
                    "register_delta": lowering["material_builders"]["register_delta"],
                }
            )
        elif kind == "melody_intent":
            primaries.append(
                {
                    **common,
                    "kind": "melody_intent",
                    "points": [
                        {"relation": "chord_member", "member": member, "contour": "hold"}
                        for member in lowering["material_builders"]["melody_members"]
                    ],
                }
            )
        elif kind == "harmony_intent":
            primaries.append(
                {
                    **common,
                    "kind": "harmony_intent_cell",
                    "root_anchors": copy.deepcopy(
                        lowering["material_builders"]["harmony_root_anchors"]
                    ),
                    "chord_intent_ids": [_ident(ids["chord_prefix"], ordinal, width)],
                }
            )
        else:
            raise _AttemptFailure(
                "SAMPLER_STRUCTURAL_SEMANTIC_INVALID", [f"/materials/{ordinal}/kind"]
            )
    chords = [
        {
            "id": _ident(ids["chord_prefix"], ordinal, width),
            "reference": {"temperament": "edo", **copy.deepcopy(reference)},
            "voicing": copy.deepcopy(lowering["chord_constants"]["voicing"]),
            "recognition": copy.deepcopy(lowering["chord_constants"]["recognition"]),
            "complexity_budget": lowering["chord_constants"]["complexity_budget"],
        }
        for ordinal, reference in enumerate(values["chord_reference"])
    ]
    active = values["active_roles"]
    realizations, rid = [], 0
    for recall, (section, material) in enumerate(values["recalls"]):
        for role in (
            role
            for role in ROLES
            if role in active and role in _COMPATIBLE[values["material_kind"][material]]
        ):
            entries = []
            for kind, amount in transforms.get((section, material), []):
                if kind == "rotate":
                    entries.append({"op": "rotate", "ticks": amount * quantum[material]})
            realizations.append(
                {
                    "id": _ident(ids["realization_prefix"], rid, width),
                    "section_id": form[section]["id"],
                    "role": role,
                    "material_id": primary_ids[material],
                    **copy.deepcopy(lowering["realization_constants"]),
                    "rhythm_transforms": entries,
                    "pitch_transforms": [],
                }
            )
            rid += 1
    program_id = ids["program_prefix"] + _b32(
        hashlib.sha256(b"cps.structural-program-id/v1\0" + _raw_sha(attempt_seed_hash)).digest(), 26
    )
    result = {
        "schema": "cps.structural-song-program",
        "schema_version": "1.0.0",
        "program_id": program_id,
        "seed": request["root_seed"],
        "clock": copy.deepcopy(clock),
        "lattice": lattice,
        "form": form,
        "materials": helpers + primaries,
        "chord_intents": chords,
        "realizations": realizations,
        "compile_policy": copy.deepcopy(lowering["compile_policy"]),
        "limits": copy.deepcopy(lowering["limits"]),
    }
    all_ids = [item["id"] for item in form + helpers + primaries + chords + realizations] + [
        program_id
    ]
    if len(all_ids) != len(set(all_ids)):
        raise _AttemptFailure("SAMPLER_ID_COLLISION", [""], all_ids, "unique ids")
    return result


def _coverage(
    program: Mapping[str, Any],
    values: Mapping[str, Any],
    transforms: Mapping[tuple[int, int], list[tuple[str, int]]],
) -> None:
    sections = [item["id"] for item in program["form"]]
    realizations = program["realizations"]
    missing = [
        f"/form/{index}"
        for index, section in enumerate(sections)
        if not any(row["section_id"] == section for row in realizations)
    ]
    if missing:
        raise _AttemptFailure(
            "SAMPLER_SECTION_UNCOVERED", missing, "uncovered", "at least one realization", True
        )
    sounding = {row["role"] for row in realizations}
    minimum = values["minimum_sounding_roles"]
    if len(sounding) < minimum:
        raise _AttemptFailure(
            "SAMPLER_SOUNDING_ROLE_UNDERSHOOT",
            [
                f"/realizations/{index}"
                for index, row in enumerate(realizations)
                if row["role"] in ROLES
            ],
            len(sounding),
            minimum,
            True,
        )
    by_material: dict[str, list[dict[str, Any]]] = {}
    for row in realizations:
        by_material.setdefault(row["material_id"], []).append(row)
    repeated = {
        material: rows
        for material, rows in by_material.items()
        if len({row["section_id"] for row in rows}) >= 2
    }
    if not repeated:
        raise _AttemptFailure(
            "SAMPLER_RECALL_MISSING", ["/realizations"], "none", "material in two sections", True
        )
    good = False
    for material, rows in repeated.items():
        ordinal = next(
            index for index, value in enumerate(values["primary_ids"]) if value == material
        )
        occurrences = [pair for pair in values["recalls"] if pair[1] == ordinal]
        steps = next(
            item for item in program["materials"] if item["id"] == values["helper_ids"][ordinal]
        )["steps"]
        for section, _ in occurrences[1:]:
            if any(
                kind == "rotate" and amount % len(steps) != 0
                for kind, amount in transforms.get((section, ordinal), [])
            ):
                good = True
    if not good:
        raise _AttemptFailure(
            "SAMPLER_NON_IDENTITY_RECALL_MISSING",
            ["/realizations"],
            "none",
            "nonidentity later recall",
            True,
        )


def execute_structural_sampler(
    request: Mapping[str, Any],
    sampler_manifest: Mapping[str, Any],
    lowering_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the sealed v1.1 sampler and return its result, trace, and payload."""
    try:
        _request_valid(request)
        _validate_sampler_binding(request, sampler_manifest, lowering_manifest)
    except StructuralSamplerError as error:
        return _envelope_failure(request, error.code)
    maximum = sampler_manifest.get("maximum_rejections_per_seed")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 256:
        return _envelope_failure(request, "SAMPLER_MANIFEST_MISMATCH")
    attempts = []
    for ordinal in range(maximum):
        seed = _attempt_seed(request, ordinal)
        decisions: list[dict[str, Any]] = []
        candidate = None
        try:
            program = _decision_program(sampler_manifest)
            selected: dict[str, Any] = {}
            recalls: list[tuple[int, int]] | None = None
            transforms: dict[tuple[int, int], list[tuple[str, int]]] = {}
            for decision in program:
                for owner, path in _expand(decision, selected, recalls):
                    value, trace = _trace_choice(
                        decision["ordinal"],
                        path,
                        sampler_manifest["tables"][decision["table"]],
                        f"/tables/{decision['table']}",
                        seed,
                    )
                    decisions.append(trace)
                    table = decision["table"]
                    if table in {
                        "section_count",
                        "total_bars",
                        "material_count",
                        "active_roles",
                        "equave_domain",
                    }:
                        selected[table] = value
                    elif table in {
                        "section_role",
                        "section_bars",
                        "material_kind",
                        "rhythm_grid",
                        "rhythm_density",
                        "chord_reference",
                    }:
                        selected.setdefault(table, {})[
                            owner.get("section", owner.get("material"))
                        ] = value
                    elif table == "recall_decision":
                        selected.setdefault("recall_votes", {})[
                            (owner["section"], owner["material"])
                        ] = value
                    elif table == "transform_count":
                        selected.setdefault("transform_count", {})[
                            (owner["section"], owner["material"])
                        ] = value
                    elif table in {"transform_type", "rotate_amount"}:
                        selected.setdefault(table, {})[
                            (owner["section"], owner["material"], owner["transform"])
                        ] = value
                if decision["table"] == "recall_decision":
                    recalls = [
                        pair for pair, include in selected["recall_votes"].items() if include
                    ]
            for name in ("section_count", "material_count", "total_bars"):
                if not isinstance(selected.get(name), int):
                    raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", [f"/tables/{name}"])
            if not isinstance(selected.get("active_roles"), list) or selected["active_roles"] != [
                role for role in ROLES if role in selected["active_roles"]
            ]:
                raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/tables/active_roles"])
            selected["section_role"] = [
                selected["section_role"][n] for n in range(selected["section_count"])
            ]
            selected["section_bars"] = [
                selected["section_bars"][n] for n in range(selected["section_count"])
            ]
            for name in ("material_kind", "rhythm_grid", "rhythm_density", "chord_reference"):
                selected[name] = [selected[name][n] for n in range(selected["material_count"])]
            selected["recalls"] = recalls or []
            selected["minimum_sounding_roles"] = sampler_manifest["limits"][
                "minimum_sounding_roles"
            ]
            for pair in selected["recalls"]:
                transforms[pair] = [
                    (
                        selected.get("transform_type", {}).get((pair[0], pair[1], n)),
                        selected.get("rotate_amount", {}).get((pair[0], pair[1], n)),
                    )
                    for n in range(selected.get("transform_count", {}).get(pair, 0))
                ]
                if any(
                    kind not in {"identity", "rotate"} or not isinstance(amount, int)
                    for kind, amount in transforms[pair]
                ):
                    raise _AttemptFailure("SAMPLER_PATH_EXPANSION_INVALID", ["/decision_program"])
            candidate = _lower(request, lowering_manifest, selected, transforms, seed)
            selected["primary_ids"] = [
                row["material_id"] for row in candidate["realizations"]
            ]  # replaced below with stable ordinal list
            ids = lowering_manifest["id_policy"]
            selected["helper_ids"] = [
                _ident(ids["rhythm_prefix"], n, ids["ordinal_width"])
                for n in range(selected["material_count"])
            ]
            selected["primary_ids"] = [
                _ident(
                    ids["rhythm_prefix" if kind == "rhythm" else "material_prefix"],
                    n,
                    ids["ordinal_width"],
                )
                for n, kind in enumerate(selected["material_kind"])
            ]
            _coverage(candidate, selected, transforms)
        except _AttemptFailure as error:
            evidence = _failure(ordinal, error.code, error.pointers, error.actual, error.expected)
            attempts.append(
                {
                    "attempt_ordinal": ordinal,
                    "attempt_seed_hash": seed,
                    "decisions": decisions,
                    "candidate_program_hash": structural_program_hash(candidate)
                    if error.candidate and candidate is not None
                    else None,
                    "outcome": "rejected",
                    "rejection_evidence": evidence,
                    "rejection_evidence_hash": evidence["evidence_hash"],
                }
            )
            continue
        payload_hash = structural_program_hash(candidate)
        attempts.append(
            {
                "attempt_ordinal": ordinal,
                "attempt_seed_hash": seed,
                "decisions": decisions,
                "candidate_program_hash": payload_hash,
                "outcome": "accepted",
                "rejection_evidence": None,
                "rejection_evidence_hash": None,
            }
        )
        return _success(request, attempts, candidate)
    return _exhausted(request, attempts)


def _trace(request: Mapping[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    trace = {
        "schema": "cps.structural-sampler-trace",
        "schema_version": "1.1.0",
        "run_hash": request["run_hash"],
        "context_hash": request["context_hash"],
        "source_decision_hash": request["source_decision_hash"],
        "sampler_request_hash": request["request_hash"],
        "sampler_manifest_hash": request["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": request["structural_lowering_manifest_hash"],
        "structural_program_schema_hash": request["structural_program_schema_hash"],
        "structural_rejection_evidence_schema_hash": request[
            "structural_rejection_evidence_schema_hash"
        ],
        "attempts": attempts,
        "terminal_attempt_ordinal": len(attempts) - 1,
        "trace_hash": "",
    }
    trace["trace_hash"] = _hash("cps.structural-sampler-trace/v1.1", trace, omit="trace_hash")
    return trace


def _result_base(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "cps.structural-sampler-result",
        "schema_version": "1.1.0",
        "run_hash": request.get("run_hash"),
        "context_hash": request.get("context_hash"),
        "source_decision_hash": request.get("source_decision_hash"),
        "request_hash": request.get("request_hash"),
        "sampler_manifest_hash": request.get("sampler_manifest_hash"),
        "structural_lowering_manifest_hash": request.get("structural_lowering_manifest_hash"),
        "structural_program_schema_hash": request.get("structural_program_schema_hash"),
        "structural_rejection_evidence_schema_hash": request.get(
            "structural_rejection_evidence_schema_hash"
        ),
    }


def _envelope_failure(request: Mapping[str, Any], code: str) -> dict[str, Any]:
    result = {
        **_result_base(request),
        "status": "failure",
        "structural_program_hash": None,
        "rejections_consumed": 0,
        "decision_trace_hash": None,
        "terminal_rejection_evidence_hash": None,
        "error": code,
        "result_hash": "",
    }
    result["result_hash"] = _hash("cps.structural-sampler-result/v1.1", result, omit="result_hash")
    return {"result": result, "trace": None, "structural_program": None}


def _success(
    request: Mapping[str, Any], attempts: list[dict[str, Any]], program: dict[str, Any]
) -> dict[str, Any]:
    trace = _trace(request, attempts)
    result = {
        **_result_base(request),
        "status": "success",
        "structural_program_hash": structural_program_hash(program),
        "rejections_consumed": len(attempts) - 1,
        "decision_trace_hash": trace["trace_hash"],
        "terminal_rejection_evidence_hash": None,
        "error": None,
        "result_hash": "",
    }
    result["result_hash"] = _hash("cps.structural-sampler-result/v1.1", result, omit="result_hash")
    return {"result": result, "trace": trace, "structural_program": program}


def _exhausted(request: Mapping[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    trace = _trace(request, attempts)
    result = {
        **_result_base(request),
        "status": "failure",
        "structural_program_hash": None,
        "rejections_consumed": len(attempts),
        "decision_trace_hash": trace["trace_hash"],
        "terminal_rejection_evidence_hash": attempts[-1]["rejection_evidence_hash"],
        "error": "SAMPLER_REJECTIONS_EXHAUSTED",
        "result_hash": "",
    }
    result["result_hash"] = _hash("cps.structural-sampler-result/v1.1", result, omit="result_hash")
    return {"result": result, "trace": trace, "structural_program": None}
