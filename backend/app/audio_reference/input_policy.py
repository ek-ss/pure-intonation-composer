"""Versioned input policy for reference-audio analysis.

The policy bounds what the baseline will accept: file size, decoded length,
sample rate, channel count, and wall-clock budget.  Anything outside the
bounds stops the run with a stable, machine-readable reason instead of
failing mid-analysis.  The policy is part of the receipt so two runs with
different policies are never conflated.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class InputPolicyError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


POLICY_ID = "cps.audio-reference-input-policy"
POLICY_VERSION = "1.0.0"


@dataclass(frozen=True)
class InputPolicy:
    max_file_size_bytes: int = 256 * 1024 * 1024
    max_duration_seconds: int = 3600
    min_duration_seconds: int = 1
    sample_rate_range_hz: tuple[int, int] = (8000, 192_000)
    channel_count: tuple[int, int] = (1, 2)
    max_analysis_wall_time_seconds: int = 3600

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "max_file_size_bytes": self.max_file_size_bytes,
            "max_duration_seconds": self.max_duration_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "sample_rate_range_hz": list(self.sample_rate_range_hz),
            "channel_count": list(self.channel_count),
            "max_analysis_wall_time_seconds": self.max_analysis_wall_time_seconds,
        }


def default_policy() -> InputPolicy:
    return InputPolicy()


def policy_hash(policy: InputPolicy) -> str:
    payload = policy.as_dict()
    body = {key: value for key, value in payload.items() if key not in ("policy_id", "policy_version")}
    prefix = f"{POLICY_ID}/{POLICY_VERSION}\0".encode()
    import json

    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(prefix + canonical).hexdigest()


def check_file(path: Path, policy: InputPolicy) -> None:
    if not path.is_file():
        raise InputPolicyError("INPUT_FILE_MISSING", str(path))
    size = path.stat().st_size
    if size == 0:
        raise InputPolicyError("INPUT_FILE_EMPTY", str(path))
    if size > policy.max_file_size_bytes:
        raise InputPolicyError(
            "INPUT_FILE_TOO_LARGE", f"{size} bytes > {policy.max_file_size_bytes}"
        )


def check_decoded(
    sample_rate: int, frame_count: int, channels: int, policy: InputPolicy
) -> None:
    if not (policy.sample_rate_range_hz[0] <= sample_rate <= policy.sample_rate_range_hz[1]):
        raise InputPolicyError(
            "INPUT_SAMPLE_RATE_OUT_OF_RANGE",
            f"{sample_rate} Hz outside {policy.sample_rate_range_hz}",
        )
    if not (policy.channel_count[0] <= channels <= policy.channel_count[1]):
        raise InputPolicyError(
            "INPUT_CHANNEL_COUNT_OUT_OF_RANGE",
            f"{channels} channels outside {policy.channel_count}",
        )
    duration = frame_count / sample_rate
    if duration < policy.min_duration_seconds:
        raise InputPolicyError(
            "INPUT_TOO_SHORT", f"{duration:.3f}s < {policy.min_duration_seconds}s"
        )
    if duration > policy.max_duration_seconds:
        raise InputPolicyError(
            "INPUT_TOO_LONG", f"{duration:.3f}s > {policy.max_duration_seconds}s"
        )
