"""Pure-Python deterministic DSP primitives for the audio reference baseline.

No third-party numeric backend is imported: the baseline must run on the
standard library alone so that the same PCM always yields the same
observations on the same build.  Adapter workers (librosa, Essentia, ...)
may replace individual stages later; they are not part of this module.

All public functions return plain Python lists of ``float`` or ``int`` and
perform no allocation-order-dependent work: results are bit-stable for a
given input.
"""

from __future__ import annotations

import math


class DspError(ValueError):
    """Raised when a DSP input is outside the supported domain."""


def fft_magnitude(samples: list[float]) -> list[float]:
    """Magnitude spectrum of a real, power-of-two-length signal.

    Returns ``n // 2 + 1`` magnitudes (DC through Nyquist) computed with an
    iterative radix-2 Cooley-Tukey transform.  Deterministic for a given
    input list.
    """

    n = len(samples)
    if n < 2 or (n & (n - 1)) != 0:
        raise DspError("FFT length must be a power of two >= 2")
    re = list(samples)
    im = [0.0] * n
    bits = n.bit_length() - 1
    for i in range(n):
        r = 0
        v = i
        for _ in range(bits):
            r = (r << 1) | (v & 1)
            v >>= 1
        j = r
        if i < j:
            re[i], re[j] = re[j], re[i]
    length = 2
    while length <= n:
        angle = -2.0 * math.pi / length
        wlen_c, wlen_s = math.cos(angle), math.sin(angle)
        half = length // 2
        for i in range(0, n, length):
            wr, wi = 1.0, 0.0
            for k in range(half):
                ar, ai = re[i + k], im[i + k]
                br, bi = re[i + k + half], im[i + k + half]
                tr = br * wr - bi * wi
                ti = br * wi + bi * wr
                re[i + k] = ar + tr
                im[i + k] = ai + ti
                re[i + k + half] = ar - tr
                im[i + k + half] = ai - ti
                nr = wr * wlen_c - wi * wlen_s
                wi = wr * wlen_s + wi * wlen_c
                wr = nr
        length *= 2
    return [math.hypot(re[k], im[k]) for k in range(n // 2 + 1)]


def hann_window(length: int) -> list[float]:
    if length < 1:
        raise DspError("window length must be positive")
    if length == 1:
        return [1.0]
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (length - 1)) for i in range(length)]


def stft_magnitudes(
    samples: list[float], frame_size: int, hop: int, window: list[float] | None = None
) -> tuple[list[list[float]], list[int]]:
    """Short-time Fourier magnitudes.

    Returns ``(spectra, frame_starts)`` where each spectrum has
    ``frame_size // 2 + 1`` entries and ``frame_starts`` holds the sample
    offset of each frame.  Frames shorter than ``frame_size`` at the tail are
    zero-padded, so the last frame always starts at the largest multiple of
    ``hop`` below ``len(samples)``.
    """

    if frame_size < 2 or (frame_size & (frame_size - 1)) != 0:
        raise DspError("frame_size must be a power of two >= 2")
    if hop < 1 or hop > frame_size:
        raise DspError("hop must be in [1, frame_size]")
    if window is None:
        window = hann_window(frame_size)
    if len(window) != frame_size:
        raise DspError("window length must equal frame_size")
    total = len(samples)
    if total == 0:
        return [], []
    spectra: list[list[float]] = []
    starts: list[int] = []
    start = 0
    while start < total:
        frame = [0.0] * frame_size
        available = min(frame_size, total - start)
        for i in range(available):
            frame[i] = samples[start + i] * window[i]
        spectra.append(fft_magnitude(frame))
        starts.append(start)
        start += hop
    return spectra, starts


def resample_linear(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    """Linear-interpolation resample to a lower analysis rate.

    Only down-sampling (``target_rate <= source_rate``) is supported; the
    baseline keeps the source rate by default and uses this for long files.
    """

    if source_rate < 1 or target_rate < 1:
        raise DspError("sample rates must be positive")
    if target_rate > source_rate:
        raise DspError("baseline resampling only supports down-sampling")
    if target_rate == source_rate:
        return list(samples)
    total = len(samples)
    if total == 0:
        return []
    ratio = source_rate / target_rate
    out_length = int(total / ratio)
    out: list[float] = []
    for i in range(out_length):
        position = i * ratio
        left = int(position)
        if left >= total:
            break
        frac = position - left
        out.append(samples[left] * (1.0 - frac) + samples[min(left + 1, total - 1)] * frac)
    return out


def rms_block(samples: list[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(v * v for v in samples) / len(samples))


def peak_abs(samples: list[float]) -> float:
    return max((abs(v) for v in samples), default=0.0)


def zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = sum((a < 0.0 <= b) or (b < 0.0 <= a) for a, b in zip(samples, samples[1:]))
    return crossings / (len(samples) - 1)


def autocorrelation(values: list[float], max_lag: int) -> list[float]:
    """Unnormalized autocorrelation lags 0..max_lag (inclusive)."""

    n = len(values)
    if n == 0 or max_lag < 0:
        return []
    limit = min(n, max_lag + 1)
    out: list[float] = []
    for lag in range(limit):
        acc = 0.0
        for i in range(n - lag):
            acc += values[i] * values[i + lag]
        out.append(acc)
    return out


def moving_average(values: list[float], window: int) -> list[float]:
    if window < 1:
        raise DspError("window must be positive")
    if not values:
        return []
    out: list[float] = []
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= window:
            running -= values[i - window]
        out.append(running / min(i + 1, window))
    return out


def pick_peaks(values: list[float], min_prominence: float, min_distance: int) -> list[int]:
    """Indices of local maxima at least ``min_prominence`` above the local mean.

    ``min_distance`` enforces a minimum gap between accepted peaks (in
    elements).  Ties keep the earlier index.  Deterministic.
    """

    if not values:
        return []
    n = len(values)
    context = max(1, min(n, 8))
    peaks: list[int] = []
    last = -min_distance
    for i in range(n):
        if i - last < min_distance:
            continue
        left = max(0, i - context)
        right = min(n, i + context + 1)
        local = values[left:right]
        if not (values[i] == max(local) and values[i] > min_prominence):
            continue
        baseline = sum(local) / len(local)
        if values[i] <= baseline:
            continue
        peaks.append(i)
        last = i
    return peaks


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        raise DspError("vectors must be non-empty and equal length")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
