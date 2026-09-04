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
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _canon(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def program_hash(p: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            b"cps.song-program/0.1\0" + _canon({k: v for k, v in p.items() if k != "program_id"})
        ).hexdigest()
    )


def _id(prefix: bytes, mutation: str, source: str) -> str:
    return (
        base64.b32encode(
            hashlib.sha256(prefix + mutation.encode() + b"\0" + source.encode()).digest()
        )
        .decode()
        .lower()
        .rstrip("=")[:20]
    )


def _find(items: list[dict[str, Any]], ident: str) -> dict[str, Any]:
    for x in items:
        if x["id"] == ident:
            return x
    raise MutationError("MUTATION_REFERENCE_NOT_FOUND")


def _roots(op: str, p: dict[str, Any], x: dict[str, Any]) -> list[dict[str, str]]:
    q = x["parameters"]
    k = q.get("kind")
    if k == "replace_bounded_scalar":
        return (
            [{"kind": "global_form", "id": "global_form"}, {"kind": "section", "id": q["owner_id"]}]
            if q["field"] == "bars"
            else [
                {
                    "kind": "production" if q["owner_kind"] == "production" else "realization",
                    "id": q["owner_id"],
                }
            ]
        )
    if k == "replace_distribution_choice":
        return (
            [{"kind": "production", "id": "production"}]
            if q["field"] == "profile_id"
            else [{"kind": q["owner_kind"], "id": q["owner_id"]}]
        )
    if k == "transpose_material_vector" or k == "replace_root_anchor_item":
        return [{"kind": "material", "id": q["material_id"]}]
    if k == "rotate_rhythm":
        return [{"kind": "rhythm", "id": q["rhythm_id"]}]
    if k == "replace_chord_intent_reference":
        return [{"kind": "chord_intent", "id": q["chord_intent_id"]}]
    if k == "edit_section":
        return [
            {"kind": "global_form", "id": "global_form"},
            {"kind": "section", "id": q["section_id"]},
        ]
    if k == "swap_track_catalog_entry":
        return [{"kind": "track", "id": q["track_id"]}]
    raise MutationError("MUTATION_PARAMETER_INVALID")


def _ordered(rs: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rs, key=lambda x: (x["kind"].encode(), x["id"].encode()))


def _rotate(rhythm: dict[str, Any], steps: int) -> None:
    on = sorted({x["at_tick"] for x in rhythm["steps"]})
    gaps = [b - a for a, b in zip(on, on[1:])] + [rhythm["length_ticks"] - on[-1] + on[0]]
    quantum = math.gcd(
        rhythm["length_ticks"],
        *(x["duration_ticks"] for x in rhythm["steps"]),
        *(x for x in gaps if x),
    )
    rhythm["steps"] = sorted(
        (
            {**x, "at_tick": (x["at_tick"] + steps * quantum) % rhythm["length_ticks"]}
            for x in rhythm["steps"]
        ),
        key=lambda x: x["at_tick"],
    )


