"""Regenerate authoritative search-decision fixtures and expected sidecars."""

from __future__ import annotations

import json
from pathlib import Path

from .search_decision_oracle import (
    DecisionContractError, action_id, archive_admission, challenger_acceptance,
    comparison_set_hash, near_duplicate, reserve_render, round_decision,
    validate_action, validate_charge, validate_components,
)

OUT = Path(__file__).parent / "fixtures" / "search_decisions"
H = lambda digit: "sha256:" + digit * 64


def write(name: str, value: object) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    metrics = [
        {"id":"genre","direction":"maximize","margin_q":10,"ordinal":0,"source":{"artifact_kind":"evaluation_report","schema_hash":H("a"),"json_pointer":"/metrics/genre"}},
        {"id":"artifact","direction":"minimize","margin_q":5,"ordinal":1,"source":{"artifact_kind":"evaluation_report","schema_hash":H("a"),"json_pointer":"/metrics/artifact"}},
    ]
    success = {
        "archive": {"directions":["maximize","minimize"],"candidate_quality":[90,2],"candidate_hash":H("1"),"incumbent_quality":[80,4],"incumbent_hash":H("2"),"eligible":True},
        "challenger": {"metrics":metrics,"challenger":[120,20],"champion":[100,30],"challenger_hash":H("1"),"champion_hash":H("2"),"hard_checks_passed":True},
        "near_duplicate": {"candidate_hash":H("3"),"threshold_q":100,"comparisons":[{"program_hash":H("1"),"fingerprint_hash":H("4"),"component_distances_q":[40,30],"aggregate_distance_q":70},{"program_hash":H("2"),"fingerprint_hash":H("5"),"component_distances_q":[90,20],"aggregate_distance_q":110}]},
        "stopping": {"improved":True,"patience_before":4,"patience_limit":5,"round_":2,"maximum_rounds":10,"cancelled":False,"budget_exhausted":False,"accepted":False},
        "cancellation": {"run_hash":H("a"),"coordinate":{"round":2,"phase_ordinal":7,"candidate_ordinal":3}},
        "render": {"used_before":1000,"requested":400,"ceiling":2000},
    }
    success_expected = {
        "archive": archive_admission(**success["archive"]),
        "challenger": challenger_acceptance(**success["challenger"]),
        "near_duplicate": near_duplicate(**success["near_duplicate"]),
        "comparison_set_hash": comparison_set_hash([H("1"),H("2")]),
        "stopping": round_decision(**success["stopping"]),
        "cancellation_action_id": action_id(success["cancellation"]["run_hash"], **{"round_":2,"phase":7,"candidate":3}),
        "render": reserve_render(**success["render"]),
    }
    boundaries = {
        "archive_empty": {"directions":["maximize"],"candidate_quality":[1],"candidate_hash":H("1"),"incumbent_quality":None,"incumbent_hash":None,"eligible":True},
        "archive_hash_tie": {"directions":["maximize"],"candidate_quality":[1],"candidate_hash":H("1"),"incumbent_quality":[1],"incumbent_hash":H("2"),"eligible":True},
        "challenger_exact_margins": {"metrics":metrics,"challenger":[110,25],"champion":[100,30],"challenger_hash":H("1"),"champion_hash":H("2"),"hard_checks_passed":True},
        "near_exact_threshold": {"candidate_hash":H("3"),"threshold_q":100,"comparisons":[{"program_hash":H("1"),"fingerprint_hash":H("4"),"component_distances_q":[60,40],"aggregate_distance_q":100}]},
        "near_threshold_plus_one": {"candidate_hash":H("3"),"threshold_q":99,"comparisons":[{"program_hash":H("1"),"fingerprint_hash":H("4"),"component_distances_q":[60,40],"aggregate_distance_q":100}]},
        "render_exact": {"used_before":600,"requested":400,"ceiling":1000},
        "render_plus_one": {"used_before":600,"requested":401,"ceiling":1000},
        "stop_precedence": {"improved":False,"patience_before":4,"patience_limit":5,"round_":9,"maximum_rounds":10,"cancelled":True,"budget_exhausted":True,"accepted":True},
        "patience_exact": {"improved":False,"patience_before":4,"patience_limit":5,"round_":1,"maximum_rounds":10,"cancelled":False,"budget_exhausted":False,"accepted":False},
    }
    boundary_expected = {
        "archive_empty": archive_admission(**boundaries["archive_empty"]),
        "archive_hash_tie": archive_admission(**boundaries["archive_hash_tie"]),
        "challenger_exact_margins": challenger_acceptance(**boundaries["challenger_exact_margins"]),
        "near_exact_threshold": near_duplicate(**boundaries["near_exact_threshold"]),
        "near_threshold_plus_one": near_duplicate(**boundaries["near_threshold_plus_one"]),
        "render_exact": reserve_render(**boundaries["render_exact"]),
        "render_plus_one": reserve_render(**boundaries["render_plus_one"]),
        "stop_precedence": round_decision(**boundaries["stop_precedence"]),
        "patience_exact": round_decision(**boundaries["patience_exact"]),
    }
    valid_action = {"run_hash":H("a"),"round":1,"phase_ordinal":3,"candidate_ordinal":2}
    valid_action["action_id"] = action_id(valid_action["run_hash"],1,3,2)
    negatives = [
        {"id":"action_id_mismatch","call":"validate_action","input":{**valid_action,"action_id":"act_"+"a"*26},"expected":{"code":"ACTION_ID_MISMATCH","pointer":"/action_id"}},
        {"id":"charge_arithmetic","call":"validate_charge","input":{"used_before":600,"requested_frames":400,"ceiling":1000,"reservation_status":"reserved","used_after":999},"expected":{"code":"RENDER_CHARGE_ARITHMETIC_MISMATCH","pointer":""}},
        {"id":"comparison_unsorted","call":"comparison_set_hash","input":[H("2"),H("1")],"expected":{"code":"COMPARISON_SET_NOT_SORTED","pointer":""}},
        {"id":"duplicate_component","call":"validate_components","input":[metrics[0],{**metrics[1],"id":"genre"}],"expected":{"code":"DUPLICATE_COMPONENT_ID","pointer":""}},
        {"id":"ordinal_gap","call":"validate_components","input":[metrics[0],{**metrics[1],"ordinal":2}],"expected":{"code":"INVALID_COMPONENT_ORDINAL","pointer":""}},
        {"id":"render_zero","call":"reserve_render","input":{"used_before":0,"requested":0,"ceiling":10},"expected":{"code":"INVALID_RENDER_BUDGET","pointer":""}},
    ]
    funcs = {"validate_action":lambda x:validate_action(x),"validate_charge":lambda x:validate_charge(x),"comparison_set_hash":comparison_set_hash,"validate_components":validate_components,"reserve_render":lambda x:reserve_render(**x)}
    for case in negatives:
        try: funcs[case["call"]](case["input"])
        except DecisionContractError as exc:
            assert {"code":exc.code,"pointer":exc.pointer} == case["expected"]
        else: raise AssertionError(case["id"])
    write("success/cases.json", success); write("success/expected.json", success_expected)
    write("boundary/cases.json", boundaries); write("boundary/expected.json", boundary_expected)
    write("negative/cases.json", [{k:v for k,v in case.items() if k != "expected"} for case in negatives])
    write("negative/expected.json", {case["id"]:case["expected"] for case in negatives})
    write("coverage.json", {
        "archive_empty_occupied_tie":"success/archive,boundary/archive_empty,boundary/archive_hash_tie",
        "pareto_directions_and_exact_margin":"success/challenger,boundary/challenger_exact_margins",
        "duplicate_threshold_adjacent":"success/near_duplicate,boundary/near_exact_threshold,boundary/near_threshold_plus_one",
        "render_exact_and_plus_one":"boundary/render_exact,boundary/render_plus_one",
        "patience_and_simultaneous_stop":"boundary/patience_exact,boundary/stop_precedence",
        "action_id_and_cancel_cutoff":"success/cancellation,negative/action_id_mismatch",
        "semantic_negatives":"negative/cases.json"
    })
    write("manifest.json", {"schema":"cps.search-decision-fixture-manifest","schema_version":"1.0.0","oracle":"backend.songprogram_conformance.search_decision_oracle","success":"success/cases.json","success_expected":"success/expected.json","boundary":"boundary/cases.json","boundary_expected":"boundary/expected.json","negative":"negative/cases.json","negative_expected":"negative/expected.json","coverage":"coverage.json"})


if __name__ == "__main__": main()
