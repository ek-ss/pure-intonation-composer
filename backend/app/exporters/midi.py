from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2


@dataclass(frozen=True)
class MidiNote:
    ratio: Fraction
    start_beats: float
    duration_beats: float
    velocity: int = 100


def midi_bytes(notes: list[MidiNote], base_frequency: float = 220, ticks_per_beat: int = 480) -> bytes:
    """Export rational pitches as nearest-note MIDI type-0 events."""
    if not 20 <= base_frequency <= 2000 or not 24 <= ticks_per_beat <= 960:
        raise ValueError("MIDI settings are invalid")
    events: list[tuple[int, bytes]] = [(0, b"\xff\x51\x03\x07\xa1\x20")]
    for note in notes:
        if note.ratio <= 0 or note.start_beats < 0 or note.duration_beats <= 0 or not 1 <= note.velocity <= 127:
            raise ValueError("MIDI note is invalid")
        number = max(0, min(127, round(69 + 12 * log2(base_frequency * float(note.ratio) / 440))))
        events.extend([(round(note.start_beats * ticks_per_beat), bytes((0x90, number, note.velocity))), (round((note.start_beats + note.duration_beats) * ticks_per_beat), bytes((0x80, number, 0)))])
    events.sort(key=lambda item: (item[0], item[1][0] == 0x90))
    previous, track = 0, bytearray()
    for tick, data in events:
        track.extend(_variable_length(tick - previous))
        track.extend(data)
        previous = tick
    track.extend(b"\x00\xff\x2f\x00")
    return b"MThd\x00\x00\x00\x06\x00\x00\x00\x01" + ticks_per_beat.to_bytes(2, "big") + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def _variable_length(value: int) -> bytes:
    result = [value & 0x7F]
    while value > 0x7F:
        value >>= 7
        result.insert(0, (value & 0x7F) | 0x80)
    return bytes(result)
