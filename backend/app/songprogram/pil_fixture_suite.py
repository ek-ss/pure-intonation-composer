"""Read-only Perceptual Interpretation Layer oracle-suite validation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping

from .fixture_suite import _validate_suite
from . import perceptual
from .perceptual import PilError
from .search_decisions import decision_artifact_hash
from .validator import ProjectValidationError, validate_project


PIL_REQUIRED_COVERAGE = [
    "success",
    "failure",
    "kernel_edge",
    "kernel_tie",
    "kernel_empty_support",
    "chord_similarity",
    "ambiguous_winner",
    "missing_bass",
    "voice_matching",
    "matching_tie",
    "unequal_voice_count",
    "identity_constraint",
    "trajectory_similarity",
    "trajectory_missing_bass",
    "equave_2_1",
    "equave_3_1",
    "phase_independence",
    "cache_cold",
    "cache_hit",
    "cache_corrupt",
    "cross_process",
    "parallel_1",
    "parallel_2",
    "parallel_4",
    "parallel_8",
]


def _fail() -> None:
    raise PilError("PIL_FIXTURE_SUITE_INVALID")


def validate_pil_fixture_suite(
    suite: Mapping[str, Any],
    suite_directory: str | Path,
    schema_bytes_by_hash: Mapping[str, bytes],
    validate_case: Callable[[Mapping[str, Any], Mapping[str, Any]], None],
) -> list[dict[str, Any]]:
    """Authenticate PIL cases without executing them or changing expected bytes."""
    return _validate_suite(
        suite,
        suite_directory,
        schema_bytes_by_hash,
        validate_case,
        schema_name="cps.pil-oracle-suite-index",
        required_coverage=PIL_REQUIRED_COVERAGE,
        fail=_fail,
        bind_case_coverage=True,
    )


def validate_pil_oracle_case_bindings(case: Mapping[str, Any]) -> None:
    """Validate phase-exact assets and every locally recomputable case binding."""
    try:
        manifest = case["manifest"]
        project = case["project"]
        perceptual.validate_manifest(manifest)
        validate_project(project)
        if perceptual.project_hash(project) != case.get("project_hash"):
            _fail()

        policy = case.get("segmentation_policy")
        spec = case.get("feature_spec")
        vocabulary = case.get("vocabulary")
        voice_policy = case.get("voice_matching_policy")
        templates = case.get("trajectory_template_set")
        presence = tuple(
            value is not None for value in (policy, spec, vocabulary, voice_policy, templates)
        )
        if presence not in {
            (False, False, False, False, False),
            (True, False, False, False, False),
            (True, True, True, False, False),
            (True, True, True, True, True),
        }:
            _fail()
        expected_bindings = {}
        if policy is not None:
            expected_bindings["segmentation_policy_hash"] = perceptual.segmentation_policy_hash(
                policy
            )
        if spec is not None:
            expected_bindings["feature_spec_hash"] = perceptual.chord_feature_spec_hash(spec)
            expected_bindings["vocabulary_hash"] = perceptual.chord_vocabulary_hash(vocabulary)
        if voice_policy is not None:
            expected_bindings["voice_matching_policy_hash"] = perceptual.voice_matching_policy_hash(
                voice_policy
            )
            expected_bindings["trajectory_template_set_hash"] = (
                perceptual.trajectory_template_set_hash(templates)
            )
        if any(manifest.get(key) != value for key, value in expected_bindings.items()):
            _fail()
        if policy is not None:
            perceptual.validate_segmentation_policy(policy, manifest)
        if spec is not None:
            perceptual.validate_chord_feature_spec(spec, manifest, policy)
            perceptual.validate_chord_vocabulary(vocabulary, manifest, spec)
        if voice_policy is not None:
            perceptual.validate_voice_matching_policy(voice_policy, manifest, spec)
            perceptual.validate_trajectory_template_set(
                templates, manifest, spec, vocabulary, voice_policy
            )
    except (KeyError, TypeError, ProjectValidationError, PilError) as error:
        if isinstance(error, PilError) and error.code == "PIL_FIXTURE_SUITE_INVALID":
            raise
        _fail()


def _run_case(case: Mapping[str, Any], cache_dir: str | Path | None = None) -> dict[str, Any]:
    keyword_assets = {
        key: case[key]
        for key in (
            "segmentation_policy",
            "feature_spec",
            "voice_matching_policy",
            "trajectory_template_set",
        )
        if case[key] is not None
    }
    if case["vocabulary"] is not None:
        keyword_assets["chord_vocabulary"] = case["vocabulary"]
    return perceptual.run_perceptual_interpretation(
        case["project"],
        case["manifest"],
        expected_project_hash=case["project_hash"],
        native_ji_report_hash=case["native_ji_report_hash"],
        cache_dir=cache_dir,
        **keyword_assets,
    )


def execute_pil_oracle_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Execute and compare one authenticated case without updating its authority."""
    validate_pil_oracle_case_bindings(case)
    project_before = deepcopy(case["project"])
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        _fail()
    try:
        report = _run_case(case)
        canonical = perceptual.canonical_report_bytes(report)
        observed = {
            "status": report["status"],
            "error": report["error"],
            "report_hash": report["report_hash"],
            "canonical_report_sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        }
    except (KeyError, TypeError, PilError):
        _fail()
    if dict(expected) != observed or case["project"] != project_before:
        _fail()

    coverage = set(case.get("coverage", ()))
    cache_labels = {"cache_cold", "cache_hit", "cache_corrupt"}
    if coverage & cache_labels:
        if not cache_labels <= coverage:
            _fail()
        with tempfile.TemporaryDirectory(prefix="cps-pil-oracle-cache-") as directory:
            cold = _run_case(case, directory)
            hit = _run_case(case, directory)
            entries = list(Path(directory).iterdir())
            if len(entries) != 1:
                _fail()
            entries[0].write_bytes(b"corrupt")
            corrupt = _run_case(case, directory)
        if not (
            perceptual.canonical_report_bytes(cold)
            == perceptual.canonical_report_bytes(hit)
            == perceptual.canonical_report_bytes(corrupt)
            == canonical
        ):
            _fail()
    return report


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _case_results_hash(results: list[dict[str, str]]) -> str:
    digest = hashlib.sha256(b"cps.pil-case-results/v1\0" + _canonical(results)).hexdigest()
    return "sha256:" + digest


def _subprocess_case(case: Mapping[str, Any], seed: str) -> dict[str, str]:
    backend = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = seed
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(backend) + (os.pathsep + python_path if python_path else "")
    completed = subprocess.run(
        [sys.executable, "-m", "app.songprogram.pil_fixture_worker"],
        input=_canonical(case),
        capture_output=True,
        cwd=backend,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        _fail()
    try:
        report = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail()
    if not isinstance(report, dict):
        _fail()
    canonical = perceptual.canonical_report_bytes(report)
    if (
        canonical != completed.stdout
        or not _is_sha(report.get("report_hash"))
        or report.get("report_hash") != case["expected"]["report_hash"]
    ):
        _fail()
    return {
        "case_id": case["case_id"],
        "report_hash": report["report_hash"],
        "canonical_report_sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }


def execute_pil_oracle_matrix(suite_hash: str, cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Run the fixed seed/concurrency matrix and return canonical parity evidence."""
    if not _is_sha(suite_hash) or not cases:
        _fail()
    if any(not isinstance(case.get("case_id"), str) for case in cases):
        _fail()
    ordered = sorted(cases, key=lambda case: case["case_id"].encode("utf-8"))
    if ordered != cases or len({case.get("case_id") for case in cases}) != len(cases):
        _fail()
    executions = [case.get("execution") for case in cases]
    if any(not isinstance(item, Mapping) for item in executions):
        _fail()
    worker_counts = executions[0].get("worker_counts")
    seeds = executions[0].get("pythonhashseeds")
    if (
        worker_counts != [1, 2, 4, 8]
        or not isinstance(seeds, list)
        or not seeds
        or any(
            not isinstance(seed, str)
            or not (
                seed == "random"
                or (
                    seed.isdecimal()
                    and len(seed) <= 10
                    and str(int(seed)) == seed
                    and int(seed) <= 4_294_967_295
                )
            )
            for seed in seeds
        )
        or len(seeds) != len(set(seeds))
        or any(item.get("worker_counts") != worker_counts for item in executions)
        or any(item.get("pythonhashseeds") != seeds for item in executions)
    ):
        _fail()

    baseline: list[dict[str, str]] | None = None
    rows = []
    for seed in seeds:
        for worker_count in worker_counts:
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                results = list(pool.map(lambda case: _subprocess_case(case, seed), cases))
            if baseline is None:
                baseline = results
            elif results != baseline:
                _fail()
            rows.append(
                {
                    "pythonhashseed": seed,
                    "worker_count": worker_count,
                    "case_results_hash": _case_results_hash(results),
                }
            )
    receipt = {
        "schema": "cps.pil-oracle-matrix-receipt",
        "schema_version": "1.0.0",
        "suite_hash": suite_hash,
        "case_results": baseline,
        "executions": rows,
        "matrix_hash": "",
    }
    receipt["matrix_hash"] = decision_artifact_hash(receipt, "matrix_hash")
    validate_pil_matrix_receipt(receipt, suite_hash, cases)
    return receipt


def validate_pil_matrix_receipt(
    receipt: Mapping[str, Any], suite_hash: str, cases: list[Mapping[str, Any]]
) -> None:
    """Recompute matrix coordinates, ordered results and every receipt hash."""
    required = {
        "schema",
        "schema_version",
        "suite_hash",
        "case_results",
        "executions",
        "matrix_hash",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        _fail()
    if (
        receipt.get("schema") != "cps.pil-oracle-matrix-receipt"
        or receipt.get("schema_version") != "1.0.0"
        or receipt.get("suite_hash") != suite_hash
        or receipt.get("matrix_hash") != decision_artifact_hash(receipt, "matrix_hash")
    ):
        _fail()
    if not cases or any(not isinstance(case.get("case_id"), str) for case in cases):
        _fail()
    if any(not isinstance(case.get("expected"), Mapping) for case in cases):
        _fail()
    expected_results = [
        {
            "case_id": case["case_id"],
            "report_hash": case.get("expected", {}).get("report_hash"),
            "canonical_report_sha256": case.get("expected", {}).get("canonical_report_sha256"),
        }
        for case in cases
    ]
    if receipt.get("case_results") != expected_results or any(
        not _is_sha(row["report_hash"]) or not _is_sha(row["canonical_report_sha256"])
        for row in expected_results
    ):
        _fail()
    execution = cases[0].get("execution")
    if not isinstance(execution, Mapping) or any(
        case.get("execution") != execution for case in cases
    ):
        _fail()
    expected_hash = _case_results_hash(expected_results)
    expected_rows = [
        {
            "pythonhashseed": seed,
            "worker_count": worker_count,
            "case_results_hash": expected_hash,
        }
        for seed in execution.get("pythonhashseeds", ())
        for worker_count in execution.get("worker_counts", ())
    ]
    if receipt.get("executions") != expected_rows:
        _fail()


__all__ = (
    "PIL_REQUIRED_COVERAGE",
    "execute_pil_oracle_case",
    "execute_pil_oracle_matrix",
    "validate_pil_matrix_receipt",
    "validate_pil_fixture_suite",
    "validate_pil_oracle_case_bindings",
)
