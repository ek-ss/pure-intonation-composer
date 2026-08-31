"""Rebuild the normative GEN0-C catalog, manifest, cases, and PCM32 WAV assets."""

from __future__ import annotations

import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / "fixtures" / "render"
ASSETS = OUT / "assets"
CATALOG_PREFIX = b"cps.instrument-catalog/v1\0"
MANIFEST_PREFIX = b"cps.render-manifest/v1\0"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(prefix: bytes, payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(prefix + payload).hexdigest()


def wav_mono(samples: tuple[int, ...]) -> bytes:
    pcm = b"".join(struct.pack("<i", value) for value in samples)
    fmt = struct.pack("<HHIIHH", 1, 1, 48_000, 192_000, 4, 32)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_asset(samples: tuple[int, ...], assets: Path) -> dict[str, Any]:
    data = wav_mono(samples)
    hex_digest = hashlib.sha256(data).hexdigest()
    (assets / f"{hex_digest}.wav").write_bytes(data)
    return {
        "uri": f"asset://sha256/{hex_digest}",
        "sha256": f"sha256:{hex_digest}",
        "byte_length": len(data),
        "sample_rate": 48_000,
        "channels": 1,
        "frames": len(samples),
    }


def phase_increment(base_millihz: int, ratio: Fraction, root_millihz: int) -> int:
    return round(Fraction(base_millihz, root_millihz) * ratio * (1 << 32))


def build(out: Path = OUT) -> None:
    assets = out / "assets"
    out.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    for old in assets.glob("*.wav"):
        old.unlink()

    pitched_2 = write_asset((0, 536_870_912, 1_073_741_824, 536_870_912, 0, -536_870_912, -1_073_741_824, -536_870_912), assets)
    pitched_3 = write_asset((0, 268_435_456, 805_306_368, 1_073_741_824, 805_306_368, 268_435_456, -268_435_456, -805_306_368), assets)
    drum = write_asset((1_610_612_736, -805_306_368, 402_653_184, -201_326_592, 100_663_296, -50_331_648, 25_165_824, 0), assets)

    catalog = {
        "schema": "cps.instrument-catalog", "schema_version": "1.0.0", "engine": "sample-linear-q31/v1",
        "entries": [
            {"kind": "drum_kit", "instrument_id": "drum_fixture_kit", "role": "drums", "engine": "sample-linear-q31/v1", "maximum_polyphony": 8, "gain_q14": 16384, "note_map": [{"drum_note": 36, "asset": drum, "gain_q14": 16384}]},
            {"kind": "pitched", "instrument_id": "pitched_fixture_2_1", "role": "harmony", "engine": "sample-linear-q31/v1", "asset": pitched_2, "root_frequency_millihz": 220_000, "allowed_frequency_millihz": [20_000, 4_000_000], "loop": {"mode": "forward", "start_frame": 0, "end_frame": 8}, "maximum_polyphony": 8, "gain_q14": 16384, "release_frames": 4},
            {"kind": "pitched", "instrument_id": "pitched_fixture_3_1", "role": "harmony", "engine": "sample-linear-q31/v1", "asset": pitched_3, "root_frequency_millihz": 330_000, "allowed_frequency_millihz": [20_000, 4_000_000], "loop": {"mode": "forward", "start_frame": 0, "end_frame": 8}, "maximum_polyphony": 8, "gain_q14": 12288, "release_frames": 7},
        ],
    }
    catalog_bytes = canonical_bytes(catalog)
    catalog_digest = digest(CATALOG_PREFIX, catalog_bytes)
    (out / "catalog.json").write_bytes(catalog_bytes)

    contracts = []
    for contract_id, version, relative in (
        ("instrument-catalog-render-manifest", "1.0.0", "docs/instrument_catalog_render_manifest_contract.md"),
        ("song-program-renderer-evaluation", "1.0.0", "docs/song_program_renderer_evaluation_contract.md"),
    ):
        raw = (REPO / relative).read_bytes()
        contracts.append({"id": contract_id, "version": version, "raw_bytes_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()})
    source_artifact = "backend/songprogram_conformance/build_renderer_catalog_fixtures.py"
    source_raw = (REPO / source_artifact).read_bytes()
    lock_raw = (REPO / "backend" / "requirements.txt").read_bytes()
    manifest_core = {
        "schema": "cps.render-manifest", "schema_version": "1.0.0",
        "renderer_build": {"implementation_id": "cps-reference-renderer", "source_artifact": source_artifact, "source_sha256": "sha256:" + hashlib.sha256(source_raw).hexdigest(), "dependency_lock_sha256": "sha256:" + hashlib.sha256(lock_raw).hexdigest()},
        "catalog_digest": catalog_digest, "contracts": contracts,
        "numeric_constants": {"engine": "sample-linear-q31/v1", "output_sample_rate": 48_000, "output_channels": 2, "sample_bits": 32, "q_fractional_bits": 31, "phase_fractional_bits": 32, "block_frames": 256, "trailing_zero_frames": 256, "multiply_rounding": "round-half-to-even", "accumulator_bits": 64, "final_conversion": "saturate-once"},
    }
    manifest = dict(manifest_core)
    manifest["render_manifest_digest"] = digest(MANIFEST_PREFIX, canonical_bytes(manifest_core))
    (out / "render_manifest.json").write_bytes(canonical_bytes(manifest))

    cases = {
        "schema": "cps.render-fixture-cases", "schema_version": "1.0.0", "catalog_digest": catalog_digest,
        "render_manifest_digest": manifest["render_manifest_digest"], "cases": [
            {"id": "pitched_domain_2_1", "kind": "pitched", "instrument_id": "pitched_fixture_2_1", "asset_uri": pitched_2["uri"], "start_frame": 0, "end_frame": 16, "project_equave": "2/1", "project_base_millihz": 220_000, "event_ratio": "3/2", "expected_phase_increment_q32": phase_increment(220_000, Fraction(3, 2), 220_000), "release_frames": 4},
            {"id": "pitched_domain_3_1", "kind": "pitched", "instrument_id": "pitched_fixture_3_1", "asset_uri": pitched_3["uri"], "start_frame": 0, "end_frame": 16, "project_equave": "3/1", "project_base_millihz": 330_000, "event_ratio": "4/3", "expected_phase_increment_q32": phase_increment(330_000, Fraction(4, 3), 330_000), "release_frames": 7},
            {"id": "drum_note_36", "kind": "drum", "instrument_id": "drum_fixture_kit", "asset_uri": drum["uri"], "start_frame": 0, "end_frame": 8, "drum_note": 36, "expected_asset_frames": 8},
        ],
    }
    (out / "cases.json").write_bytes(canonical_bytes(cases))

    files = []
    for path in sorted((path for path in out.rglob("*") if path.is_file() and path.name != "fixture_set.json"), key=lambda item: str(item.relative_to(out))):
        raw = path.read_bytes()
        files.append({"path": str(path.relative_to(out)), "byte_length": len(raw), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()})
    fixture_set = {"schema": "cps.render-fixture-set", "schema_version": "1.0.0", "files": files}
    (out / "fixture_set.json").write_bytes(canonical_bytes(fixture_set))


if __name__ == "__main__":
    build()
