from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.songprogram import perceptual


ROOT = Path(__file__).resolve().parent
PACK_PATH = ROOT / "fixtures" / "pil_negative" / "pack.json"
SUITE_DIR = ROOT / "fixtures" / "pil_oracle"
SCHEMA_PATH = ROOT / "schemas" / "pil_negative_case_pack.schema.json"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _artifact_hash(value: dict[str, object], self_member: str) -> str:
    body = {key: item for key, item in value.items() if key != self_member}
    prefix = (
        "cps-artifact-hash/v1\0" + str(value["schema"]) + "\0" + str(value["schema_version"]) + "\0"
    ).encode()
    return "sha256:" + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def _replace(document: dict[str, object], pointer: str, replacement: object) -> None:
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]]
    target: object = document
    for token in tokens[:-1]:
        assert isinstance(target, dict)
        target = target[token]
    assert isinstance(target, dict)
    target[tokens[-1]] = replacement


def test_pil_negative_pack_is_closed_and_authoritative() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(pack) == set(schema["required"])
    assert pack["pack_hash"] == _artifact_hash(pack, "pack_hash")
    suite = json.loads((SUITE_DIR / "suite_index.json").read_text(encoding="utf-8"))
    matrix = json.loads((SUITE_DIR / "matrix_receipt.json").read_text(encoding="utf-8"))
    assert pack["oracle_suite_hash"] == suite["suite_hash"] == matrix["suite_hash"]
    assert pack["oracle_matrix_receipt_hash"] == matrix["matrix_hash"]
    assert [case["case_id"] for case in pack["cases"]] == sorted(
        case["case_id"] for case in pack["cases"]
    )
    assert {case["expected_error"] for case in pack["cases"]} == {
        "PIL_BINDING_MISMATCH",
        "PIL_SCHEMA_INVALID",
    }


@pytest.mark.parametrize("case_ordinal", [0, 1])
def test_pil_negative_case_executes_reference_entry_point(case_ordinal: int) -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    case = pack["cases"][case_ordinal]
    path = SUITE_DIR / f"{case['base_case_id']}.json"
    raw = path.read_bytes()
    assert "sha256:" + hashlib.sha256(raw).hexdigest() == case["base_case_raw_sha256"]
    base = json.loads(raw)
    mutated = copy.deepcopy(base)
    _replace(mutated, case["json_pointer"], case["replacement"])

    with pytest.raises(perceptual.PilError) as caught:
        perceptual.run_perceptual_interpretation(
            mutated["project"],
            mutated["manifest"],
            expected_project_hash=perceptual.project_hash(mutated["project"]),
            native_ji_report_hash=mutated["native_ji_report_hash"],
            segmentation_policy=mutated["segmentation_policy"],
            feature_spec=mutated["feature_spec"],
            chord_vocabulary=mutated["vocabulary"],
            voice_matching_policy=mutated["voice_matching_policy"],
            trajectory_template_set=mutated["trajectory_template_set"],
        )
    assert caught.value.code == case["expected_error"]


def test_phase_1_4_calibration_schemas_close_c1_through_c6() -> None:
    decision = json.loads(
        (ROOT / "schemas" / "pil_calibration_decision.schema.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (ROOT / "schemas" / "pil_metric_registry.schema.json").read_text(encoding="utf-8")
    )
    assert decision["additionalProperties"] is False
    assert registry["additionalProperties"] is False
    assert decision["properties"]["scope"] == {"const": "phase_1_4"}
    required = set(decision["required"])
    assert {
        "pil_manifest_hash",
        "metric_registry_hash",
        "oracle_suite_index_hash",
        "oracle_matrix_receipt_hash",
        "calibration_fixture_set_hash",
    } <= required
    promotion_required = set(decision["$defs"]["promotion"]["required"])
    assert {
        "aggregation",
        "direction",
        "acceptance_threshold_q",
        "missing_policy",
    } <= promotion_required
    assert decision["$defs"]["promotion"]["properties"]["missing_policy"] == {
        "const": "unavailable"
    }
    assert decision["$defs"]["promotion"]["properties"]["metric_id"]["pattern"].startswith(
        "^pil\\."
    )

    registry_artifact = json.loads(
        (ROOT / "fixtures" / "pil_calibration" / "metric_registry.json").read_text(encoding="utf-8")
    )
    assert registry_artifact["registry_hash"] == _artifact_hash(registry_artifact, "registry_hash")
    metric_ids = [row["metric_id"] for row in registry_artifact["metrics"]]
    assert metric_ids == sorted(metric_ids)
    assert len(metric_ids) == len(set(metric_ids))
    assert all(metric_id.startswith("pil.") for metric_id in metric_ids)

    readiness = json.loads(
        (ROOT / "fixtures" / "pil_calibration" / "promotion_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    assert readiness["readiness_hash"] == _artifact_hash(readiness, "readiness_hash")
    assert readiness["status"] == "blocked"
    assert readiness["metric_registry_hash"] == registry_artifact["registry_hash"]
    assert (
        readiness["oracle_suite_index_hash"]
        == "sha256:06c7c7c7e44fd467ab2eea2ee57a1a79a23084bf8d0836a13851efe6f51ffd90"
    )
    assert (
        readiness["oracle_matrix_receipt_hash"]
        == "sha256:734b54e584f4f75e1e0285a5ac491b17a5c44d107fd556d85c8e788cfafe62ea"
    )
    assert all(
        row["status"] == "missing_external_authority" and row["artifact_hash"] is None
        for row in readiness["external_authorities"]
    )
