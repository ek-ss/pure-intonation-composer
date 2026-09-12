from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
DOC = ROOT.parent / "docs" / "song_program_perceptual_interpretation_layer_contract.md"

HASHES = {
    "perceptual_voice_matching_policy.schema.json": "288ae738994562e8ca67465c28cf102ce163ebfe35884c901860ee6f32e15690",
    "perceptual_voice_matching_record.schema.json": "ae74975c01dedf1bf1cceea9d90e4a3a25fbb9c8e904aeae9e4313a49a28de29",
    "perceptual_transition_feature_record.schema.json": "ff3e0c7e125f57347be40d31f77671572d7bde4450f52e65a0292f70e3cecff5",
    "perceptual_trajectory_template_set.schema.json": "119fe9a73b47a11859c3d840d2541181d302c27c0a55fa5ff35215dfe42b1b45",
    "perceptual_trajectory_result.schema.json": "86ad76be91b2c2e2c33fac2630c7b3daa4fcaca4016740b0d930d3f0ab5d7dd1",
}


def test_phase4_schema_bytes_are_closed_and_frozen() -> None:
    for name, expected in HASHES.items():
        raw = (SCHEMAS / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        assert json.loads(raw)["additionalProperties"] is False


def test_matching_policy_closes_orientation_cost_and_kernels() -> None:
    policy = json.loads((SCHEMAS / "perceptual_voice_matching_policy.schema.json").read_text())
    properties = policy["properties"]
    assert properties["algorithm"]["const"] == "pil-injective-voice-matching-dp/v1"
    assert properties["identity_constraint"]["const"] == "same-event-id-must-match/v1"
    assert properties["half_period_tie"]["const"] == "negative"
    assert set(properties["cost_weights"]["required"]) == {
        "absolute_motion",
        "circular_motion",
        "pitch_mapping_l1",
        "role_mismatch",
    }


def test_trajectory_authority_forbids_hard_label_alignment() -> None:
    template = json.loads((SCHEMAS / "perceptual_trajectory_template_set.schema.json").read_text())
    assert template["properties"]["alignment"]["properties"]["algorithm"]["const"] == (
        "all-consecutive-windows/v1"
    )
    text = " ".join(DOC.read_text().split())
    for phrase in (
        "no skips, padding, time warping or hard-label string matching",
        "null bass removes its weight rather than contributing zero",
        "Native GEN0-B matching is neither an input nor fallback",
    ):
        assert phrase in text


def test_report_has_auditable_phase4_evidence() -> None:
    report = json.loads((SCHEMAS / "perceptual_interpretation_report.schema.json").read_text())
    assert "functional_trajectory" in report["properties"]["completed_phase"]["enum"]
    assert {"voice_matching_records", "transition_feature_records"} <= set(report["required"])
    assert report["properties"]["trajectory_interpretations"]["items"]["$ref"] == (
        "perceptual_trajectory_result.schema.json"
    )
