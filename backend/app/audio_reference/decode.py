"""Reference-audio decoding to canonical int32 (Q31) PCM.

WAV decodes with the standard library.  FLAC/MP3/AAC decode through an
optional adapter (``soundfile`` when installed); the adapter id and version
are recorded in the decode conditions so receipts stay reproducible.  The
canonical PCM is interleaved little-endian int32 scaled to Q31, and its
SHA-256 is the ``pcm_hash`` used across all artifacts.
"""

from __future__ import annotations

import array
import hashlib
import io
import struct
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .input_policy import InputPolicy, check_decoded, check_file

Q31_SCALE = 2**31


class DecodeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


FORMAT_BY_SUFFIX = {
    ".wav": "wav",
    ".flac": "flac",
    ".mp3": "mp3",
    ".aac": "aac",
    ".m4a": "aac",
}


@dataclass(frozen=True)
class DecodedAudio:
    source_path: str
    source_hash: str
    format: str
    decoder_id: str
    decoder_version: str
    source_bit_depth: int | None
    sample_rate: int
    channels: int
    frame_count: int
    pcm: tuple[array.array, ...]  # per-channel int32 Q31, channel-major
    pcm_hash: str

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate

    def mono_q31(self) -> array.array:
        """Equal-weight downmix to a single Q31 channel (round-half-even)."""

        if self.channels == 1:
            return array.array("i", self.pcm[0])
        out = array.array("i")
        out.extend(
            _round_half_even(sum(self.pcm[c][i] for c in range(self.channels)) / self.channels)
            for i in range(self.frame_count)
        )
        return out

    def channel_floats(self, channel: int) -> list[float]:
        scale = 1.0 / Q31_SCALE
        return [v * scale for v in self.pcm[channel]]

    def mono_floats(self) -> list[float]:
        if self.channels == 1:
            return self.channel_floats(0)
        scale = 1.0 / (Q31_SCALE * self.channels)
        return [
            sum(self.pcm[c][i] for c in range(self.channels)) * scale for i in range(self.frame_count)
        ]


def _round_half_even(value: float) -> int:
    import math

    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in FORMAT_BY_SUFFIX:
        raise DecodeError("INPUT_FORMAT_UNSUPPORTED", f"{path.suffix} (expected .wav/.flac/.mp3/.aac)")
    return FORMAT_BY_SUFFIX[suffix]


def _to_q31(value: float) -> int:
    scaled = int(round(value * Q31_SCALE))
    return max(-Q31_SCALE, min(Q31_SCALE - 1, scaled))


def _decode_wav(payload: bytes) -> tuple[tuple[array.array, ...], int, int, int]:
    try:
        with wave.open(io.BytesIO(payload), "rb") as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            comptype = source.getcomptype()
            raw = source.readframes(frames)
    except (EOFError, struct.error, wave.Error) as error:
        raise DecodeError("WAV_DECODE_FAILED", str(error)) from None
    if comptype == "NONE":
        if width == 1:
            values = [(v - 128) / 128.0 for v in raw]
        elif width == 2:
            values = [v / 32768.0 for v in struct.unpack("<" + "h" * (len(raw) // 2), raw)]
        elif width == 3:
            triples = len(raw) // 3
            values = []
            for i in range(triples):
                lo, mid, hi = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
                v = lo | (mid << 8) | (hi << 16)
                if v & 0x800000:
                    v -= 1 << 24
                values.append(v / (2**23))
        elif width == 4:
            values = [v / (2**31) for v in struct.unpack("<" + "i" * (len(raw) // 4), raw)]
        else:
            raise DecodeError("WAV_SAMPLE_WIDTH_UNSUPPORTED", f"{width} bytes")
    elif comptype == "FLOAT":
        if width != 4:
            raise DecodeError("WAV_FLOAT_WIDTH_UNSUPPORTED", f"{width} bytes")
        values = list(struct.unpack("<" + "f" * (len(raw) // 4), raw))
    else:
        raise DecodeError("WAV_COMPRESSION_UNSUPPORTED", f"comptype={comptype}")
    if len(values) != frames * channels:
        raise DecodeError("WAV_FRAME_COUNT_MISMATCH", f"{len(values)} != {frames * channels}")
    per_channel: list[array.array] = [array.array("i") for _ in range(channels)]
    for index, value in enumerate(values):
        per_channel[index % channels].append(_to_q31(value))
    return tuple(per_channel), rate, channels, width * 8


def _decode_soundfile(payload: bytes, format_name: str) -> tuple[tuple[array.array, ...], int, int, int]:
    try:
        import soundfile  # type: ignore[import-not-found]
    except ImportError as error:
        raise DecodeError(
            "AUDIO_DECODE_ADAPTER_UNAVAILABLE",
            f"{format_name} requires the optional 'soundfile' adapter; install it or provide WAV",
        ) from error
    try:
        data, rate = soundfile.read(io.BytesIO(payload), dtype="float64", always_2d=True)
    except Exception as error:
        raise DecodeError(f"{format_name.upper()}_DECODE_FAILED", str(error)) from None
    channels = data.shape[1]
    per_channel: list[array.array] = [array.array("i") for _ in range(channels)]
    for c in range(channels):
        per_channel[c].extend(_to_q31(value) for value in data[:, c])
    return tuple(per_channel), int(rate), channels, 32


def _pcm_hash(pcm: tuple[array.array, ...], channels: int, frame_count: int) -> str:
    digest = hashlib.sha256()
    digest.update(b"cps.audio-reference-pcm/v1\0")
    chunk = 65_536
    for start in range(0, frame_count, chunk):
        end = min(start + chunk, frame_count)
        for c in range(channels):
            digest.update(pcm[c][start:end].tobytes())
    return "sha256:" + digest.hexdigest()


def decode_audio(path: Path, policy: InputPolicy) -> DecodedAudio:
    check_file(path, policy)
    payload = path.read_bytes()
    source_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
    format_name = detect_format(path)
    if format_name == "wav":
        pcm, rate, channels, bit_depth = _decode_wav(payload)
        decoder_id = "python-wave/v1"
        decoder_version = sys.version.split()[0]
    else:
        pcm, rate, channels, bit_depth = _decode_soundfile(payload, format_name)
        try:
            import soundfile  # type: ignore[import-not-found]

            decoder_version = soundfile.__version__
        except ImportError:  # pragma: no cover - adapter already failed above
            decoder_version = "unknown"
        decoder_id = f"soundfile/{decoder_version}"
    check_decoded(rate, len(pcm[0]) if pcm else 0, channels, policy)
    frame_count = len(pcm[0]) if pcm else 0
    return DecodedAudio(
        source_path=str(path),
        source_hash=source_hash,
        format=format_name,
        decoder_id=decoder_id,
        decoder_version=decoder_version,
        source_bit_depth=bit_depth,
        sample_rate=rate,
        channels=channels,
        frame_count=frame_count,
        pcm=pcm,
        pcm_hash=_pcm_hash(pcm, channels, frame_count),
    )


def decode_conditions(decoded: DecodedAudio) -> dict[str, Any]:
    return {
        "format": decoded.format,
        "decoder_id": decoded.decoder_id,
        "decoder_version": decoded.decoder_version,
        "source_bit_depth": decoded.source_bit_depth,
        "sample_rate_hz": decoded.sample_rate,
        "channels": decoded.channels,
        "frame_count": decoded.frame_count,
        "pcm_hash": decoded.pcm_hash,
    }
