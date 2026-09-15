"""Build production-independent authoritative GEN0 cohort fixtures."""

from __future__ import annotations
import copy
import json
import re
import shutil
from pathlib import Path
from .gen0_cohort_oracle import (
    FAMILIES,
    artifact_identity,
    build_report,
    canonical,
    cas_index_hash,
    comparison_set_hash,
    derive_mode_keys,
    domain_hash,
    fingerprint_distances,
    fingerprint_hash,
    ledger_hash,
    manifest_hash,
    matrix_receipt_hash,
    qd_cell,
    raw_sha256,
    record_hash,
    report_hash,
    suite_hash,
)

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / "schemas"
OUT = HERE / "fixtures" / "gen0_cohort_gate"
FIX = HERE / "fixtures"
AUTH = FIX / "search_loop_13" / "shared_authority" / "artifacts"
Z = "sha256:" + "0" * 64
FIELDS = (
    "sampler_request",
    "sampler_result",
    "production_request",
    "production_result",
    "program",
    "compile_report",
    "project",
    "evaluation_report",
    "fingerprint_record",
    "near_duplicate_decision",
)
COVERAGE = json.loads((SCHEMAS / "gen0_cohort_gate_fixture_suite_index.schema.json").read_text())[
    "$defs"
]["coverage"]["enum"]
AS = {
    "sampler_manifest": ("sampler_manifest_1_1.schema.json", "sampler-manifest-v1.1"),
    "structural_lowering_manifest": (
        "structural_lowering_manifest.schema.json",
        "structural-lowering-manifest-v1",
    ),
    "production_lowering_manifest": (
        "broad_prior_production_manifest.schema.json",
        "production-lowering-manifest-v1",
    ),
    "compiler_manifest": ("compiler_manifest_1_1.schema.json", "compiler-manifest-v1.1"),
    "evaluation_manifest": ("evaluation_manifest_1_1.schema.json", "evaluation-manifest-v1.1"),
    "descriptor_spec": ("descriptor_spec.schema.json", "descriptor-spec-v1"),
    "fingerprint_spec": ("fingerprint_spec.schema.json", "fingerprint-spec-v1"),
    "qd_manifest": ("qd_manifest.schema.json", "qd-manifest-v1"),
    "near_duplicate_calibration_decision": (
        "near_duplicate_calibration_decision.schema.json",
        "near-duplicate-calibration-decision-v1",
    ),
    "sampler_request": ("structural_sampler_request_1_1.schema.json", "generic-cps-artifact-v1"),
    "sampler_result": (
        "structural_sampler_result_1_1.schema.json",
        "structural-sampler-result-v1.1",
    ),
    "production_request": (
        "broad_prior_production_request_1_1.schema.json",
        "generic-cps-artifact-v1",
    ),
    "production_result": (
        "broad_prior_production_result_1_1.schema.json",
        "broad-prior-production-result-v1.1",
    ),
    "program": ("song_program_0_1.schema.json", "song-program-v0.1"),
    "compile_report": ("compile_report_1_1.schema.json", "generic-cps-artifact-v1"),
    "project": ("arrangement_project_1_2.schema.json", "arrangement-project-v1.2"),
    "evaluation_report": ("evaluation_report_1_1.schema.json", "generic-cps-artifact-v1"),
    "fingerprint_record": ("fingerprint_record.schema.json", "generic-cps-artifact-v1"),
    "fingerprint_component": (
        "gen0_cohort_fingerprint_component.schema.json",
        "fingerprint-component-v1",
    ),
    "near_duplicate_decision": ("near_duplicate_decision.schema.json", "generic-cps-artifact-v1"),
}
ERR = (
    "COHORT_REPORT_SCHEMA_INVALID",
    "COHORT_MANIFEST_INVALID",
    "COHORT_MANIFEST_HASH_MISMATCH",
    "COHORT_RECORD_COUNT_MISMATCH",
    "COHORT_RECORD_ORDER_INVALID",
    "COHORT_RECORD_HASH_MISMATCH",
    "COHORT_COORDINATE_MISMATCH",
    "COHORT_ARTIFACT_BINDING_MISMATCH",
    "COHORT_STAGE_PRECEDENCE_INVALID",
    "COHORT_DUPLICATE_CLASSIFICATION_INVALID",
    "COHORT_MODE_KEY_INVALID",
    "COHORT_LEDGER_HASH_MISMATCH",
    "COHORT_AGGREGATE_MISMATCH",
    "COHORT_GATE_RESULT_MISMATCH",
    "COHORT_REPORT_HASH_MISMATCH",
)


