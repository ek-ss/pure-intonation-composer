"""Independent reference oracle for Mutation Application Contract 1.1.

This module deliberately does not import ``app``.  It is intentionally small
and literal so fixture verification does not share production implementation
paths.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from fractions import Fraction
from typing import Any


class OracleMutationError(ValueError):
    def __init__(self, code: str, stage: str, ordinal: int) -> None:
        super().__init__(code)
        self.code, self.stage, self.ordinal = code, stage, ordinal


def canonical_lf(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def artifact_hash(domain: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + canonical_lf(value)).hexdigest()


def program_hash(program: dict[str, Any]) -> str:
    core = {key: value for key, value in program.items() if key != "program_id"}
    return "sha256:" + hashlib.sha256(b"cps.song-program/0.1\0" + canonical_lf(core)[:-1]).hexdigest()


def _find(items: list[dict[str, Any]], ident: str, ordinal: int) -> dict[str, Any]:
    for item in items:
        if item["id"] == ident:
            return item
    raise OracleMutationError("MUTATION_REFERENCE_NOT_FOUND", "mutation", ordinal)


def _sort_roots(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(items, key=lambda item: (item["kind"].encode(), item["id"].encode()))


def roots(parameters: dict[str, Any], ordinal: int) -> list[dict[str, str]]:
    kind = parameters["kind"]
    if kind == "replace_bounded_scalar":
        if parameters["owner_kind"] == "section" and parameters["field"] == "bars":
            value = [{"kind": "section", "id": parameters["owner_id"]}, {"kind": "global_form", "id": "global_form"}]
        elif parameters["owner_kind"] in {"realization", "production"}:
            value = [{"kind": parameters["owner_kind"], "id": parameters["owner_id"]}]
        else:
            raise OracleMutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    elif kind == "replace_distribution_choice":
        value = [{"kind": "production", "id": "production"}] if parameters["owner_kind"] == "production" else [{"kind": parameters["owner_kind"], "id": parameters["owner_id"]}]
    elif kind in {"transpose_material_vector", "replace_root_anchor_item"}:
        value = [{"kind": "material", "id": parameters["material_id"]}]
    elif kind == "rotate_rhythm":
        value = [{"kind": "rhythm", "id": parameters["rhythm_id"]}]
    elif kind == "replace_chord_intent_reference":
        value = [{"kind": "chord_intent", "id": parameters["chord_intent_id"]}]
    elif kind == "edit_section":
        value = [{"kind": "section", "id": parameters["section_id"]}, {"kind": "global_form", "id": "global_form"}]
    elif kind == "swap_track_catalog_entry":
        value = [{"kind": "track", "id": parameters["track_id"]}]
    else:
        raise OracleMutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
    return _sort_roots(value)


def _closure(program: dict[str, Any], actual: list[dict[str, str]], mutation: dict[str, Any], after: bool) -> list[dict[str, str]]:
    found = {(item["kind"], item["id"]) for item in actual}
    changed = True
    while changed:
        changed = False
        for kind, ident in list(found):
            additions: list[tuple[str, str]] = []
            if kind == "rhythm":
                additions += [("material", x["id"]) for x in program["materials"] if x.get("rhythm_id") == ident]
            elif kind == "chord_intent":
                additions += [("material", x["id"]) for x in program["materials"] if ident in x.get("chord_intent_ids", [])]
            elif kind == "material":
                additions += [("realization", x["id"]) for x in program["realizations"] if x["material_id"] == ident]
            elif kind == "section":
                additions += [("realization", x["id"]) for x in program["realizations"] if x["section_id"] == ident]
            elif kind == "track":
                additions += [("realization", x["id"]) for x in program["realizations"] if x["track_id"] == ident]
                if ident in program["production"]["tracks"]:
                    additions.append(("production", ident))
            elif kind == "global_form":
                p = mutation["parameters"]
                if p["kind"] == "edit_section" and p["action"] == "duplicate":
                    marker = "sec_" + _derived(b"cps.mutation-section-id/v1\0", mutation["mutation_id"], p["section_id"])
                    start = next((i for i, x in enumerate(program["form"]) if x["id"] == marker), len(program["form"])) if after else next(i for i, x in enumerate(program["form"]) if x["id"] == p["insert_after_section_id"]) + 1
                else:
                    start = next((i for i, x in enumerate(program["form"]) if x["id"] == p.get("section_id", p.get("owner_id"))), len(program["form"]))
                additions += [("section", x["id"]) for x in program["form"][start:]]
            for addition in additions:
                if addition not in found:
                    found.add(addition); changed = True
    return [{"kind": kind, "id": ident} for kind, ident in sorted(found, key=lambda item: (item[0].encode(), item[1].encode()))]


def _derived(prefix: bytes, mutation_id: str, source_id: str) -> str:
    raw = hashlib.sha256(prefix + mutation_id.encode() + b"\0" + source_id.encode()).digest()
    return base64.b32encode(raw).decode().lower().rstrip("=")[:20]


def _components(operation: str, parameters: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    song_order = ["form", "tracks", "materials", "chord_intents", "realizations", "production"]
    song = [key for key in song_order if before[key] != after[key]]
    if not song:
        return [], [], []
    project = ["source_program_hash"]
    downstream: list[str] = []
    if (operation == "replace_bounded_scalar" and parameters["field"] == "bars") or operation == "edit_section": project.append("form_clock")
    if (operation == "replace_distribution_choice" and parameters["owner_kind"] == "section") or operation == "edit_section": project.append("form_metadata")
    if (operation == "replace_distribution_choice" and parameters["owner_kind"] == "track") or operation == "swap_track_catalog_entry": project.append("track_records")
    if operation == "replace_bounded_scalar" and parameters["owner_kind"] == "production": project.append("mix")
    broad = operation in {"transpose_material_vector", "replace_root_anchor_item", "rotate_rhythm", "replace_chord_intent_reference", "edit_section"} or (operation == "replace_bounded_scalar" and parameters["owner_kind"] == "section") or (operation == "replace_distribution_choice" and parameters["owner_kind"] in {"material", "track"})
    if broad: project += ["material_instances", "resolved_chords", "harmony_occurrences", "events"]; downstream.append("lineage_index")
    if operation == "replace_bounded_scalar" and parameters["owner_kind"] == "realization": project += ["harmony_occurrences", "events"]; downstream.append("lineage_index")
    section_choice = operation == "replace_distribution_choice" and parameters["owner_kind"] == "section"
    if not section_choice: downstream += ["render_stems", "render_mix", "audio_evaluation"]
    production_like = (operation == "replace_bounded_scalar" and parameters["owner_kind"] == "production") or (operation == "replace_distribution_choice" and parameters["owner_kind"] == "production") or operation == "swap_track_catalog_entry"
    if not production_like: downstream.append("descriptors")
    po = [x for x in ["source_program_hash","form_clock","form_metadata","track_records","mix","material_instances","resolved_chords","harmony_occurrences","events"] if x in project]
    do = [x for x in ["lineage_index","render_stems","render_mix","audio_evaluation","descriptors"] if x in downstream]
    return song, po, do


def _apply_one(program: dict[str, Any], mutation: dict[str, Any], choices: dict[str, Any], catalog: dict[str, Any], ordinal: int) -> dict[str, Any]:
    p, op = mutation["parameters"], mutation["operation"]
    result = copy.deepcopy(program)
    if op == "replace_bounded_scalar":
        bounds = {"bars":(1,32),"velocity_scale_q":(0,10000),"gate_scale_q":(1,10000),"gain_q":(0,10000),"pan_q":(-10000,10000)}
        if p["field"] not in bounds or (p["minimum"],p["maximum"]) != bounds[p["field"]] or not p["minimum"] <= p["value"] <= p["maximum"]:
            raise OracleMutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        if p["owner_kind"] == "production": target = result["production"]["tracks"].get(p["owner_id"])
        else: target = _find(result["form"] if p["owner_kind"] == "section" else result["realizations"], p["owner_id"], ordinal)
        if target is None: raise OracleMutationError("MUTATION_REFERENCE_NOT_FOUND", "mutation", ordinal)
        target[p["field"]] = p["value"]
    elif op == "replace_distribution_choice":
        choice = next((x for x in choices["entries"] if x["choice_id"] == p["choice_id"] and x["owner_kind"] == p["owner_kind"] and x["field"] == p["field"]), None)
        if choice is None: raise OracleMutationError("MUTATION_CHOICE_UNRESOLVED", "mutation", ordinal)
        if p["owner_kind"] == "production": target = result["production"]
        else: target = _find(result[{"section":"form","material":"materials","track":"tracks"}[p["owner_kind"]]], p["owner_id"], ordinal)
        target[p["field"]] = choice["value"]
    elif op == "transpose_material_vector":
        target = _find(result["materials"], p["material_id"], ordinal)
        field = "vectors" if target["kind"] == "direct_vector_cell" else "root_anchors" if target["kind"] == "harmony_intent_cell" else None
        if field is None or len(p["vector_delta"]) != len(result["lattice"]["generators"]): raise OracleMutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        target[field] = [[a+b for a,b in zip(v,p["vector_delta"],strict=True)] for v in target[field]]
    elif op == "rotate_rhythm":
        target = _find(result["materials"], p["rhythm_id"], ordinal)
        if target["kind"] != "rhythm_cell": raise OracleMutationError("MUTATION_PARAMETER_INVALID", "mutation", ordinal)
        onsets = sorted({x["at_tick"] for x in target["steps"]}); gaps=[b-a for a,b in zip(onsets,onsets[1:])] + [target["length_ticks"]-onsets[-1]+onsets[0]]
        quantum=math.gcd(target["length_ticks"],*(x["duration_ticks"] for x in target["steps"]),*(x for x in gaps if x))
        target["steps"] = [x for _,x in sorted(enumerate(({**x,"at_tick":(x["at_tick"]+p["steps"]*quantum)%target["length_ticks"]} for x in target["steps"])), key=lambda pair:(pair[1]["at_tick"],pair[0]))]
    elif op == "replace_chord_intent_reference":
        target=_find(result["chord_intents"],p["chord_intent_id"],ordinal); values=sorted(p["steps"])
        if len(values)!=len(set(values)) or any(x<0 or x>=p["divisions"] for x in values): raise OracleMutationError("MUTATION_PARAMETER_INVALID","mutation",ordinal)
        ratio=Fraction(p["reference_equave"]); target["reference"]={"temperament":"edo","equave":f"{ratio.numerator}/{ratio.denominator}","divisions":p["divisions"],"steps":values}
    elif op == "replace_root_anchor_item":
        target=_find(result["materials"],p["material_id"],ordinal)
        if target["kind"]!="harmony_intent_cell" or p["index"]>=len(target["root_anchors"]) or len(p["vector"])!=len(result["lattice"]["generators"]): raise OracleMutationError("MUTATION_PARAMETER_INVALID","mutation",ordinal)
        target["root_anchors"][p["index"]]=p["vector"]
    elif op == "edit_section":
        source=_find(result["form"],p["section_id"],ordinal)
        if p["action"]=="delete":
            if p["insert_after_section_id"] is not None or len(result["form"])==1: raise OracleMutationError("MUTATION_PARAMETER_INVALID","mutation",ordinal)
            result["form"]=[x for x in result["form"] if x["id"]!=source["id"]]; result["realizations"]=[x for x in result["realizations"] if x["section_id"]!=source["id"]]
        else:
            predecessor=_find(result["form"],p["insert_after_section_id"],ordinal); sid="sec_"+_derived(b"cps.mutation-section-id/v1\0",mutation["mutation_id"],source["id"])
            if any(x["id"]==sid for x in result["form"]): raise OracleMutationError("MUTATION_ID_COLLISION","application",ordinal)
            result["form"].insert(result["form"].index(predecessor)+1,{**source,"id":sid})
            rebuilt=[]
            for item in result["realizations"]:
                rebuilt.append(item)
                if item["section_id"]==source["id"]: rebuilt.append({**item,"id":"real_"+_derived(b"cps.mutation-realization-id/v1\0",mutation["mutation_id"],item["id"]),"section_id":sid})
            result["realizations"]=rebuilt
    elif op == "swap_track_catalog_entry":
        track=_find(result["tracks"],p["track_id"],ordinal); entry=next((x for x in catalog["entries"] if x["instrument_id"]==p["instrument_id"]),None)
        if entry is None: raise OracleMutationError("MUTATION_REFERENCE_NOT_FOUND","mutation",ordinal)
        if (track["role"]=="drums") != (entry["kind"]=="drum_kit"): raise OracleMutationError("MUTATION_PARAMETER_INVALID","mutation",ordinal)
        if track["role"]=="drums" and any(note not in {x["drum_note"] for x in entry["note_map"]} for note in track["drum_map"].values()): raise OracleMutationError("MUTATION_PARAMETER_INVALID","mutation",ordinal)
        track["instrument_id"]=p["instrument_id"]
    return result


def evaluate(program: dict[str, Any], mutation: dict[str, Any], locks: list[dict[str,str]], choices: dict[str,Any], catalog: dict[str,Any], request_hash: str) -> dict[str,Any]:
    ordinal=0; before=copy.deepcopy(program); input_hash=program_hash(before); actual=None; trial=None
    try:
        if mutation.get("operation") != mutation.get("parameters",{}).get("kind"): raise OracleMutationError("MUTATION_OPERATION_MISMATCH","mutation",0)
        if mutation.get("base_program_hash") != input_hash: raise OracleMutationError("MUTATION_BASE_HASH_MISMATCH","mutation",0)
        trial=_apply_one(before,mutation,choices,catalog,0)
        actual=roots(mutation["parameters"],0)
        if actual != _sort_roots(mutation.get("declared_scope",[])): raise OracleMutationError("MUTATION_SCOPE_MISMATCH","scope",0)
        if any(x in locks for x in actual): raise OracleMutationError("MUTATION_LOCKED","lock",0)
        after=trial; after_hash=program_hash(after)
        cb=_closure(before,actual,mutation,False); ca=_closure(after,actual,mutation,True)
        song,project,downstream=_components(mutation["operation"],mutation["parameters"],before,after)
        entry={"ordinal":0,"mutation_id":mutation["mutation_id"],"operation":mutation["operation"],"before_program_hash":input_hash,"after_program_hash":after_hash,"identity":input_hash==after_hash,"actual_roots":actual,"closure_before":cb,"closure_after":ca,"song_program_components":song,"project_components":project,"downstream_components":downstream}
        impact={"schema":"cps.mutation-impact-report","schema_version":"1.0.0","request_hash":request_hash,"base_program_hash":input_hash,"result_program_hash":after_hash,"identity":input_hash==after_hash,"entries":[entry]}
        impact_hash=artifact_hash("cps.mutation-impact-report/v1",impact)
        step={"ordinal":0,"mutation_id":mutation["mutation_id"],"mutation_hash":artifact_hash("cps.mutation/v1",mutation),"input_program_hash":input_hash,"status":"complete","identity":input_hash==after_hash,"actual_roots":actual,"scope_hash":artifact_hash("cps.mutation-scope/v1",actual),"closure_before":cb,"closure_after":ca,"closure_hash":artifact_hash("cps.mutation-closure/v1",{"closure_before":cb,"closure_after":ca}),"output_program_hash":after_hash,"impact_hash":artifact_hash("cps.mutation-impact/v1",entry),"error":None}
        receipt={"schema":"cps.mutation-application-receipt","schema_version":"1.0.0","request_hash":request_hash,"status":"complete","base_program_hash":input_hash,"result_program_hash":after_hash,"impact_report_hash":impact_hash,"steps":[step],"error":None,"receipt_hash":""}
        receipt["receipt_hash"]=artifact_hash("cps.mutation-application-receipt/v1",{k:v for k,v in receipt.items() if k!="receipt_hash"})
        return {"status":"success","program":after,"impact":impact,"receipt":receipt,"error":None}
    except OracleMutationError as error:
        err={"code":error.code,"stage":error.stage,"pointer":"","mutation_ordinal":error.ordinal}
        mutation_hash=artifact_hash("cps.mutation/v1",mutation)
        step={"ordinal":0,"mutation_id":mutation.get("mutation_id"),"mutation_hash":mutation_hash,"input_program_hash":input_hash,"status":"failed","identity":None,"actual_roots":actual,"scope_hash":artifact_hash("cps.mutation-scope/v1",actual) if actual is not None else None,"closure_before":None,"closure_after":None,"closure_hash":None,"output_program_hash":None,"impact_hash":None,"error":err}
        receipt={"schema":"cps.mutation-application-receipt","schema_version":"1.0.0","request_hash":request_hash,"status":"failed","base_program_hash":input_hash,"result_program_hash":None,"impact_report_hash":None,"steps":[step],"error":err,"receipt_hash":""}
        receipt["receipt_hash"]=artifact_hash("cps.mutation-application-receipt/v1",{k:v for k,v in receipt.items() if k!="receipt_hash"})
        return {"status":"failure","program":None,"impact":None,"receipt":receipt,"error":err}
