from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.renderer import RenderError, RenderResult, render_reference


ROOT = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "render"


def _asset(uri: str) -> bytes:
    return (ROOT / "assets" / f"{uri.rsplit('/', 1)[1]}.wav").read_bytes()


def _project(instrument: str, *, kind: str = "note", ratio: str = "3/2") -> dict[str, Any]:
    digest = "sha256:" + hashlib.sha256(
        b"cps.instrument-catalog/v1\0" + (ROOT / "catalog.json").read_bytes()
    ).hexdigest()
    drum = kind == "drum"
    return {
        "compiler": {"instrument_catalog_digest": digest},
        "lattice": {"base_frequency_millihz": 220_000},
        "clock": {"tempo_milli_bpm": 120_000, "ticks_per_beat": 480},
        "render_settings": {"sample_rate": 48_000, "channel_layout": "stereo"},
        "tracks": [{"id": "a", "role": "drums" if drum else "harmony", "instrument_id": instrument, "maximum_polyphony": 8}],
        "mix": {"a": {"gain_q": 10_000, "pan_q": 0}},
        "events": [{"id": "ev_a", "kind": kind, "track_id": "a", "start_tick": 0, "duration_ticks": 1, "velocity": 127, "ratio": None if drum else ratio, "drum_note": 36 if drum else None}],
    }


def _render(project: dict[str, Any]) -> RenderResult:
    return render_reference(project, (ROOT / "catalog.json").read_bytes(), _asset, render_manifest_digest="sha256:" + "0" * 64, project_artifact_hash="sha256:" + "1" * 64)


def _render_with_catalog(project: dict[str, Any], catalog: dict[str, Any]) -> RenderResult:
    catalog_bytes = (json.dumps(catalog, sort_keys=True, separators=(",", ":")) + "\n").encode()
    project["compiler"]["instrument_catalog_digest"] = "sha256:" + hashlib.sha256(  # type: ignore[index]
        b"cps.instrument-catalog/v1\0" + catalog_bytes
    ).hexdigest()
    return render_reference(
        project,
        catalog_bytes,
        _asset,
        render_manifest_digest="sha256:" + "0" * 64,
        project_artifact_hash="sha256:" + "1" * 64,
    )


def test_pitched_reference_render_is_stable_and_reports_pcm() -> None:
    result = _render(_project("pitched_fixture_2_1"))
    assert result.wav[:12] == b"RIFF" + (len(result.wav) - 8).to_bytes(4, "little") + b"WAVE"
    assert result.report["frame_count"] == 310
    assert result.report["pcm_hash"] == "sha256:" + hashlib.sha256(result.wav[44:]).hexdigest()
    assert result.report["track_hashes"][0]["pcm_byte_length"] == 310 * 8
    assert _render(_project("pitched_fixture_2_1")) == result


def test_drum_ignores_duration_and_uses_mapped_asset() -> None:
    result = _render(_project("drum_fixture_kit", kind="drum"))
    assert result.report["frame_count"] == 264
    assert any(result.wav[44:])


def test_drum_applies_track_gain_after_sample_and_kit_gain() -> None:
    project = _project("drum_fixture_kit", kind="drum")
    project["mix"]["a"]["gain_q"] = 0  # type: ignore[index]
    result = _render(project)
    assert not any(result.wav[44:])
    assert result.report["track_hashes"][0]["peak_absolute_sample"] == 0


def test_polyphony_is_checked_before_rendering() -> None:
    project = _project("pitched_fixture_2_1")
    project["tracks"][0]["maximum_polyphony"] = 1  # type: ignore[index]
    project["events"].append(dict(project["events"][0], id="ev_b"))
    with pytest.raises(RenderError, match="RENDER_POLYPHONY_EXCEEDED"):
        _render(project)


def test_non_looping_asset_does_not_extend_silent_release() -> None:
    project = _project("pitched_fixture_2_1")
    project["events"][0]["duration_ticks"] = 4800  # type: ignore[index]
    catalog = json.loads((ROOT / "catalog.json").read_text())
    entry = next(item for item in catalog["entries"] if item["instrument_id"] == "pitched_fixture_2_1")
    entry["loop"] = {"mode": "none", "start_frame": 0, "end_frame": 0}
    result = _render_with_catalog(project, catalog)
    assert result.report["frame_count"] == 262


def test_unmapped_drum_is_a_typed_failure() -> None:
    project = _project("drum_fixture_kit", kind="drum")
    project["events"][0]["drum_note"] = 37  # type: ignore[index]
    with pytest.raises(RenderError, match="DRUM_NOTE_UNMAPPED"):
        _render(project)
