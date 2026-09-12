from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
DOC = ROOT.parent / "docs" / "song_program_perceptual_interpretation_layer_contract.md"


def test_pil_is_explicitly_parallel_and_non_replacing() -> None:
    text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "new, parallel interpretation",
        "Neither branch consumes the other branch's report",
        "never removes or aliases a Native JI criterion",
        "Native GEN0-B matching is neither an input nor fallback and remains the\n"
        "sole owner of native voice-leading metrics",
        "cannot trigger a Native JI fallback",
    ):
        assert phrase in text


def test_pil_artifacts_are_closed_and_separately_identified() -> None:
    manifest = json.loads((SCHEMAS / "perceptual_interpretation_manifest.schema.json").read_text())
    report = json.loads((SCHEMAS / "perceptual_interpretation_report.schema.json").read_text())
    assert manifest["additionalProperties"] is False
    assert report["additionalProperties"] is False
    assert manifest["properties"]["algorithm"]["const"] == "pil-parallel-interpretation/v1"
    assert manifest["properties"]["interpretation_period"]["const"] == "2/1"
    assert "native_ji_report_hash" in report["required"]
    assert "native_ji" not in report["properties"]
    assert len(report["allOf"]) == 2


def test_pil_initial_kernel_is_integer_soft_mapping_not_hard_quantization() -> None:
    manifest = json.loads((SCHEMAS / "perceptual_interpretation_manifest.schema.json").read_text())
    kernel = manifest["properties"]["pitch_kernel"]["properties"]
    assert kernel["algorithm"]["const"] == "triangular-millicent-q31/v1"
    assert kernel["normalization_total"]["const"] == 2**31 - 1
    text = DOC.read_text(encoding="utf-8")
    assert "Hard nearest-note quantization is forbidden" in text
    assert "Gaussian is reserved" in text


def test_segmentation_policy_closes_weights_merge_and_failure_order() -> None:
    raw = (SCHEMAS / "perceptual_segmentation_policy.schema.json").read_bytes()
    policy = json.loads(raw)
    assert "sha256:" + hashlib.sha256(raw).hexdigest() == (
        "sha256:77559f2ad4f563c761be20505eec8af4c4a04e63b51b9201df680e280bfa370d"
    )
    assert policy["additionalProperties"] is False
    assert set(policy["properties"]["role_gain_q"]["required"]) == {
        "drums", "bass", "harmony", "melody", "texture"
    }
    assert policy["properties"]["algorithm"]["const"] == "pil-harmonic-segmentation-grid-events/v1"
    assert policy["properties"]["boundary_priority"]["prefixItems"] == [
        {"const": "endpoint"}, {"const": "bass_change"},
        {"const": "sustained_change"},
        {"const": "pitch_distribution_change"}, {"const": "metrical"},
    ]
    text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "event_weight = RHE",
        "Accept both endpoints first",
        "PIL_SEGMENTATION_POLICY_INVALID",
        "First failure wins in this order",
    ):
        assert phrase in text
