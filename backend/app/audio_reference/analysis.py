"""Assemble the ``analysis.json`` document.

The analysis is a separate schema (spec section 2): it records the input PCM
identity, decode conditions, time reference, and every observation with its
span, method/model version, confidence definition, and candidates.  Audio-
specific numbers live here rather than being forced into an existing profile
schema's ``additionalProperties: false``.
"""

from __future__ import annotations

from typing import Any

from .decode import DecodedAudio, decode_conditions
from .input_policy import InputPolicy, policy_hash
from .observations import MODEL_ID, MODEL_VERSION

ANALYSIS_SCHEMA = "cps.audio-reference-analysis"
ANALYSIS_SCHEMA_VERSION = "0.1.0"


def build_analysis(
    decoded: DecodedAudio,
    policy: InputPolicy,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": ANALYSIS_SCHEMA,
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "input": {
            "path": decoded.source_path,
            "source_hash": decoded.source_hash,
            "decode": decode_conditions(decoded),
            "time_reference": {
                "origin": "first-sample",
                "sample_rate_hz": decoded.sample_rate,
                "frame_count": decoded.frame_count,
            },
        },
        "input_policy_hash": policy_hash(policy),
        "observations": observations,
    }
