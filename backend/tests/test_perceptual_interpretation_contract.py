from __future__ import annotations

import json
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
        "matching remains unchanged and continues to own native voice-leading metrics",
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
