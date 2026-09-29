"""Acoustic observations: energy, onset density, register, stereo balance.

Implements spec section 3.4.  All levels are in-song relative integers
(Q14 for energy/density, permyrad for balance) so they map directly onto the
profile's ``energy_q``/``density_q`` without assuming an absolute loudness
authority.  Melody note-events and precise instrument ID are left to adapter
workers; the baseline reports register from chroma centroid only.
"""

from __future__ import annotations

import math
from typing import Any

from .decode import DecodedAudio
from .observations import confidence, make_observation, next_id


def _q14(value: float) -> int:
    return max(0, min(16384, int(round(value * 16384))))


def energy_curve(
    mono: list[float], beat_samples: list[int], counter: dict[str, int]
) -> tuple[list[dict[str, Any]], list[int]]:
    """Per-beat RMS energy normalized to the song maximum.

    Returns ``(observations, per_beat_energy_q14)``.
    """

    if not beat_samples:
        return [], []
    energies: list[float] = []
    for index, start in enumerate(beat_samples):
        end = beat_samples[index + 1] if index + 1 < len(beat_samples) else min(start + 4096, len(mono))
        block = mono[start:end]
        if not block:
            energies.append(0)
            continue
        rms = math.sqrt(sum(v * v for v in block) / len(block))
        energies.append(rms)
    peak = max(energies) if energies else 0.0
    scale = 16384.0 / peak if peak > 0 else 0.0
    q14 = [_q14(e * scale) for e in energies]
    observations = [
        make_observation(
            next_id(counter, "energy"),
            "energy",
            beat_samples[0],
            beat_samples[-1],
            value={"peak_q14": max(q14) if q14 else 0},
            candidates=[{"sample": s, "energy_q14": e} for s, e in zip(beat_samples[:256], q14[:256])],
            conf=confidence(8000, "rms-relative/v1"),
            method="block-rms-relative/v1",
        )
    ]
    return observations, q14


def onset_density(
    onset_samples: list[int], beat_samples: list[int], counter: dict[str, int]
) -> tuple[list[dict[str, Any]], list[int]]:
    """Per-beat onset count normalized to the song maximum.

    Returns ``(observations, per_beat_density_q14)``.
    """

    if not beat_samples:
        return [], []
    counts: list[int] = []
    for index, start in enumerate(beat_samples):
        end = beat_samples[index + 1] if index + 1 < len(beat_samples) else (onset_samples[-1] + 1 if onset_samples else 0)
        counts.append(sum(1 for s in onset_samples if start <= s < end))
    peak = max(counts) if counts else 0
    scale = 16384.0 / peak if peak > 0 else 0.0
    q14 = [int(round(c * scale)) for c in counts]
    observations = [
        make_observation(
            next_id(counter, "onset_density"),
            "onset_density",
            beat_samples[0],
            beat_samples[-1],
            value={"peak_q14": max(q14) if q14 else 0},
            candidates=[{"sample": s, "density_q14": d} for s, d in zip(beat_samples[:256], q14[:256])],
            conf=confidence(8000, "onset-count-relative/v1"),
            method="onset-count-per-beat/v1",
        )
    ]
    return observations, q14


def register_estimate(
    chroma_frames: list[list[float]], starts: list[int], sample_rate: int, counter: dict[str, int]
) -> list[dict[str, Any]]:
    """Register from chroma centroid (semitones above C, in-song relative)."""

    if not chroma_frames:
        return [
            make_observation(
                next_id(counter, "register"),
                "register",
                0,
                sample_rate,
                value=None,
                conf=None,
                method="chroma-centroid/v1",
                unresolved_reason="no_chroma",
            )
        ]
    centroids: list[int] = []
    for chroma in chroma_frames:
        total = sum(chroma)
        if total <= 0:
            continue
        centroid = sum(p * c for p, c in enumerate(chroma)) / total
        centroids.append(int(round(centroid * 100)))  # centisemitones
    if not centroids:
        return [
            make_observation(
                next_id(counter, "register"),
                "register",
                0,
                sample_rate,
                value=None,
                conf=None,
                method="chroma-centroid/v1",
                unresolved_reason="no_tonal_content",
            )
        ]
    centroids.sort()
    median = centroids[len(centroids) // 2]
    return [
        make_observation(
            next_id(counter, "register"),
            "register",
            starts[0] if starts else 0,
            starts[-1] if starts else sample_rate,
            value={"median_centisemitone": median},
            candidates=[{"p10_centisemitone": centroids[len(centroids) // 10], "p90_centisemitone": centroids[(len(centroids) * 9) // 10]}],
            conf=confidence(6000, "chroma-centroid/v1"),
            method="chroma-centroid/v1",
        )
    ]


def stereo_balance(
    decoded: DecodedAudio, beat_samples: list[int], counter: dict[str, int]
) -> list[dict[str, Any]]:
    """Per-beat left/right energy asymmetry in permyrad (in-song relative)."""

    if decoded.channels != 2 or not beat_samples:
        return []
    left = decoded.channel_floats(0)
    right = decoded.channel_floats(1)
    balances: list[int] = []
    for index, start in enumerate(beat_samples):
        end = beat_samples[index + 1] if index + 1 < len(beat_samples) else min(start + 4096, len(left))
        el = sum(v * v for v in left[start:end])
        er = sum(v * v for v in right[start:end])
        denom = el + er
        balances.append(int(round((el - er) / denom * 10_000)) if denom > 0 else 0)
    return [
        make_observation(
            next_id(counter, "stereo_balance"),
            "stereo_balance",
            beat_samples[0],
            beat_samples[-1],
            value={
                "mean_permille": int(sum(balances) / len(balances)),
                "max_abs_permille": max(abs(v) for v in balances),
            },
            candidates=[{"sample": s, "balance_permille": b} for s, b in zip(beat_samples[:256], balances[:256])],
            conf=confidence(7000, "energy-asymmetry/v1"),
            method="block-energy-asymmetry/v1",
        )
    ]
