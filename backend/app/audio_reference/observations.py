"""Observation record construction for the audio reference analysis.

An observation is one measured claim about a time span of the input PCM:
``{id, type, start_sample, end_sample, value, candidates, confidence,
provenance, unresolved_reason}``.  Units are never mixed: sample indices for
spans, milli-BPM for tempo, Q14/Q31 integers for levels.  ``confidence`` is
not a calibrated probability; its definition, model version and calibration
set are recorded alongside the value.  Unestimable observations keep their
record with ``value: null`` and a reason instead of being dropped.
"""

from __future__ import annotations

from typing import Any

MODEL_ID = "cps.audio-reference-baseline"
MODEL_VERSION = "1.0.0"

OBSERVATION_TYPES = (
    "silence",
    "clipping",
    "channel_difference",
    "phase_difference",
    "noise_floor",
    "onset",
    "tempo",
    "beat",
    "downbeat",
    "meter",
    "section",
    "repetition",
    "chord",
    "key",
    "energy",
    "onset_density",
    "register",
    "stereo_balance",
)


class ObservationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def confidence(
    value_q: int, definition: str, calibration_set: str | None = None
) -> dict[str, Any]:
    if not 0 <= value_q <= 10_000:
        raise ObservationError("CONFIDENCE_OUT_OF_RANGE", str(value_q))
    return {
        "value_q": value_q,
        "definition": definition,
        "model_version": MODEL_VERSION,
        "calibration_set": calibration_set,
    }


def provenance(method: str) -> dict[str, Any]:
    return {"method": method, "model_version": MODEL_VERSION}


def make_observation(
    observation_id: str,
    obs_type: str,
    start_sample: int,
    end_sample: int,
    value: Any = None,
    candidates: list[Any] | None = None,
    conf: dict[str, Any] | None = None,
    method: str = "unspecified/v1",
    unresolved_reason: str | None = None,
) -> dict[str, Any]:
    if obs_type not in OBSERVATION_TYPES:
        raise ObservationError("OBSERVATION_TYPE_UNKNOWN", obs_type)
    if not 0 <= start_sample <= end_sample:
        raise ObservationError("OBSERVATION_SPAN_INVALID", f"{start_sample}..{end_sample}")
    if value is None and unresolved_reason is None:
        raise ObservationError("OBSERVATION_UNRESOLVED_WITHOUT_REASON", observation_id)
    return {
        "id": observation_id,
        "type": obs_type,
        "start_sample": start_sample,
        "end_sample": end_sample,
        "value": value,
        "candidates": candidates if candidates is not None else [],
        "confidence": conf,
        "provenance": provenance(method),
        "unresolved_reason": unresolved_reason,
    }


def next_id(counter: dict[str, int], obs_type: str) -> str:
    counter[obs_type] = counter.get(obs_type, 0) + 1
    return f"obs_{obs_type}_{counter[obs_type]:03d}"
