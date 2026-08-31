from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from songprogram_conformance.build_renderer_catalog_fixtures import (
    CATALOG_PREFIX,
    MANIFEST_PREFIX,
    REPO,
    build,
    canonical_bytes,
    digest,
)


FIXTURES = REPO / "backend" / "songprogram_conformance" / "fixtures" / "render"


def _json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_clean_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "render"
    build(rebuilt)
    assert _tree(rebuilt) == _tree(FIXTURES)


def test_catalog_and_manifest_preimages() -> None:
    catalog_bytes = (FIXTURES / "catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    assert catalog_bytes == canonical_bytes(catalog)
    catalog_digest = digest(CATALOG_PREFIX, catalog_bytes)

    manifest = _json("render_manifest.json")
    stored_manifest_digest = manifest.pop("render_manifest_digest")
    assert manifest["catalog_digest"] == catalog_digest
    assert stored_manifest_digest == digest(MANIFEST_PREFIX, canonical_bytes(manifest))

    renderer_build = manifest["renderer_build"]
    assert renderer_build["source_sha256"] == "sha256:" + hashlib.sha256(
        (REPO / renderer_build["source_artifact"]).read_bytes()
    ).hexdigest()
    assert renderer_build["dependency_lock_sha256"] == "sha256:" + hashlib.sha256(
        (REPO / "backend" / "requirements.txt").read_bytes()
    ).hexdigest()

    paths = {
        "instrument-catalog-render-manifest": REPO / "docs" / "instrument_catalog_render_manifest_contract.md",
        "song-program-renderer-evaluation": REPO / "docs" / "song_program_renderer_evaluation_contract.md",
    }
    for record in manifest["contracts"]:
        path = paths[record["id"]]
        assert record["raw_bytes_sha256"] == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_assets_are_hash_named_canonical_pcm32_wav() -> None:
    catalog = _json("catalog.json")
    assets: list[dict[str, Any]] = []
    for entry in catalog["entries"]:
        if entry["kind"] == "pitched":
            assets.append(entry["asset"])
        else:
            assets.extend(mapping["asset"] for mapping in entry["note_map"])

    assert len(assets) == 3
    for asset in assets:
        expected_hex = str(asset["sha256"]).removeprefix("sha256:")
        path = FIXTURES / "assets" / f"{expected_hex}.wav"
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_hex
        assert asset["uri"] == f"asset://sha256/{expected_hex}"
        assert asset["byte_length"] == len(raw)
        assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE" and raw[12:16] == b"fmt "
        assert struct.unpack_from("<I", raw, 4)[0] == len(raw) - 8
        assert struct.unpack_from("<I", raw, 16)[0] == 16
        audio_format, channels, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", raw, 20)
        assert (audio_format, channels, rate, byte_rate, align, bits) == (1, 1, 48_000, 192_000, 4, 32)
        assert raw[36:40] == b"data"
        data_size = struct.unpack_from("<I", raw, 40)[0]
        assert data_size == len(raw) - 44 == int(asset["frames"]) * 4


def test_fixture_cases_bind_equaves_release_and_drum_note() -> None:
    cases = _json("cases.json")["cases"]
    by_id = {case["id"]: case for case in cases}
    assert by_id["pitched_domain_2_1"]["project_equave"] == "2/1"
    assert by_id["pitched_domain_2_1"]["release_frames"] == 4
    assert by_id["pitched_domain_3_1"]["project_equave"] == "3/1"
    assert by_id["pitched_domain_3_1"]["release_frames"] == 7
    assert by_id["drum_note_36"]["drum_note"] == 36


def test_fixture_set_freezes_every_authoritative_input() -> None:
    fixture_set = _json("fixture_set.json")
    observed = []
    for record in fixture_set["files"]:
        raw = (FIXTURES / record["path"]).read_bytes()
        assert record["byte_length"] == len(raw)
        assert record["sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        observed.append(record["path"])
    assert observed == sorted(observed)
    assert observed == [
        str(path.relative_to(FIXTURES))
        for path in sorted(FIXTURES.rglob("*"))
        if path.is_file() and path.name != "fixture_set.json"
    ]
