from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from io import BytesIO
from math import pi, sin
from struct import pack
from wave import open as wave_open


@dataclass(frozen=True)
class NoteEvent:
    ratio: Fraction
    start_seconds: float
    duration_seconds: float
    velocity: int = 100


@dataclass(frozen=True)
class Envelope:
    attack_seconds: float = 0.02
    decay_seconds: float = 0.14
    sustain_level: float = 0.65
    release_seconds: float = 0.28


def render_wav(events: list[NoteEvent], base_frequency: float = 220, waveform: str = "sine", envelope: Envelope = Envelope(), sample_rate: int = 22_050, delay_seconds: float = 0, reverb_amount: float = 0) -> bytes:
    """Offline-render sine, saw, square, triangle, or additive notes to WAV."""
    _validate(events, base_frequency, waveform, envelope, sample_rate, delay_seconds, reverb_amount)
    total = max((event.start_seconds + event.duration_seconds + envelope.release_seconds for event in events), default=0.1)
    samples = [0.0] * (int(total * sample_rate) + 1)
    for event in events:
        start = int(event.start_seconds * sample_rate)
        end = min(len(samples), int((event.start_seconds + event.duration_seconds + envelope.release_seconds) * sample_rate))
        frequency, amplitude = base_frequency * float(event.ratio), event.velocity / 127 * 0.28
        for index in range(start, end):
            elapsed = (index - start) / sample_rate
            samples[index] += amplitude * _waveform(waveform, frequency, elapsed) * _envelope(elapsed, event.duration_seconds, envelope)
    _apply_delay(samples, sample_rate, delay_seconds)
    _apply_reverb(samples, sample_rate, reverb_amount)
    peak = max((abs(sample) for sample in samples), default=1)
    scale = min(1, 0.98 / peak)
    buffer = BytesIO()
    with wave_open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(pack("<h", int(max(-0.98, min(0.98, sample * scale)) * 32767)) for sample in samples))
    return buffer.getvalue()


def _waveform(kind: str, frequency: float, time: float) -> float:
    phase = (frequency * time) % 1
    if kind == "sine":
        return sin(2 * pi * phase)
    if kind == "saw":
        return 2 * phase - 1
    if kind == "square":
        return 1.0 if phase < 0.5 else -1.0
    if kind == "triangle":
        return 1 - 4 * abs(phase - 0.5)
    return sum(sin(2 * pi * phase * harmonic) / harmonic for harmonic in range(1, 6)) / 1.4636


def _envelope(time: float, duration: float, envelope: Envelope) -> float:
    if time < envelope.attack_seconds:
        return time / envelope.attack_seconds
    if time < envelope.attack_seconds + envelope.decay_seconds:
        return 1 - (1 - envelope.sustain_level) * (time - envelope.attack_seconds) / envelope.decay_seconds
    if time < duration:
        return envelope.sustain_level
    if time < duration + envelope.release_seconds:
        return envelope.sustain_level * (1 - (time - duration) / envelope.release_seconds)
    return 0


def _apply_delay(samples: list[float], sample_rate: int, seconds: float) -> None:
    delay = int(seconds * sample_rate)
    if delay:
        for index in range(delay, len(samples)):
            samples[index] += samples[index - delay] * 0.35


def _apply_reverb(samples: list[float], sample_rate: int, amount: float) -> None:
    for seconds in (0.029, 0.043, 0.071):
        delay = int(seconds * sample_rate)
        for index in range(delay, len(samples)):
            samples[index] += samples[index - delay] * amount / 3


def _validate(events: list[NoteEvent], frequency: float, waveform: str, envelope: Envelope, sample_rate: int, delay: float, reverb: float) -> None:
    if waveform not in {"sine", "saw", "square", "triangle", "additive"} or not 20 <= frequency <= 2000 or not 8_000 <= sample_rate <= 96_000:
        raise ValueError("audio settings are invalid")
    if min(envelope.attack_seconds, envelope.decay_seconds, envelope.release_seconds) <= 0 or not 0 <= envelope.sustain_level <= 1 or delay < 0 or not 0 <= reverb <= 1:
        raise ValueError("envelope or effects settings are invalid")
    if any(event.ratio <= 0 or event.start_seconds < 0 or event.duration_seconds <= 0 or not 1 <= event.velocity <= 127 for event in events):
        raise ValueError("note events are invalid")
