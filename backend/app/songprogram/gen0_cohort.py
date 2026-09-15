"""GEN0 1,000-seed cohort gate — production aggregation and validation.

Normative source: ``docs/song_program_gen0_cohort_gate_contract.md``
(``cps-gen0-cohort-gate/v1``).  A cohort report observes already-produced
artifacts; it never repairs, retries, discards, or reorders a candidate, and
it never promotes any ``pil.*`` metric.

This module implements the artifact-free validation stages and the full
aggregate/report layer:

- canonical identities (section 6): manifest, record, ledger, CAS-index and
  report hashes plus mode-key derivation;
- record structure, coordinate, presence-matrix, classification and
  mode-key-set checks that do not require CAS resolution (validation
  precedence section 7 stages 1-6 and 12-15, plus the artifact-free parts of
  stages 7 and 9-11);
- aggregate counts, round-half-even basis-point rates, mode maxima, gate
  evaluation and report construction (sections 2, 4 and 5).

Deep artifact-binding validation (CAS resolution, request/result cross-links,
fingerprint component and near-duplicate recomputation — the resolver-bound
parts of stages 7-11) requires the oracle-published CAS and is layered on top
of this module; production code never creates authoritative expected hashes
(section 8).
"""

from __future__ import annotations

import hashlib
from fractions import Fraction
from typing import Any, Mapping, Sequence

from .compiler import _canonical, _rhe

COHORT_CONTRACT = "cps-gen0-cohort-gate/v1"
MANIFEST_SCHEMA = "cps.gen0-cohort-gate-manifest"
RECORD_SCHEMA = "cps.gen0-cohort-candidate-record"
LEDGER_SCHEMA = "cps.gen0-cohort-candidate-ledger"
REPORT_SCHEMA = "cps.gen0-cohort-gate-report"
COHORT_SCHEMA_VERSION = "1.0.0"
COHORT_SIZE = 1000

TERMINAL_STAGES = (
    "sampler",
    "production",
    "compiler",
    "evaluation",
    "fingerprint",
    "duplicate",
    "complete",
)
MODE_FAMILIES = ("root_anchor_ngram", "chord_intent_ngram", "harmony_rhythm_fingerprint")
DUPLICATE_CLASSES = ("exact_duplicate", "near_duplicate", "distinct")

THRESHOLDS_BP = {
    "compile_success_ge": 9500,
    "initial_viability_ge": 7000,
    "planner_viability_ge": 8000,
    "exact_duplicate_lt": 100,
    "near_duplicate_lt": 1000,
    "transformed_recall_ge": 8000,
    "mode_prevalence_le": 3500,
}

_ARTIFACT_KEYS = (
    "sampler_result",
    "production_result",
    "program",
    "compile_report",
    "project",
    "evaluation_report",
    "fingerprint_record",
    "near_duplicate_decision",
)
# Presence matrix (contract section 3): how many entries of
# ``_ARTIFACT_KEYS`` (pipeline order) are non-null per terminal stage.  A
# failed result/report ("F") is non-null; only later stages are null.
_STAGE_NON_NULL_COUNT = {
    "sampler": 1,
    "production": 2,
    "compiler": 4,
    "evaluation": 6,
    "fingerprint": 6,
    "duplicate": 7,
    "complete": 8,
}
_FIXED_TERMINAL_CODES = {
    "fingerprint": "FINGERPRINT_COMPUTATION_FAILED",
    "duplicate": "NEAR_DUPLICATE_DECISION_FAILED",
}
_SHA_PREFIX = "sha256:"


