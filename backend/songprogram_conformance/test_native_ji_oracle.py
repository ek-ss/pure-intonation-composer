from __future__ import annotations

import hashlib
import json
from pathlib import Path

from songprogram_conformance.native_ji_oracle import (
    SCHEMAS,
    artifact_hash,
    canonical,
    evaluate,
    project_hash,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_nonfunctional_native_ji_fixture_is_independently_recomputed() -> None:
    case = _load(FIXTURES / "pil_oracle/pil_nonfunctional_two_reports.json")
    manifest = _load(FIXTURES / "native_ji/pil_nonfunctional_manifest.json")
    expected = _load(FIXTURES / "native_ji/pil_nonfunctional_report.json")

    manifest_schema = _load(SCHEMAS / "native_ji_evaluation_manifest.schema.json")
    report_schema = _load(SCHEMAS / "native_ji_evaluation_report.schema.json")
    assert manifest_schema["additionalProperties"] is False
    assert report_schema["additionalProperties"] is False
    assert set(manifest) == set(manifest_schema["required"])
    assert set(expected) == set(report_schema["required"])
    assert artifact_hash(manifest, "manifest_hash") == manifest["manifest_hash"]
    assert project_hash(case["project"]) == case["project_hash"] == expected["project_hash"]
    assert evaluate(case["project"], manifest) == expected
    assert case["native_ji_report_hash"] == expected["report_hash"]
    assert expected["metrics"][0]["value_q"] >= 5800
    assert "sha256:" + hashlib.sha256(canonical(expected)).hexdigest() == (
        "sha256:68816be5e0d782f517ad235fa50dba6385bc3b6f8a632eb7bb2847478772ece1"
    )
