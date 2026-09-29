"""Time-axis observations: onsets, tempo, beats, meter/downbeat, sections.

Implements spec section 3.2.  Onsets come from half-wave-rectified spectral
flux over the shared STFT; tempo is an autocorrelation peak of the onset
envelope with double/half candidates; beats are a phase-aligned grid snapped
to onsets; meter and downbeat keep multiple hypotheses when ambiguous (bar_0
is not forced); sections come from a beat-synchronous self-similarity
change-point scan.  All times are integer source samples; tempo is milli-BPM.
"""

from __future__ import annotations

import math
from typing import Any

from . import dsp
from .decode import DecodedAudio
from .observations import confidence, make_observation, next_id

FRAME_SIZE = 2048
HOP = 1024
MIN_BPM = 30
MAX_BPM = 300


def spectral_flux(spectra: list[list[float]]) -> list[float]:
    """Half-wave-rectified spectral flux per frame (first frame is 0)."""

    if not spectra:
        return []
    flux = [0.0]
    previous = spectra[0]
    for frame in spectra[1:]:
        acc = 0.0
        for a, b in zip(previous, frame):
            diff = b - a
            if diff > 0.0:
                acc += diff
        flux.append(acc)
        previous = frame
    return flux


def detect_onsets(
    flux: list[float], starts: list[int], sample_rate: int
) -> tuple[list[int], list[int]]:
    """Peak-pick the onset envelope.

    Returns ``(onset_samples, onset_strength_q14)``.  The adaptive threshold
    is the smoothed envelope mean plus a small multiple of its spread, so a
    quiet passage does not produce onsets and a loud one does not saturate.
    """

    if not flux:
        return [], []
    smoothed = dsp.moving_average(flux, 8)
    mean = sum(smoothed) / len(smoothed)
    spread = math.sqrt(sum((v - mean) ** 2 for v in smoothed) / len(smoothed))
    threshold = max(mean + 0.5 * spread, 1e-9)
    min_distance_frames = max(1, int(0.1 * sample_rate / HOP))  # >= 100 ms
    peaks = dsp.pick_peaks(flux, min_prominence=threshold, min_distance=min_distance_frames)
    onset_samples = [starts[i] for i in peaks if i < len(starts)]
    peak_max = max(flux) if flux else 1.0
    scale = 16384.0 / peak_max if peak_max > 0 else 0.0
    strengths = [int(round(flux[i] * scale)) for i in peaks if i < len(starts)]
    return onset_samples, strengths