def load(p):
    return json.loads(Path(p).read_text())


def h(s):
    return raw_sha256(s.encode())


def dump(p, v):
    d = canonical(v) + b"\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(d)
    return {"path": p.relative_to(OUT).as_posix(), "raw_sha256": raw_sha256(d)}


def closure(seeds):
    out = set(seeds)
    todo = list(seeds)
    while todo:
        n = todo.pop()
        for ref in re.findall(r'"\$ref"\s*:\s*"([^"#]+\.schema\.json)', (SCHEMAS / n).read_text()):
            c = Path(ref).name
            if c not in out:
                out.add(c)
                todo.append(c)
    return out


class CAS:
    def __init__(self, sh):
        self.sh = sh
        self.docs = {}

    def add(self, k, v):
        x = artifact_identity(AS[k][1], v)
        self.docs.setdefault((x, k), copy.deepcopy(v))
        return x

    def finish(self):
        es = []
        for (x, k), v in self.docs.items():
            es.append(
                {
                    "artifact_hash": x,
                    "artifact_kind": k,
                    "schema_hash": self.sh[k],
                    **dump(OUT / "cas" / k / (x[7:] + ".json"), v),
                }
            )
        es.sort(
            key=lambda r: (
                bytes.fromhex(r["artifact_hash"][7:]),
                r["artifact_kind"].encode(),
                r["path"].encode(),
            )
        )
        v = {
            "schema": "cps.gen0-cohort-gate-cas-index",
            "schema_version": "1.0.0",
            "entries": es,
            "index_hash": Z,
        }
        v["index_hash"] = cas_index_hash(v)
        return v


def bound(c):
    v = {
        k: load(AUTH / f)
        for k, f in {
            "sampler_manifest": "sampler_manifest.json",
            "structural_lowering_manifest": "structural_lowering_manifest.json",
            "production_lowering_manifest": "broad_prior_production_manifest.json",
            "compiler_manifest": "compiler_manifest.json",
            "evaluation_manifest": "evaluation_manifest.json",
            "descriptor_spec": "descriptor_spec.json",
            "fingerprint_spec": "fingerprint_spec.json",
            "qd_manifest": "qd_manifest.json",
        }.items()
    }
    sl = c.add("structural_lowering_manifest", v["structural_lowering_manifest"])
    cm = c.add("compiler_manifest", v["compiler_manifest"])
    s = v["sampler_manifest"]
    s.update(structural_lowering_manifest_hash=sl, compiler_manifest_hash=cm)
    s["manifest_hash"] = artifact_identity("sampler-manifest-v1.1", s)
    sm = c.add("sampler_manifest", s)
    p = v["production_lowering_manifest"]
    p["sampler_manifest_hash"] = sm
    pm = c.add("production_lowering_manifest", p)
    e = v["evaluation_manifest"]
    if not any(x["id"] == "rhythmic_syncopation_q" for x in e["metrics"]):
        e["metrics"].append(
            {
                "id": "rhythmic_syncopation_q",
                "ordinal": 8,
                "sources": [
                    {
                        "artifact_kind": "compile_report",
                        "schema_hash": c.sh["compile_report"],
                        "json_pointer": "/search_statistics/chord_query_count",
                    }
                ],
                "operator": {"kind": "integer_identity"},
                "direction": "maximize",
                "required_render": False,
            }
        )
    e["manifest_hash"] = artifact_identity("evaluation-manifest-v1.1", e)
    em = c.add("evaluation_manifest", e)
    ds = c.add("descriptor_spec", v["descriptor_spec"])
    fs = c.add("fingerprint_spec", v["fingerprint_spec"])
    q = v["qd_manifest"]
    q.update(descriptor_spec_hash=ds, fingerprint_spec_hash=fs, evaluation_manifest_hash=em)
    qm = c.add("qd_manifest", q)
    return {
        "sampler_manifest_hash": sm,
        "structural_lowering_manifest_hash": sl,
        "production_lowering_manifest_hash": pm,
        "compiler_manifest_hash": cm,
        "evaluation_manifest_hash": em,
        "descriptor_spec_hash": ds,
        "fingerprint_spec_hash": fs,
        "qd_manifest_hash": qm,
    }, v


