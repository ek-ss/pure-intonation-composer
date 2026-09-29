"""Harmonic observations: chroma, chord candidates, local key.

Implements spec section 3.3.  Chroma is built by harmonic summation of the
shared STFT magnitudes (12-EDO comparison labels only; it is not a JI/equave
authority).  Chords are matched per beat against triad/seventh templates plus
an explicit no-chord class, smoothed across beats, and spans the quality stage
marked unsuitable are forced to no-chord.  Local key uses Krumhansl-Kessler
circular correlation.  Unknown tensions are reported, not dropped.
"""

from __future__ import annotations

import math
from typing import Any

from .observations import confidence, make_observation, next_id

NYQUIST_LIMIT = 16  # harmonics summed per fundamental
OCTAVES = 4  # fundamental octaves considered (downward)

MAJOR_PROFILE = [6.35, 2.23, 2.82, 1.54, 2.51, 2.90, 2.62, 1.30, 3.46, 2.27, 2.01, 1.94]
MINOR_PROFILE = [6.53, 1.21, 3.48, 2.50, 1.67, 2.69, 3.01, 1.84, 2.44, 1.96, 2.53, 1.58]

CHORD_QUALITIES = {
    "major": [0, 4, 7],
    "minor": [0, 3, 7],
    "dominant7": [0, 4, 7, 10],
    "major7": [0, 4, 7, 11],
    "minor7": [0, 3, 7, 10],
    "halfdim7": [0, 3, 6, 10],
    "dim": [0, 3, 6],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}


def _fundamental_frequency(pitch_class: int) -> float:
    # A4 = 440 Hz reference; pitch class 9 (A) at MIDI 69.
    return 440.0 * 2 ** ((pitch_class - 9) / 12.0)


def compute_chroma(
    spectra: list[list[float]], starts: list[int], sample_rate: int, frame_size: int
) -> list[list[float]]:
    """12-dim chroma per STFT frame via harmonic summation."""

    bin_width = sample_rate / frame_size
    nyquist = sample_rate / 2.0
    chroma_frames: list[list[float]] = []
    for mag in spectra:
        chroma = [0.0] * 12
        for p in range(12):
            base = _fundamental_frequency(p)
            for octave in range(OCTAVES):
                fundamental = base / (2.0 ** octave)
                for h in range(1, NYQUIST_LIMIT + 1):
                    freq = fundamental * h
                    if freq > nyquist:
                        break
                    bin_index = int(round(freq / bin_width))
                    if 0 <= bin_index < len(mag):
                        chroma[p] += mag[bin_index] / h
        chroma_frames.append(chroma)
    return chroma_frames


def _normalize(v: list[float]) -> list[float]:
    total = sum(v)
    if total <= 0:
        return [0.0] * len(v)
    return [x / total for x in v]


def _template_vector(root: int, quality: str) -> list[float]:
    vec = [0.0] * 12
    for offset in CHORD_QUALITIES[quality]:
        vec[(root + offset) % 12] = 1.0
    return vec


def _match_score(chroma: list[float], template: list[float]) -> float:
    """Inner product minus a penalty for energy outside the template."""

    hit = sum(c * t for c, t in zip(chroma, template))
    miss = sum(c for c, t in zip(chroma, template) if t == 0.0)
    return hit - 0.5 * miss


