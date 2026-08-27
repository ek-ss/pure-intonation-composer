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


@dataclass(frozen=True)
class MidiDrumHit:
    note: int
    start_beats: float
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


_MICROTONAL_CHANNELS = tuple(channel for channel in range(16) if channel != 9)


def microtonal_midi_bytes(
    notes: list[MidiNote],
    base_frequency: float = 220,
    ticks_per_beat: int = 480,
    pitch_bend_range_semitones: int = 2,
) -> bytes:
    """Export rational pitches as pitch-bend retuned MIDI type-0 events.

    Each note is placed on its own channel (round-robin over channels 1-16
    skipping 10) with a pitch-bend event before the note-on so the sounding
    pitch matches base_frequency * ratio exactly.
    """
    if not 20 <= base_frequency <= 2000 or not 24 <= ticks_per_beat <= 960:
        raise ValueError("MIDI settings are invalid")
    if not 1 <= pitch_bend_range_semitones <= 48:
        raise ValueError("pitch bend range must be between 1 and 48 semitones")
    events: list[tuple[int, bytes]] = [(0, b"\xff\x51\x03\x07\xa1\x20")]
    for index, note in enumerate(notes):
        if note.ratio <= 0 or note.start_beats < 0 or note.duration_beats <= 0 or not 1 <= note.velocity <= 127:
            raise ValueError("MIDI note is invalid")
        channel = _MICROTONAL_CHANNELS[index % len(_MICROTONAL_CHANNELS)]
        semitones = 12 * log2(base_frequency * float(note.ratio) / 440)
        bend = semitones - round(semitones)
        number = max(0, min(127, 69 + round(semitones)))
        value = max(0, min(16383, 8192 + round(bend / pitch_bend_range_semitones * 8192)))
        on = round(note.start_beats * ticks_per_beat)
        events.extend([
            (on, bytes((0xE0 | channel, value & 0x7F, value >> 7))),
            (on, bytes((0x90 | channel, number, note.velocity))),
            (round((note.start_beats + note.duration_beats) * ticks_per_beat), bytes((0x80 | channel, number, 0))),
        ])
    events.sort(key=lambda item: (item[0], (item[1][0] & 0xF0) == 0x90))
    previous, track = 0, bytearray()
    for tick, data in events:
        track.extend(_variable_length(tick - previous))
        track.extend(data)
        previous = tick
    track.extend(b"\x00\xff\x2f\x00")
    return b"MThd\x00\x00\x00\x06\x00\x00\x00\x01" + ticks_per_beat.to_bytes(2, "big") + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def drum_midi_bytes(hits: list[MidiDrumHit], ticks_per_beat: int = 480) -> bytes:
    """Export drum hits as General MIDI percussion (channel 10) type-0 events."""
    if not 24 <= ticks_per_beat <= 960:
        raise ValueError("MIDI settings are invalid")
    events: list[tuple[int, bytes]] = [(0, b"\xff\x51\x03\x07\xa1\x20")]
    for hit in hits:
        if not 0 <= hit.note <= 127 or hit.start_beats < 0 or not 1 <= hit.velocity <= 127:
            raise ValueError("MIDI drum hit is invalid")
        on = round(hit.start_beats * ticks_per_beat)
        events.extend([(on, bytes((0x99, hit.note, hit.velocity))), (on + ticks_per_beat // 4, bytes((0x89, hit.note, 0)))])
    events.sort(key=lambda item: (item[0], item[1][0] == 0x99))
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


@dataclass(frozen=True)
class MidiArrangementTrack:
    """One named part of a multitrack arrangement export."""

    name: str
    notes: tuple[MidiNote, ...] = ()
    drums: tuple[MidiDrumHit, ...] = ()


def arrangement_midi_bytes(
    tracks: list[MidiArrangementTrack],
    tempo_bpm: float,
    beats_per_bar: int,
    ticks_per_beat: int = 480,
    base_frequency: float = 220,
    markers: list[tuple[int, str]] | None = None,
    time_signatures: list[tuple[int, int, int]] | None = None,
    pitch_bend_range_semitones: int = 2,
) -> bytes:
    """Export an arrangement as a Standard MIDI File type 1.

    Track 0 carries tempo, meter, and section markers; every arrangement part
    becomes one named track. Pitched notes are retuned with per-note pitch
    bend. Channel allocation is global: simultaneous notes that need different
    bends never share a channel, and channel 10 is reserved for GM percussion.
    """
    if not 30 <= tempo_bpm <= 300 or not 2 <= beats_per_bar <= 13:
        raise ValueError("arrangement MIDI clock settings are invalid")
    if not 24 <= ticks_per_beat <= 960 or not 20 <= base_frequency <= 2000:
        raise ValueError("arrangement MIDI tuning settings are invalid")
    allocation = _allocate_channels(tracks, ticks_per_beat, base_frequency)
    chunks = [
        _conductor_chunk(
            tempo_bpm, beats_per_bar, markers or [], time_signatures or []
        )
    ]
    for track_index, track in enumerate(tracks):
        chunks.append(
            _part_chunk(
                track, allocation[track_index], ticks_per_beat, base_frequency,
                pitch_bend_range_semitones,
            )
        )
    header = (
        b"MThd\x00\x00\x00\x06\x00\x01"
        + len(chunks).to_bytes(2, "big")
        + ticks_per_beat.to_bytes(2, "big")
    )
    return header + b"".join(chunks)


def _allocate_channels(
    tracks: list[MidiArrangementTrack], ticks_per_beat: int, base_frequency: float
) -> list[dict[int, int]]:
    """Assign every pitched note a conflict-free channel, per track note order."""
    available = [channel for channel in range(16) if channel != 9]
    # channel -> list of (start_tick, end_tick, bend_semitones, number)
    busy: dict[int, list[tuple[int, int, float, int]]] = {channel: [] for channel in available}
    allocation: list[dict[int, int]] = []
    for track in tracks:
        track_allocation: dict[int, int] = {}
        for index, note in enumerate(sorted(track.notes, key=lambda item: item.start_beats)):
            start = round(note.start_beats * ticks_per_beat)
            end = round((note.start_beats + note.duration_beats) * ticks_per_beat)
            semitones = 12 * log2(base_frequency * float(note.ratio) / 440)
            bend = semitones - round(semitones)
            number = max(0, min(127, 69 + round(semitones)))
            placed = False
            for channel in available:
                if all(
                    end <= other_start or start >= other_end or (other_bend == bend and other_number != number)
                    for other_start, other_end, other_bend, other_number in busy[channel]
                ):
                    busy[channel].append((start, end, bend, number))
                    track_allocation[index] = channel
                    placed = True
                    break
            if not placed:
                raise ValueError(
                    "pitch-bend channel budget exceeded: too many simultaneous notes "
                    "with distinct exact tunings for the 15 available channels; reduce "
                    "polyphony, shorten sustained notes, or split the arrangement"
                )
        allocation.append(track_allocation)
    return allocation


def _conductor_chunk(
    tempo_bpm: float,
    beats_per_bar: int,
    markers: list[tuple[int, str]],
    time_signatures: list[tuple[int, int, int]],
) -> bytes:
    microseconds = round(60_000_000 / tempo_bpm)
    events: list[tuple[int, bytes]] = [
        (0, b"\xff\x51\x03" + microseconds.to_bytes(3, "big"))
    ]
    signatures = time_signatures or [(0, beats_per_bar, 4)]
    for tick, numerator, denominator in signatures:
        if tick < 0 or not 2 <= numerator <= 13 or denominator not in {2, 4, 8, 16}:
            raise ValueError("arrangement MIDI time signature is invalid")
        denominator_power = {2: 1, 4: 2, 8: 3, 16: 4}[denominator]
        events.append(
            (
                tick,
                bytes(
                    (0xFF, 0x58, 0x04, numerator, denominator_power, 0x18, 0x08)
                ),
            )
        )
    for tick, name in sorted(markers):
        text = name.encode("utf-8")[:120]
        events.append((tick, b"\xff\x06" + _variable_length(len(text)) + text))
    events.sort(key=lambda item: item[0])
    return _track_chunk(events)


def _part_chunk(
    track: MidiArrangementTrack,
    allocation: dict[int, int],
    ticks_per_beat: int,
    base_frequency: float,
    pitch_bend_range_semitones: int,
) -> bytes:
    name = track.name.encode("utf-8")[:120]
    events: list[tuple[int, int, bytes]] = [
        (0, 0, b"\xff\x03" + _variable_length(len(name)) + name)
    ]
    index = 0
    for note in sorted(track.notes, key=lambda item: item.start_beats):
        channel = allocation[index]
        semitones = 12 * log2(base_frequency * float(note.ratio) / 440)
        bend = semitones - round(semitones)
        number = max(0, min(127, 69 + round(semitones)))
        value = max(0, min(16383, 8192 + round(bend / pitch_bend_range_semitones * 8192)))
        on = round(note.start_beats * ticks_per_beat)
        off = round((note.start_beats + note.duration_beats) * ticks_per_beat)
        events.extend(
            [
                (on, 1, bytes((0xE0 | channel, value & 0x7F, value >> 7))),
                (on, 2, bytes((0x90 | channel, number, note.velocity))),
                (off, 0, bytes((0x80 | channel, number, 0))),
            ]
        )
        index += 1
    for hit in track.drums:
        on = round(hit.start_beats * ticks_per_beat)
        events.extend(
            [
                (on, 2, bytes((0x99, hit.note, hit.velocity))),
                (on + ticks_per_beat // 4, 0, bytes((0x89, hit.note, 0))),
            ]
        )
    events.sort(key=lambda item: (item[0], item[1]))
    return _track_chunk([(tick, data) for tick, _priority, data in events])


def _track_chunk(events: list[tuple[int, bytes]]) -> bytes:
    track = bytearray()
    previous = 0
    for tick, data in events:
        track.extend(_variable_length(tick - previous))
        track.extend(data)
        previous = tick
    track.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)
