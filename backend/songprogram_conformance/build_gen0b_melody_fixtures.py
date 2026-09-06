"""Generate checked-in GEN0-B/melody fixtures without production compiler code."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .canonical import canonical_bytes
from .gen0b_melody_oracle import artifact_hash, progression_result
from .identifiers import (budget_profile_digest, compiler_build_id, event_id,
    harmony_occurrence_id, program_hash, project_artifact_hash, semantic_address)
from .identifiers import resolved_chord_id
from .reference import parse_ratio, ratio_mc
from .gen0b_receipt_oracle import (LEAVES, OpcodeEmitter, child_stream,
    project_validation, trace_bnb, trace_event_lowering,
    trace_symbols_and_timeline, usage)

ROOT = Path(__file__).parent
PACK = ROOT / "fixtures" / "pack"
OUT = ROOT / "fixtures" / "compiler"


def _write(name: str, value: object) -> None:
    (OUT / name).write_bytes(canonical_bytes(value) + b"\n")


def _core_hash(chord: dict) -> str:
    core = {key: value for key, value in chord.items() if key != "id"}
    return "sha256:" + hashlib.sha256(b"cps.resolved-chord/v1\0" + canonical_bytes(core)).hexdigest()


def _bare_hash(value: object) -> str:
    return "sha256:"+hashlib.sha256(canonical_bytes(value)).hexdigest()


def _child_receipt(child: dict) -> str:
    return artifact_hash("cps.charge-receipt-child/v1.1",child)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_program = json.loads((PACK / "minimal_triad_song_program.json").read_text())
    base_project = json.loads((PACK / "resolved_triad_project.json").read_text())
    base_manifest = json.loads((PACK / "compiler_manifest_sp0.json").read_text())
    instrument_catalog=json.loads((ROOT/"fixtures"/"render"/"catalog.json").read_text())
    catalog_digest=artifact_hash("cps.instrument-catalog/v1",instrument_catalog)
    resolver_profile={"schema":"cps.resolver-profile","schema_version":"1.0.0","algorithm":"sp0-joint-bnb/v1","resolver_build_id":"gen0a-bnb-reference-oracle-v1","candidates_per_intent":24,"optimized_report_schema_version":"1.0.0","progression_algorithm":"gen0-progression-exact/v1","operation_budget_profile":"gen0-progression-exact-v1"}
    resolver_profile["profile_hash"]=artifact_hash("cps.resolver-profile/v1",resolver_profile)
    manifest=deepcopy(base_manifest); manifest["schema_version"]="1.1.0"
    manifest["resolver"]={"build_id":resolver_profile["resolver_build_id"],"algorithm":resolver_profile["algorithm"],"profile_hash":resolver_profile["profile_hash"],"search_completeness":"exact"}
    manifest["progression_resolver"]={"build_id":"fixture-progression-exact-v1","algorithm":"gen0-progression-exact/v1","profile_hash":"sha256:"+"7"*64,"search_completeness":"exact","candidates_per_intent":1,"maximum_voice_motion_millicents":2400000,"crossing_policy":"forbid"}
    profile=manifest["budget_profile"]; profile["id"]="gen0-progression-exact-v1"
    profile["root_ceilings"].update({"progression_states":12288,"progression_edges":294336})
    profile["child_ceilings"].update({"exact_arithmetic_units":500000,"ordering_units":500000,"progression_states":12288,"progression_edges":294336})
    profile["shape_limits"].update({"progression_occurrences":512,"progression_candidates_per_occurrence":24})
    profile["digest"]=""; profile["digest"]=budget_profile_digest(profile)
    program = deepcopy(base_program)
    program["program_id"] = "sp_gen0b_melody"
    program["production"]["catalog_digest"]=catalog_digest
    manifest["instrument_catalog_digest"]=catalog_digest
    manifest["build_id"]=""; manifest["build_id"]=compiler_build_id(manifest)
    program["materials"][0]["steps"] = [
        {"at_tick": i * 640, "duration_ticks": 640, "accent_q": 8000, "lane_id": None}
        for i in range(3)
    ]
    program["materials"][1]["root_anchors"] = [[0, 0]]
    program["materials"].extend([
        {"id":"rhythm_melody","kind":"rhythm_cell","length_ticks":1920,"steps":[
            {"at_tick":i*640,"duration_ticks":240,"accent_q":8000,"lane_id":None} for i in range(3)]},
        {"id":"melody_a","kind":"melody_intent","rhythm_id":"rhythm_melody","points":[
            {"relation":"chord_member","member":i,"contour":"hold"} for i in range(3)],"mapping":"zip"},
    ])
    program["tracks"].append({"id":"melody","role":"melody","instrument_id":"pi17","register_millicents":[-1200000,3600000],"maximum_polyphony":1,"drum_map":None})
    program["realizations"].append({"id":"real_melody","section_id":"sec_a","track_id":"melody","material_id":"melody_a","at_tick":0,"repeat":1,"every_ticks":1920,"rhythm_transforms":[],"pitch_transforms":[],"velocity_scale_q":10000,"gate_scale_q":10000})
    program["production"]["tracks"]["melody"] = {"gain_q":8000,"pan_q":0}

    chord = deepcopy(base_project["resolved_chords"][0])
    chord["resolver_build_id"]=manifest["resolver"]["build_id"]
    chord["id"]=""; chord["id"]=resolved_chord_id(chord)
    core_hash = _core_hash(chord)
    voices = []
    for index, target in enumerate(chord["target_voice_ordinals"]):
        absolute = [a+b for a,b in zip(chord["anchor_vector"], chord["voice_offsets"][index])]
        voices.append({"target_ordinal":target,"absolute_vector":absolute,"equave_exponent":chord["equave_exponents"][index],"exact_ratio":chord["exact_ratios"][index],"ratio_millicents":ratio_mc(parse_ratio(chord["exact_ratios"][index]))})
    voices.sort(key=lambda v:(v["ratio_millicents"],v["target_ordinal"],v["absolute_vector"],v["equave_exponent"],v["exact_ratio"]))
    candidate = {"core_hash":core_hash,"resolved_chord":chord,"domain_hash":chord["domain_hash"],"intent_hash":chord["intent_hash"],"anchor_vector":[0,0],"voices":voices,"local_pair_rms_millicents":chord["pair_rms_error_millicents"],"local_pair_max_millicents":chord["maximum_pair_error_millicents"],"local_complexity":chord["complexity_score"]}
    occ_ids = [harmony_occurrence_id("sec_a","real_harmony",0,"harmony_a",i) for i in range(3)]
    query = {"schema":"cps.progression-query","schema_version":"1.2.0","algorithm":"gen0-progression-exact/v1","numeric_contract":"cps-numeric/decimal-log2-rhe-v1","budget_profile":"gen0-progression-exact-v1","domain_hash":chord["domain_hash"],"domain_equave":"2/1","maximum_voice_motion_millicents":2400000,"crossing_policy":"forbid","occurrences":[]}
    for i, oid in enumerate(occ_ids):
        query["occurrences"].append({"id":oid,"start_tick":i*640,"duration_ticks":640,"track_id":"harmony","register_millicents":[-1200000,3600000],"maximum_polyphony":4,"overlapping_nonprogression_pitched_events":0,"intent_hash":chord["intent_hash"],"root_anchor":[0,0],"candidate_cores":[candidate]})
    result = progression_result(query)

    project = deepcopy(base_project)
    project["source_program"]["hash"] = program_hash(program)
    project["compiler"]["build_id"]=manifest["build_id"]
    project["compiler"]["resolver_build_id"]=manifest["resolver"]["build_id"]
    project["compiler"]["resolver_profile_hash"]=manifest["resolver"]["profile_hash"]
    project["compiler"]["budget_profile_digest"]=profile["digest"]
    project["compiler"]["instrument_catalog_digest"]=manifest["instrument_catalog_digest"]
    project["tracks"] = sorted(deepcopy(program["tracks"]), key=lambda x:x["id"])
    project["resolved_chords"]=[deepcopy(chord)]
    project["mix"] = deepcopy(program["production"]["tracks"])
    project["material_instances"] = [deepcopy(base_project["material_instances"][0]), {"id":"mi_melody","material_id":"melody_a","realization_id":"real_melody","section_id":"sec_a","track_id":"melody","repeat_ordinal":0,"at_tick":0,"source_program_path":"/realizations/1"}]
    project["material_instances"].sort(key=lambda x:x["id"])
    project["harmony_occurrences"] = [{"chord_index":i,"section_id":"sec_a","start_tick":i*640,"duration_ticks":640,"resolved_chord_id":chord["id"]} for i in range(3)]
    project["events"] = []
    for step in range(3):
        for shape, ratio in enumerate(chord["exact_ratios"]):
            address=semantic_address("sec_a","real_harmony",0,"harmony_a",step,shape)
            event={"id":"","kind":"note","track_id":"harmony","section_id":"sec_a","start_tick":step*640,"duration_ticks":640,"velocity":100,"articulation":"normal","drum_note":None,"ratio":ratio,"chord_index":step,"pitch_provenance":{"kind":"resolved_chord_voice","resolved_chord_id":chord["id"],"target_voice_ordinal":chord["target_voice_ordinals"][shape],"shape_voice_ordinal":shape,"anchor_vector":[0,0],"offset_vector":chord["voice_offsets"][shape],"final_vector":chord["voice_offsets"][shape],"equave_exponent":chord["equave_exponents"][shape],"final_ratio":ratio},"source":{"material_instance_id":"mi_harmony","source_step_ordinal":step,"emitted_voice_ordinal":shape,"semantic_address":address}}
            event["id"]=event_id(event); project["events"].append(event)
        shape=chord["target_voice_ordinals"].index(step)
        ratio=chord["exact_ratios"][shape]; vector=chord["voice_offsets"][shape]
        address=semantic_address("sec_a","real_melody",0,"melody_a",step,0)
        event={"id":"","kind":"note","track_id":"melody","section_id":"sec_a","start_tick":step*640,"duration_ticks":240,"velocity":100,"articulation":"normal","drum_note":None,"ratio":ratio,"chord_index":step,"pitch_provenance":{"kind":"resolved_melody","melody_intent_id":"melody_a","relation":"chord_member","active_resolved_chord_id":chord["id"],"active_target_voice_ordinal":step,"next_resolved_chord_id":None,"source_vector":vector,"relation_delta_vector":[0,0],"tonal_center_delta_vector":[0,0],"final_vector":vector,"equave_exponent":chord["equave_exponents"][shape],"final_ratio":ratio},"source":{"material_instance_id":"mi_melody","source_step_ordinal":step,"emitted_voice_ordinal":0,"semantic_address":address}}
        event["id"]=event_id(event); project["events"].append(event)
    project["events"].sort(key=lambda e:(e["start_tick"],e["track_id"].encode(),1,e["ratio"],e["source"]["semantic_address"],e["id"]))
    phash=project_artifact_hash(project)
    occurrences=[{"occurrence_id":occ_ids[i],"section_id":"sec_a","track_id":"harmony","realization_id":"real_harmony","repeat_ordinal":0,"material_id":"harmony_a","source_step_ordinal":i,"start_tick":i*640,"duration_ticks":640,"intent_id":"ci_major","intent_hash":chord["intent_hash"],"root_anchor":[0,0]} for i in range(3)]
    query_hash=artifact_hash("cps.progression-query/v1",query); result_hash=artifact_hash("cps.progression-result/v1",result)
    bindings=[]
    for i in range(3):
        event=next(e for e in project["events"] if e["track_id"]=="melody" and e["source"]["source_step_ordinal"]==i)
        shape=chord["target_voice_ordinals"].index(i)
        bindings.append({"binding_ordinal":i,"section_id":"sec_a","track_id":"melody","realization_id":"real_melody","repeat_ordinal":0,"material_id":"melody_a","source_step_ordinal":i,"point_ordinal":i,"start_tick":i*640,"duration_ticks":240,"member":i,"active_occurrence_id":occ_ids[i],"active_track_id":"harmony","project_chord_index":i,"selected_core_hash":core_hash,"resolved_chord_id":chord["id"],"shape_voice_ordinal":shape,"source_vector":chord["voice_offsets"][shape],"equave_exponent":chord["equave_exponents"][shape],"exact_ratio":chord["exact_ratios"][shape],"event_id":event["id"]})
    binding_expected={"schema":"cps.chord-member-melody-binding-expected","schema_version":"1.0.0","source_program_hash":program_hash(program),"project_hash":phash,"bindings":bindings}
    failure={"schema":"cps.chord-member-melody-failure-cases","schema_version":"1.0.0","cases":[{"id":"member_absent","mutation":{"points":[{"relation":"chord_member","member":7,"contour":"hold"}]},"expected_error":"MELODY_HARMONY_CONFLICT"},{"id":"boundary_crossing","interval":{"start_tick":600,"duration_ticks":80},"expected_error":"MELODY_HARMONY_CONFLICT"}]}

    # Complete independent logical stream and receipt.
    compile_request={"song_program":program,"compiler_manifest":manifest,
                     "instrument_catalog_digest":manifest["instrument_catalog_digest"]}
    input_hash=artifact_hash("cps.compile-request/v1",compile_request)
    emitter=OpcodeEmitter(input_hash); emitter.structural_parse(program)
    trace_symbols_and_timeline(emitter,program)
    emitter.charged_sort(len(occurrences))
    domain={"equave":program["lattice"]["equave"],"generators":program["lattice"]["generators"],
            "coordinate_bounds":program["lattice"]["coordinate_bounds"],"register_bounds":program["lattice"]["register_bounds"],
            "maximum_odd_limit":program["lattice"]["maximum_odd_limit"],
            "maximum_reduced_complexity_bits":program["lattice"]["pitch_exploration"]["maximum_reduced_complexity_bits"]}
    oracle_query={"schema":"cps.sp0-oracle-query/v1","numeric_contract":manifest["numeric_contract"],"domain":domain,
        "intent":{"reference_equave":program["chord_intents"][0]["reference"]["equave"],
                  "reference_divisions":program["chord_intents"][0]["reference"]["divisions"],
                  "steps":program["chord_intents"][0]["reference"]["steps"],
                  **program["chord_intents"][0]["voicing"],**program["chord_intents"][0]["recognition"],
                  "complexity_budget":program["chord_intents"][0]["complexity_budget"]},
        "anchor":{"vector":[0,0],"equave_exponent":0}}
    chord_query_hash=_bare_hash(oracle_query); chord_child_id="chord_"+chord_query_hash[7:23]
    stats=trace_bnb(emitter,program["lattice"],program["chord_intents"][0],[0,0],chord_child_id,1,(-1200000,3600000))
    winner=stats["incumbents"][0]
    assert [f"{voice[2].numerator}/{voice[2].denominator}" for voice in winner[1]] == chord["exact_ratios"]
    assert list(winner[2]) == chord["pair_errors_millicents"]
    assert list(winner[0][:3]) == [chord["pair_rms_error_millicents"],chord["maximum_pair_error_millicents"],chord["complexity_score"]]
    emitter.charged_sort(len(candidate["voices"]),chord_child_id)
    progression_query_hash=artifact_hash("cps.progression-query/v1",query)
    progression_child_id="progression_"+progression_query_hash[7:23]
    emitter.progression([item["candidate_cores"] for item in query["occurrences"]],progression_child_id)
    emitter.charged_sort(len(project["resolved_chords"])); emitter.charged_sort(len(project["harmony_occurrences"]))
    emitter.charged_sort(len(bindings)); trace_event_lowering(emitter,project); emitter.charged_sort(len(project["events"]))
    project_validation(emitter,project)
    root_stream=emitter.stream()
    chord_stream=child_stream(root_stream,chord_child_id,chord_query_hash)
    progression_stream=child_stream(root_stream,progression_child_id,progression_query_hash)
    def child_usage(stream: dict, names: tuple[str,...]) -> dict:
        all_usage=usage(stream["records"]); result={name:all_usage[name] for name in names}; result["total_logical_units"]=sum(result.values()); return result
    chord_child={"kind":"chord_query","query_id":chord_child_id,"input_hash":chord_query_hash,"status":"complete",
        "usage":child_usage(chord_stream,("chord_search_nodes","pair_relations","numeric_eval_units","exact_arithmetic_units","ordering_units")),"opcode_stream_hash":chord_stream["stream_hash"]}
    progression_child={"kind":"progression_query","query_id":progression_child_id,"input_hash":progression_query_hash,"status":"complete",
        "usage":child_usage(progression_stream,("progression_states","progression_edges")),"opcode_stream_hash":progression_stream["stream_hash"]}
    receipt={"schema":"cps.charge-receipt","schema_version":"1.1.0","budget_profile_id":"gen0-progression-exact-v1",
        "budget_profile_digest":profile["digest"],"input_hash":input_hash,"status":"complete","usage":usage(root_stream["records"]),
        "children":[chord_child,progression_child],"opcode_stream_hash":root_stream["stream_hash"]}
    receipt_digest=artifact_hash("cps.charge-receipt/v1.1",receipt)
    manifest_hash=artifact_hash("cps.compiler-manifest/v1.1",manifest)
    evidence={"schema":"cps.gen0b-compiler-evidence","schema_version":"1.0.0","source_program_hash":program_hash(program),
        "compiler_manifest_hash":manifest_hash,"occurrences":occurrences,
        "gen0a_results":[{"query_hash":chord_query_hash,"domain_hash":chord["domain_hash"],"intent_hash":chord["intent_hash"],
            "root_anchor":[0,0],"requested_k":1,"ordered_core_hashes":[core_hash],"child_receipt_digest":_child_receipt(chord_child)}],
        "progression_runs":[{"query_ordinal":0,"track_id":"harmony","occurrence_ids":occ_ids,"query":query,
            "query_hash":progression_query_hash,"result":result,"result_hash":result_hash,
            "child_receipt_digest":_child_receipt(progression_child),"selected":[{"occurrence_id":occ_ids[i],
                "selected_core_hash":core_hash,"resolved_chord_id":chord["id"],"project_chord_index":i} for i in range(3)]}],
        "resolved_chord_ids":[chord["id"]],"event_ids":[item["id"] for item in project["events"]],"project_hash":phash,
        "root_receipt_digest":receipt_digest}
    evidence["evidence_hash"]=artifact_hash("cps.gen0b-compiler-evidence/v1",evidence)
    melody_report={"schema":"cps.chord-member-melody-report","schema_version":"1.0.0","source_program_hash":program_hash(program),
        "gen0b_evidence_hash":evidence["evidence_hash"],"project_hash":phash,"bindings":bindings}
    melody_report["report_hash"]=artifact_hash("cps.chord-member-melody-report/v1",melody_report)
    compile_report={"schema":"cps.compile-report","schema_version":"1.1.0","source_program_hash":program_hash(program),
        "compiler_manifest_hash":manifest_hash,"compiler_build_id":manifest["build_id"],"budget_profile_digest":profile["digest"],
        "status":"success","project_hash":phash,"evidence_hash":evidence["evidence_hash"],"receipt":receipt,
        "search_statistics":{"chord_query_count":1,"chord_candidates_examined":stats["complete_nodes"],
            "chord_eligible_candidates":stats["eligible"],"progression_query_count":1,
            "progression_states":3,"progression_edges":2},"error":None}
    _write("gen0b_root_opcode_stream.json",root_stream); _write("gen0b_chord_opcode_stream.json",chord_stream)
    _write("gen0b_progression_opcode_stream.json",progression_stream); _write("gen0b_charge_receipt.json",receipt)
    _write("gen0b_compiler_evidence.json",evidence); _write("gen0b_compile_report.json",compile_report)
    _write("chord_member_melody_report.json",melody_report)
    _write("resolver_profile_gen0a_bnb.json",resolver_profile); _write("gen0b_compiler_manifest.json",manifest); _write("gen0b_melody_song_program.json",program); _write("gen0b_progression_query.json",query); _write("gen0b_progression_result.json",result)
    _write("gen0b_melody_project.json",project); _write("chord_member_melody_bindings.json",binding_expected); _write("chord_member_melody_failures.json",failure)
    files=[name for name in sorted(p.name for p in OUT.glob("*.json")) if name != "gen0b_melody_fixture_set.json"]
    fixture={"schema":"cps.gen0b-melody-fixture-set","schema_version":"1.0.0","files":files,
             "file_sha256":{name:"sha256:"+hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in files}}
    _write("gen0b_melody_fixture_set.json",fixture)


if __name__ == "__main__": main()