def _autocorr_peak_bpm(
    centered: list[float], sample_rate: int
) -> tuple[float, float, list[float]] | None:
    """Best-lag BPM of a high-passed onset envelope, or ``None``.

    Returns ``(fractional_lag, score, autocorrelation)``.  Octave resolution:
    a periodic signal also correlates at integer multiples of its period, and
    those can marginally exceed the fundamental; among the strong peaks (>=
    80% of the maximum) the shortest lag (highest tempo) is preferred.
    """

    min_lag = int(60 * sample_rate / (MAX_BPM * HOP))
    max_lag = int(60 * sample_rate / (MIN_BPM * HOP))
    min_lag = max(1, min(min_lag, len(centered) // 2))
    if max_lag < min_lag:
        return None
    max_lag = min(max_lag, len(centered) - 1)
    ac = dsp.autocorrelation(centered, max_lag)
    eligible = [ac[lag] for lag in range(min_lag, max_lag + 1)]
    if not eligible or max(eligible) <= 0:
        return None
    peak = max(eligible)
    threshold = 0.8 * peak
    for lag in range(min_lag, max_lag + 1):
        if ac[lag] < threshold:
            continue
        # Parabolic interpolation around the peak for sub-frame lag resolution;
        # one frame of quantization is ~10% of a 120 BPM period, which would
        # otherwise masquerade as an in-song tempo change.
        fractional = float(lag)
        if 0 < lag < len(ac) - 1:
            left, mid, right = ac[lag - 1], ac[lag], ac[lag + 1]
            denominator = left - 2.0 * mid + right
            if denominator != 0.0:
                delta = 0.5 * (left - right) / denominator
                fractional = lag + max(-0.5, min(0.5, delta))
        return fractional, ac[lag], ac
    return None


def _high_pass(flux: list[float], sample_rate: int) -> list[float]:
    # Subtract a ~1.5 s moving average so slow section-level energy trends do
    # not dominate the autocorrelation at long lags (the classic 120->30 BPM
    # octave error).
    window = max(8, min(64, int(1.5 * sample_rate / HOP)))
    trend = dsp.moving_average(flux, window)
    return [v - t for v, t in zip(flux, trend)]


def estimate_tempo(flux: list[float], sample_rate: int) -> dict[str, Any]:
    """Autocorrelation tempo estimate with double/half candidates.

    The onset envelope is high-passed and autocorrelated over lags that map
    to 30..300 BPM.  The strongest eligible lag is the base tempo; its octave
    relatives are reported as candidates so a 4/4 song at 120 is not silently
    read as 60 or 240.  Windowed local estimates are recorded alongside the
    base so downstream stages can distinguish a stable tempo from an in-song
    tempo change (which the fixed-clock schema cannot express).
    """

    if len(flux) < 8:
        return {
            "value": None,
            "candidates": [],
            "confidence": None,
            "unresolved_reason": "insufficient_onset_envelope",
        }
    centered = _high_pass(flux, sample_rate)
    result = _autocorr_peak_bpm(centered, sample_rate)
    if result is None:
        return {
            "value": None,
            "candidates": [],
            "confidence": None,
            "unresolved_reason": "no_tempo_periodicity",
        }
    best_lag, best_score, ac = result
    period_seconds = best_lag * HOP / sample_rate
    base_bpm = 60.0 / period_seconds
    candidates: list[dict[str, Any]] = []
    for factor in (0.5, 1.0, 2.0):
        bpm = base_bpm * factor
        if MIN_BPM <= bpm <= MAX_BPM:
            candidates.append(
                {"tempo_milli_bpm": int(round(bpm * 1000)), "relation": {0.5: "half", 1.0: "base", 2.0: "double"}[factor]}
            )
    # Confidence: how dominant the peak is versus its neighbors.
    center = int(best_lag)
    half = max(1, center // 8)
    neighborhood = [ac[lag] for lag in range(max(0, center - half), min(len(ac), center + half + 1))]
    peak = max(neighborhood) if neighborhood else best_score
    floor = min(v for v in neighborhood if v >= 0) if neighborhood else 0.0
    prominence = (peak - floor) / peak if peak > 0 else 0.0
    value = None
    for cand in candidates:
        if cand["relation"] == "base":
            value = {"tempo_milli_bpm": cand["tempo_milli_bpm"]}
    if value is not None:
        value["local_tempo_milli_bpm"] = local_tempos(centered, sample_rate)
    return {
        "value": value,
        "candidates": candidates,
        "confidence": confidence(int(round(prominence * 10_000)), "autocorrelation-peak-prominence/v1"),
        "unresolved_reason": None if value else "base_tempo_out_of_range",
    }


def local_tempos(centered: list[float], sample_rate: int) -> list[int]:
    """Windowed local tempo estimates (milli-BPM) across the envelope.

    Each ~8 s window is peak-picked independently, so an in-song tempo change
    shows up as a spread of local values even though the global estimate is a
    single number.  Eight seconds is long enough for a stable autocorrelation
    yet short enough to resolve section-level tempo changes; windows without
    periodicity are skipped rather than reported as zero.
    """

    window_frames = max(16, int(8 * sample_rate / HOP))
    if len(centered) < window_frames:
        return []
    local: list[int] = []
    for start in range(0, len(centered) - window_frames + 1, window_frames // 2):
        segment = centered[start : start + window_frames]
        result = _autocorr_peak_bpm(segment, sample_rate)
        if result is None:
            continue
        lag, _score, _ac = result
        bpm = 60.0 / (lag * HOP / sample_rate)
        if MIN_BPM <= bpm <= MAX_BPM:
            local.append(int(round(bpm * 1000)))
    return local


def track_beats(
    onset_samples: list[int],
    onset_strengths: list[int],
    tempo_milli_bpm: int,
    sample_rate: int,
    total_samples: int,
) -> tuple[list[int], list[int]]:
    """Phase-align a beat grid to the onsets and snap.

    Returns ``(beat_samples, beat_strength_q14)``.  The grid phase is the
    onset offset that maximizes aligned onset strength; a grid beat with no
    onset inside the snap window keeps its grid time but a reduced strength,
    so a steady passage still yields a complete beat lattice.
    """

    if tempo_milli_bpm <= 0:
        return [], []
    beat_period = 60_000 / tempo_milli_bpm * sample_rate  # samples per beat
    if beat_period < 1:
        return [], []
    snap_window = max(1, int(0.3 * beat_period))  # +/- 30% of a beat
    if onset_samples:
        best_phase = 0
        best_score = -1.0
        for origin in onset_samples[:64]:
            score = 0.0
            for onset, strength in zip(onset_samples, onset_strengths):
                delta = (onset - origin) % beat_period
                distance = min(delta, beat_period - delta)
                if distance <= snap_window:
                    score += strength * (1.0 - distance / snap_window)
            if score > best_score:
                best_score = score
                best_phase = origin
    else:
        best_phase = 0
    total = max(total_samples, max(onset_samples) if onset_samples else 0)
    beats: list[int] = []
    strengths: list[int] = []
    # Extend the phase-aligned grid backward so it covers from sample 0, not
    # just from the chosen origin forward.
    grid: float = float(best_phase)
    while grid - beat_period >= 0:
        grid -= beat_period
    while grid <= total:
        aligned = 0
        for onset, strength in zip(onset_samples, onset_strengths):
            distance = abs(onset - grid)
            if distance <= snap_window:
                aligned = max(aligned, int(round(strength * (1.0 - distance / snap_window) * 0.5)))
        beats.append(int(grid))
        strengths.append(aligned if aligned > 0 else 1024)
        grid += beat_period
    return beats, strengths


def estimate_meter(
    beat_samples: list[int],
    beat_strengths: list[int],
    sample_rate: int,
) -> dict[str, Any]:
    """Meter and downbeat hypotheses from beat-strength periodicity.

    Autocorrelates the beat strength over 2..8-beat lags and keeps every
    eligible ``beats_per_bar`` (SongProgram allows 2/3/4/6) whose score is
    within tolerance of the best.  When the top two are close, both are
    returned and no single bar_0 is asserted.
    """

    if len(beat_samples) < 8:
        return {
            "value": None,
            "candidates": [],
            "confidence": None,
            "unresolved_reason": "insufficient_beats",
        }
    mean = sum(beat_strengths) / len(beat_strengths)
    centered = [v - mean for v in beat_strengths]
    ac = dsp.autocorrelation(centered, min(8, len(beat_strengths) - 1))
    scores: dict[int, float] = {}
    for beats_per_bar in (2, 3, 4, 6):
        if beats_per_bar < len(ac):
            scores[beats_per_bar] = ac[beats_per_bar]
    if not scores:
        return {
            "value": None,
            "candidates": [],
            "confidence": None,
            "unresolved_reason": "insufficient_beats",
        }
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_score = ranked[0][1]
    eligible = [bpb for bpb, score in ranked if score > 0 and (best_score <= 0 or score >= 0.6 * best_score)]
    if not eligible:
        return {
            "value": None,
            "candidates": [],
            "confidence": None,
            "unresolved_reason": "no_meter_periodicity",
        }
    candidates = []
    for bpb in eligible:
        # Downbeat phase: the beat offset maximizing summed strength per bar.
        best_offset = 0
        best_phase_score = -1.0
        for offset in range(bpb):
            phase_score = sum(beat_strengths[i] for i in range(offset, len(beat_samples), bpb))
            if phase_score > best_phase_score:
                best_phase_score = phase_score
                best_offset = offset
        candidates.append(
            {
                "beats_per_bar": bpb,
                "downbeat_beat_offset": best_offset,
                "bar_0_sample": beat_samples[best_offset] if best_offset < len(beat_samples) else beat_samples[0],
            }
        )
    ambiguous = len(eligible) > 1 and ranked[1][1] >= 0.8 * ranked[0][1]
    value = None if ambiguous else {
        "beats_per_bar": candidates[0]["beats_per_bar"],
        "downbeat_beat_offset": candidates[0]["downbeat_beat_offset"],
        "bar_0_sample": candidates[0]["bar_0_sample"],
    }
    dominance = ranked[0][1] / (ranked[1][1] or 1.0) if len(ranked) > 1 and ranked[1][1] > 0 else 2.0
    conf_value = int(round(min(1.0, (dominance - 1.0) / 2.0 + 0.5) * 10_000)) if not ambiguous else int(round(0.5 * 10_000))
    return {
        "value": value,
        "candidates": candidates,
        "confidence": confidence(max(0, min(10_000, conf_value)), "meter-peak-dominance/v1"),
        "unresolved_reason": None if value else "meter_ambiguous",
    }


def _beat_features(
    mono: list[float],
    beat_samples: list[int],
    sample_rate: int,
) -> list[list[float]]:
    """Per-beat feature vector: [energy, onset-ish transient, brightness]."""

    features: list[list[float]] = []
    for index, start in enumerate(beat_samples):
        end = beat_samples[index + 1] if index + 1 < len(beat_samples) else min(start + int(60_000 / 120 * sample_rate), len(mono))
        end = max(end, start + 1)
        block = mono[start:end]
        if not block:
            features.append([0.0, 0.0, 0.0])
            continue
        energy = math.sqrt(sum(v * v for v in block) / len(block))
        transients = sum(1 for a, b in zip(block, block[1:]) if abs(b - a) > 0.05) / max(1, len(block) - 1)
        brightness = dsp.zero_crossing_rate(block)
        features.append([energy, transients, brightness])
    return features


def detect_sections(
    mono: list[float],
    beat_samples: list[int],
    sample_rate: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Change-point section scan over beat-synchronous features.

    Returns ``(sections, repetitions)``.  A boundary is accepted where the
    cosine dissimilarity between consecutive beat features exceeds an
    adaptive threshold; adjacent boundaries closer than two beats are merged.
    Repetitions are section pairs whose mean feature vectors are highly
    similar (the self-similarity relation the spec asks to surface).
    """

    if len(beat_samples) < 4:
        return [], []
    features = _beat_features(mono, beat_samples, sample_rate)
    dissimilarities: list[float] = []
    for i in range(len(features) - 1):
        dissimilarities.append(1.0 - dsp.cosine_similarity(features[i], features[i + 1]))
    if not dissimilarities:
        return [], []
    mean = sum(dissimilarities) / len(dissimilarities)
    spread = math.sqrt(sum((v - mean) ** 2 for v in dissimilarities) / len(dissimilarities))
    threshold = mean + 1.5 * spread
    boundaries: list[int] = [0]
    for i, value in enumerate(dissimilarities):
        if value >= threshold and i + 1 - boundaries[-1] >= 2:
            boundaries.append(i + 1)
    if not boundaries or boundaries[-1] != len(beat_samples):
        boundaries.append(len(beat_samples))
    sections: list[dict[str, Any]] = []
    for i in range(len(boundaries) - 1):
        start_beat = boundaries[i]
        end_beat = boundaries[i + 1]
        if end_beat <= start_beat:
            continue
        sections.append(
            {
                "start_beat": start_beat,
                "end_beat": end_beat,
                "start_sample": beat_samples[start_beat],
                "end_sample": beat_samples[min(end_beat, len(beat_samples) - 1)]
                + (sample_rate // 2 if end_beat >= len(beat_samples) else 0),
                "beat_count": end_beat - start_beat,
            }
        )
    repetitions: list[dict[str, Any]] = []
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            fi = [sum(f[k] for f in features[sections[i]["start_beat"]:sections[i]["end_beat"]]) / max(1, sections[i]["beat_count"]) for k in range(3)]
            fj = [sum(f[k] for f in features[sections[j]["start_beat"]:sections[j]["end_beat"]]) / max(1, sections[j]["beat_count"]) for k in range(3)]
            similarity = dsp.cosine_similarity(fi, fj)
            if similarity >= 0.92:
                repetitions.append(
                    {
                        "section_a": i,
                        "section_b": j,
                        "similarity_q14": int(round(similarity * 16384)),
                    }
                )
    return sections, repetitions


def analyze_time_axis(
    decoded: DecodedAudio,
    spectra: list[list[float]],
    starts: list[int],
    counter: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the full time-axis stage.

    Returns ``(observations, intermediates)`` where ``intermediates`` carries
    the onset/beat lattices and tempo that the harmony and acoustics stages
    consume, so the shared STFT is computed once.
    """

    observations: list[dict[str, Any]] = []
    sample_rate = decoded.sample_rate
    total = decoded.frame_count
    flux = spectral_flux(spectra)
    onset_samples, onset_strengths = detect_onsets(flux, starts, sample_rate)
    if onset_samples:
        observations.append(
            make_observation(
                next_id(counter, "onset"),
                "onset",
                onset_samples[0],
                onset_samples[-1],
                value={
                    "count": len(onset_samples),
                    "first_sample": onset_samples[0],
                    "last_sample": onset_samples[-1],
                },
                candidates=[{"sample": s, "strength_q14": st} for s, st in zip(onset_samples[:256], onset_strengths[:256])],
                conf=confidence(7000, "onset-peak-count/v1"),
                method="spectral-flux-peak/v1",
            )
        )
    tempo = estimate_tempo(flux, sample_rate)
    observations.append(
        make_observation(
            next_id(counter, "tempo"),
            "tempo",
            0,
            total,
            value=tempo["value"],
            candidates=tempo["candidates"],
            conf=tempo["confidence"],
            method="onset-envelope-autocorrelation/v1",
            unresolved_reason=tempo["unresolved_reason"],
        )
    )
    tempo_milli_bpm = tempo["value"]["tempo_milli_bpm"] if tempo["value"] else None
    beat_samples: list[int] = []
    beat_strengths: list[int] = []
    if tempo_milli_bpm:
        beat_samples, beat_strengths = track_beats(
            onset_samples, onset_strengths, tempo_milli_bpm, sample_rate, total
        )
    if beat_samples:
        observations.append(
            make_observation(
                next_id(counter, "beat"),
                "beat",
                beat_samples[0],
                beat_samples[-1],
                value={
                    "count": len(beat_samples),
                    "first_sample": beat_samples[0],
                    "last_sample": beat_samples[-1],
                },
                candidates=[{"sample": s, "strength_q14": st} for s, st in zip(beat_samples[:256], beat_strengths[:256])],
                conf=confidence(7000, "beat-grid-coverage/v1"),
                method="phase-aligned-grid/v1",
            )
        )
    meter = estimate_meter(beat_samples, beat_strengths, sample_rate)
    observations.append(
        make_observation(
            next_id(counter, "meter"),
            "meter",
            0,
            total,
            value=meter["value"],
            candidates=meter["candidates"],
            conf=meter["confidence"],
            method="beat-strength-autocorrelation/v1",
            unresolved_reason=meter["unresolved_reason"],
        )
    )
    if meter["value"] and beat_samples:
        observations.append(
            make_observation(
                next_id(counter, "downbeat"),
                "downbeat",
                meter["value"]["bar_0_sample"],
                total,
                value=meter["value"],
                candidates=meter["candidates"],
                conf=meter["confidence"],
                method="beat-strength-autocorrelation/v1",
            )
        )
    sections, repetitions = detect_sections(decoded.mono_floats(), beat_samples, sample_rate)
    if sections:
        observations.append(
            make_observation(
                next_id(counter, "section"),
                "section",
                sections[0]["start_sample"],
                sections[-1]["end_sample"],
                value={"count": len(sections)},
                candidates=[
                    {
                        "start_sample": s["start_sample"],
                        "end_sample": s["end_sample"],
                        "start_beat": s["start_beat"],
                        "end_beat": s["end_beat"],
                        "beat_count": s["beat_count"],
                    }
                    for s in sections[:64]
                ],
                conf=confidence(6000, "section-boundary-prominence/v1"),
                method="beat-self-similarity-change-point/v1",
            )
        )
    if repetitions:
        observations.append(
            make_observation(
                next_id(counter, "repetition"),
                "repetition",
                0,
                total,
                value={"count": len(repetitions)},
                candidates=repetitions[:32],
                conf=confidence(6000, "section-feature-similarity/v1"),
                method="beat-self-similarity/v1",
            )
        )
    intermediates = {
        "onset_samples": onset_samples,
        "onset_strengths": onset_strengths,
        "tempo_milli_bpm": tempo_milli_bpm,
        "beat_samples": beat_samples,
        "beat_strengths": beat_strengths,
    }
    return observations, intermediates
