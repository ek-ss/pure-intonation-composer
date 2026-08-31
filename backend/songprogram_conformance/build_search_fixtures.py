"""Build normative GEN0-D manifests, oracle traces, CAS, and replay fixtures."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, cast

from .search_oracle import action_id, canonical_bytes, choose, draw, manifest_digest, seal_record, sha, stream_key


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / "fixtures" / "search"
SCHEMAS = ROOT / "schemas"
ZERO = "sha256:" + "0" * 64


def _hash_file(path: Path) -> str:
    return sha(path.read_bytes())


def _choice(*pairs: tuple[Any, int]) -> list[dict[str, Any]]:
    return [{"value": value, "weight": weight} for value, weight in pairs]


def _write(out: Path, name: str, value: object) -> None:
    (out / name).write_bytes(canonical_bytes(value))


def build(out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cas = out / "cas" / "sha256"
    cas.mkdir(parents=True, exist_ok=True)
    for old in cas.glob("*/*"):
        old.unlink()
    for directory in cas.glob("*"):
        if directory.is_dir():
            directory.rmdir()

    sampler = {
        "schema": "cps.sampler-manifest", "schema_version": "1.0.0", "algorithm": "broad_prior_v1",
        "choice_algorithm": "sha256-u64-mod-cumulative/v1", "stream_algorithm": "path-addressed-sha256/v1",
        "song_program_schema_hash": _hash_file(SCHEMAS / "song_program_0_1.schema.json"),
        "compiler_manifest_hash": _hash_file(ROOT / "fixtures" / "pack" / "compiler_manifest_sp0.json"),
        "instrument_catalog_digest": json.loads((ROOT / "fixtures" / "render" / "render_manifest.json").read_text())["catalog_digest"],
        "maximum_rejections_per_seed": 32,
        "limits": {"minimum_sections": 3, "maximum_sections": 8, "minimum_bars": 16, "maximum_bars": 64, "minimum_materials": 2, "maximum_materials": 5, "minimum_sounding_roles": 3, "maximum_transforms_per_recall": 3},
        "tables": {
            "section_count": _choice((3, 20), (4, 35), (5, 25), (6, 12), (7, 6), (8, 2)),
            "section_role": _choice(("intro", 8), ("verse", 20), ("build", 14), ("drop", 24), ("break", 10), ("final", 14), ("outro", 10)),
            "section_bars": _choice((4, 45), (8, 40), (12, 10), (16, 5)), "total_bars": _choice((16, 10), (24, 20), (32, 35), (40, 20), (48, 10), (64, 5)),
            "material_count": _choice((2, 15), (3, 35), (4, 35), (5, 15)), "material_kind": _choice(("rhythm", 25), ("direct_vector", 25), ("harmony_intent", 30), ("melody_intent", 20)),
            "active_roles": _choice((["drums", "bass", "harmony"], 25), (["drums", "harmony", "melody"], 25), (["drums", "bass", "harmony", "melody"], 40), (["bass", "harmony", "melody", "texture"], 10)),
            "equave_domain": _choice(({"equave": "2/1", "generators": ["3/1", "5/1"], "coordinate_bounds": [[-6, 6], [-5, 5]], "register_bounds": [-3, 3]}, 65), ({"equave": "3/1", "generators": ["2/1", "5/1"], "coordinate_bounds": [[-6, 6], [-5, 5]], "register_bounds": [-2, 2]}, 35)),
            "rhythm_grid": _choice((120, 35), (240, 40), (480, 20), (60, 5)), "rhythm_density": _choice((2500, 15), (4000, 30), (5500, 35), (7000, 20)),
            "chord_reference": _choice(({"equave": "2/1", "divisions": 12, "steps": [0, 4, 7]}, 28), ({"equave": "2/1", "divisions": 12, "steps": [0, 3, 7, 10]}, 24), ({"equave": "2/1", "divisions": 12, "steps": [0, 4, 7, 11]}, 24), ({"equave": "3/1", "divisions": 13, "steps": [0, 4, 8]}, 24)),
            "recall_decision": _choice((False, 35), (True, 65)), "transform_count": _choice((1, 55), (2, 35), (3, 10)), "transform_type": _choice(("rotate", 100), ("identity", 0)),
            "rotate_amount": _choice((-3, 10), (-2, 15), (-1, 25), (1, 25), (2, 15), (3, 10)),
            "track_instrument_by_role": _choice(({"drums":"drum_fixture_kit","bass":"pitched_fixture_2_1","harmony":"pitched_fixture_2_1","melody":"pitched_fixture_3_1","texture":"pitched_fixture_3_1"}, 60), ({"drums":"drum_fixture_kit","bass":"pitched_fixture_3_1","harmony":"pitched_fixture_3_1","melody":"pitched_fixture_2_1","texture":"pitched_fixture_2_1"}, 40)),
            "gain_q": _choice((6500, 15), (7500, 35), (8500, 35), (9500, 15)), "pan_q": _choice((-5000, 15), (-2500, 20), (0, 30), (2500, 20), (5000, 15)),
        },
        "decision_program": [
            {"ordinal": i, "stage": stage, "path": path, "table": table, "repeat": repeat}
            for i, (stage, path, table, repeat) in enumerate([
                ("form", ["form", "section_count"], "section_count", "once"), ("form", ["form", "total_bars"], "total_bars", "once"), ("form", ["form", "section", "{section}", "role"], "section_role", "per_section"), ("form", ["form", "section", "{section}", "bars"], "section_bars", "per_section"),
                ("materials", ["materials", "count"], "material_count", "once"), ("materials", ["materials", "{material}", "kind"], "material_kind", "per_material"), ("materials", ["lattice", "domain"], "equave_domain", "once"), ("materials", ["materials", "{material}", "rhythm_grid"], "rhythm_grid", "per_material"), ("materials", ["materials", "{material}", "rhythm_density"], "rhythm_density", "per_material"), ("materials", ["materials", "{material}", "chord_reference"], "chord_reference", "per_material"),
                ("realizations", ["section", "{section}", "recall"], "recall_decision", "per_section"), ("realizations", ["recall", "{recall}", "transform_count"], "transform_count", "per_recall"), ("realizations", ["recall", "{recall}", "transform", "type"], "transform_type", "per_recall"), ("realizations", ["recall", "{recall}", "transform", "rotate"], "rotate_amount", "per_recall"),
                ("tracks", ["tracks", "active_roles"], "active_roles", "once"), ("tracks", ["tracks", "instrument_map"], "track_instrument_by_role", "once"), ("production", ["production", "{role}", "gain"], "gain_q", "per_role"), ("production", ["production", "{role}", "pan"], "pan_q", "per_role")
            ])
        ],
    }
    _write(out, "sampler_manifest.json", sampler)

    descriptor = {"schema":"cps.descriptor-spec","schema_version":"1.0.0","algorithm":"gen0-symbolic-descriptors/v1","project_schema_version":"1.2.0","lineage_index_schema_version":"1.0.0","quantization_ticks":120,"maximum_quantization_error_ticks":30,"minimum_recurrence_event_ticks":60,"foreground_roles":["melody"],"drums_are_foreground":True,"syncopation_maximum_per_event":5,"axes":[{"id":"rhythmic_syncopation_q","null_archived":False,"bin_edges":[0,2000,4000,6000,8000,10001]},{"id":"material_recurrence_distance_q","null_archived":False,"bin_edges":[0,2000,4000,6000,8000,10001]}]}
    fingerprint = {"schema":"cps.fingerprint-spec","schema_version":"1.0.0","algorithm":"gen0-musical-fingerprint/v1","time_quantization_ticks":120,"transposition_normalization":"first-tonal-center-zero","components":[{"id":"section_bars","distance":"padded_hamming","weight":1200},{"id":"role_time_grid","distance":"multiset_jaccard","weight":2400},{"id":"root_anchor_deltas","distance":"set_jaccard","weight":1600},{"id":"chord_steps","distance":"padded_hamming","weight":1800},{"id":"lineage_edges","distance":"multiset_jaccard","weight":1800},{"id":"sounding_intervals","distance":"multiset_jaccard","weight":1200}],"near_duplicate_threshold_q":850}
    _write(out, "descriptor_spec.json", descriptor)
    _write(out, "fingerprint_spec.json", fingerprint)
    descriptor_hash = manifest_digest("cps.descriptor-spec/v1", descriptor)
    fingerprint_hash = manifest_digest("cps.fingerprint-spec/v1", fingerprint)
    qd = {"schema":"cps.qd-manifest","schema_version":"1.0.0","algorithm":"gen0-grid-archive/v1","descriptor_spec_hash":descriptor_hash,"fingerprint_spec_hash":fingerprint_hash,"evaluation_manifest_hash":sha(b"fixture-evaluation/v1"),"acceptance_policy_hash":sha(b"fixture-pareto/v1"),"axis_ids":["rhythmic_syncopation_q","material_recurrence_distance_q"],"cell_capacity":5,"quality_fields":["transformed_recall_count","distinct_sounding_material_lineage_count","sounding_role_count","section_coverage_q","negative_program_structural_item_count","program_hash_ascending"],"cas_algorithm":"manifest-cell-revision/v1"}
    planner = {"schema":"cps.planner-manifest","schema_version":"1.0.0","protocol":"typed-mutation-planner/v1","provider":"openai","model":"gpt-5.6-terra","model_snapshot":"gpt-5.6-terra","reasoning_effort":"high","prompt_asset_hash":sha(b"fixture-planner-prompt/v1"),"input_schema_hash":sha(b"fixture-planner-input/v1"),"output_schema_hash":_hash_file(SCHEMAS / "mutation.schema.json"),"allowed_operations":["replace_bounded_scalar","replace_distribution_choice","transpose_material_vector","rotate_rhythm","replace_chord_intent_reference","replace_root_anchor_item","edit_section","swap_track_catalog_entry"],"maximum_mutations":4,"maximum_request_bytes":262144,"maximum_response_bytes":65536,"operational_timeout_milliseconds":120000,"fallback_stream_domain":"cps.mutation-fallback/v1","lock_policy":"exact-dependency-root-intersection/v1","scope_policy":"typed-dependency-closure/v1"}
    _write(out, "qd_manifest.json", qd)
    _write(out, "planner_manifest.json", planner)

    sampler_hash = manifest_digest("cps.sampler-manifest/v1", sampler)
    qd_hash = manifest_digest("cps.qd-manifest/v1", qd)
    planner_hash = manifest_digest("cps.planner-manifest/v1", planner)
    run = {"schema":"cps.search-run-manifest","schema_version":"1.1.0","root_seed":7,"sampler_manifest_hash":sampler_hash,"compiler_manifest_hash":sampler["compiler_manifest_hash"],"evaluation_manifest_hash":qd["evaluation_manifest_hash"],"qd_manifest_hash":qd_hash,"planner_manifest_hash":planner_hash,"population_size":1000,"maximum_rounds":32,"candidates_per_round":16,"patience_rounds":8,"planner_call_budget":128,"compile_logical_budget":1000000000,"render_frame_budget":1000000000,"operational_deadline_seconds":None,"mutation_schema_hash":_hash_file(SCHEMAS / "mutation.schema.json"),"run_record_schema_hash":_hash_file(SCHEMAS / "search_run_record.schema.json"),"checkpoint_schema_hash":_hash_file(SCHEMAS / "search_checkpoint.schema.json"),"artifact_store":{"algorithm":"local-content-addressed/v1","cas_root":"cas/sha256","run_root":"runs","record_framing":"u64be-length-canonical-json/v1","atomic_write":"same-directory-create-if-absent-fsync/v1"}}
    _write(out, "run_manifest.json", run)
    run_hash = manifest_digest("cps.search-run-manifest/v1", run)

    table = sampler["tables"]["section_count"]
    traces = []
    for counter in range(4):
        key = stream_key(7, 0, ["form", "section_count"])
        number = draw(key, counter)
        index, value = choose(table, number)
        traces.append({"counter":counter,"stream_key_hex":key.hex(),"draw_u64":number,"choice_index":index,"value":value})
    _write(out, "sampler_trace.json", {"schema":"cps.sampler-trace","schema_version":"1.0.0","sampler_manifest_hash":sampler_hash,"root_seed":7,"cohort_index":0,"path":["form","section_count"],"traces":traces})

    mutations = {"schema":"cps.mutation-fixture-cases","schema_version":"1.0.0","positive":[{"schema":"cps.mutation","schema_version":"1.0.0","mutation_id":"mut_aaaaaaaaaaaaaaaaaaaa","base_program_hash":ZERO,"operation":"rotate_rhythm","declared_scope":[{"kind":"rhythm","id":"rhythm_a"}],"parameters":{"kind":"rotate_rhythm","rhythm_id":"rhythm_a","steps":1}}],"negative":[{"id":"rotate_zero","expected_code":"MUTATION_PARAMETER_INVALID"},{"id":"scope_superset","expected_code":"MUTATION_SCOPE_MISMATCH"},{"id":"locked_root","expected_code":"MUTATION_LOCKED"}]}
    _write(out, "mutation_cases.json", mutations)

    qd_record = {"schema":"cps.qd-archive-record","schema_version":"1.0.0","qd_manifest_hash":qd_hash,"cell":[1,3],"revision":0,"champion":{"program_hash":sha(b"program-champion"),"project_hash":sha(b"project-champion"),"lineage_root_hash":sha(b"lineage-a"),"quality":[3,4,4,10000,-120]},"runners":[{"program_hash":sha(b"program-runner-b"),"project_hash":sha(b"project-runner-b"),"lineage_root_hash":sha(b"lineage-b"),"quality":[3,4,4,9000,-110]},{"program_hash":sha(b"program-runner-c"),"project_hash":sha(b"project-runner-c"),"lineage_root_hash":sha(b"lineage-c"),"quality":[2,4,4,10000,-100]}],"previous_record_hash":None}
    _write(out, "qd_archive_record.json", qd_record)
    descriptor_case = {"schema":"cps.descriptor-fixture-case","schema_version":"1.0.0","descriptor_spec_hash":descriptor_hash,"foreground_definition":{"pitched_roles":["melody"],"include_drums":True},"eligible_events":[{"kind":"note","role":"melody","onset_tick":120,"end_tick":600,"contribution":1}],"syncopation_numerator":1,"syncopation_maximum":5,"rhythmic_syncopation_q":2000,"lineage_pairs":[{"lineage_hash":sha(b"material-lineage-a"),"weighted_jaccard_q":0}],"material_recurrence_distance_q":0}
    _write(out, "descriptor_case.json", descriptor_case)
    lineage_index_hash = manifest_digest("cps.lineage-index/v1", {"fixture":"lineage-index-a"})
    descriptor_result = {"schema":"cps.descriptor-result","schema_version":"1.0.0","descriptor_spec_hash":descriptor_hash,"project_hash":ZERO,"lineage_index_hash":lineage_index_hash,"rhythmic_syncopation_q":2000,"material_recurrence_distance_q":0,"eligible_syncopation_events":1,"recurrence_pair_count":1}
    _write(out, "descriptor_result.json", descriptor_result)
    fingerprint_components = cast(list[dict[str, Any]], fingerprint["components"])
    fingerprint_payloads = {"section_bars":[4,8,8],"role_time_grid":[["melody",0,4]],"root_anchor_deltas":[[0,0],[1,0]],"chord_steps":[[0,4,7]],"lineage_edges":[["a","a","rotate"]],"sounding_intervals":["3/2"]}
    fingerprint_case: dict[str, Any] = {"schema":"cps.fingerprint-fixture-case","schema_version":"1.0.0","fingerprint_spec_hash":fingerprint_hash,"components":[{"id":component["id"],"payload":fingerprint_payloads[component["id"]],"component_hash":manifest_digest("cps.fingerprint-component/v1",{"id":component["id"],"payload":fingerprint_payloads[component["id"]]})} for component in fingerprint_components]}
    fingerprint_case["fingerprint_hash"] = manifest_digest("cps.musical-fingerprint/v1", [item["component_hash"] for item in fingerprint_case["components"]])
    _write(out, "fingerprint_case.json", fingerprint_case)
    fingerprint_record = {"schema":"cps.fingerprint-record","schema_version":"1.0.0","fingerprint_spec_hash":fingerprint_hash,"project_hash":ZERO,"lineage_index_hash":lineage_index_hash,"component_hashes":[{"id":item["id"],"hash":item["component_hash"]} for item in fingerprint_case["components"]],"fingerprint_hash":fingerprint_case["fingerprint_hash"]}
    _write(out, "fingerprint_record.json", fingerprint_record)

    payload = canonical_bytes({"run_hash":run_hash,"status":"started"})
    payload_hash = sha(payload)
    hex_hash = payload_hash.removeprefix("sha256:")
    target = cas / hex_hash[:2] / hex_hash[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    record = seal_record({"schema":"cps.search-run-record","schema_version":"1.0.0","run_hash":run_hash,"sequence":0,"action_id":action_id(run_hash,0,0,0),"round":0,"phase_ordinal":0,"candidate_ordinal":0,"kind":"run","payload_hash":payload_hash,"previous_record_hash":None})
    _write(out, "run_record_000.json", record)
    checkpoint = {"schema":"cps.search-checkpoint","schema_version":"1.0.0","run_hash":run_hash,"last_sequence":0,"last_record_hash":record["record_hash"],"next_action_id":action_id(run_hash,0,0,1),"cursor":{"round":0,"candidate_ordinal":1,"phase_ordinal":0},"budget_usage":{"compile_logical_units":0,"render_frames":0,"planner_calls":0},"planner_calls":0,"patience_rounds":0,"cancelled":False,"archive_heads":[],"champions":[]}
    _write(out, "checkpoint.json", checkpoint)
    record_bytes = canonical_bytes(record)
    (out / "records.log").write_bytes(struct.pack(">Q", len(record_bytes)) + record_bytes)

    files=[]
    for path in sorted((p for p in out.rglob("*") if p.is_file() and p.name!="fixture_set.json"),key=lambda p:str(p.relative_to(out))):
        raw = path.read_bytes()
        files.append({"path":str(path.relative_to(out)),"byte_length":len(raw),"sha256":sha(raw)})
    _write(out,"fixture_set.json",{"schema":"cps.search-fixture-set","schema_version":"1.0.0","files":files})


if __name__ == "__main__":
    build()
