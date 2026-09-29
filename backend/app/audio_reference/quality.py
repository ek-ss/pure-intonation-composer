"""Audio-quality observations: silence, clipping, channel/phase, noise floor.

These measurements gate the downstream stages: spans that are silent or
noise-dominated are marked unsuitable for pitch identification so the harmony
stage does not invent chords out of silence.  All levels are integer Q14
(0..16384) or permyrads; no floats survive into the analysis document.
"""

from __future__ import annotations

import math
from typing import Any

from .decode import DecodedAudio
from .observations import make_observation, next_id

Q14_SCALE = 2**14


def _q14(value: float) -> int:
    return max(0, min(Q14_SCALE, int(round(value * Q14_SCALE))))


def _block_rms(samples: list[float], start: int, size: int) -> float:
    end = min(start + size, len(samples))
    if start >= end:
        return 0.0
    acc = 0.0
    for i in range(start, end):
        v = samples[i]
        acc += v * v
    return math.sqrt(acc / (end - start))


def _cross_correlation_lag(a: list[float], b: list[float], max_lag: int) -> tuple[int, float]:
    """Lag (in samples, -max_lag..max_lag) of peak normalized cross-correlation."""

    n = min(len(a), len(b))
    if n < 2:
        return 0, 0.0
    best_lag = 0
    best_score = -1.0
    norm_a = math.sqrt(sum(v * v for v in a[:n])) or 1.0
    norm_b = math.sqrt(sum(v * v for v in b[:n])) or 1.0
    for lag in range(-max_lag, max_lag + 1):
        acc = 0.0
        if lag >= 0:
            for i in range(n - lag):
                acc += a[i + lag] * b[i]
        else:
            for i in range(n + lag):
                acc += a[i] * b[i - lag]
        score = acc / (norm_a * norm_b)
        if score > best_score:
            best_score = score
            best_lag = lag
    return best_lag, best_score


def analyze_quality(decoded: DecodedAudio, block_samples: int = 2048) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    """Return ``(observations, pitch_unsuitable_spans)``.

    ``pitch_unsuitable_spans`` are ``(start_sample, end_sample)`` intervals
    the harmony stage should treat as no-chord evidence rather than tonal.
    """

    counter: dict[str, int] = {}
    observations: list[dict[str, Any]] = []
    mono = decoded.mono_floats()
    total = len(mono)
    if total == 0:
        return observations, []

    silence_threshold = 10 ** (-50 / 20)  # -50 dBFS
    pitch_threshold = 10 ** (-40 / 20)  # -40 dBFS

    rms_blocks: list[float] = []
    block_starts: list[int] = []
    for start in range(0, total, block_samples):
        rms_blocks.append(_block_rms(mono, start, block_samples))
        block_starts.append(start)

    # Silence spans: merge consecutive sub-threshold blocks.
    silent_flags = [rms < silence_threshold for rms in rms_blocks]
    pitch_unsuitable: list[tuple[int, int]] = []
    run_start: int | None = None
    for index, is_silent in enumerate(silent_flags):
        start = block_starts[index]
        end = min(start + block_samples, total)
        if is_silent and run_start is None:
            run_start = start
        if (not is_silent or index == len(silent_flags) - 1) and run_start is not None:
            span_end = end if is_silent else block_starts[index]
            observations.append(
                make_observation(
                    next_id(counter, "silence"),
                    "silence",
                    run_start,
                    span_end,
                    value={"rms_q14": _q14(max(rms_blocks[index - 1:index + 1] + [0.0]))},
                    conf=None,
                    method="block-rms-threshold/v1",
                )
            )
            run_start = None
    # Pitch-unsuitable spans: silent blocks (a superset gate for harmony).
    run_start = None
    for index, is_silent in enumerate(silent_flags):
        start = block_starts[index]
        end = min(start + block_samples, total)
        if rms_blocks[index] < pitch_threshold and run_start is None:
            run_start = start
        if rms_blocks[index] >= pitch_threshold and run_start is not None:
            pitch_unsuitable.append((run_start, start))
            run_start = None
    if run_start is not None:
        pitch_unsuitable.append((run_start, total))

    # Clipping: full-scale samples.
    clip_threshold = 0.98
    clip_count = 0
    clip_blocks: list[tuple[int, int, int]] = []
    for start in range(0, total, block_samples):
        end = min(start + block_samples, total)
        count = sum(1 for i in range(start, end) if abs(mono[i]) >= clip_threshold)
        if count:
            clip_blocks.append((start, end, count))
        clip_count += count
    if clip_count:
        observations.append(
            make_observation(
                next_id(counter, "clipping"),
                "clipping",
                0,
                total,
                value={
                    "sample_count": clip_count,
                    "block_count": len(clip_blocks),
                    "first_block": clip_blocks[0][0],
                    "last_block": clip_blocks[-1][1],
                },
                conf=None,
                method="full-scale-count/v1",
            )
        )

    # Noise floor: 5th percentile of block RMS.
    ordered = sorted(rms_blocks)
    floor_index = max(0, len(ordered) // 20)
    noise_floor = ordered[floor_index]
    observations.append(
        make_observation(
            next_id(counter, "noise_floor"),
            "noise_floor",
            0,
            total,
            value={"rms_q14": _q14(noise_floor)},
            conf=None,
            method="block-rms-percentile/v1",
        )
    )

    if decoded.channels == 2:
        left = decoded.channel_floats(0)
        right = decoded.channel_floats(1)
        # Channel difference: per-block energy asymmetry in [-1, 1] -> permyrad.
        diffs: list[int] = []
        for start in range(0, total, block_samples):
            end = min(start + block_samples, total)
            el = sum(v * v for v in left[start:end])
            er = sum(v * v for v in right[start:end])
            denom = el + er
            diffs.append(int(round((el - er) / denom * 10_000)) if denom > 0 else 0)
        observations.append(
            make_observation(
                next_id(counter, "channel_difference"),
                "channel_difference",
                0,
                total,
                value={
                    "mean_permille": int(sum(diffs) / len(diffs)),
                    "max_abs_permille": max(abs(v) for v in diffs),
                },
                conf=None,
                method="block-energy-asymmetry/v1",
            )
        )
        # Phase difference: median cross-correlation lag over voiced blocks.
        lags: list[int] = []
        for start in range(0, total, block_samples):
            if _block_rms(mono, start, block_samples) < pitch_threshold:
                continue
            end = min(start + block_samples, total)
            lag, _score = _cross_correlation_lag(left[start:end], right[start:end], max_lag=64)
            lags.append(lag)
        if lags:
            lags.sort()
            observations.append(
                make_observation(
                    next_id(counter, "phase_difference"),
                    "phase_difference",
                    0,
                    total,
                    value={
                        "median_lag_samples": lags[len(lags) // 2],
                        "voiced_block_count": len(lags),
                    },
                    conf=None,
                    method="block-cross-correlation/v1",
                )
            )

    return observations, pitch_unsuitable
