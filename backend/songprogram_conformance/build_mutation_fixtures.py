"""Build the checked-in authoritative Mutation 1.1 fixture suite."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .mutation_oracle import artifact_hash, canonical_lf, evaluate, program_hash, roots


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_digest(catalog: dict[str, Any]) -> str:
    return artifact_hash("cps.instrument-catalog/v1", catalog)


def _base() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    program = _read(FIXTURES / "pack" / "minimal_triad_song_program.json")
    catalog = _read(FIXTURES / "render" / "catalog.json")
    choices = _read(FIXTURES / "search" / "mutation_choice_catalog.json")
    program["form"].append({**program["form"][0], "id": "sec_b", "role": "outro"})
    program["tracks"] += [{"id":"drums","role":"drums","instrument_id":"drum_fixture_kit","register_millicents":None,"maximum_polyphony":8,"drum_map":{"kick":36}}]
    program["tracks"][0]["instrument_id"] = "pitched_fixture_2_1"
    program["materials"][0]["steps"] = [
        {"at_tick":0,"duration_ticks":480,"accent_q":8000,"lane_id":None},
        {"at_tick":960,"duration_ticks":480,"accent_q":7000,"lane_id":None},
    ]
    program["materials"][1]["root_anchors"] = [[0,0],[1,0]]
    program["materials"][1]["chord_intent_ids"] = ["ci_major","ci_major"]
    program["materials"].append({"id":"rhythm_drums","kind":"rhythm_cell","length_ticks":1920,"steps":[{"at_tick":0,"duration_ticks":120,"accent_q":9000,"lane_id":"kick"}]})
    program["realizations"].append({"id":"real_drums","section_id":"sec_b","track_id":"drums","material_id":"rhythm_drums","at_tick":0,"repeat":1,"every_ticks":1920,"rhythm_transforms":[],"pitch_transforms":[],"velocity_scale_q":10000,"gate_scale_q":10000})
    program["production"]["tracks"]["drums"]={"gain_q":8000,"pan_q":0}
    program["production"]["catalog_digest"]=_catalog_digest(catalog)
    return program, choices, catalog


OPS: list[tuple[str, dict[str, Any], list[dict[str,str]], dict[str,Any]]] = [
    ("replace_bounded_scalar", {"kind":"replace_bounded_scalar","owner_kind":"section","owner_id":"sec_a","field":"bars","value":2,"minimum":1,"maximum":32}, [{"kind":"global_form","id":"global_form"},{"kind":"section","id":"sec_a"}], {"value":1}),
    ("replace_distribution_choice", {"kind":"replace_distribution_choice","owner_kind":"material","owner_id":"harmony_a","field":"mapping","choice_id":"choice_jye5ymjjjgoi5lj6ix6o"}, [{"kind":"material","id":"harmony_a"}], {"choice_id":"choice_tnwjgh52rbcsot6geclq"}),
    ("transpose_material_vector", {"kind":"transpose_material_vector","material_id":"harmony_a","vector_delta":[1,0]}, [{"kind":"material","id":"harmony_a"}], {"vector_delta":[0,0]}),
    ("rotate_rhythm", {"kind":"rotate_rhythm","rhythm_id":"rhythm_chord","steps":1}, [{"kind":"rhythm","id":"rhythm_chord"}], {"steps":63}),
    ("replace_chord_intent_reference", {"kind":"replace_chord_intent_reference","chord_intent_id":"ci_major","reference_equave":"2/1","divisions":12,"steps":[0,3,7]}, [{"kind":"chord_intent","id":"ci_major"}], {"reference_equave":"3/1","divisions":96,"steps":[0,47,95]}),
    ("replace_root_anchor_item", {"kind":"replace_root_anchor_item","material_id":"harmony_a","index":1,"vector":[1,1]}, [{"kind":"material","id":"harmony_a"}], {"index":0,"vector":[-1,-1]}),
    ("edit_section", {"kind":"edit_section","action":"duplicate","section_id":"sec_a","insert_after_section_id":"sec_a"}, [{"kind":"global_form","id":"global_form"},{"kind":"section","id":"sec_a"}], {"action":"delete","section_id":"sec_b","insert_after_section_id":None}),
    ("swap_track_catalog_entry", {"kind":"swap_track_catalog_entry","track_id":"harmony","instrument_id":"pitched_fixture_3_1"}, [{"kind":"track","id":"harmony"}], {"track_id":"drums","instrument_id":"drum_fixture_kit"}),
]


def _mutation(program: dict[str,Any], index: int, operation: str, parameters: dict[str,Any], scope: list[dict[str,str]]) -> dict[str,Any]:
    alphabet="abcdefghijklmnopqrstuvwxyz234567"
    ident="".join(alphabet[(index+i)%len(alphabet)] for i in range(20))
    return {"schema":"cps.mutation","schema_version":"1.0.0","mutation_id":"mut_"+ident,"base_program_hash":program_hash(program),"operation":operation,"declared_scope":sorted(scope,key=lambda x:(x["kind"].encode(),x["id"].encode())),"parameters":parameters}


def _negative(operation: str, parameters: dict[str,Any]) -> tuple[dict[str,Any],str]:
    value=copy.deepcopy(parameters)
    if operation=="replace_bounded_scalar": value["minimum"]=0
    elif operation=="replace_distribution_choice": value["choice_id"]="choice_aaaaaaaaaaaaaaaaaaaa"
    elif operation=="transpose_material_vector": value["vector_delta"]=[1]
    elif operation=="rotate_rhythm": value["rhythm_id"]="missing"
    elif operation=="replace_chord_intent_reference": value["steps"]=[0,0]
    elif operation=="replace_root_anchor_item": value["index"]=63
    elif operation=="edit_section": value["insert_after_section_id"]="missing"
    elif operation=="swap_track_catalog_entry": value["instrument_id"]="drum_fixture_kit"
    code={"replace_distribution_choice":"MUTATION_CHOICE_UNRESOLVED","rotate_rhythm":"MUTATION_REFERENCE_NOT_FOUND","edit_section":"MUTATION_REFERENCE_NOT_FOUND"}.get(operation,"MUTATION_PARAMETER_INVALID")
    return value,code


def build(path: Path | None = None) -> dict[str,Any]:
    destination=path or FIXTURES/"mutation"
    destination.mkdir(parents=True,exist_ok=True)
    program,choices,catalog=_base(); cases=[]
    for op_index,(operation,success,scope,boundary_patch) in enumerate(OPS):
        variants=[]
        variants.append(("success",copy.deepcopy(success),scope,[],None))
        neg,code=_negative(operation,success); neg_scope=scope
        if operation=="rotate_rhythm" and neg["rhythm_id"]=="missing": neg_scope=[{"kind":"rhythm","id":"missing"}]
        variants.append(("negative",neg,neg_scope,[],code))
        variants.append(("scope",copy.deepcopy(success),scope+[{"kind":"track","id":"harmony"}],[],"MUTATION_SCOPE_MISMATCH"))
        variants.append(("lock",copy.deepcopy(success),scope,[sorted(scope,key=lambda x:(x["kind"],x["id"]))[0]],"MUTATION_LOCKED"))
        boundary={**copy.deepcopy(success),**boundary_patch}; boundary_scope=scope
        if operation=="edit_section": boundary_scope=[{"kind":"global_form","id":"global_form"},{"kind":"section","id":"sec_b"}]
        if operation=="swap_track_catalog_entry": boundary_scope=[{"kind":"track","id":"drums"}]
        variants.append(("boundary",boundary,boundary_scope,[],None))
        for variant_index,(coverage,parameters,declared,locks,expected_code) in enumerate(variants):
            mutation=_mutation(program,op_index*5+variant_index,operation,parameters,declared)
            run=_read(FIXTURES/"search"/"run_manifest.json")
            raw_hash=lambda p: "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
            run["mutation_schema_hash"]=raw_hash(ROOT/"schemas"/"mutation.schema.json")
            run["mutation_choice_catalog_hash"]=artifact_hash("cps.mutation-choice-catalog/v1",choices)
            request_core={"schema":"cps.mutation-application-request","schema_version":"1.0.0","contract":"cps-mutation-application/v1","contract_sha256":raw_hash(ROOT.parents[1]/"docs"/"song_program_mutation_application_contract.md"),"mutation_schema_sha256":raw_hash(ROOT/"schemas"/"mutation.schema.json"),"request_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_application_request.schema.json"),"impact_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_impact_report.schema.json"),"receipt_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_application_receipt.schema.json"),"action_id":"act_aaaaaaaaaaaaaaaaaaaaaaaaaa","run_manifest_hash":artifact_hash("cps.search-run-manifest/v1",run),"run_manifest":run,"base_program_hash":program_hash(program),"base_program":program,"mutation_choice_catalog_hash":artifact_hash("cps.mutation-choice-catalog/v1",choices),"mutation_choice_catalog":choices,"instrument_catalog_digest":_catalog_digest(catalog),"instrument_catalog":catalog,"locked_roots":locks,"mutations":[mutation]}
            request_hash=artifact_hash("cps.mutation-application-request/v1",request_core)
            observed=evaluate(program,mutation,locks,choices,catalog,request_hash)
            if expected_code is not None and observed["error"]["code"]!=expected_code: raise AssertionError((operation,coverage,observed))
            cases.append({"case_id":f"{operation}_{coverage}","operation":operation,"coverage":coverage,"request":request_core,"request_hash":request_hash,"expected":observed})
    # A drum swap whose selected kit lacks the track's required note mapping.
    bad_catalog=copy.deepcopy(catalog)
    drum=next(x for x in bad_catalog["entries"] if x["kind"]=="drum_kit")
    drum["note_map"][0]["drum_note"]=37
    bad_program=copy.deepcopy(program); bad_program["production"]["catalog_digest"]=_catalog_digest(bad_catalog)
    parameters={"kind":"swap_track_catalog_entry","track_id":"drums","instrument_id":"drum_fixture_kit"}
    mutation=_mutation(bad_program,40,"swap_track_catalog_entry",parameters,[{"kind":"track","id":"drums"}])
    run=_read(FIXTURES/"search"/"run_manifest.json"); raw_hash=lambda p:"sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
    run["mutation_schema_hash"]=raw_hash(ROOT/"schemas"/"mutation.schema.json"); run["mutation_choice_catalog_hash"]=artifact_hash("cps.mutation-choice-catalog/v1",choices)
    request={"schema":"cps.mutation-application-request","schema_version":"1.0.0","contract":"cps-mutation-application/v1","contract_sha256":raw_hash(ROOT.parents[1]/"docs"/"song_program_mutation_application_contract.md"),"mutation_schema_sha256":raw_hash(ROOT/"schemas"/"mutation.schema.json"),"request_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_application_request.schema.json"),"impact_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_impact_report.schema.json"),"receipt_schema_sha256":raw_hash(ROOT/"schemas"/"mutation_application_receipt.schema.json"),"action_id":"act_aaaaaaaaaaaaaaaaaaaaaaaaaa","run_manifest_hash":artifact_hash("cps.search-run-manifest/v1",run),"run_manifest":run,"base_program_hash":program_hash(bad_program),"base_program":bad_program,"mutation_choice_catalog_hash":artifact_hash("cps.mutation-choice-catalog/v1",choices),"mutation_choice_catalog":choices,"instrument_catalog_digest":_catalog_digest(bad_catalog),"instrument_catalog":bad_catalog,"locked_roots":[],"mutations":[mutation]}
    request_hash=artifact_hash("cps.mutation-application-request/v1",request); observed=evaluate(bad_program,mutation,[],choices,bad_catalog,request_hash)
    assert observed["error"]["code"]=="MUTATION_PARAMETER_INVALID"
    cases.append({"case_id":"swap_track_catalog_entry_note_map_missing","operation":"swap_track_catalog_entry","coverage":"negative","request":request,"request_hash":request_hash,"expected":observed})
    suite={"schema":"cps.mutation-fixture-suite","schema_version":"1.0.0","cases":cases}
    (destination/"cases.json").write_bytes(canonical_lf(suite))
    manifest={"schema":"cps.mutation-fixture-manifest","schema_version":"1.0.0","files":[{"path":"cases.json","sha256":"sha256:"+hashlib.sha256((destination/"cases.json").read_bytes()).hexdigest()}]}
    (destination/"manifest.json").write_bytes(canonical_lf(manifest))
    return suite


if __name__ == "__main__": build()
