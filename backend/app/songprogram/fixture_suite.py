"""Read-only SearchLoop13 authoritative fixture-suite validation."""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .search import SearchArtifactError
from .search_decisions import decision_artifact_hash


REQUIRED_COVERAGE = [
    "success",
    "failure",
    "cache_cold",
    "cache_hit",
    "cache_corrupt",
    "cancel",
    "parallel_1",
    "parallel_2",
    "parallel_4",
    "parallel_8",
]


def _search_fail() -> None:
    raise SearchArtifactError("FIXTURE_SUITE_INVALID")


def _raw_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _resolved_child(root: Path, relative: str, fail: Callable[[], None]) -> Path:
    if not isinstance(relative, str) or unicodedata.normalize("NFC", relative) != relative:
        fail()
    path = Path(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        fail()
    root_real = root.resolve(strict=True)
    candidate = (root_real / path).resolve(strict=True)
    try:
        if os.path.commonpath((str(root_real), str(candidate))) != str(root_real):
            fail()
    except ValueError:
        fail()
    return candidate


def _validate_suite(
    suite: Mapping[str, Any],
    suite_directory: str | Path,
    schema_bytes_by_hash: Mapping[str, bytes],
    validate_case: Callable[[Mapping[str, Any], Mapping[str, Any]], None],
    *,
    schema_name: str,
    required_coverage: Sequence[str],
    fail: Callable[[], None],
    bind_case_coverage: bool = False,
) -> list[dict[str, Any]]:
    """Authenticate a closed suite using caller-selected versioned authority."""
    required = {
        "schema",
        "schema_version",
        "suite_version",
        "required_coverage",
        "cases",
        "suite_hash",
    }
    if not isinstance(suite, Mapping) or set(suite) != required:
        fail()
    if suite.get("schema") != schema_name or suite.get("schema_version") != "1.0.0":
        fail()
    if suite.get("required_coverage") != list(required_coverage):
        fail()
    if suite.get("suite_hash") != decision_artifact_hash(suite, "suite_hash"):
        fail()
    rows = suite.get("cases")
    if not isinstance(rows, list) or not rows:
        fail()
    row_keys = {
        "case_id",
        "path",
        "raw_file_sha256",
        "case_hash",
        "case_schema_hash",
        "coverage",
    }
    if any(not isinstance(row, Mapping) or set(row) != row_keys for row in rows):
        fail()
    ids = [row.get("case_id") for row in rows]
    if (
        any(not isinstance(value, str) for value in ids)
        or ids != sorted(ids, key=lambda value: value.encode("utf-8"))
        or len(ids) != len(set(ids))
    ):
        fail()

    resolved: list[dict[str, Any]] = []
    for field in ("path", "raw_file_sha256", "case_hash"):
        values = [row.get(field) for row in rows]
        if any(not isinstance(value, str) for value in values) or len(values) != len(set(values)):
            fail()
    coverage: set[str] = set()
    allowed_coverage = set(required_coverage)
    for row in rows:
        try:
            raw = _resolved_child(Path(suite_directory), row["path"], fail).read_bytes()
        except (OSError, TypeError):
            fail()
        if _raw_hash(raw) != row["raw_file_sha256"]:
            fail()
        schema_raw = schema_bytes_by_hash.get(row["case_schema_hash"])
        if schema_raw is None or _raw_hash(schema_raw) != row["case_schema_hash"]:
            fail()
        try:
            case, schema = json.loads(raw), json.loads(schema_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            fail()
        if not isinstance(case, dict) or not isinstance(schema, dict):
            fail()
        validate_case(case, schema)
        if case.get("case_id") != row["case_id"] or case.get("case_hash") != row["case_hash"]:
            fail()
        if decision_artifact_hash(case, "case_hash") != row["case_hash"]:
            fail()
        labels = row["coverage"]
        if (
            not isinstance(labels, list)
            or not labels
            or any(not isinstance(label, str) for label in labels)
            or len(labels) != len(set(labels))
            or not set(labels) <= allowed_coverage
            or (bind_case_coverage and case.get("coverage") != labels)
        ):
            fail()
        coverage.update(labels)
        resolved.append(case)
    if coverage != allowed_coverage:
        fail()
    return resolved


def validate_fixture_suite(
    suite: Mapping[str, Any],
    suite_directory: str | Path,
    schema_bytes_by_hash: Mapping[str, bytes],
    validate_case: Callable[[Mapping[str, Any], Mapping[str, Any]], None],
) -> list[dict[str, Any]]:
    """Resolve and authenticate every indexed case without modifying goldens.

    ``validate_case`` is the caller's versioned JSON-Schema plus semantic
    validator. Keeping it explicit prevents this byte-closure layer from
    silently selecting an ambient schema implementation.
    """
    return _validate_suite(
        suite,
        suite_directory,
        schema_bytes_by_hash,
        validate_case,
        schema_name="cps.search-loop-13-fixture-suite-index",
        required_coverage=REQUIRED_COVERAGE,
        fail=_search_fail,
    )
