"""Independent ReferenceRenderReport per-track PCM32 payload oracle."""

from __future__ import annotations

import hashlib
import struct


I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1
I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1


def encode_track_pcm(accumulators: list[tuple[int, int]]) -> tuple[bytes, int, int]:
    payload = bytearray()
    saturation_count = 0
    peak = 0
    for left, right in accumulators:
        for value in (left, right):
            if not I64_MIN <= value <= I64_MAX:
                raise OverflowError("track accumulator outside signed 64-bit")
            saturated = min(I32_MAX, max(I32_MIN, value))
            saturation_count += int(saturated != value)
            peak = max(peak, abs(saturated))
            payload.extend(struct.pack("<i", saturated))
    return bytes(payload), saturation_count, peak


def pcm_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