class CohortGateError(Exception):
    """Stable out-of-band validation failure (contract section 7)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise CohortGateError(code)


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith(_SHA_PREFIX)
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _is_nullable_sha(value: Any) -> bool:
    return value is None or _is_sha(value)


def _is_u64(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**64


def _cohort_hash(domain: str, value: Any) -> str:
    digest = hashlib.sha256(
        domain.encode("utf-8") + b"\0" + _canonical(value) + b"\n"
    ).hexdigest()
    return _SHA_PREFIX + digest


# ---------------------------------------------------------------------------
# Canonical identities (contract section 6)
# ---------------------------------------------------------------------------


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    body = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return _cohort_hash("cps.gen0-cohort-gate-manifest/v1", body)


def record_hash(record: Mapping[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "record_hash"}
    return _cohort_hash("cps.gen0-cohort-candidate-record/v1", body)


def ledger_hash(record_hashes: Sequence[str]) -> str:
    return _cohort_hash("cps.gen0-cohort-ledger/v1", list(record_hashes))


def cas_index_hash(index: Mapping[str, Any]) -> str:
    body = {key: value for key, value in index.items() if key != "index_hash"}
    return _cohort_hash("cps.gen0-cohort-gate-cas-index/v1", body)


def report_hash(report: Mapping[str, Any]) -> str:
    body = {key: value for key, value in report.items() if key != "report_hash"}
    return _cohort_hash("cps.gen0-cohort-gate-report/v1", body)


def mode_key(family: str, payload: Any) -> str:
    """Public mode key (contract section 4)."""
    if family not in MODE_FAMILIES:
        _fail("COHORT_MODE_KEY_INVALID")
    return _cohort_hash("cps.gen0-cohort-mode-key/v1", [family, payload])


def rate_bp(count: int) -> int:
    """RHE(10000 * count / 1000); the fixed denominator keeps rates exact."""
    if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= COHORT_SIZE:
        _fail("COHORT_AGGREGATE_MISMATCH")
    return _rhe(Fraction(10_000 * count, COHORT_SIZE))


# ---------------------------------------------------------------------------
# Manifest validation (contract sections 2 and 7)
# ---------------------------------------------------------------------------


def validate_cohort_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "contract",
        "root_seed",
        "cohort_size",
        "coordinate_rule",
        "bindings",
        "binding_schema_hashes",
        "thresholds_bp",
        "rate_algorithm",
        "mode_algorithm",
        "near_duplicate_policy",
        "manifest_hash",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != required:
        _fail("COHORT_MANIFEST_INVALID")
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("schema_version") != COHORT_SCHEMA_VERSION
        or manifest.get("contract") != COHORT_CONTRACT
        or not _is_u64(manifest.get("root_seed"))
        or manifest.get("cohort_size") != COHORT_SIZE
        or manifest.get("coordinate_rule")
        != "candidate-ordinal-equals-cohort-index-0-through-999/v1"
        or manifest.get("rate_algorithm") != "round-half-even-10000-times-count-over-1000/v1"
        or manifest.get("mode_algorithm")
        != "order2-root-chord-plus-harmony-rhythm-candidate-prevalence/v1"
    ):
        _fail("COHORT_MANIFEST_INVALID")
    bindings = manifest.get("bindings")
    binding_keys = {
        "sampler_manifest_hash",
        "structural_lowering_manifest_hash",
        "production_lowering_manifest_hash",
        "compiler_manifest_hash",
        "evaluation_manifest_hash",
        "fingerprint_spec_hash",
        "qd_manifest_hash",
        "candidate_record_schema_hash",
        "gate_report_schema_hash",
    }
    if (
        not isinstance(bindings, Mapping)
        or set(bindings) != binding_keys
        or any(not _is_sha(value) for value in bindings.values())
    ):
        _fail("COHORT_MANIFEST_INVALID")
    schema_hashes = manifest.get("binding_schema_hashes")
    schema_kinds = {
        "sampler_manifest",
        "structural_lowering_manifest",
        "production_lowering_manifest",
        "compiler_manifest",
        "evaluation_manifest",
        "fingerprint_spec",
        "qd_manifest",
    }
    if (
        not isinstance(schema_hashes, Mapping)
        or set(schema_hashes) != schema_kinds
        or any(not _is_sha(value) for value in schema_hashes.values())
    ):
        _fail("COHORT_MANIFEST_INVALID")
    if manifest.get("thresholds_bp") != THRESHOLDS_BP:
        _fail("COHORT_MANIFEST_INVALID")
    policy = manifest.get("near_duplicate_policy")
    if (
        not isinstance(policy, Mapping)
        or set(policy) != {"status", "calibration_decision_hash"}
        or (
            policy.get("status") == "audit_only"
            and policy.get("calibration_decision_hash") is not None
        )
        or (
            policy.get("status") == "enforced"
            and not _is_sha(policy.get("calibration_decision_hash"))
        )
        or policy.get("status") not in ("audit_only", "enforced")
    ):
        _fail("COHORT_MANIFEST_INVALID")
    if not _is_sha(manifest.get("manifest_hash")):
        _fail("COHORT_MANIFEST_INVALID")
    if manifest["manifest_hash"] != manifest_hash(manifest):
        _fail("COHORT_MANIFEST_HASH_MISMATCH")


# ---------------------------------------------------------------------------
# Record and ledger validation (contract sections 3 and 7)
# ---------------------------------------------------------------------------


def _validate_record_structure(record: Mapping[str, Any]) -> None:
    """Schema-level record shape; the contract names no record-schema code, so
    a malformed record can never reach later stages and is reported as
    ``COHORT_RECORD_HASH_MISMATCH`` only when its hash recomputes cleanly."""
    required = {
        "schema",
        "schema_version",
        "cohort_manifest_hash",
        "candidate_ordinal",
        "root_seed",
        "cohort_index",
        "terminal_stage",
        "terminal_code",
        "artifact_hashes",
        "compile_success",
        "automatic_viable",
        "has_transformed_recall",
        "duplicate_classification",
        "qd_cell",
        "mode_keys",
        "record_hash",
    }
    if not isinstance(record, Mapping) or set(record) != required:
        _fail("COHORT_RECORD_HASH_MISMATCH")
    if (
        record.get("schema") != RECORD_SCHEMA
        or record.get("schema_version") != COHORT_SCHEMA_VERSION
        or not _is_sha(record.get("cohort_manifest_hash"))
        or not _is_sha(record.get("record_hash"))
        or record.get("terminal_stage") not in TERMINAL_STAGES
        or not isinstance(record.get("compile_success"), bool)
        or not isinstance(record.get("automatic_viable"), bool)
        or not isinstance(record.get("has_transformed_recall"), bool)
        or record.get("duplicate_classification") not in (*DUPLICATE_CLASSES, None)
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")
    ordinal = record.get("candidate_ordinal")
    index = record.get("cohort_index")
    if (
        not _is_u64(record.get("root_seed"))
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or not isinstance(index, int)
        or isinstance(index, bool)
        or not 0 <= ordinal < COHORT_SIZE
        or not 0 <= index < COHORT_SIZE
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")
    terminal_code = record.get("terminal_code")
    if terminal_code is not None and not (
        isinstance(terminal_code, str)
        and terminal_code
        and terminal_code.upper() == terminal_code
        and all(character.isalnum() or character == "_" for character in terminal_code)
        and terminal_code[0].isalpha()
        and len(terminal_code) <= 128
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")
    hashes = record.get("artifact_hashes")
    if (
        not isinstance(hashes, Mapping)
        or set(hashes) != set(_ARTIFACT_KEYS)
        or any(not _is_nullable_sha(value) for value in hashes.values())
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")
    cell = record.get("qd_cell")
    if cell is not None and not (
        isinstance(cell, list)
        and len(cell) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in cell)
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")
    mode_keys = record.get("mode_keys")
    if (
        not isinstance(mode_keys, Mapping)
        or set(mode_keys) != set(MODE_FAMILIES)
        or any(
            not isinstance(keys, list)
            or len(keys) != len(set(keys))
            or any(not _is_sha(key) for key in keys)
            for keys in mode_keys.values()
        )
    ):
        _fail("COHORT_RECORD_HASH_MISMATCH")


def _validate_record_coordinate(
    record: Mapping[str, Any], ordinal: int, manifest: Mapping[str, Any]
) -> None:
    """Artifact-free coordinate checks (stage 7)."""
    if (
        record["candidate_ordinal"] != ordinal
        or record["cohort_index"] != ordinal
        or record["root_seed"] != manifest["root_seed"]
        or record["cohort_manifest_hash"] != manifest["manifest_hash"]
    ):
        _fail("COHORT_COORDINATE_MISMATCH")


def _validate_record_presence(record: Mapping[str, Any]) -> None:
    """Artifact-free presence matrix and fixed terminal codes (stage 9)."""
    stage = record["terminal_stage"]
    stage_index = TERMINAL_STAGES.index(stage)
    non_null = _STAGE_NON_NULL_COUNT[stage]
    hashes = record["artifact_hashes"]
    for position, key in enumerate(_ARTIFACT_KEYS):
        if (hashes[key] is not None) != (position < non_null):
            _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    terminal_code = record["terminal_code"]
    if stage in _FIXED_TERMINAL_CODES:
        if terminal_code != _FIXED_TERMINAL_CODES[stage]:
            _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    elif stage == "complete":
        if terminal_code is not None:
            _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    elif terminal_code is None:
        _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    # Derived facts follow the terminal stage (contract section 3).
    if record["compile_success"] != (stage_index >= TERMINAL_STAGES.index("evaluation")):
        _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    if record["automatic_viable"] and stage_index < TERMINAL_STAGES.index("fingerprint"):
        _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    if record["has_transformed_recall"] and stage_index < TERMINAL_STAGES.index("fingerprint"):
        _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    if record["duplicate_classification"] is not None and stage != "complete":
        _fail("COHORT_STAGE_PRECEDENCE_INVALID")
    if stage == "complete" and record["duplicate_classification"] is None:
        _fail("COHORT_DUPLICATE_CLASSIFICATION_INVALID")


def validate_cohort_ledger(
    ledger: Mapping[str, Any], manifest: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Validate ledger shape, record order/hashes and the ledger hash.

    Returns the ordered records.  Validation stops at the first applicable
    code (contract section 7).
    """
    required = {"schema", "schema_version", "cohort_manifest_hash", "records", "ledger_hash"}
    if (
        not isinstance(ledger, Mapping)
        or set(ledger) != required
        or ledger.get("schema") != LEDGER_SCHEMA
        or ledger.get("schema_version") != COHORT_SCHEMA_VERSION
        or not _is_sha(ledger.get("ledger_hash"))
    ):
        _fail("COHORT_REPORT_SCHEMA_INVALID")
    if ledger.get("cohort_manifest_hash") != manifest["manifest_hash"]:
        _fail("COHORT_MANIFEST_HASH_MISMATCH")
    records = ledger.get("records")
    if not isinstance(records, list) or len(records) != COHORT_SIZE:
        _fail("COHORT_RECORD_COUNT_MISMATCH")
    ordinals = [record.get("candidate_ordinal") if isinstance(record, Mapping) else None
                for record in records]
    if ordinals != list(range(COHORT_SIZE)):
        _fail("COHORT_RECORD_ORDER_INVALID")
    for record in records:
        _validate_record_structure(record)
        if record["record_hash"] != record_hash(record):
            _fail("COHORT_RECORD_HASH_MISMATCH")
    for ordinal, record in enumerate(records):
        _validate_record_coordinate(record, ordinal, manifest)
        _validate_record_presence(record)
    if ledger["ledger_hash"] != ledger_hash([record["record_hash"] for record in records]):
        _fail("COHORT_LEDGER_HASH_MISMATCH")
    return records


