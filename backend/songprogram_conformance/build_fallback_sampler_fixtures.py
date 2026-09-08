"""Oracle-maintainer builder for fallback/sampler authoritative fixtures."""
from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from .canonical import canonical_bytes
from .fallback_sampler_oracle import SemanticError, lower_production, register_endpoint_mc, select_fallback, validate_fallback_manifest, weighted_choice

OUT = Path(__file__).parent / "fixtures" / "fallback_sampler"

def write(name, value):
    (OUT / name).write_bytes(canonical_bytes(value) + b"\n")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = json.loads((Path(__file__).parent / "schemas" / "fallback_manifest.schema.json").read_text())
    # Minimal semantic manifests are fixture protocol inputs, not JSON-Schema instances.
    tables={"bounded_scalars":[{"owner_kind":"section","field":"bars","choices":[{"value":4,"weight":1}]}],"distribution_choice_ids":[{"value":"choice_aaaaaaaaaaaaaaaaaaaa","weight":1}],"transpose_unit_vectors":[{"value":[-1,0],"weight":1},{"value":[1,0],"weight":1}],"rotate_ordinal_steps":[{"value":v,"weight":1} for v in [-4,-3,-2,-1,1,2,3,4]],"chord_references":[{"value":{"equave":"2/1","divisions":12,"steps":[0,4,7]},"weight":1}],"root_anchor_unit_vectors":[{"value":[0,-1],"weight":1},{"value":[0,1],"weight":1}],"edit_actions":[{"value":"delete","weight":1},{"value":"duplicate","weight":1}],"instrument_entry_ids":[{"value":"inst_a","weight":1}]}
    ops=["replace_bounded_scalar","replace_distribution_choice","transpose_material_vector","rotate_rhythm","replace_chord_intent_reference","replace_root_anchor_item","edit_section","swap_track_catalog_entry"]
    manifest={"maximum_attempts_per_candidate":16,"maximum_mutations":4,"stream_domain":"cps.mutation-fallback/v1","operation_table":[{"operation":op,"weight":1} for op in ops],"parameter_tables":tables}
    validate_fallback_manifest(manifest,2)
    negatives=[]
    mutations=[("duplicate",lambda m:m["parameter_tables"]["edit_actions"].append(deepcopy(m["parameter_tables"]["edit_actions"][0]))),("zero_weight",lambda m:m["parameter_tables"]["edit_actions"][0].update(weight=0)),("overflow",lambda m:[x.update(weight=(1<<64)-1) for x in m["parameter_tables"]["edit_actions"]]),("bad_vector",lambda m:m["parameter_tables"]["transpose_unit_vectors"][0].update(value=[1,1])),("bad_rotation",lambda m:m["parameter_tables"]["rotate_ordinal_steps"][0].update(value=-5)),("bad_chord",lambda m:m["parameter_tables"]["chord_references"][0]["value"].update(steps=[0,12]))]
    for name,change in mutations:
        item=deepcopy(manifest); change(item)
        try: validate_fallback_manifest(item,2); outcome="accepted"
        except SemanticError as e: outcome=str(e)
        negatives.append({"id":name,"manifest":item,"expected_error":outcome})
    weighted={"table":[{"value":"a","weight":1},{"value":"b","weight":2}],"cases":[{"draw":x,"expected":weighted_choice([{"value":"a","weight":1},{"value":"b","weight":2}],x)} for x in [0,1,2,3,(1<<64)-1]]}
    request={"root_seed":0,"run_manifest_hash":"sha256:"+"a"*64,"program_hash":"sha256:"+"b"*64,"request_hash":"sha256:"+"c"*64,"action_coordinate":{"round":2,"candidate":3},"locked_roots":[],"requested_mutation_count":1,"program":{"lattice":{"generators":["3/2","5/4"]}}}
    def row(delta,identity=False,root="mat_a"):
        return {"operation":"transpose_material_vector","owner_kind":"material","owner_id":"mat_a","field_or_index":"vector_delta","parameter":{"kind":"transpose_material_vector","material_id":"mat_a","vector_delta":delta},"parameter_weight":1,"actual_roots":[{"kind":"material","id":root}],"identity":identity}
    rows=[row([-1,0]),row([1,0])]
    fallback_success=select_fallback(request,manifest,rows)
    fallback_batch={"schema":"cps.fallback-batch-oracle","schema_version":"1.0.0","mutation_application_request_schema_version":"1.1.0","fallback_request_hash":request["request_hash"],"base_program_hash":request["program_hash"],"mutations":fallback_success["mutations"],"expected_application_request_count":1,"expected_application_receipt_count":1}
    retry_rows=[row([-1,0],True),row([1,0])]
    retry_request=deepcopy(request)
    for seed in range(1000):
        retry_request["root_seed"]=seed
        candidate=select_fallback(retry_request,manifest,retry_rows)
        if candidate["attempts_consumed"]>1: break
    locked_request=deepcopy(request); locked_request["locked_roots"]=[{"kind":"material","id":"locked"}]
    lock_rows=[row([-1,0],False,"locked"),row([1,0],False,"open")]
    fallback_lock=select_fallback(locked_request,manifest,lock_rows)
    exhaustion_request=deepcopy(request)
    try: select_fallback(exhaustion_request,manifest,[row([1,0],True)])
    except SemanticError as exc: exhaustion={"expected_error":str(exc),"maximum_attempts":manifest.get("maximum_attempts_per_candidate",16)}
    sha="sha256:"+"1"*64
    profile={"profile_id":"clean","profile_payload":{"profile_id":"clean","render_profile_id":"render_clean"},"profile_payload_hash":"sha256:"+"2"*64}
    drum={"drum_map_id":"basic","drum_map":{"kick":36,"snare":38},"drum_map_payload_hash":"sha256:"+"3"*64}
    def t(v,w=1): return [{"value":v,"weight":w}]
    role_ids={r:t("kit" if r=="drums" else r+"_inst") for r in ["drums","bass","harmony","melody","texture"]}
    role_int={r:t(8 if r!="drums" else 16) for r in role_ids}
    gain={r:t(8000) for r in role_ids}; pan={r:t(0) for r in role_ids}
    prod={"stream_domain":"cps.broad-prior-production/v1","sampler_manifest_hash":sha,"instrument_catalog_digest":"sha256:"+"4"*64,"profile_ids":t(profile),"instrument_entries_by_role":role_ids,"register_presets_by_role":{r:t([-1200000,1200000]) for r in ["bass","harmony","melody","texture"]},"polyphony_by_role":role_int,"drum_map_profiles":t(drum),"gain_q_by_role":gain,"pan_q_by_role":pan}
    catalog={"entries":[{"instrument_id":"kit","role":"drums","maximum_polyphony":32}]+[{"instrument_id":r+"_inst","role":r,"maximum_polyphony":16,"allowed_frequency_millihz":[220000,880000]} for r in ["bass","harmony","melody","texture"]]}
    req={"root_seed":7,"production_rejection_ordinal":0,"sampler_manifest_hash":sha,"instrument_catalog_digest":"sha256:"+"4"*64,"active_roles":["drums","bass","harmony"],"program":{"lattice":{"base_frequency_millihz":440000}}}
    expected=lower_production(req,prod,catalog)
    write("fallback_manifest_semantic.json",manifest); write("fallback_negative_cases.json",negatives); write("weighted_boundaries.json",weighted)
    write("fallback_request_core.json",request); write("fallback_eligible_rows.json",rows); write("fallback_success_expected.json",fallback_success)
    write("fallback_batch_expected.json",fallback_batch)
    write("fallback_retry_request_core.json",retry_request); write("fallback_retry_rows.json",retry_rows); write("fallback_retry_expected.json",candidate)
    write("fallback_lock_request_core.json",locked_request); write("fallback_lock_rows.json",lock_rows); write("fallback_lock_expected.json",fallback_lock)
    write("fallback_exhaustion_expected.json",exhaustion)
    write("register_boundary_cases.json",{"base_frequency_millihz":440000,"catalog_frequency_millihz":[220000,880000],"catalog_endpoint_mc":[register_endpoint_mc(220000,440000),register_endpoint_mc(880000,440000)],"cases":[{"register":[-1200000,1200000],"expected":"compatible"},{"register":[-1200001,1200000],"expected":"below_by_1"},{"register":[-1200000,1200001],"expected":"above_by_1"}]})
    write("production_manifest.json",prod); write("production_catalog.json",catalog); write("production_request.json",req); write("production_expected.json",expected)
    files=sorted(p.name for p in OUT.iterdir() if p.name!="manifest.json")
    write("manifest.json",{"schema":"cps.fallback-sampler-fixture-set","schema_version":"1.0.0","authority_commit":"90fdf13","files":[{"path":x,"sha256":"sha256:"+__import__('hashlib').sha256((OUT/x).read_bytes()).hexdigest()} for x in files]})

if __name__ == "__main__": main()