def estimate_chords(
    chroma_frames: list[list[float]],
    starts: list[int],
    beat_samples: list[int],
    sample_rate: int,
    pitch_unsuitable: list[tuple[int, int]],
    counter: dict[str, int],
) -> list[dict[str, Any]]:
    """Per-beat chord candidates with no-chord/unknown and beat smoothing."""

    observations: list[dict[str, Any]] = []
    if not beat_samples or not chroma_frames:
        observations.append(
            make_observation(
                next_id(counter, "chord"),
                "chord",
                0,
                sample_rate,
                value=None,
                conf=None,
                method="chroma-template-match/v1",
                unresolved_reason="no_beat_lattice",
            )
        )
        return observations

    def is_unsuitable(sample: int) -> bool:
        return any(start <= sample < end for start, end in pitch_unsuitable)

    # Average chroma over the frames inside each beat span.
    beat_chromas: list[list[float]] = []
    for index, start in enumerate(beat_samples):
        end = beat_samples[index + 1] if index + 1 < len(beat_samples) else (starts[-1] + sample_rate if starts else 0)
        frame_indices = [i for i, s in enumerate(starts) if start <= s < end]
        if frame_indices:
            acc = [0.0] * 12
            for i in frame_indices:
                for p in range(12):
                    acc[p] += chroma_frames[i][p]
            beat_chromas.append(_normalize(acc))
        else:
            beat_chromas.append([0.0] * 12)
    # Beat-synchronous smoothing (3-beat centered moving average).
    smoothed: list[list[float]] = []
    for i in range(len(beat_chromas)):
        lo = max(0, i - 1)
        hi = min(len(beat_chromas), i + 2)
        acc = [0.0] * 12
        for j in range(lo, hi):
            for p in range(12):
                acc[p] += beat_chromas[j][p]
        smoothed.append(_normalize(acc))

    templates = [(root, quality) for root in range(12) for quality in CHORD_QUALITIES]
    template_vectors = {
        (root, quality): _template_vector(root, quality) for root, quality in templates
    }
    no_chord_threshold = 0.12  # normalized chroma energy below this -> no-chord
    for index, chroma in enumerate(smoothed):
        energy = sum(chroma)
        start = beat_samples[index]
        if is_unsuitable(start) or energy < no_chord_threshold:
            observations.append(
                make_observation(
                    next_id(counter, "chord"),
                    "chord",
                    start,
                    beat_samples[index + 1] if index + 1 < len(beat_samples) else start + sample_rate,
                    value={"root": None, "quality": "no-chord", "bass": None},
                    conf=confidence(5000, "chroma-energy-gate/v1"),
                    method="chroma-template-match/v1",
                )
            )
            continue
        scored = []
        for (root, quality), vec in template_vectors.items():
            scored.append((_match_score(chroma, vec), root, quality))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        best_score, best_root, best_quality = scored[0]
        bass = max(range(12), key=lambda p: (chroma[p], -p))
        top = [
            {"root": r, "quality": q, "score_q14": int(round(max(0.0, s) * 16384))}
            for s, r, q in scored[:4]
        ]
        observations.append(
            make_observation(
                next_id(counter, "chord"),
                "chord",
                start,
                beat_samples[index + 1] if index + 1 < len(beat_samples) else start + sample_rate,
                value={"root": best_root, "quality": best_quality, "bass": bass},
                candidates=top,
                conf=confidence(int(round(min(1.0, best_score) * 10_000)), "template-match-margin/v1"),
                method="chroma-template-match/v1",
            )
        )
    return observations


def estimate_key(
    chroma_frames: list[list[float]],
    starts: list[int],
    sample_rate: int,
    counter: dict[str, int],
) -> list[dict[str, Any]]:
    """Local key via Krumhansl-Kessler circular correlation (12-EDO labels)."""

    if not chroma_frames:
        return [
            make_observation(
                next_id(counter, "key"),
                "key",
                0,
                sample_rate,
                value=None,
                conf=None,
                method="krumhansl-kessler/v1",
                unresolved_reason="no_chroma",
            )
        ]
    total_frames = len(chroma_frames)
    window = max(1, total_frames // 8)  # ~8 local windows across the file
    observations: list[dict[str, Any]] = []
    for w in range(0, total_frames, window):
        acc = [0.0] * 12
        for i in range(w, min(w + window, total_frames)):
            for p in range(12):
                acc[p] += chroma_frames[i][p]
        chroma = _normalize(acc)
        if sum(chroma) <= 0:
            continue
        mean = sum(chroma) / 12
        std = math.sqrt(sum((c - mean) ** 2 for c in chroma) / 12) or 1.0
        best = None
        for rotation in range(12):
            for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
                rotated = [profile[(p - rotation) % 12] for p in range(12)]
                rmean = sum(rotated) / 12
                rstd = math.sqrt(sum((r - rmean) ** 2 for r in rotated) / 12) or 1.0
                corr = sum((c - mean) * (r - rmean) for c, r in zip(chroma, rotated)) / (12 * std * rstd)
                if best is None or corr > best[0]:
                    best = (corr, rotation, mode)
        if best is None:
            continue
        corr, rotation, mode = best
        start_sample = starts[w] if w < len(starts) else 0
        end_sample = starts[min(w + window, total_frames) - 1] if total_frames else start_sample
        observations.append(
            make_observation(
                next_id(counter, "key"),
                "key",
                start_sample,
                end_sample,
                value={"rotation": rotation, "mode": mode},
                candidates=[{"rotation": rotation, "mode": mode, "correlation_q14": int(round(max(0.0, corr) * 16384))}],
                conf=confidence(int(round(max(0.0, corr) * 10_000)), "key-profile-correlation/v1"),
                method="krumhansl-kessler/v1",
            )
        )
    return observations
