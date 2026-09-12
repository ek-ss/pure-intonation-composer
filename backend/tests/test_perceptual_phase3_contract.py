from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
DOC = ROOT.parent / "docs" / "song_program_perceptual_interpretation_layer_contract.md"

EXPECTED_RAW_HASHES = {
    "perceptual_chord_feature_spec.schema.json":
        "ab6ffd1bfe5d5dbe12a81a80a9175eb32c36e510306b22f4122b2ed3727695e1",
    "perceptual_chord_feature_record.schema.json":
        "0e039841d18d1496161ba2283fdbd1dca743fd719288ca465823f03be0add1a6",
    "perceptual_chord_vocabulary.schema.json":
        "cd6741bcd4e94a03e7ce9bcbb6422d761108e9900191c6500c2775cdfefec11b",
}


def test_phase3_schema_bytes_are_frozen_and_closed() -> None:
    for name, expected in EXPECTED_RAW_HASHES.items():
        raw = (SCHEMAS / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        assert json.loads(raw)["additionalProperties"] is False


def test_feature_spec_closes_algorithms_weights_and_thresholds() -> None:
    schema = json.loads((SCHEMAS / "perceptual_chord_feature_spec.schema.json").read_text())
    properties = schema["properties"]
    assert properties["interval_distribution_algorithm"]["const"] == (
        "circular-ordered-autocorrelation-q31/v1"
    )
    similarity = properties["similarity"]["properties"]
    assert similarity["algorithm"]["const"] == "weighted-normalized-l1-q10000/v1"
    assert {"confidence_floor_q", "winner_margin_floor_q", "maximum_candidates"} <= set(
        similarity
    )


def test_report_embeds_features_and_phase3_is_parallel() -> None:
    report = json.loads((SCHEMAS / "perceptual_interpretation_report.schema.json").read_text())
    assert "feature_records" in report["required"]
    assert "chord_similarity" in report["properties"]["completed_phase"]["enum"]
    text = " ".join(DOC.read_text().split())
    assert "never copies or recomputes those values" in text
    assert "cannot alter or suppress Native JI evidence" in text