def calibration(c, fs, t):
    v = {
        "schema": "cps.near-duplicate-calibration-decision",
        "schema_version": "1.0.0",
        "scope": "gen0_musical_fingerprint_near_duplicate",
        "status": "promoted",
        "fingerprint_spec_hash": fs,
        "threshold_q": t,
        "calibration_dataset_hash": h("cal-data"),
        "acceptance_policy_hash": h("cal-policy"),
        "evidence_summary_hash": h("cal-evidence"),
        "precision_q": 10000,
        "false_accept_q": 0,
        "false_reject_q": 0,
        "failure_code": None,
        "decision_hash": Z,
    }
    v["decision_hash"] = artifact_identity("near-duplicate-calibration-decision-v1", v)
    return c.add("near_duplicate_calibration_decision", v)


def gate_manifest(b, sh, cal=None):
    pol = (
        {
            "status": "audit_only",
            "calibration_decision_hash": None,
            "calibration_decision_schema_hash": None,
        }
        if cal is None
        else {
            "status": "enforced",
            "calibration_decision_hash": cal,
            "calibration_decision_schema_hash": sh["near_duplicate_calibration_decision"],
        }
    )
    v = {
        "schema": "cps.gen0-cohort-gate-manifest",
        "schema_version": "1.0.0",
        "contract": "cps-gen0-cohort-gate/v1",
        "root_seed": 1592639710,
        "cohort_size": 1000,
        "coordinate_rule": "candidate-ordinal-equals-cohort-index-0-through-999/v1",
        "bindings": {
            **b,
            "candidate_record_schema_hash": raw_sha256(
                (SCHEMAS / "gen0_cohort_candidate_record.schema.json").read_bytes()
            ),
            "candidate_ledger_schema_hash": raw_sha256(
                (SCHEMAS / "gen0_cohort_candidate_ledger.schema.json").read_bytes()
            ),
            "gate_report_schema_hash": raw_sha256(
                (SCHEMAS / "gen0_cohort_gate_report.schema.json").read_bytes()
            ),
        },
        "binding_schema_hashes": {
            k: sh[k]
            for k in (
                "sampler_manifest",
                "structural_lowering_manifest",
                "production_lowering_manifest",
                "compiler_manifest",
                "evaluation_manifest",
                "descriptor_spec",
                "fingerprint_spec",
                "qd_manifest",
            )
        },
        "candidate_artifact_schema_hashes": {k: sh[k] for k in (*FIELDS, "fingerprint_component")},
        "thresholds_bp": {
            "compile_success_ge": 9500,
            "initial_viability_ge": 7000,
            "planner_viability_ge": 8000,
            "exact_duplicate_lt": 100,
            "near_duplicate_lt": 1000,
            "transformed_recall_ge": 8000,
            "mode_prevalence_le": 3500,
        },
        "rate_algorithm": "round-half-even-10000-times-count-over-1000/v1",
        "mode_algorithm": "order2-root-chord-plus-harmony-rhythm-candidate-prevalence/v1",
        "near_duplicate_policy": pol,
        "manifest_hash": Z,
    }
    v["manifest_hash"] = manifest_hash(v)
    return v


def structural():
    p = load(FIX / "pack" / "minimal_direct_song_program.json")
    r = p["realizations"][0]
    sec = p["form"][0]
    p.pop("tracks")
    p.pop("production")
    p.update(
        schema="cps.structural-song-program",
        schema_version="1.0.0",
        program_id="sp_gen0_structural",
    )
    p["form"] = []
    p["realizations"] = []
    for i in range(3):
        a = copy.deepcopy(sec)
        a["id"] = f"sec_{i}"
        p["form"].append(a)
        a = copy.deepcopy(r)
        a.pop("track_id")
        a.update(id=f"real_{i}", section_id=f"sec_{i}", role="melody")
        p["realizations"].append(a)
    return p


SP = structural()


