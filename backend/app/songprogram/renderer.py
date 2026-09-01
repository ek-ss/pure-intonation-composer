"""Integer-only GEN0-C reference PCM renderer."""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import struct
from collections.abc import Callable, Mapping
from typing import Any

Q31 = 1 << 31
Q32 = 1 << 32
LO = -(1 << 31)
HI = (1 << 31) - 1


class RenderError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RenderResult:
    wav: bytes
    report: dict[str, Any]


def _sha(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def _rhe(x: Fraction) -> int:
    s = -1 if x < 0 else 1
    n, d = abs(x.numerator), x.denominator
    q, r = divmod(n, d)
    return s * (q + int(r * 2 > d or (r * 2 == d and q % 2)))


def _mul(x: int, n: int, d: int) -> int:
    return _rhe(Fraction(x * n, d))


def _gain(value: int, factors: tuple[tuple[int, int], ...]) -> int:
    for numerator, denominator in factors:
        value = _mul(value, numerator, denominator)
    return value


def _add_i64(left: int, right: int) -> int:
    value = left + right
    if not -(1 << 63) <= value < (1 << 63):
        raise RenderError("RENDER_ACCUMULATOR_OVERFLOW")
    return value


def _sat(x: int) -> tuple[int, int]:
    if not -(1 << 63) <= x < (1 << 63):
        raise RenderError("RENDER_ACCUMULATOR_OVERFLOW")
    y = min(HI, max(LO, x))
    return y, int(y != x)


def encode_pcm(a: list[tuple[int, int]]) -> tuple[bytes, int, int]:
    out = bytearray()
    count = peak = 0
    for left, right in a:
        for x in (left, right):
            y, c = _sat(x)
            out.extend(struct.pack("<i", y))
            count += c
            peak = max(peak, abs(y))
    return bytes(out), count, peak


def _asset(
    meta: Mapping[str, Any], resolve: Callable[[str], bytes]
) -> tuple[tuple[tuple[int, ...], ...], int]:
    try:
        b = resolve(str(meta["uri"]))
    except (KeyError, FileNotFoundError) as e:
        raise RenderError("ASSET_NOT_FOUND") from e
    if len(b) != meta["byte_length"]:
        raise RenderError("ASSET_LENGTH_MISMATCH")
    if _sha(b) != meta["sha256"]:
        raise RenderError("ASSET_HASH_MISMATCH")
    if (
        len(b) < 44
        or b[:4] != b"RIFF"
        or b[8:12] != b"WAVE"
        or b[12:16] != b"fmt "
        or b[36:40] != b"data"
        or struct.unpack_from("<I", b, 4)[0] != len(b) - 8
        or struct.unpack_from("<I", b, 16)[0] != 16
        or struct.unpack_from("<I", b, 40)[0] != len(b) - 44
    ):
        raise RenderError("ASSET_WAV_NONCANONICAL")
    fmt, ch, rate, br, align, bits = struct.unpack_from("<HHIIHH", b, 20)
    if (fmt, rate, bits, align, br) != (1, 48000, 32, ch * 4, 48000 * ch * 4) or ch not in (1, 2):
        raise RenderError("ASSET_WAV_NONCANONICAL")
    frames = (len(b) - 44) // align
    if (meta["channels"], meta["sample_rate"], meta["frames"]) != (ch, rate, frames):
        raise RenderError("ASSET_METADATA_MISMATCH")
    v = struct.unpack("<" + "i" * (frames * ch), b[44:])
    return tuple(tuple(v[i * ch : (i + 1) * ch]) for i in range(frames)), ch


def render_reference(
    project: Mapping[str, Any],
    catalog_bytes: bytes,
    resolve_asset: Callable[[str], bytes],
    *,
    render_manifest_digest: str,
    project_artifact_hash: str,
) -> RenderResult:
    c = json.loads(catalog_bytes)
    canon = (
        json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if canon != catalog_bytes:
        raise RenderError("CATALOG_ENTRY_INVALID")
    cd = _sha(b"cps.instrument-catalog/v1\0" + catalog_bytes)
    if project["compiler"]["instrument_catalog_digest"] != cd:
        raise RenderError("CATALOG_DIGEST_MISMATCH")
    if project["render_settings"] != {"sample_rate": 48000, "channel_layout": "stereo"}:
        raise RenderError("UNSUPPORTED_SCHEMA_CAPABILITY")
    if c.get("schema") != "cps.instrument-catalog" or c.get("schema_version") != "1.0.0" or c.get("engine") != "sample-linear-q31/v1":
        raise RenderError("CATALOG_ENTRY_INVALID")
    entry_ids = [entry["instrument_id"] for entry in c["entries"]]
    if entry_ids != sorted(entry_ids, key=str.encode) or len(entry_ids) != len(set(entry_ids)):
        raise RenderError("CATALOG_ENTRY_INVALID")
    for entry in c["entries"]:
        if entry["kind"] == "drum_kit":
            notes = [mapping["drum_note"] for mapping in entry["note_map"]]
            if notes != sorted(notes) or len(notes) != len(set(notes)):
                raise RenderError("CATALOG_ENTRY_INVALID")
    entries = {x["instrument_id"]: x for x in c["entries"]}
    tracks = {x["id"]: x for x in project["tracks"]}
    clk = project["clock"]
    base = int(project["lattice"]["base_frequency_millihz"])
    voices = []
    for e in project["events"]:
        t = tracks[e["track_id"]]
        en = entries.get(t["instrument_id"])
        if not en:
            raise RenderError("CATALOG_ENTRY_NOT_FOUND")
        start = _rhe(
            Fraction(
                e["start_tick"] * 60 * 48000 * 1000, clk["tempo_milli_bpm"] * clk["ticks_per_beat"]
            )
        )
        end = _rhe(
            Fraction(
                (e["start_tick"] + e["duration_ticks"]) * 60 * 48000 * 1000,
                clk["tempo_milli_bpm"] * clk["ticks_per_beat"],
            )
        )
        if e["kind"] == "drum":
            if en["kind"] != "drum_kit":
                raise RenderError("CATALOG_ENTRY_INVALID")
            m = next((x for x in en["note_map"] if x["drum_note"] == e["drum_note"]), None)
            if not m:
                raise RenderError("DRUM_NOTE_UNMAPPED")
            sm, ch = _asset(m["asset"], resolve_asset)
            voices.append((e, t, en, m, sm, ch, start, start + len(sm), end, 0))
        else:
            if en["kind"] != "pitched":
                raise RenderError("CATALOG_ENTRY_INVALID")
            ratio = Fraction(e["ratio"])
            lo, hi = en["allowed_frequency_millihz"]
            if not lo <= base * ratio <= hi:
                raise RenderError("CATALOG_ENTRY_INVALID")
            sm, ch = _asset(en["asset"], resolve_asset)
            inc = _rhe(Fraction(base, en["root_frequency_millihz"]) * ratio * 48000 * Q32 / 48000)
            finish = end + en["release_frames"]
            if en["loop"]["mode"] == "none":
                asset_end = start + (len(sm) * Q32 + inc - 1) // inc
                finish = min(finish, asset_end)
            voices.append((e, t, en, en, sm, ch, start, finish, end, inc))
    for track_id, track in tracks.items():
        intervals = [(voice[6], voice[7], voice[2]["maximum_polyphony"]) for voice in voices if voice[1]["id"] == track_id]
        points = sorted(
            [(start, 1, limit) for start, _, limit in intervals]
            + [(finish, -1, limit) for _, finish, limit in intervals],
            key=lambda item: (item[0], item[1]),
        )
        active = 0
        for _, delta, catalog_limit in points:
            active += delta
            if active > min(track["maximum_polyphony"], catalog_limit):
                raise RenderError("RENDER_POLYPHONY_EXCEEDED")
    n = max((x[7] for x in voices), default=0) + 256
    buses = {k: [(0, 0) for _ in range(n)] for k in tracks}
    for e, t, en, m, sm, ch, start, finish, end, inc in sorted(
        voices, key=lambda x: (x[1]["id"].encode(), x[0]["id"].encode())
    ):
        pan = project["mix"][t["id"]]["pan_q"]
        pg = (max(0, 10000 - max(pan, 0)), max(0, 10000 + min(pan, 0)))
        for f in range(start, min(finish, n - 256)):
            gains: tuple[tuple[int, int], ...]
            if e["kind"] == "drum":
                v = sm[f - start]
                lr: tuple[int, int] = (v[0], v[0] if ch == 1 else v[1])
                gains = ((e["velocity"], 127), (m["gain_q14"], 16384), (en["gain_q14"], 16384), (project["mix"][t["id"]]["gain_q"], 10000))
            else:
                phase = (f - start) * inc
                i, fr = divmod(phase, Q32)
                loop = en["loop"]
                a, b = loop["start_frame"], loop["end_frame"]
                if loop["mode"] == "forward" and i >= b:
                    phase = a * Q32 + (phase - b * Q32) % ((b - a) * Q32)
                    i, fr = divmod(phase, Q32)
                if i >= len(sm):
                    lr = (0, 0)
                else:
                    j = (
                        (a if i + 1 == b else i + 1)
                        if loop["mode"] == "forward"
                        else min(i + 1, len(sm) - 1)
                    )
                    interpolated = tuple(
                        _mul(sm[i][z], Q32 - fr, Q32) + _mul(sm[j][z], fr, Q32) for z in range(ch)
                    )
                    lr = (interpolated[0], interpolated[0] if ch == 1 else interpolated[1])
                if f >= end:
                    lr = (_mul(lr[0], finish - f, en["release_frames"]), _mul(lr[1], finish - f, en["release_frames"]))
                gains = ((e["velocity"], 127), (en["gain_q14"], 16384), (project["mix"][t["id"]]["gain_q"], 10000))
            lr = (_gain(lr[0], gains), _gain(lr[1], gains))
            lr = (_mul(lr[0], pg[0], 10000), _mul(lr[1], pg[1], 10000))
            old = buses[t["id"]][f]
            buses[t["id"]][f] = (_add_i64(old[0], lr[0]), _add_i64(old[1], lr[1]))
    mix = [(0, 0) for _ in range(n)]
    for k in sorted(buses, key=lambda x: x.encode()):
        mix = [(_add_i64(a[0], b[0]), _add_i64(a[1], b[1])) for a, b in zip(mix, buses[k])]
    pcm, sc, peak = encode_pcm(mix)
    wav = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 2, 48000, 384000, 8, 32)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )
    th = []
    for k in sorted(buses, key=lambda x: x.encode()):
        track_pcm, s, q = encode_pcm(buses[k])
        th.append(
            {
                "track_id": k,
                "format": "pcm-s32le-stereo-interleaved/v1",
                "frame_count": n,
                "pcm_byte_length": len(track_pcm),
                "pcm_hash": _sha(track_pcm),
                "saturation_count": s,
                "peak_absolute_sample": q,
            }
        )
    return RenderResult(
        wav,
        {
            "schema": "cps.reference-render-report",
            "schema_version": "1.1.0",
            "project_artifact_hash": project_artifact_hash,
            "render_manifest_digest": render_manifest_digest,
            "catalog_digest": cd,
            "wav_hash": _sha(wav),
            "pcm_hash": _sha(pcm),
            "frame_count": n,
            "saturation_count": sc,
            "peak_absolute_sample": peak,
            "track_hashes": th,
        },
    )