# ---------------------------------------------------------------------------
# Aggregation and gates (contract sections 4 and 5)
# ---------------------------------------------------------------------------


def _mode_maximum(records: Sequence[Mapping[str, Any]], family: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records:
        for key in record["mode_keys"][family]:
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return {"family": family, "key": None, "candidate_count": 0, "prevalence_bp": 0}
    best = min(
        counts.items(),
        key=lambda item: (-item[1], bytes.fromhex(item[0][len(_SHA_PREFIX):])),
    )
    return {
        "family": family,
        "key": best[0],
        "candidate_count": best[1],
        "prevalence_bp": rate_bp(best[1]),
    }


def _gate(value_bp: int, comparator: str, threshold_bp: int) -> dict[str, Any]:
    if comparator == "ge":
        passed = value_bp >= threshold_bp
    elif comparator == "lt":
        passed = value_bp < threshold_bp
    elif comparator == "le":
        passed = value_bp <= threshold_bp
    else:  # pragma: no cover - internal comparators are fixed
        _fail("COHORT_GATE_RESULT_MISMATCH")
    return {
        "value_bp": value_bp,
        "comparator": comparator,
        "threshold_bp": threshold_bp,
        "status": "passed" if passed else "failed",
    }


def build_gen0_cohort_report(
    manifest: Mapping[str, Any], ledger: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate the bound manifest and ledger, then aggregate the report.

    Rates use ``RHE(10000 * count / 1000)``; every gate comparator is exact
    (contract sections 2 and 5).  A validation failure raises
    :class:`CohortGateError` and produces no report (contract section 7).
    """
    validate_cohort_manifest(manifest)
    records = validate_cohort_ledger(ledger, manifest)
    body = build_report_body(manifest, records, ledger["ledger_hash"])
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": COHORT_SCHEMA_VERSION,
        "status": "success",
        "cohort_manifest_hash": manifest["manifest_hash"],
        "ledger_hash": ledger["ledger_hash"],
        "candidate_count": COHORT_SIZE,
        **body,
        "failure_code": None,
    }
    report["report_hash"] = report_hash(report)
    validate_gen0_cohort_report(report, manifest, ledger)
    return report


def validate_gen0_cohort_report(
    report: Mapping[str, Any], manifest: Mapping[str, Any], ledger: Mapping[str, Any]
) -> None:
    """Recompute every count, rate, maximum, gate and identity (section 7)."""
    required = {
        "schema",
        "schema_version",
        "status",
        "cohort_manifest_hash",
        "ledger_hash",
        "candidate_count",
        "terminal_stage_counts",
        "counts",
        "rates_bp",
        "qd_occupied_cells",
        "mode_maxima",
        "gates",
        "initial_gen0_passed",
        "planner_eligible",
        "failure_code",
        "report_hash",
    }
    if (
        not isinstance(report, Mapping)
        or set(report) != required
        or report.get("schema") != REPORT_SCHEMA
        or report.get("schema_version") != COHORT_SCHEMA_VERSION
        or report.get("status") != "success"
        or report.get("candidate_count") != COHORT_SIZE
        or report.get("failure_code") is not None
        or not _is_sha(report.get("report_hash"))
    ):
        _fail("COHORT_REPORT_SCHEMA_INVALID")
    validate_cohort_manifest(manifest)
    if report.get("cohort_manifest_hash") != manifest["manifest_hash"]:
        _fail("COHORT_MANIFEST_HASH_MISMATCH")
    records = validate_cohort_ledger(ledger, manifest)
    if report.get("ledger_hash") != ledger["ledger_hash"]:
        _fail("COHORT_LEDGER_HASH_MISMATCH")

    expected = build_report_body(manifest, records, ledger["ledger_hash"])
    for field in ("terminal_stage_counts", "counts", "rates_bp"):
        if report.get(field) != expected[field]:
            _fail("COHORT_AGGREGATE_MISMATCH")
    if report.get("qd_occupied_cells") != expected["qd_occupied_cells"]:
        _fail("COHORT_AGGREGATE_MISMATCH")
    if report.get("mode_maxima") != expected["mode_maxima"]:
        _fail("COHORT_MODE_KEY_INVALID")
    if (
        report.get("gates") != expected["gates"]
        or report.get("initial_gen0_passed") != expected["initial_gen0_passed"]
        or report.get("planner_eligible") != expected["planner_eligible"]
    ):
        _fail("COHORT_GATE_RESULT_MISMATCH")
    if report["report_hash"] != report_hash(report):
        _fail("COHORT_REPORT_HASH_MISMATCH")


def build_report_body(
    manifest: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    ledger_hash_value: str,
) -> dict[str, Any]:
    """Aggregate the expected report body from already-validated records."""
    terminal_counts = {stage: 0 for stage in TERMINAL_STAGES}
    for record in records:
        terminal_counts[record["terminal_stage"]] += 1
    compile_count = sum(1 for record in records if record["compile_success"])
    viable_count = sum(1 for record in records if record["automatic_viable"])
    exact_count = sum(
        1 for record in records if record["duplicate_classification"] == "exact_duplicate"
    )
    near_count = sum(
        1 for record in records if record["duplicate_classification"] == "near_duplicate"
    )
    distinct_count = sum(
        1 for record in records if record["duplicate_classification"] == "distinct"
    )
    recall_count = sum(1 for record in records if record["has_transformed_recall"])
    qd_cells = sorted(
        {
            tuple(record["qd_cell"])
            for record in records
            if record["automatic_viable"]
            and record["duplicate_classification"] == "distinct"
            and record["qd_cell"] is not None
        }
    )
    mode_maxima = [_mode_maximum(records, family) for family in MODE_FAMILIES]
    gate_maximum = max(mode_maxima, key=lambda row: row["candidate_count"])
    thresholds = manifest["thresholds_bp"]
    rates = {
        "compile_success": rate_bp(compile_count),
        "automatic_viable": rate_bp(viable_count),
        "exact_duplicate": rate_bp(exact_count),
        "near_duplicate": rate_bp(near_count),
        "transformed_recall": rate_bp(recall_count),
    }
    gates = {
        "compile_success": _gate(rates["compile_success"], "ge", thresholds["compile_success_ge"]),
        "initial_viability": _gate(
            rates["automatic_viable"], "ge", thresholds["initial_viability_ge"]
        ),
        "planner_viability": _gate(
            rates["automatic_viable"], "ge", thresholds["planner_viability_ge"]
        ),
        "exact_duplicate": _gate(rates["exact_duplicate"], "lt", thresholds["exact_duplicate_lt"]),
        "transformed_recall": _gate(
            rates["transformed_recall"], "ge", thresholds["transformed_recall_ge"]
        ),
        "mode_prevalence": _gate(
            gate_maximum["prevalence_bp"], "le", thresholds["mode_prevalence_le"]
        ),
    }
    near_gate = _gate(rates["near_duplicate"], "lt", thresholds["near_duplicate_lt"])
    if manifest["near_duplicate_policy"]["status"] == "audit_only":
        near_gate["status"] = "not_enforced"
    gates["near_duplicate"] = near_gate
    initial_passed = all(
        gates[name]["status"] == "passed"
        for name in (
            "compile_success",
            "initial_viability",
            "exact_duplicate",
            "transformed_recall",
            "mode_prevalence",
        )
    )
    planner_eligible = (
        initial_passed
        and gates["planner_viability"]["status"] == "passed"
        and gates["near_duplicate"]["status"] == "passed"
    )
    return {
        "terminal_stage_counts": terminal_counts,
        "counts": {
            "compile_success": compile_count,
            "automatic_viable": viable_count,
            "exact_duplicate": exact_count,
            "near_duplicate": near_count,
            "distinct": distinct_count,
            "transformed_recall": recall_count,
        },
        "rates_bp": rates,
        "qd_occupied_cells": [list(cell) for cell in qd_cells],
        "mode_maxima": mode_maxima,
        "gates": gates,
        "initial_gen0_passed": initial_passed,
        "planner_eligible": planner_eligible,
    }


__all__ = (
    "COHORT_CONTRACT",
    "COHORT_SCHEMA_VERSION",
    "COHORT_SIZE",
    "CohortGateError",
    "DUPLICATE_CLASSES",
    "LEDGER_SCHEMA",
    "MANIFEST_SCHEMA",
    "MODE_FAMILIES",
    "RECORD_SCHEMA",
    "REPORT_SCHEMA",
    "TERMINAL_STAGES",
    "THRESHOLDS_BP",
    "build_gen0_cohort_report",
    "cas_index_hash",
    "ledger_hash",
    "manifest_hash",
    "mode_key",
    "rate_bp",
    "record_hash",
    "report_hash",
    "validate_cohort_ledger",
    "validate_cohort_manifest",
    "validate_gen0_cohort_report",
)
