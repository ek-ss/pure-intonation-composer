"""Read-only SearchLoop13 authoritative fixture-suite validation."""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any, Callable, Mapping

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


def _fail() -> None:
    raise SearchArtifactError("FIXTURE_SUITE_INVALID")


def _raw_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _resolved_child(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or unicodedata.normalize("NFC", relative) != relative:
        _fail()
    path = Path(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail()
    root_real = root.resolve(strict=True)
    candidate = (root_real / path).resolve(strict=True)
    try:
        if os.path.commonpath((str(root_real), str(candidate))) != str(root_real):
            _fail()
    except ValueError:
        _fail()
    return candidate


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
    required = {
        "schema",
        "schema_version",
        "suite_version",
        "required_coverage",
        "cases",
        "suite_hash",
    }
    if not isinstance(suite, Mapping) or set(suite) != required:
        _fail()
    if (
        suite.get("schema") != "cps.search-loop-13-fixture-suite-index"
        or suite.get("schema_version") != "1.0.0"
    ):
        _fail()
    if suite.get("required_coverage") != REQUIRED_COVERAGE:
        _fail()
    if suite.get("suite_hash") != decision_artifact_hash(suite, "suite_hash"):
        _fail()
    rows = suite.get("cases")
    if not isinstance(rows, list) or not rows:
        _fail()
    ids = [row.get("case_id") for row in rows if isinstance(row, Mapping)]
    if (
        len(ids) != len(rows)
        or ids != sorted(ids, key=lambda value: value.encode("utf-8"))
        or len(ids) != len(set(ids))
    ):
        _fail()

    resolved: list[dict[str, Any]] = []
    unique_fields = ("path", "raw_file_sha256", "case_hash")
    for field in unique_fields:
        values = [row.get(field) for row in rows]
        if len(values) != len(set(values)):
            _fail()
    coverage: set[str] = set()
    for row in rows:
        if set(row) != {
            "case_id",
            "path",
            "raw_file_sha256",
            "case_hash",
            "case_schema_hash",
            "coverage",
        }:
            _fail()
        raw = _resolved_child(Path(suite_directory), row["path"]).read_bytes()
        if _raw_hash(raw) != row["raw_file_sha256"]:
            _fail()
        schema_raw = schema_bytes_by_hash.get(row["case_schema_hash"])
        if schema_raw is None or _raw_hash(schema_raw) != row["case_schema_hash"]:
            _fail()
        try:
            case, schema = json.loads(raw), json.loads(schema_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail()
        if not isinstance(case, dict) or not isinstance(schema, dict):
            _fail()
        validate_case(case, schema)
        if case.get("case_id") != row["case_id"] or case.get("case_hash") != row["case_hash"]:
            _fail()
        if decision_artifact_hash(case, "case_hash") != row["case_hash"]:
            _fail()
        labels = row["coverage"]
        if not isinstance(labels, list) or not labels or len(labels) != len(set(labels)):
            _fail()
        coverage.update(labels)
        resolved.append(case)
    if coverage != set(REQUIRED_COVERAGE):
        _fail()
    return resolved