def payloads(i, ex, nr, mo):
    common = i < mo
    near = ex < i <= ex + nr
    sound = ["1/1"] * 16
    if near:
        sound[-1] = "3/2"
    return {
        "section_bars": [4, 4] if i <= ex or near else [i + 1],
        "role_time_grid": [["harmony", 0 if common else i, 1]],
        "root_anchor_deltas": [[0], [1]] if common else [[i], [i + 1]],
        "chord_steps": [[0], [2]] if common else [[i], [i + 2]],
        "lineage_edges": [],
        "sounding_intervals": sound,
    }


def component(c, id, p):
    v = {
        "schema": "cps.gen0-cohort-fingerprint-component",
        "schema_version": "1.0.0",
        "id": id,
        "payload": p,
        "component_hash": Z,
    }
    v["component_hash"] = artifact_identity("fingerprint-component-v1", v)
    return c.add("fingerprint_component", v)


def artifacts(c, m, bv, i, vi, rec, ex, nr, mo, ok):
    B = m["bindings"]
    run = h("run")
    ctx = h("context")
    dec = h(f"decision:{i}")
    srh = domain_hash("cps.structural-song-program/1.0", SP)
    rq = {
        "schema": "cps.structural-sampler-request",
        "schema_version": "1.1.0",
        "run_hash": run,
        "context_hash": ctx,
        "source_decision_hash": dec,
        "sampler_manifest_hash": B["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": B["structural_lowering_manifest_hash"],
        "structural_program_schema_hash": bv["sampler_manifest"]["structural_program_schema_hash"],
        "structural_rejection_evidence_schema_hash": bv["sampler_manifest"][
            "structural_rejection_evidence_schema_hash"
        ],
        "root_seed": m["root_seed"],
        "cohort_index": i,
        "request_hash": Z,
    }
    rq["request_hash"] = artifact_identity("generic-cps-artifact-v1", rq)
    rqh = c.add("sampler_request", rq)
    sr = {
        "schema": "cps.structural-sampler-result",
        "schema_version": "1.1.0",
        "status": "success",
        "run_hash": run,
        "context_hash": ctx,
        "source_decision_hash": dec,
        "request_hash": rqh,
        "sampler_manifest_hash": B["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": B["structural_lowering_manifest_hash"],
        "structural_program_schema_hash": rq["structural_program_schema_hash"],
        "structural_rejection_evidence_schema_hash": rq[
            "structural_rejection_evidence_schema_hash"
        ],
        "structural_program_hash": srh,
        "rejections_consumed": 0,
        "decision_trace_hash": h(f"trace:{i}"),
        "terminal_rejection_evidence_hash": None,
        "error": None,
        "result_hash": Z,
    }
    sr["result_hash"] = artifact_identity("structural-sampler-result-v1.1", sr)
    sr = c.add("sampler_result", sr)
    pr = {
        "schema": "cps.broad-prior-production-request",
        "schema_version": "1.1.0",
        "run_hash": run,
        "context_hash": ctx,
        "source_decision_hash": dec,
        "root_seed": m["root_seed"],
        "cohort_index": i,
        "production_rejection_ordinal": 0,
        "sampler_manifest_hash": B["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": B["structural_lowering_manifest_hash"],
        "production_lowering_manifest_hash": B["production_lowering_manifest_hash"],
        "instrument_catalog_digest": bv["production_lowering_manifest"][
            "instrument_catalog_digest"
        ],
        "structural_program_hash": srh,
        "structural_program": SP,
        "active_roles": ["bass", "harmony", "melody"],
        "lattice_equave": SP["lattice"]["equave"],
        "request_hash": Z,
    }
    pr["request_hash"] = artifact_identity("generic-cps-artifact-v1", pr)
    prh = c.add("production_request", pr)
    p = load(FIX / "pack" / "minimal_direct_song_program.json")
    p.update(seed=0 if i <= ex else i, program_id="sp_gen0")
    p["production"]["catalog_digest"] = pr["instrument_catalog_digest"]
    ph = c.add("program", p)
    ps = {
        "schema": "cps.broad-prior-production-result",
        "schema_version": "1.1.0",
        "status": "success",
        "run_hash": run,
        "context_hash": ctx,
        "source_decision_hash": dec,
        "request_hash": prh,
        "sampler_manifest_hash": B["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": B["structural_lowering_manifest_hash"],
        "production_lowering_manifest_hash": B["production_lowering_manifest_hash"],
        "instrument_catalog_digest": pr["instrument_catalog_digest"],
        "structural_program_hash": srh,
        "rejections_consumed": 0,
        "role_decisions": [],
        "decision_trace": [],
        "output": {
            "profile_id": p["production"]["profile_id"],
            "profile_payload_hash": h("profile"),
            "catalog_digest": p["production"]["catalog_digest"],
            "program": p,
            "program_hash": ph,
        },
        "error": None,
        "result_hash": Z,
    }
    ps["result_hash"] = artifact_identity("broad-prior-production-result-v1.1", ps)
    psh = c.add("production_result", ps)
    pj = load(FIX / "pack" / "minimal_direct_project.json")
    pj["material_instances"][0]["source_program_path"] = ""
    pj["source_program"]["hash"] = ph
    pj["compiler"]["build_id"] = bv["compiler_manifest"]["build_id"]
    pj["compiler"]["instrument_catalog_digest"] = bv["compiler_manifest"][
        "instrument_catalog_digest"
    ]
    pjh = c.add("project", pj)
    cr = load(FIX / "compiler" / "gen0b_compile_report.json")
    cr.update(
        source_program_hash=ph,
        compiler_manifest_hash=B["compiler_manifest_hash"],
        compiler_build_id=bv["compiler_manifest"]["build_id"],
    )
    if ok:
        cr.update(status="success", project_hash=pjh, error=None)
    else:
        cr.update(
            status="failure",
            project_hash=None,
            evidence_hash=None,
            error={
                "code": "COMPILE_FAILED",
                "stage": "compile",
                "pointer": "",
                "counter": None,
                "requested": None,
                "used": None,
                "ceiling": None,
                "child_query_id": None,
                "snapshot": {},
                "partial_project": None,
            },
        )
    crh = c.add("compile_report", cr)
    hs = dict(zip(FIELDS, (rqh, sr, prh, psh, ph, crh, None, None, None, None)))
    if not ok:
        return hs, None, None
    hs["project"] = pjh
    em = bv["evaluation_manifest"]
    hard = []
    for x in em["hard_checks"]:
        sb = [
            {
                **s,
                "artifact_hash": {"compile_report": crh, "project": pjh}.get(
                    s["artifact_kind"], h("missing")
                ),
            }
            for s in x["sources"]
        ]
        hard.append(
            {
                "id": x["id"],
                "ordinal": x["ordinal"],
                "passed": vi,
                "evidence": {
                    "source_bindings": sb,
                    "operator": x["operator"],
                    "inputs": [0],
                    "result": vi,
                    "evidence_hash": h(f"hard:{i}:{vi}"),
                },
            }
        )
    mv = {
        "rhythmic_syncopation_q": (i % 5) * 2000,
        "material_recurrence_distance_q": ((i // 5) % 5) * 2000,
        "transformed_recall_count": 1 if rec else 0,
    }
    mets = [
        {
            "id": x["id"],
            "ordinal": x["ordinal"],
            "value": mv.get(x["id"], 1),
            "missing_reason": None,
            "evidence": None,
            "available_source_bindings": [],
        }
        for x in em["metrics"]
    ]
    er = {
        "schema": "cps.evaluation-report",
        "schema_version": "1.1.0",
        "status": "success",
        "run_hash": run,
        "context_hash": ctx,
        "source_decision_hash": dec,
        "evaluation_manifest_hash": B["evaluation_manifest_hash"],
        "genre_intent_hash": em["genre_intent_hash"],
        "program_hash": ph,
        "project_hash": pjh,
        "request_hash": h(f"eval:{i}"),
        "hard_checks": hard,
        "metrics": mets,
        "failure_code": None,
        "report_hash": Z,
    }
    er["report_hash"] = artifact_identity("generic-cps-artifact-v1", er)
    hs["evaluation_report"] = c.add("evaluation_report", er)
    pl = payloads(i, ex, nr, mo)
    ch = [component(c, x["id"], pl[x["id"]]) for x in bv["fingerprint_spec"]["components"]]
    fp = {
        "schema": "cps.fingerprint-record",
        "schema_version": "1.0.0",
        "fingerprint_spec_hash": B["fingerprint_spec_hash"],
        "project_hash": pjh,
        "lineage_index_hash": h("lineage"),
        "component_hashes": [
            {"id": x["id"], "hash": z} for x, z in zip(bv["fingerprint_spec"]["components"], ch)
        ],
        "fingerprint_hash": fingerprint_hash(ch),
    }
    hs["fingerprint_record"] = c.add("fingerprint_record", fp)
    return (
        hs,
        {
            "program_hash": ph,
            "fingerprint_record_hash": hs["fingerprint_record"],
            "fingerprint_hash": fp["fingerprint_hash"],
            "payloads": pl,
        },
        {x["id"]: x["value"] for x in mets},
    )


def rows(c, m, bv, cc, vi, ex, nr, rec, mo):
    out = []
    universe = []
    fs = bv["fingerprint_spec"]
    for i in range(1000):
        ok = i < cc
        hs, can, mv = artifacts(c, m, bv, i, ok and i < vi, ok and i < rec, ex, nr, mo, ok)
        if not ok:
            stage = "compiler"
            code = "COMPILE_FAILED"
            clas = None
            qd = None
            modes = {x: [] for x in FAMILIES}
        else:
            comps = []
            for old in sorted(universe, key=lambda x: bytes.fromhex(x["program_hash"][7:])):
                ds, ag = fingerprint_distances(fs, can["payloads"], old["payloads"])
                comps.append(
                    {
                        "program_hash": old["program_hash"],
                        "fingerprint_hash": old["fingerprint_hash"],
                        "component_distances_q": ds,
                        "aggregate_distance_q": ag,
                    }
                )
            exact = next((x for x in comps if x["program_hash"] == can["program_hash"]), None)
            nearest = (
                None
                if not comps
                else min(
                    comps,
                    key=lambda x: (
                        x["aggregate_distance_q"],
                        tuple(x["component_distances_q"]),
                        bytes.fromhex(x["program_hash"][7:]),
                    ),
                )
            )
            if exact:
                clas, rep, nv = "exact_duplicate", can["program_hash"], exact
            elif nearest and nearest["aggregate_distance_q"] <= fs["near_duplicate_threshold_q"]:
                clas, rep, nv = "near_duplicate", nearest["program_hash"], nearest
            else:
                clas, rep, nv = "distinct", can["program_hash"], nearest
            pgs = [x["program_hash"] for x in comps]
            nd = {
                "schema": "cps.near-duplicate-decision",
                "schema_version": "1.0.0",
                "run_hash": h("run"),
                "fingerprint_spec_hash": m["bindings"]["fingerprint_spec_hash"],
                "candidate_ordinal": i,
                "candidate_program_hash": can["program_hash"],
                "candidate_fingerprint_hash": can["fingerprint_hash"],
                "comparison_set_hash": comparison_set_hash(pgs),
                "comparison_program_hashes": pgs,
                "nearest": nv,
                "threshold_q": fs["near_duplicate_threshold_q"],
                "classification": clas,
                "representative_program_hash": rep,
                "decision_hash": Z,
            }
            nd["decision_hash"] = artifact_identity("generic-cps-artifact-v1", nd)
            hs["near_duplicate_decision"] = c.add("near_duplicate_decision", nd)
            if clas == "distinct":
                universe.append(can)
            stage = "complete"
            code = None
            qd = qd_cell(bv["descriptor_spec"], mv)
            modes = derive_mode_keys(can["payloads"])
        r = {
            "schema": "cps.gen0-cohort-candidate-record",
            "schema_version": "1.0.0",
            "cohort_manifest_hash": m["manifest_hash"],
            "candidate_ordinal": i,
            "root_seed": m["root_seed"],
            "cohort_index": i,
            "terminal_stage": stage,
            "terminal_code": code,
            "artifact_hashes": hs,
            "compile_success": ok,
            "automatic_viable": ok and i < vi,
            "has_transformed_recall": ok and i < rec,
            "duplicate_classification": clas,
            "qd_cell": qd,
            "mode_keys": modes,
            "record_hash": Z,
        }
        r["record_hash"] = record_hash(r)
        out.append(r)
    return out


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    core = (
        "gen0_cohort_gate_manifest",
        "gen0_cohort_candidate_record",
        "gen0_cohort_candidate_ledger",
        "gen0_cohort_gate_report",
        "gen0_cohort_gate_cas_index",
        "gen0_cohort_gate_matrix_receipt",
        "gen0_cohort_gate_fixture_suite_index",
    )
    cf = {x + ".schema.json" for x in core}
    files = closure(cf | {x[0] for x in AS.values()})
    refs = {}
    reg = []
    raw = {}
    for f in files:
        t = OUT / "schemas" / f
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCHEMAS / f, t)
        d = t.read_bytes()
        raw[f] = raw_sha256(d)
        s = load(t)
        kinds = [k for k, x in AS.items() if x[0] == f]
        reg.append(
            {
                "schema_id": s["$id"],
                "path": t.relative_to(OUT).as_posix(),
                "raw_sha256": raw[f],
                "artifact_kinds": kinds,
                "identity_rules": [AS[k][1] for k in kinds],
            }
        )
        if f in cf:
            refs[
                {
                    "gen0_cohort_gate_manifest": "manifest",
                    "gen0_cohort_candidate_record": "candidate_record",
                    "gen0_cohort_candidate_ledger": "candidate_ledger",
                    "gen0_cohort_gate_report": "report",
                    "gen0_cohort_gate_cas_index": "cas_index",
                    "gen0_cohort_gate_matrix_receipt": "matrix_receipt",
                    "gen0_cohort_gate_fixture_suite_index": "suite_index",
                }[f[:-12]]
            ] = {"path": t.relative_to(OUT).as_posix(), "raw_sha256": raw[f]}
    reg.sort(
        key=lambda x: (
            bytes.fromhex(x["raw_sha256"][7:]),
            x["schema_id"].encode(),
            x["path"].encode(),
        )
    )
    sh = {k: raw[x[0]] for k, x in AS.items()}
    c = CAS(sh)
    b, bv = bound(c)
    cal = calibration(
        c, b["fingerprint_spec_hash"], bv["fingerprint_spec"]["near_duplicate_threshold_q"]
    )
    cases = []
    golden = None
    specs = [
        (
            "golden",
            0,
            1000,
            800,
            9,
            99,
            800,
            350,
            [
                "golden.success",
                "policy.near_audit_only",
                "boundary.compile.9500_pass",
                "boundary.initial_viability.7000_pass",
                "boundary.planner_viability.8000_pass",
                "boundary.exact_duplicate.90_pass",
                "boundary.near_duplicate.990_pass",
                "boundary.transformed_recall.8000_pass",
                "boundary.mode.3500_pass",
                "process.pythonhashseed_0_1_7_42",
                "parallel.workers_1_2_4_8",
            ],
        ),
        ("enforced", 1, 1000, 800, 9, 99, 800, 350, ["policy.near_enforced"]),
        ("compile_949", 0, 949, 800, 9, 99, 800, 350, ["boundary.compile.9490_fail"]),
        ("viable_699", 0, 1000, 699, 9, 99, 800, 350, ["boundary.initial_viability.6990_fail"]),
        ("viable_799", 0, 1000, 799, 9, 99, 800, 350, ["boundary.planner_viability.7990_fail"]),
        ("exact_10", 0, 1000, 800, 10, 99, 800, 350, ["boundary.exact_duplicate.100_fail"]),
        ("near_100", 1, 1000, 800, 9, 100, 800, 350, ["boundary.near_duplicate.1000_fail"]),
        ("recall_799", 0, 1000, 800, 9, 99, 799, 350, ["boundary.transformed_recall.7990_fail"]),
        ("mode_351", 0, 1000, 800, 9, 99, 800, 351, ["boundary.mode.3510_fail"]),
    ]
    for cid, enf, cc, vi, ex, nr, rec, mo, cov in specs:
        m = gate_manifest(b, sh, cal if enf else None)
        rr = rows(c, m, bv, cc, vi, ex, nr, rec, mo)
        le = {
            "schema": "cps.gen0-cohort-candidate-ledger",
            "schema_version": "1.0.0",
            "cohort_manifest_hash": m["manifest_hash"],
            "records": rr,
            "ledger_hash": ledger_hash(rr),
        }
        rp = build_report(m, rr)
        base = OUT / "cases" / cid
        cases.append(
            {
                "case_id": cid,
                "kind": "success",
                "manifest": dump(base / "manifest.json", m),
                "records": dump(base / "ledger.json", le),
                "coverage": cov,
                "expected_report": dump(base / "report.json", rp),
            }
        )
        golden = golden or (m, le, rp)
    for pos, label in enumerate(COVERAGE[17:32]):
        m, le, rp = copy.deepcopy(golden)
        if pos == 0:
            rp.pop("status")
        elif pos == 1:
            m["cohort_size"] = 999
        elif pos == 2:
            m["root_seed"] += 1
        elif pos == 3:
            le["records"].pop()
        elif pos == 4:
            le["records"][0], le["records"][1] = le["records"][1], le["records"][0]
        elif pos == 5:
            le["records"][0]["record_hash"] = Z
        elif pos == 6:
            le["records"][0]["cohort_index"] = 1
            le["records"][0]["record_hash"] = record_hash(le["records"][0])
        elif pos == 7:
            le["records"][0]["artifact_hashes"]["program"] = Z
            le["records"][0]["record_hash"] = record_hash(le["records"][0])
        elif pos == 8:
            le["records"][0]["compile_success"] = False
            le["records"][0]["record_hash"] = record_hash(le["records"][0])
        elif pos == 9:
            le["records"][0]["duplicate_classification"] = None
            le["records"][0]["record_hash"] = record_hash(le["records"][0])
        elif pos == 10:
            le["records"][0]["mode_keys"][FAMILIES[0]][0] = h("invalid-mode-key")
            le["records"][0]["record_hash"] = record_hash(le["records"][0])
        elif pos == 11:
            le["ledger_hash"] = Z
        elif pos == 12:
            rp["counts"]["compile_success"] -= 1
            rp["report_hash"] = report_hash(rp)
        elif pos == 13:
            rp["gates"]["compile_success"]["status"] = "failed"
            rp["report_hash"] = report_hash(rp)
        else:
            rp["report_hash"] = Z
        base = OUT / "cases" / label.replace(".", "_")
        cases.append(
            {
                "case_id": label.replace(".", "_"),
                "kind": "failure",
                "manifest": dump(base / "manifest.json", m),
                "records": dump(base / "ledger.json", le),
                "coverage": [label],
                "input_report": dump(base / "report.json", rp),
                "expected_code": ERR[pos],
            }
        )
    ci = dump(OUT / "cas_index.json", c.finish())
    gm, gl, gr = golden
    rb = canonical(gr) + b"\n"
    co = [
        {
            "python_hash_seed": s,
            "workers": w,
            "report_raw_sha256": raw_sha256(rb),
            "report_hash": gr["report_hash"],
        }
        for s in (0, 1, 7, 42)
        for w in (1, 2, 4, 8)
    ]
    mr = {
        "schema": "cps.gen0-cohort-gate-matrix-receipt",
        "schema_version": "1.0.0",
        "cohort_manifest_hash": gm["manifest_hash"],
        "ledger_hash": gl["ledger_hash"],
        "baseline_report_hash": gr["report_hash"],
        "coordinates": co,
        "all_equal": True,
        "receipt_hash": Z,
    }
    mr["receipt_hash"] = matrix_receipt_hash(mr)
    mr = dump(OUT / "matrix_receipt.json", mr)
    idx = {
        "schema": "cps.gen0-cohort-gate-fixture-suite-index",
        "schema_version": "1.0.0",
        "contract": "cps-gen0-cohort-gate/v1",
        "generator_identity": "cps-independent-gen0-cohort-oracle/1.0.0",
        "schemas": refs,
        "schema_registry": reg,
        "cas_index": ci,
        "matrix_receipt": mr,
        "cases": sorted(cases, key=lambda x: x["case_id"].encode()),
        "coverage": COVERAGE,
        "suite_hash": Z,
    }
    idx["suite_hash"] = suite_hash(idx)
    dump(OUT / "suite_index.json", idx)


if __name__ == "__main__":
    build()
