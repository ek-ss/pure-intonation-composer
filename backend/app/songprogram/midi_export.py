"""Deterministic microtonal evaluation MIDI export for ArrangementProject 1.2."""

from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any, Mapping

from .search import canonical_bytes

PITCH_BEND_RANGE_SEMITONES = 2
_PITCHED_CHANNELS = tuple(channel for channel in range(16) if channel != 9)
_PROGRAM_BY_ROLE = {"bass": 38, "harmony": 89, "melody": 81, "texture": 99}


class MidiExportError(ValueError):
    pass


def _vlq(value: int) -> bytes:
    if value < 0:
        raise MidiExportError("MIDI_TICK_INVALID")
    result = bytearray([value & 0x7F])
    value >>= 7
    while value:
        result.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return bytes(result)


def _ratio_mc(value: Fraction) -> int:
    if value <= 0:
        raise MidiExportError("MIDI_RATIO_INVALID")
    with localcontext() as context:
        context.prec = 80
        result = Decimal(1200000) * (
            Decimal(value.numerator).ln() - Decimal(value.denominator).ln()
        ) / Decimal(2).ln()
        return int(result.to_integral_value(rounding=ROUND_HALF_EVEN))


def _pitch(base_frequency_millihz: int, ratio: str) -> tuple[int, int]:
    offset_mc = _ratio_mc(Fraction(base_frequency_millihz, 440000) * Fraction(ratio))
    note_offset = round(offset_mc / 100000)
    note = 69 + note_offset
    if not 0 <= note <= 127:
        raise MidiExportError("MIDI_NOTE_OUT_OF_RANGE")
    residual_mc = offset_mc - note_offset * 100000
    bend = 8192 + round(residual_mc * 8192 / (PITCH_BEND_RANGE_SEMITONES * 100000))
    return note, max(0, min(16383, bend))


def _event(priority: int, payload: bytes) -> tuple[int, bytes]:
    return priority, payload


