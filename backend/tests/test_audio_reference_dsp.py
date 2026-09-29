from __future__ import annotations

import math

import pytest

from app.audio_reference import dsp


def _sine(frequency: float, n: int, rate: int) -> list[float]:
    return [math.sin(2.0 * math.pi * frequency * i / rate) for i in range(n)]


def test_fft_peaks_at_the_driving_bin() -> None:
    rate = 8192
    n = 1024
    frequency = 440.0
    samples = _sine(frequency, n, rate)
    magnitudes = dsp.fft_magnitude(samples)
    expected_bin = round(frequency * n / rate)
    peak_bin = max(range(len(magnitudes)), key=lambda i: magnitudes[i])
    assert peak_bin == expected_bin
    # The DC and far bins are much smaller than the driving bin.
    assert magnitudes[peak_bin] > 10 * magnitudes[0]


def test_fft_rejects_non_power_of_two() -> None:
    with pytest.raises(dsp.DspError):
        dsp.fft_magnitude([0.0, 1.0, 2.0])


def test_hann_window_is_symmetric_and_zero_at_edges() -> None:
    window = dsp.hann_window(64)
    assert len(window) == 64
    assert window[0] == pytest.approx(0.0, abs=1e-9)
    assert window[-1] == pytest.approx(0.0, abs=1e-9)
    for i in range(len(window)):
        assert window[i] == pytest.approx(window[-1 - i], abs=1e-9)
    # The symmetric Hann (denominator N-1) peaks just under 1.0 for even N.
    assert max(window) == pytest.approx(1.0, abs=1e-3)


def test_stft_frame_starts_and_count() -> None:
    samples = [0.0] * 10_000
    spectra, starts = dsp.stft_magnitudes(samples, frame_size=256, hop=128)
    assert starts[0] == 0
    assert all(b - a == 128 for a, b in zip(starts, starts[1:]))
    # The last frame starts at the largest multiple of hop below len(samples).
    assert starts[-1] == (len(samples) // 128) * 128
    assert all(len(s) == 256 // 2 + 1 for s in spectra)


def test_stft_rejects_bad_geometry() -> None:
    with pytest.raises(dsp.DspError):
        dsp.stft_magnitudes([0.0] * 10, frame_size=100, hop=128)
    with pytest.raises(dsp.DspError):
        dsp.stft_magnitudes([0.0] * 10, frame_size=256, hop=300)


def test_resample_downsamples_and_preserves_length_ratio() -> None:
    samples = _sine(100.0, 20_000, 20_000)
    out = dsp.resample_linear(samples, 20_000, 10_000)
    assert len(out) == pytest.approx(10_000, rel=0.01)
    with pytest.raises(dsp.DspError):
        dsp.resample_linear(samples, 10_000, 20_000)  # up-sampling unsupported


def test_autocorrelation_of_periodic_signal_peaks_at_period() -> None:
    period = 16
    values = [1.0 if (i % period) < 8 else -1.0 for i in range(period * 20)]
    ac = dsp.autocorrelation(values, period * 3)
    # The square wave repeats every `period` samples, so the autocorrelation at
    # that lag is maximal (equal to lag 0 for a perfect period).
    assert ac[period] == pytest.approx(ac[0], rel=0.05)


def test_pick_peaks_respects_min_distance() -> None:
    # Three equal spikes spaced 4 apart.
    values = [0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0]
    # min_distance=3 keeps all three (they are 4 apart).
    assert dsp.pick_peaks(values, min_prominence=1.0, min_distance=3) == [1, 5, 9]
    # min_distance=5 suppresses the middle spike (only 4 from the first).
    assert dsp.pick_peaks(values, min_prominence=1.0, min_distance=5) == [1, 9]


def test_cosine_similarity_bounds() -> None:
    a = [1.0, 2.0, 3.0]
    assert dsp.cosine_similarity(a, a) == pytest.approx(1.0)
    assert dsp.cosine_similarity(a, [-x for x in a]) == pytest.approx(-1.0)
    assert dsp.cosine_similarity(a, [0.0, 0.0, 0.0]) == 0.0
    with pytest.raises(dsp.DspError):
        dsp.cosine_similarity(a, [1.0, 2.0])