def apply_mutations(
    program: dict[str, Any],
    mutations: list[dict[str, Any],],
    locked_roots: list[dict[str, str]],
    choice_catalog: dict[str, Any],
    catalog: dict[str, Any],
    action_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current = copy.deepcopy(program)
    impacts = []
    locked = {(x["kind"], x["id"]) for x in locked_roots}
    for ordinal, m in enumerate(mutations):
        q = m.get("parameters", {})
        op = m.get("operation")
        if op != q.get("kind"):
            raise MutationError("MUTATION_OPERATION_MISMATCH")
        if m.get("base_program_hash") != program_hash(current):
            raise MutationError("MUTATION_BASE_HASH_MISMATCH")
        roots = _ordered(_roots(op, current, m))
        if _canon(roots) != _canon(_ordered(m.get("declared_scope", []))):
            raise MutationError("MUTATION_SCOPE_MISMATCH")
        if any((r["kind"], r["id"]) in locked for r in roots):
            raise MutationError("MUTATION_LOCKED")
        trial = copy.deepcopy(current)
        try:
            if op == "rotate_rhythm":
                _rotate(_find(trial["materials"], q["rhythm_id"]), q["steps"])
            elif op == "transpose_material_vector":
                z = _find(trial["materials"], q["material_id"])
                field = "vectors" if z["kind"] == "direct_vector_cell" else "root_anchors"
                z[field] = [
                    [a + b for a, b in zip(v, q["vector_delta"], strict=True)] for v in z[field]
                ]
            elif op == "replace_root_anchor_item":
                _find(trial["materials"], q["material_id"])["root_anchors"][q["index"]] = q[
                    "vector"
                ]
            elif op == "replace_chord_intent_reference":
                z = _find(trial["chord_intents"], q["chord_intent_id"])
                f = Fraction(q["reference_equave"])
                steps = sorted(q["steps"])
                if len(set(steps)) != len(steps) or any(not 0 <= s < q["divisions"] for s in steps):
                    raise MutationError("MUTATION_PARAMETER_INVALID")
                z["reference"] = {
                    "temperament": "edo",
                    "equave": f"{f.numerator}/{f.denominator}",
                    "divisions": q["divisions"],
                    "steps": steps,
                }
            elif op == "replace_bounded_scalar":
                bounds = {
                    "bars": (1, 32),
                    "velocity_scale_q": (0, 10000),
                    "gate_scale_q": (1, 10000),
                    "gain_q": (0, 10000),
                    "pan_q": (-10000, 10000),
                }
                lo, hi = bounds.get(q["field"], (1, 0))
                if (q["minimum"], q["maximum"]) != (lo, hi) or not lo <= q["value"] <= hi:
                    raise MutationError("MUTATION_PARAMETER_INVALID")
                target = (
                    trial["production"]["tracks"][q["owner_id"]]
                    if q["owner_kind"] == "production"
                    else _find(
                        trial["form"] if q["owner_kind"] == "section" else trial["realizations"],
                        q["owner_id"],
                    )
                )
                target[q["field"]] = q["value"]
            elif op == "replace_distribution_choice":
                choice = next(
                    (
                        item
                        for item in choice_catalog.get("entries", [])
                        if item.get("choice_id") == q["choice_id"]
                        and item.get("owner_kind") == q["owner_kind"]
                        and item.get("field") == q["field"]
                    ),
                    None,
                )
                if choice is None:
                    raise MutationError("MUTATION_CHOICE_UNRESOLVED")
                if q["owner_kind"] == "production":
                    if q["owner_id"] != "production" or q["field"] != "profile_id":
                        raise MutationError("MUTATION_PARAMETER_INVALID")
                    trial["production"]["profile_id"] = choice["value"]
                else:
                    collection = {"section": "form", "material": "materials", "track": "tracks"}[
                        q["owner_kind"]
                    ]
                    target = _find(trial[collection], q["owner_id"])
                    if q["owner_kind"] == "material" and target["kind"] == "rhythm_cell":
                        raise MutationError("MUTATION_PARAMETER_INVALID")
                    target[q["field"]] = choice["value"]
            elif op == "edit_section":
                source = _find(trial["form"], q["section_id"])
                if q["action"] == "delete":
                    if q["insert_after_section_id"] is not None or len(trial["form"]) == 1:
                        raise MutationError("MUTATION_PARAMETER_INVALID")
                    trial["form"] = [item for item in trial["form"] if item["id"] != source["id"]]
                    trial["realizations"] = [
                        item for item in trial["realizations"] if item["section_id"] != source["id"]
                    ]
                elif q["action"] == "duplicate":
                    predecessor = _find(trial["form"], q["insert_after_section_id"])
                    section_id = "sec_" + _id(
                        b"cps.mutation-section-id/v1\0", m["mutation_id"], source["id"]
                    )
                    if any(item["id"] == section_id for item in trial["form"]):
                        raise MutationError("MUTATION_ID_COLLISION")
                    duplicate = {**source, "id": section_id}
                    index = trial["form"].index(predecessor) + 1
                    trial["form"].insert(index, duplicate)
                    copies = []
                    for realization in trial["realizations"]:
                        if realization["section_id"] == source["id"]:
                            rid = "real_" + _id(
                                b"cps.mutation-realization-id/v1\0",
                                m["mutation_id"],
                                realization["id"],
                            )
                            if any(item["id"] == rid for item in trial["realizations"]):
                                raise MutationError("MUTATION_ID_COLLISION")
                            copies.append({**realization, "id": rid, "section_id": section_id})
                    trial["realizations"].extend(copies)
                else:
                    raise MutationError("MUTATION_PARAMETER_INVALID")
            elif op == "swap_track_catalog_entry":
                if catalog.get("digest") not in (None, trial["production"]["catalog_digest"]):
                    raise MutationError("MUTATION_CATALOG_MISMATCH")
                track = _find(trial["tracks"], q["track_id"])
                entry = next(
                    (
                        item
                        for item in catalog.get("entries", [])
                        if item.get("instrument_id") == q["instrument_id"]
                    ),
                    None,
                )
                if entry is None:
                    raise MutationError("MUTATION_CATALOG_MISMATCH")
                if (track["role"] == "drums") != (entry.get("kind") == "drum_kit"):
                    raise MutationError("MUTATION_PARAMETER_INVALID")
                if track["role"] == "drums":
                    available = {item.get("drum_note") for item in entry.get("note_map", [])}
                    if any(note not in available for note in track.get("drum_map", {}).values()):
                        raise MutationError("MUTATION_PARAMETER_INVALID")
                track["instrument_id"] = q["instrument_id"]
            else:
                raise MutationError("MUTATION_PARAMETER_INVALID")
        except (KeyError, IndexError):
            raise MutationError("MUTATION_REFERENCE_NOT_FOUND")
        current = trial
        impacts.append({"ordinal": ordinal, "roots": roots, "program_hash": program_hash(current)})
    return current, impacts