def export_evaluation_midi(
    project: Mapping[str, Any],
    *,
    pitched_channels: tuple[int, ...] = _PITCHED_CHANNELS,
    algorithm: str = "smf0-per-note-channel-pitch-bend/v1",
    program_by_track: Mapping[str, int] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Return SMF type-0 bytes plus a hash-bound, machine-readable export manifest."""
    ticks_per_beat = int(project["clock"]["ticks_per_beat"])
    tempo_us = round(60_000_000_000 / int(project["clock"]["tempo_milli_bpm"]))
    if not 1 <= tempo_us <= 0xFFFFFF:
        raise MidiExportError("MIDI_TEMPO_INVALID")
    tracks = {track["id"]: track for track in project["tracks"]}
    overrides = dict(program_by_track or {})
    if (len(overrides) > 1 or any(
        track_id not in tracks or tracks[track_id]["role"] == "drums"
        or type(program) is not int or not 0 <= program <= 127
        for track_id, program in overrides.items()
    )):
        raise MidiExportError("MIDI_PROGRAM_OVERRIDE_INVALID")
    scheduled: dict[int, list[tuple[int, bytes]]] = {0: []}
    separate_tracks = bool(overrides)
    per_track: dict[str, dict[int, list[tuple[int, bytes]]]] = {}
    if separate_tracks:
        for track_id in tracks:
            name = track_id.encode("ascii")
            per_track[track_id] = {0: [_event(0, b"\xff\x03" + _vlq(len(name)) + name)]}
    scheduled[0].append(_event(0, b"\xff\x51\x03" + tempo_us.to_bytes(3, "big")))
    denominator = int(project["clock"]["beats_per_bar"])
    scheduled[0].append(_event(1, bytes((0xFF, 0x58, 0x04, denominator, 2, 24, 8))))
    if not pitched_channels or len(set(pitched_channels)) != len(pitched_channels) or any(
        not 0 <= channel <= 15 or channel == 9 for channel in pitched_channels
    ):
        raise MidiExportError("MIDI_CHANNEL_SET_INVALID")
    piano_channels = pitched_channels[:4] if separate_tracks else ()
    accompaniment_channels = pitched_channels[4:] if separate_tracks else pitched_channels
    if separate_tracks and (not piano_channels or not accompaniment_channels):
        raise MidiExportError("MIDI_CHANNEL_SET_INVALID")
    for channel in pitched_channels:
        status = 0xB0 | channel
        for controller, value in ((101, 0), (100, 0), (6, PITCH_BEND_RANGE_SEMITONES), (38, 0)):
            scheduled[0].append(_event(2, bytes((status, controller, value))))

    active_until = {channel: -1 for channel in pitched_channels}
    pitched = sorted(
        (event for event in project["events"] if event["kind"] == "note"),
        key=lambda event: (event["start_tick"], event["id"]),
    )
    for note_event in pitched:
        start = int(note_event["start_tick"])
        end = start + int(note_event["duration_ticks"])
        track_id = note_event["track_id"]
        pool = (piano_channels if track_id in overrides else accompaniment_channels)
        available = [channel for channel in pool if active_until[channel] <= start]
        if not available:
            raise MidiExportError("MIDI_CHANNELS_EXHAUSTED")
        channel = available[0]
        active_until[channel] = end
        note, bend = _pitch(int(project["lattice"]["base_frequency_millihz"]), note_event["ratio"])
        role = tracks[track_id]["role"]
        destination = per_track[track_id] if separate_tracks else scheduled
        destination.setdefault(start, []).extend(
            [
                _event(4, bytes((0xC0 | channel, overrides.get(track_id, _PROGRAM_BY_ROLE[role])))),
                _event(5, bytes((0xE0 | channel, bend & 0x7F, bend >> 7))),
                _event(6, bytes((0x90 | channel, note, int(note_event["velocity"])))),
            ]
        )
        destination.setdefault(end, []).append(_event(3, bytes((0x80 | channel, note, 0))))

    for drum in sorted(
        (event for event in project["events"] if event["kind"] == "drum"),
        key=lambda event: (event["start_tick"], event["id"]),
    ):
        start = int(drum["start_tick"])
        end = start + int(drum["duration_ticks"])
        note = int(drum["drum_note"])
        destination = per_track[drum["track_id"]] if separate_tracks else scheduled
        destination.setdefault(start, []).append(
            _event(6, bytes((0x99, note, int(drum["velocity"]))))
        )
        destination.setdefault(end, []).append(_event(3, bytes((0x89, note, 0))))

    def encode_track(events: Mapping[int, list[tuple[int, bytes]]]) -> bytes:
        body = bytearray()
        previous_tick = 0
        for tick in sorted(events):
            first = True
            for _, payload in sorted(events[tick], key=lambda item: (item[0], item[1])):
                body.extend(_vlq(tick - previous_tick if first else 0))
                body.extend(payload)
                previous_tick = tick
                first = False
        body.extend(b"\x00\xff\x2f\x00")
        return b"MTrk" + len(body).to_bytes(4, "big") + bytes(body)

    ordered = [scheduled] + list(per_track.values()) if separate_tracks else [scheduled]
    midi = (b"MThd\x00\x00\x00\x06" + (1 if separate_tracks else 0).to_bytes(2, "big")
            + len(ordered).to_bytes(2, "big") + ticks_per_beat.to_bytes(2, "big"))
    midi += b"".join(encode_track(events) for events in ordered)
    midi_hash = "sha256:" + hashlib.sha256(midi).hexdigest()
    manifest = {
        "schema": "cps.evaluation-reference-midi-manifest",
        "schema_version": "1.1.0" if overrides else "1.0.0",
        "algorithm": "smf1-named-tracks-per-note-pitch-bend/v1" if separate_tracks else algorithm,
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "pitch_bend_range_semitones": PITCH_BEND_RANGE_SEMITONES,
        "program_by_role": _PROGRAM_BY_ROLE,
        "midi_hash": midi_hash,
        "manifest_hash": "",
    }
    if overrides:
        manifest["program_by_track"] = overrides
    manifest["manifest_hash"] = "sha256:" + hashlib.sha256(
        (b"cps.evaluation-reference-midi-manifest/v1.1\0" if overrides
         else b"cps.evaluation-reference-midi-manifest/v1\0")
        + canonical_bytes({key: value for key, value in manifest.items() if key != "manifest_hash"})
    ).hexdigest()
    return midi, manifest
