from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from app.audio_reference.decode import (
    DecodedAudio,
    DecodeError,
    _to_q31,
    decode_audio,
    detect_format,
)
from app.audio_reference.input_policy import InputPolicyError, default_policy


def _write_wav(path: Path, samples: list[float], rate: int = 22050, channels: int = 1) -> None:
    """Write a 16-bit PCM WAV.

    ``samples`` is interleaved: for stereo pass ``[L0, R0, L1, R1, ...]``.
    Values are floats in [-1, 1].
    """

    interleaved = [int(round(max(-1.0, min(1.0, v)) * 32767)) for v in samples]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<" + "h" * len(interleaved), *interleaved))


def test_detect_format_by_suffix() -> None:
    assert detect_format(Path("a.wav")) == "wav"
    assert detect_format(Path("a.flac")) == "flac"
    assert detect_format(Path("a.mp3")) == "mp3"
    assert detect_format(Path("a.m4a")) == "aac"
    with pytest.raises(DecodeError) as exc:
        detect_format(Path("a.ogg"))
    assert exc.value.code == "INPUT_FORMAT_UNSUPPORTED"


def test_to_q31_scales_and_clamps() -> None:
    assert _to_q31(0.0) == 0
    assert _to_q31(1.0) == 2**31 - 1
    assert _to_q31(-1.0) == -(2**31)
    assert _to_q31(2.0) == 2**31 - 1  # clamped
    assert _to_q31(0.5) == 2**30


def test_decode_wav_16bit_roundtrip(tmp_path: Path) -> None:
    rate = 22050
    samples = [math.sin(2.0 * math.pi * 440.0 * i / rate) for i in range(rate)]
    path = tmp_path / "tone.wav"
    _write_wav(path, samples, rate)
    decoded = decode_audio(path, default_policy())
    assert isinstance(decoded, DecodedAudio)
    assert decoded.format == "wav"
    assert decoded.sample_rate == rate
    assert decoded.channels == 1
    assert decoded.frame_count == rate
    # The loudest sample should be near full scale in Q31.
    assert max(abs(v) for v in decoded.pcm[0]) > 0.9 * 2**31
    assert decoded.source_hash.startswith("sha256:")
    assert decoded.pcm_hash.startswith("sha256:")


def test_decode_is_deterministic(tmp_path: Path) -> None:
    rate = 22050
    samples = [math.sin(2.0 * math.pi * 110.0 * i / rate) for i in range(rate)]
    path = tmp_path / "tone.wav"
    _write_wav(path, samples, rate)
    first = decode_audio(path, default_policy())
    second = decode_audio(path, default_policy())
    assert first.pcm_hash == second.pcm_hash
    assert first.source_hash == second.source_hash


def test_decode_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.wav"
    path.write_bytes(b"")
    with pytest.raises(InputPolicyError) as exc:
        decode_audio(path, default_policy())
    assert exc.value.code == "INPUT_FILE_EMPTY"


def test_decode_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "big.wav"
    path.write_bytes(b"\x00" * (default_policy().max_file_size_bytes + 1))
    with pytest.raises(InputPolicyError) as exc:
        decode_audio(path, default_policy())
    assert exc.value.code == "INPUT_FILE_TOO_LARGE"


def test_decode_rejects_out_of_range_sample_rate(tmp_path: Path) -> None:
    # A valid WAV header at an out-of-policy sample rate.
    path = tmp_path / "rate.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(500)  # below the 8000 Hz policy floor
        handle.writeframes(struct.pack("<hh", 0, 0))
    with pytest.raises(InputPolicyError) as exc:
        decode_audio(path, default_policy())
    assert exc.value.code == "INPUT_SAMPLE_RATE_OUT_OF_RANGE"


def test_decode_rejects_too_short(tmp_path: Path) -> None:
    path = tmp_path / "short.wav"
    _write_wav(path, [0.5] * 100, rate=22050)  # ~4.5 ms
    with pytest.raises(InputPolicyError) as exc:
        decode_audio(path, default_policy())
    assert exc.value.code == "INPUT_TOO_SHORT"


def test_mono_downmix_averages_channels(tmp_path: Path) -> None:
    rate = 22050
    left = [1.0] * rate
    right = [-1.0] * rate
    interleaved = [v for pair in zip(left, right) for v in pair]  # L0,R0,L1,R1,...
    path = tmp_path / "stereo.wav"
    _write_wav(path, interleaved, rate, channels=2)
    decoded = decode_audio(path, default_policy())
    assert decoded.channels == 2
    mono = decoded.mono_q31()
    # Equal and opposite channels cancel to (near) zero.
    assert max(abs(v) for v in mono) < 0.01 * 2**31
