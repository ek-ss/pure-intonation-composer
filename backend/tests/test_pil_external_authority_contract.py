from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "songprogram_conformance"


def _load_schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _artifact_hash(value: dict[str, object], self_member: str) -> str:
    body = {key: item for key, item in value.items() if key != self_member}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    prefix = (f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0").encode()
    return "sha256:" + hashlib.sha256(prefix + canonical).hexdigest()


def test_phase_1_4_external_authority_schemas_are_distinct_from_fixture_only() -> None:
    policy = _load_schema("pil_calibration_acceptance_policy.schema.json")
    fixture_set = _load_schema("pil_calibration_fixture_set.schema.json")
    evidence = _load_schema("pil_calibration_metric_evidence_summary.schema.json")
    old_fixture = _load_schema("calibration_fixture_set.schema.json")

    assert policy["properties"]["scope"] == {"const": "phase_1_4"}
    assert fixture_set["properties"]["scope"] == {"const": "phase_1_4_external"}
    assert evidence["properties"]["scope"] == {"const": "phase_1_4_external"}
    assert old_fixture["properties"]["scope"] == {"const": "search_loop_13_fixture_only"}
    assert (
        fixture_set["properties"]["schema"]["const"] != old_fixture["properties"]["schema"]["const"]
    )
    assert "evidence_summary_hash" not in fixture_set["required"]
    assert "fixture_set_hash" in evidence["required"]


def test_genre_registry_is_closed_sorted_and_self_hashed() -> None:
    registry = json.loads(
        (ROOT / "fixtures" / "pil_calibration" / "genre_metric_registry.json").read_text(
            encoding="utf-8"
        )
    )
    assert registry["registry_hash"] == _artifact_hash(registry, "registry_hash")
    ids = [row["metric_id"] for row in registry["metrics"]]
    assert ids == sorted(ids)
    assert ids == [
        "pil.genre.cliche_dependence_q",
        "pil.genre.idiomaticity_q",
        "pil.genre.novelty_q",
        "pil.genre.typicality_q",
    ]
    assert all(row["missing_policy"] == "unavailable" for row in registry["metrics"])
    assert registry["metrics"][0]["direction"] == "minimize"
    assert all(row["direction"] == "maximize" for row in registry["metrics"][1:])


def test_genre_decision_is_versioned_and_binds_complete_context() -> None:
    decision = _load_schema("pil_genre_calibration_decision.schema.json")
    properties = decision["properties"]
    assert properties["schema_version"] == {"const": "2.0.0"}
    assert properties["scope"] == {"const": "genre_phase_5"}
    assert properties["phase5_build_id"] == {"const": "pil.phase5.1.0.0"}
    assert {
        "genre_intent_hash",
        "genre_model_hash",
        "genre_reference_set_manifest_hash",
        "genre_metric_registry_hash",
        "oracle_suite_index_hash",
        "calibration_fixture_set_hash",
        "acceptance_policy_hash",
        "evidence_summary_hash",
    } <= set(decision["required"])
    assert properties["metric_ids"]["items"]["pattern"].startswith("^pil\\.genre\\.")


def test_fixture_only_search_loop_decision_remains_unchanged_authority_kind() -> None:
    fixture = json.loads(
        (
            ROOT
            / "fixtures"
            / "search_loop_13"
            / "calibration_authority"
            / "artifacts"
            / "calibration_decision.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture["schema"] == "cps.calibration-decision"
    assert fixture["schema_version"] == "1.1.0"
    assert "scope" not in fixture
    assert not any(metric_id.startswith("pil.") for metric_id in fixture["metric_ids"])
