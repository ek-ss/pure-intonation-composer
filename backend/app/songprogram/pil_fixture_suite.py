"""Read-only Perceptual Interpretation Layer oracle-suite validation."""

from __future__ import annotations

import hashlib
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from .fixture_suite import _validate_suite
from . import perceptual
from .perceptual import PilError
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


__all__ = (
    "PIL_REQUIRED_COVERAGE",
    "execute_pil_oracle_case",
    "validate_pil_fixture_suite",
    "validate_pil_oracle_case_bindings",
)
