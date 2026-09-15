"""Independent GEN0 cohort aggregation and identity oracle.

This module intentionally imports no production sampler/compiler/evaluator code.
Artifact/CAS validation is performed by the fixture validator before values are
passed to :func:`build_report`.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence


FAMILIES = (
    "root_anchor_ngram",
    "chord_intent_ngram",
    "harmony_rhythm_fingerprint",
)
STAGES = ("sampler", "production", "compiler", "evaluation", "fingerprint", "duplicate", "complete")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def raw_sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def domain_hash(domain: str, value: Any, *, lf: bool = True) -> str:
    payload = canonical(value) + (b"\n" if lf else b"")
    return raw_sha256(domain.encode("utf-8") + b"\0" + payload)


def without(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != field}


def manifest_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-gate-manifest/v1", without(value, "manifest_hash"))


def record_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-candidate-record/v1", without(value, "record_hash"))


def ledger_hash(records: Sequence[Mapping[str, Any]]) -> str:
    return domain_hash("cps.gen0-cohort-ledger/v1", [row["record_hash"] for row in records])


def report_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-gate-report/v1", without(value, "report_hash"))


def suite_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-gate-fixture-suite-index/v1", without(value, "suite_hash"))


def matrix_receipt_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-gate-matrix-receipt/v1", without(value, "receipt_hash"))


def cas_index_hash(value: Mapping[str, Any]) -> str:
    return domain_hash("cps.gen0-cohort-gate-cas-index/v1", without(value, "index_hash"))


def fingerprint_hash(component_hashes: Sequence[str]) -> str:
    return domain_hash("cps.musical-fingerprint/v1", list(component_hashes))


def comparison_set_hash(program_hashes: Sequence[str]) -> str:
    value = {
        "schema": "cps.near-duplicate-comparison-set",
        "schema_version": "1.0.0",
        "program_hashes": list(program_hashes),
    }
    return generic_artifact_hash(value)


def _rhe(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    remainder = value.numerator % value.denominator
    doubled = remainder * 2
    if doubled < value.denominator:
        return floor
    if doubled > value.denominator:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def component_distance(kind: str, left: Sequence[Any], right: Sequence[Any]) -> int:
    """Return the closed 0..10000 GEN0 component distance."""
    if kind == "padded_hamming":
        size = max(len(left), len(right))
        if size == 0:
            return 0
        mismatches = sum(
            (left[index] if index < len(left) else None)
            != (right[index] if index < len(right) else None)
            for index in range(size)
        )
        return _rhe(Fraction(10000 * mismatches, size))
    left_counter = Counter(canonical(item) for item in left)
    right_counter = Counter(canonical(item) for item in right)
    if kind == "set_jaccard":
        left_counter = Counter(left_counter.keys())
        right_counter = Counter(right_counter.keys())
    elif kind != "multiset_jaccard":
        raise ValueError(f"unknown component distance: {kind}")
    keys = set(left_counter) | set(right_counter)
    union = sum(max(left_counter[key], right_counter[key]) for key in keys)
    if union == 0:
        return 0
    intersection = sum(min(left_counter[key], right_counter[key]) for key in keys)
    return _rhe(Fraction(10000 * (union - intersection), union))


def fingerprint_distances(
    spec: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[list[int], int]:
    distances = [
        component_distance(component["distance"], left[component["id"]], right[component["id"]])
        for component in spec["components"]
    ]
    weights = [component["weight"] for component in spec["components"]]
    aggregate = _rhe(Fraction(sum(a * b for a, b in zip(distances, weights)), sum(weights)))
    return distances, aggregate


def qd_cell(descriptor: Mapping[str, Any], metric_values: Mapping[str, Any]) -> list[int] | None:
    result: list[int] = []
    for axis in descriptor["axes"]:
        value = metric_values.get(axis["id"])
        if value is None:
            return None
        edges = axis["bin_edges"]
        bins = [
            index for index, (low, high) in enumerate(zip(edges, edges[1:])) if low <= value < high
        ]
        if len(bins) != 1:
            return None
        result.append(bins[0])
    return result


def generic_artifact_hash(value: Mapping[str, Any], omitted: str | None = None) -> str:
    body = dict(value) if omitted is None else without(value, omitted)
    prefix = f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0".encode()
    return raw_sha256(prefix + canonical(body))


def artifact_identity(rule: str, value: Mapping[str, Any]) -> str:
    """Apply a closed registry identity-rule ID without production imports."""
    rules: dict[str, tuple[str, str | None, bool]] = {
        "sampler-manifest-v1.1": ("cps.sampler-manifest/v1.1", "manifest_hash", True),
        "structural-lowering-manifest-v1": (
            "cps.structural-lowering-manifest/v1",
            "manifest_hash",
            True,
        ),
        "production-lowering-manifest-v1": ("cps.production-lowering-manifest/v1", None, True),
        "compiler-manifest-v1.1": ("cps.compiler-manifest/v1.1", None, True),
        "fingerprint-spec-v1": ("cps.fingerprint-spec/v1", None, True),
        "descriptor-spec-v1": ("cps.descriptor-spec/v1", None, True),
        "qd-manifest-v1": ("cps.qd-manifest/v1", None, True),
        "near-duplicate-calibration-decision-v1": (
            "cps.near-duplicate-calibration-decision/v1",
            "decision_hash",
            True,
        ),
        "structural-sampler-result-v1.1": (
            "cps.structural-sampler-result/v1.1",
            "result_hash",
            True,
        ),
        "broad-prior-production-result-v1.1": (
            "cps.broad-prior-production-result/v1.1",
            "result_hash",
            True,
        ),
    }
    if rule in rules:
        domain, omitted, lf = rules[rule]
        return domain_hash(domain, value if omitted is None else without(value, omitted), lf=lf)
    if rule == "evaluation-manifest-v1.1":
        return generic_artifact_hash(value, "manifest_hash")
    if rule == "generic-cps-artifact-v1":
        omitted = {
            "cps.evaluation-manifest": "manifest_hash",
            "cps.structural-sampler-request": "request_hash",
            "cps.broad-prior-production-request": "request_hash",
            "cps.evaluation-report": "report_hash",
            "cps.near-duplicate-decision": "decision_hash",
        }.get(value["schema"])
        return generic_artifact_hash(value, omitted)
    if rule == "fingerprint-component-v1":
        return domain_hash(
            "cps.fingerprint-component/v1", {"id": value["id"], "payload": value["payload"]}
        )
    if rule == "song-program-v0.1":
        return raw_sha256(b"cps.song-program/0.1\0" + canonical(without(value, "program_id")))
    if rule == "arrangement-project-v1.2":
        return raw_sha256(
            value["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + canonical(value)
        )
    raise ValueError(f"unknown identity rule: {rule}")


def mode_key(family: str, payload: Any) -> str:
    if family not in FAMILIES:
        raise ValueError("unknown mode family")
    return domain_hash("cps.gen0-cohort-mode-key/v1", [family, payload])


def sequence_windows(payload: Sequence[Any]) -> list[Any]:
    if not payload:
        return [[]]
    if len(payload) == 1:
        return [[payload[0]]]
    return [[payload[index], payload[index + 1]] for index in range(len(payload) - 1)]


def derive_mode_keys(components: Mapping[str, Any]) -> dict[str, list[str]]:
    root = {
        mode_key(FAMILIES[0], value) for value in sequence_windows(components["root_anchor_deltas"])
    }
    chord = {mode_key(FAMILIES[1], value) for value in sequence_windows(components["chord_steps"])}
    harmony_payload = [
        components["role_time_grid"],
        components["root_anchor_deltas"],
        components["chord_steps"],
        components["sounding_intervals"],
    ]
    harmony = {mode_key(FAMILIES[2], harmony_payload)}
    return {
        family: sorted(values, key=lambda item: bytes.fromhex(item[7:]))
        for family, values in zip(FAMILIES, (root, chord, harmony))
    }


def _gate(value: int, comparator: str, threshold: int, status: str | None = None) -> dict[str, Any]:
    passed = {"ge": value >= threshold, "lt": value < threshold, "le": value <= threshold}[
        comparator
    ]
    return {
        "value_bp": value,
        "comparator": comparator,
        "threshold_bp": threshold,
        "status": status or ("passed" if passed else "failed"),
    }


def _maximum(rows: Iterable[tuple[str, int]]) -> tuple[str | None, int]:
    values = list(rows)
    if not values:
        return None, 0
    values.sort(key=lambda row: (-row[1], bytes.fromhex(row[0][7:])))
    return values[0]


def build_report(
    manifest: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if len(records) != 1000:
        raise ValueError("cohort must contain exactly 1000 records")
    if [row["candidate_ordinal"] for row in records] != list(range(1000)):
        raise ValueError("records are not in ordinal order")
    stage_counts = Counter(row["terminal_stage"] for row in records)
    classifications = Counter(row["duplicate_classification"] for row in records)
    counts = {
        "compile_success": sum(bool(row["compile_success"]) for row in records),
        "automatic_viable": sum(bool(row["automatic_viable"]) for row in records),
        "exact_duplicate": classifications["exact_duplicate"],
        "near_duplicate": classifications["near_duplicate"],
        "distinct": classifications["distinct"],
        "transformed_recall": sum(bool(row["has_transformed_recall"]) for row in records),
    }
    rates = {
        key: counts[key] * 10
        for key in (
            "compile_success",
            "automatic_viable",
            "exact_duplicate",
            "near_duplicate",
            "transformed_recall",
        )
    }
    family_counts = {family: Counter() for family in FAMILIES}
    for row in records:
        if row["terminal_stage"] == "complete":
            for family in FAMILIES:
                family_counts[family].update(set(row["mode_keys"][family]))
    maxima = []
    for family in FAMILIES:
        key, count = _maximum(family_counts[family].items())
        maxima.append(
            {"family": family, "key": key, "candidate_count": count, "prevalence_bp": count * 10}
        )
    mode_value = max(row["prevalence_bp"] for row in maxima)
    thresholds = manifest["thresholds_bp"]
    near_status = (
        "not_enforced" if manifest["near_duplicate_policy"]["status"] == "audit_only" else None
    )
    gates = {
        "compile_success": _gate(rates["compile_success"], "ge", thresholds["compile_success_ge"]),
        "initial_viability": _gate(
            rates["automatic_viable"], "ge", thresholds["initial_viability_ge"]
        ),
        "planner_viability": _gate(
            rates["automatic_viable"], "ge", thresholds["planner_viability_ge"]
        ),
        "exact_duplicate": _gate(rates["exact_duplicate"], "lt", thresholds["exact_duplicate_lt"]),
        "near_duplicate": _gate(
            rates["near_duplicate"], "lt", thresholds["near_duplicate_lt"], near_status
        ),
        "transformed_recall": _gate(
            rates["transformed_recall"], "ge", thresholds["transformed_recall_ge"]
        ),
        "mode_prevalence": _gate(mode_value, "le", thresholds["mode_prevalence_le"]),
    }
    initial = all(
        gates[key]["status"] == "passed"
        for key in (
            "compile_success",
            "initial_viability",
            "exact_duplicate",
            "transformed_recall",
            "mode_prevalence",
        )
    )
    planner = (
        initial
        and gates["planner_viability"]["status"] == "passed"
        and gates["near_duplicate"]["status"] == "passed"
    )
    report = {
        "schema": "cps.gen0-cohort-gate-report",
        "schema_version": "1.0.0",
        "status": "success",
        "cohort_manifest_hash": manifest["manifest_hash"],
        "ledger_hash": ledger_hash(records),
        "candidate_count": 1000,
        "terminal_stage_counts": {stage: stage_counts[stage] for stage in STAGES},
        "counts": counts,
        "rates_bp": rates,
        "qd_occupied_cells": sorted(
            {
                tuple(row["qd_cell"])
                for row in records
                if row["automatic_viable"]
                and row["duplicate_classification"] == "distinct"
                and row["qd_cell"] is not None
            }
        ),
        "mode_maxima": maxima,
        "gates": gates,
        "initial_gen0_passed": initial,
        "planner_eligible": planner,
        "failure_code": None,
    }
    report["qd_occupied_cells"] = [list(cell) for cell in report["qd_occupied_cells"]]
    report["report_hash"] = report_hash(report)
    return report
