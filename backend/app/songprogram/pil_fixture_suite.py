"""Read-only Perceptual Interpretation Layer oracle-suite validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .fixture_suite import _validate_suite
from .perceptual import PilError


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


__all__ = ("PIL_REQUIRED_COVERAGE", "validate_pil_fixture_suite")
