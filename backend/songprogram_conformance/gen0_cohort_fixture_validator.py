"""Read-only validator for the authoritative GEN0 cohort fixture suite."""

from __future__ import annotations
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from .build_gen0_cohort_fixtures import FIELDS
from .gen0_cohort_oracle import (
    FAMILIES,
    artifact_identity,
    build_report,
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

ERRORS = (
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
SHA0 = "sha256:" + "0" * 64


def load(p):
    return json.loads(Path(p).read_text())


def safe(root: Path, name: str) -> Path:
    if not re.fullmatch(
        r"(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*//)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name
    ):
        raise ValueError("unsafe fixture path")
    p = root / name
    q = root
    for part in Path(name).parts:
        q = q / part
        if q.is_symlink():
            raise ValueError("symlink fixture path")
    if not p.is_file():
        raise ValueError(f"missing fixture: {name}")
    return p


def presence(r):
    stop = {
        "sampler": 2,
        "production": 4,
        "compiler": 6,
        "evaluation": 8,
        "fingerprint": 8,
        "duplicate": 9,
        "complete": 10,
    }[r["terminal_stage"]]
    return all((r["artifact_hashes"][x] is not None) == (i < stop) for i, x in enumerate(FIELDS))


class Context:
    def __init__(self, root, index):
        self.root = root
        self.schemas = {}
        self.schema_by_hash = {}
        resources = Registry()
        order = sorted(
            index["schema_registry"],
            key=lambda x: (
                bytes.fromhex(x["raw_sha256"][7:]),
                x["schema_id"].encode(),
                x["path"].encode(),
            ),
        )
        if order != index["schema_registry"]:
            raise ValueError("schema registry order")
        if len({x["raw_sha256"] for x in order}) != len(order) or len(
            {x["schema_id"] for x in order}
        ) != len(order):
            raise ValueError("duplicate schema registry entry")
        for e in order:
            p = safe(root, e["path"])
            raw = p.read_bytes()
            if raw_sha256(raw) != e["raw_sha256"]:
                raise ValueError("schema hash mismatch")
            s = json.loads(raw)
            if s.get("$id") != e["schema_id"]:
                raise ValueError("schema id mismatch")
            self.schemas[e["schema_id"]] = s
            self.schema_by_hash[e["raw_sha256"]] = (e, s)
            resources = resources.with_resource(e["schema_id"], Resource.from_contents(s))
        self.registry = resources
        # Every local ref must be present and confinement-safe; Registry detects bad cycles while validation runs.
        for s in self.schemas.values():
            for ref in self._refs(s):
                if ref.startswith("http:") or ref.startswith("https:") or ref.startswith("#"):
                    continue
                target = "https://cps.local/schemas/" + ref.split("#", 1)[0]
                if target not in self.schemas:
                    raise ValueError(f"missing schema ref: {ref}")
        self.validators = {
            h: Draft202012Validator(s, registry=resources)
            for h, (e, s) in self.schema_by_hash.items()
        }
        cas = load(safe(root, index["cas_index"]["path"]))
        self.valid_named(index["schemas"]["cas_index"]["raw_sha256"], cas)
        if cas_index_hash(cas) != cas["index_hash"] or not cas["entries"]:
            raise ValueError("CAS index invalid or empty")
        expected = sorted(
            cas["entries"],
            key=lambda x: (
                bytes.fromhex(x["artifact_hash"][7:]),
                x["artifact_kind"].encode(),
                x["path"].encode(),
            ),
        )
        if expected != cas["entries"]:
            raise ValueError("CAS order invalid")
        self.cas = {}
        for e in cas["entries"]:
            key = (e["artifact_hash"], e["artifact_kind"])
            if key in self.cas:
                raise ValueError("duplicate CAS entry")
            p = safe(root, e["path"])
            raw = p.read_bytes()
            if raw_sha256(raw) != e["raw_sha256"]:
                raise ValueError("CAS raw mismatch")
            se = self.schema_by_hash.get(e["schema_hash"])
            if not se or e["artifact_kind"] not in se[0]["artifact_kinds"]:
                raise ValueError("CAS schema authority mismatch")
            pos = se[0]["artifact_kinds"].index(e["artifact_kind"])
            rule = se[0]["identity_rules"][pos]
            doc = json.loads(raw)
            try:
                self.valid_named(e["schema_hash"], doc)
            except ValueError as exc:
                first = next(self.validators[e["schema_hash"]].iter_errors(doc), None)
                raise ValueError(
                    f"CAS schema invalid: {e['artifact_kind']} {e['path']}: {first}"
                ) from exc
            if artifact_identity(rule, doc) != e["artifact_hash"]:
                raise ValueError("CAS identity mismatch")
            self.cas[key] = doc

    def _refs(self, v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "$ref":
                    yield x
                else:
                    yield from self._refs(x)
        elif isinstance(v, list):
            for x in v:
                yield from self._refs(x)

    def valid_named(self, h, v):
        if h not in self.validators or not self.validators[h].is_valid(v):
            raise ValueError("schema invalid")

    def is_valid(self, h, v):
        return h in self.validators and self.validators[h].is_valid(v)

    def get(self, h, k):
        return self.cas.get((h, k))


def bindings(ctx, m):
    try:
        for k in (
            "sampler_manifest",
            "structural_lowering_manifest",
            "production_lowering_manifest",
            "compiler_manifest",
            "evaluation_manifest",
            "descriptor_spec",
            "fingerprint_spec",
            "qd_manifest",
        ):
            if m["binding_schema_hashes"][k] not in ctx.schema_by_hash:
                return None
            e = ctx.schema_by_hash[m["binding_schema_hashes"][k]][0]
            if k not in e["artifact_kinds"]:
                return None
        for k in (*FIELDS, "fingerprint_component"):
            h = m["candidate_artifact_schema_hashes"][k]
            e = ctx.schema_by_hash.get(h)
            if not e or k not in e[0]["artifact_kinds"]:
                return None
        vals = {
            k: ctx.get(m["bindings"][k + "_hash"], k)
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
        }
        if any(v is None for v in vals.values()):
            return None
        if (
            vals["sampler_manifest"]["structural_lowering_manifest_hash"]
            != m["bindings"]["structural_lowering_manifest_hash"]
            or vals["sampler_manifest"]["compiler_manifest_hash"]
            != m["bindings"]["compiler_manifest_hash"]
        ):
            return None
        if (
            vals["production_lowering_manifest"]["sampler_manifest_hash"]
            != m["bindings"]["sampler_manifest_hash"]
        ):
            return None
        q = vals["qd_manifest"]
        if any(
            q[x + "_hash"] != m["bindings"][x + "_hash"]
            for x in ("descriptor_spec", "fingerprint_spec", "evaluation_manifest")
        ):
            return None
        if q["axis_ids"] != [x["id"] for x in vals["descriptor_spec"]["axes"]]:
            return None
        if m["near_duplicate_policy"]["status"] == "enforced":
            p = m["near_duplicate_policy"]
            cal = ctx.get(p["calibration_decision_hash"], "near_duplicate_calibration_decision")
            if (
                not cal
                or p["calibration_decision_schema_hash"] not in ctx.schema_by_hash
                or cal["status"] != "promoted"
                or cal["fingerprint_spec_hash"] != m["bindings"]["fingerprint_spec_hash"]
                or cal["threshold_q"] != vals["fingerprint_spec"]["near_duplicate_threshold_q"]
            ):
                return None
        return vals
    except (KeyError, TypeError, ValueError):
        return None


def validate_case(m, ledger, report, schemas, ctx):
    if not ctx.is_valid(schemas["report"], report):
        return ERRORS[0]
    if not ctx.is_valid(schemas["manifest"], m):
        return ERRORS[1]
    if manifest_hash(m) != m["manifest_hash"]:
        return ERRORS[2]
    rs = ledger.get("records", [])
    if len(rs) != 1000:
        return ERRORS[3]
    if [x.get("candidate_ordinal") for x in rs] != list(range(1000)):
        return ERRORS[4]
    if any(
        not ctx.is_valid(schemas["candidate_record"], r) or record_hash(r) != r.get("record_hash")
        for r in rs
    ):
        return ERRORS[5]
    if any(
        r["cohort_manifest_hash"] != m["manifest_hash"]
        or r["root_seed"] != m["root_seed"]
        or r["cohort_index"] != r["candidate_ordinal"]
        for r in rs
    ):
        return ERRORS[6]
    bv = bindings(ctx, m)
    if bv is None:
        return ERRORS[7]
    universe = []
    for r in rs:
        a = {
            k: (None if r["artifact_hashes"][k] is None else ctx.get(r["artifact_hashes"][k], k))
            for k in FIELDS
        }
        if any(r["artifact_hashes"][k] is not None and a[k] is None for k in FIELDS):
            return ERRORS[7]
        try:
            rq, sr, pr, ps, p, cr, pj, er, fp, nd = (a[k] for k in FIELDS)
            if rq and (
                rq["root_seed"] != r["root_seed"]
                or rq["cohort_index"] != r["cohort_index"]
                or rq["request_hash"] != r["artifact_hashes"]["sampler_request"]
            ):
                return ERRORS[6]
            if sr and (not rq or sr["request_hash"] != rq["request_hash"]):
                return ERRORS[6]
            if pr and (
                pr["root_seed"] != r["root_seed"]
                or pr["cohort_index"] != r["cohort_index"]
                or pr["request_hash"] != r["artifact_hashes"]["production_request"]
            ):
                return ERRORS[6]
            if ps and (not pr or ps["request_hash"] != pr["request_hash"]):
                return ERRORS[6]
            if pr:
                sph = domain_hash("cps.structural-song-program/1.0", pr["structural_program"])
                if pr["structural_program_hash"] != sph or (
                    sr and sr["structural_program_hash"] != sph
                ):
                    return ERRORS[7]
            if ps:
                if (
                    not p
                    or ps["output"]["program"] != p
                    or ps["output"]["program_hash"] != r["artifact_hashes"]["program"]
                ):
                    return ERRORS[7]
            if cr and (
                cr["source_program_hash"] != r["artifact_hashes"]["program"]
                or cr["compiler_manifest_hash"] != m["bindings"]["compiler_manifest_hash"]
                or cr["compiler_build_id"] != bv["compiler_manifest"]["build_id"]
            ):
                return ERRORS[7]
            if pj and (
                pj["source_program"]["hash"] != r["artifact_hashes"]["program"]
                or pj["compiler"]["build_id"] != bv["compiler_manifest"]["build_id"]
            ):
                return ERRORS[7]
            if (
                cr
                and cr["status"] == "success"
                and cr["project_hash"] != r["artifact_hashes"]["project"]
            ):
                return ERRORS[7]
            if er:
                if (er["evaluation_manifest_hash"], er["program_hash"], er["project_hash"]) != (
                    m["bindings"]["evaluation_manifest_hash"],
                    r["artifact_hashes"]["program"],
                    r["artifact_hashes"]["project"],
                ):
                    return ERRORS[7]
                hard = {(x["id"], x["ordinal"]): x for x in er["hard_checks"]}
                required = [
                    (x["id"], x["ordinal"]) for x in bv["evaluation_manifest"]["hard_checks"]
                ]
                auto = all(k in hard and hard[k]["passed"] for k in required)
                mets = {(x["id"], x["ordinal"]): x for x in er["metrics"]}
                tr = [
                    x
                    for x in bv["evaluation_manifest"]["metrics"]
                    if x["id"] == "transformed_recall_count"
                ]
                if len(tr) != 1 or (tr[0]["id"], tr[0]["ordinal"]) not in mets:
                    return ERRORS[7]
                recall = mets[(tr[0]["id"], tr[0]["ordinal"])]["value"] >= 1
                vals = {}
                for ax in bv["descriptor_spec"]["axes"]:
                    defs = [x for x in bv["evaluation_manifest"]["metrics"] if x["id"] == ax["id"]]
                    if len(defs) != 1 or (ax["id"], defs[0]["ordinal"]) not in mets:
                        return ERRORS[7]
                    vals[ax["id"]] = mets[(ax["id"], defs[0]["ordinal"])]["value"]
                if (
                    auto != r["automatic_viable"]
                    or recall != r["has_transformed_recall"]
                    or qd_cell(bv["descriptor_spec"], vals) != r["qd_cell"]
                ):
                    return ERRORS[7]
            payload = {}
            if fp:
                if (
                    fp["fingerprint_spec_hash"] != m["bindings"]["fingerprint_spec_hash"]
                    or fp["project_hash"] != r["artifact_hashes"]["project"]
                ):
                    return ERRORS[7]
                specs = bv["fingerprint_spec"]["components"]
                if [x["id"] for x in fp["component_hashes"]] != [x["id"] for x in specs] or fp[
                    "fingerprint_hash"
                ] != fingerprint_hash([x["hash"] for x in fp["component_hashes"]]):
                    return ERRORS[7]
                for x in fp["component_hashes"]:
                    z = ctx.get(x["hash"], "fingerprint_component")
                    if not z or z["id"] != x["id"] or z["component_hash"] != x["hash"]:
                        return ERRORS[7]
                    payload[x["id"]] = z["payload"]
            if nd:
                if not fp or (
                    nd["candidate_ordinal"],
                    nd["candidate_program_hash"],
                    nd["candidate_fingerprint_hash"],
                    nd["fingerprint_spec_hash"],
                    nd["threshold_q"],
                ) != (
                    r["candidate_ordinal"],
                    r["artifact_hashes"]["program"],
                    fp["fingerprint_hash"],
                    m["bindings"]["fingerprint_spec_hash"],
                    bv["fingerprint_spec"]["near_duplicate_threshold_q"],
                ):
                    return ERRORS[7]
                cs = []
                for old in sorted(universe, key=lambda x: bytes.fromhex(x["program_hash"][7:])):
                    ds, ag = fingerprint_distances(bv["fingerprint_spec"], payload, old["payload"])
                    cs.append(
                        {
                            "program_hash": old["program_hash"],
                            "fingerprint_hash": old["fingerprint_hash"],
                            "component_distances_q": ds,
                            "aggregate_distance_q": ag,
                        }
                    )
                pgs = [x["program_hash"] for x in cs]
                exact = next(
                    (x for x in cs if x["program_hash"] == nd["candidate_program_hash"]), None
                )
                near = (
                    None
                    if not cs
                    else min(
                        cs,
                        key=lambda x: (
                            x["aggregate_distance_q"],
                            tuple(x["component_distances_q"]),
                            bytes.fromhex(x["program_hash"][7:]),
                        ),
                    )
                )
                if exact:
                    clas, rep, nv = "exact_duplicate", nd["candidate_program_hash"], exact
                elif near and near["aggregate_distance_q"] <= nd["threshold_q"]:
                    clas, rep, nv = "near_duplicate", near["program_hash"], near
                else:
                    clas, rep, nv = "distinct", nd["candidate_program_hash"], near
                if (
                    nd["comparison_program_hashes"],
                    nd["comparison_set_hash"],
                    nd["nearest"],
                    nd["classification"],
                    nd["representative_program_hash"],
                ) != (pgs, comparison_set_hash(pgs), nv, clas, rep):
                    return ERRORS[7]
            else:
                clas = None
        except (KeyError, TypeError, ValueError):
            return ERRORS[7]
        if not presence(r) or bool(r["compile_success"]) != (
            r["terminal_stage"] in {"evaluation", "fingerprint", "duplicate", "complete"}
        ):
            return ERRORS[8]
        status = {
            "sampler": sr and sr["status"] == "failure" and r["terminal_code"] == sr["error"],
            "production": ps and ps["status"] == "failure" and r["terminal_code"] == ps["error"],
            "compiler": cr
            and cr["status"] == "failure"
            and r["terminal_code"] == cr["error"]["code"],
            "evaluation": er
            and er["status"] == "failure"
            and r["terminal_code"] == er["failure_code"],
            "fingerprint": r["terminal_code"] == "FINGERPRINT_COMPUTATION_FAILED",
            "duplicate": r["terminal_code"] == "NEAR_DUPLICATE_DECISION_FAILED",
            "complete": r["terminal_code"] is None,
        }.get(r["terminal_stage"])
        if not status:
            return ERRORS[8]
        if (r["terminal_stage"] == "complete") != (r["duplicate_classification"] is not None) or (
            nd and r["duplicate_classification"] != clas
        ):
            return ERRORS[9]
        expected = (
            derive_mode_keys(payload)
            if r["terminal_stage"] == "complete"
            else {x: [] for x in FAMILIES}
        )
        if r["mode_keys"] != expected:
            return ERRORS[10]
        if r["terminal_stage"] == "complete" and clas == "distinct":
            universe.append(
                {
                    "program_hash": r["artifact_hashes"]["program"],
                    "fingerprint_hash": fp["fingerprint_hash"],
                    "payload": payload,
                }
            )
    if ledger.get("cohort_manifest_hash") != m["manifest_hash"] or ledger.get(
        "ledger_hash"
    ) != ledger_hash(rs):
        return ERRORS[11]
    exp = build_report(m, rs)
    if any(
        report.get(x) != exp[x]
        for x in (
            "candidate_count",
            "terminal_stage_counts",
            "counts",
            "rates_bp",
            "qd_occupied_cells",
            "mode_maxima",
        )
    ):
        return ERRORS[12]
    if any(report.get(x) != exp[x] for x in ("gates", "initial_gen0_passed", "planner_eligible")):
        return ERRORS[13]
    if report.get("report_hash") != report_hash(report):
        return ERRORS[14]
    return None


def validate_suite(root: Path):
    index = load(safe(root, "suite_index.json"))
    if suite_hash(index) != index["suite_hash"]:
        raise ValueError("suite hash mismatch")
    ctx = Context(root, index)
    schemas = {k: v["raw_sha256"] for k, v in index["schemas"].items()}
    if not ctx.is_valid(schemas["suite_index"], index):
        raise ValueError("suite index schema invalid")
    for ref in (
        list(index["schemas"].values())
        + [index["cas_index"], index["matrix_receipt"]]
        + [
            z
            for x in index["cases"]
            for z in [x["manifest"], x["records"], x.get("expected_report", x.get("input_report"))]
        ]
    ):
        if raw_sha256(safe(root, ref["path"]).read_bytes()) != ref["raw_sha256"]:
            raise ValueError("raw fixture mismatch")
    receipt = load(safe(root, index["matrix_receipt"]["path"]))
    ctx.valid_named(schemas["matrix_receipt"], receipt)
    if matrix_receipt_hash(receipt) != receipt["receipt_hash"] or [
        (x["python_hash_seed"], x["workers"]) for x in receipt["coordinates"]
    ] != [(s, w) for s in (0, 1, 7, 42) for w in (1, 2, 4, 8)]:
        raise ValueError("matrix receipt invalid")
    results = {}
    for case in index["cases"]:
        m = load(root / case["manifest"]["path"])
        le = load(root / case["records"]["path"])
        ref = case.get("expected_report", case.get("input_report"))
        code = validate_case(m, le, load(root / ref["path"]), schemas, ctx)
        want = None if case["kind"] == "success" else case["expected_code"]
        if code != want:
            raise ValueError(f"{case['case_id']}: expected {want}, got {code}")
        results[case["case_id"]] = code
    cov = [z for x in index["cases"] for z in x["coverage"]]
    if sorted(cov) != sorted(index["coverage"]) or len(cov) != 34:
        raise ValueError("coverage mismatch")
    return {"case_count": len(index["cases"]), "coverage_count": len(cov), "results": results}
