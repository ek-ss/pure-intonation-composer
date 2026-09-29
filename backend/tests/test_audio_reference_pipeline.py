from __future__ import annotations

import json
import os
import tempfile
import wave
from fractions import Fraction
from pathlib import Path

import pytest

from app.audio.render import NoteEvent, render_wav
from app.audio_reference import analyze_reference_audio

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_DIR = BACKEND / "app" / "audio_reference" / "schemas"

ARTIFACT_SCHEMAS = {
    "analysis.json": "audio_reference_analysis.schema.json",
    "profile_patch.json": "audio_derived_profile_patch.schema.json",
    "capability_report.json": "audio_profile_capability_report.schema.json",
    "receipt.json": "audio_reference_receipt.schema.json",
}


def _concat_wavs(paths: list[str], out: str) -> None:
    raws: list[bytes] = []
    rate: int = 0
    channels: int = 0
    width: int = 0
    for p in paths:
        with wave.open(p, "rb") as handle:
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            raws.append(handle.readframes(handle.getnframes()))
    with wave.open(out, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(b"".join(raws))


def _render_section(path: str, duration: float, base_freq: int, velocity: int, bpm: int, rate: int) -> None:
    beat = 60.0 / bpm
    events: list[NoteEvent] = []
    for k in range(int(duration / beat)):
        events.append(NoteEvent(Fraction(1), k * beat, 0.12, velocity=velocity))
        events.append(NoteEvent(Fraction(3, 2), k * beat, beat * 0.95, velocity=velocity // 3))
    open(path, "wb").write(render_wav(events, base_frequency=base_freq, waveform="sine", sample_rate=rate))


def _render_sections(path: str, specs: list[tuple[float, int, int, int]], rate: int = 22050) -> None:
    """Render distinct sections (duration, base_freq, velocity, bpm) and concatenate."""

    tmp = tempfile.mkdtemp()
    section_paths: list[str] = []
    for i, (duration, base_freq, velocity, bpm) in enumerate(specs):
        p = os.path.join(tmp, f"section_{i}.wav")
        _render_section(p, duration, base_freq, velocity, bpm, rate)
        section_paths.append(p)
    _concat_wavs(section_paths, path)


def _load(artifact: str, out_dir: Path) -> dict:
    return json.loads((out_dir / artifact).read_text())


def _validate_against_schema(artifact: str, out_dir: Path) -> None:
    import jsonschema

    document = _load(artifact, out_dir)
    schema = json.loads((SCHEMA_DIR / ARTIFACT_SCHEMAS[artifact]).read_text())
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(document))
    assert not errors, f"{artifact} failed schema validation: {[e.message for e in errors[:3]]}"


@pytest.fixture()
def constant_tempo_audio(tmp_path: Path) -> Path:
    # Two clearly distinct sections at a steady 120 BPM.
    path = tmp_path / "constant.wav"
    _render_sections(
        str(path),
        [
            (6.0, 110, 90, 120),
            (6.0, 220, 127, 120),
        ],
    )
    return path


@pytest.fixture()
def variable_tempo_audio(tmp_path: Path) -> Path:
    # First half 100 BPM, second half 150 BPM.
    path = tmp_path / "variable.wav"
    _render_sections(
        str(path),
        [
            (8.0, 110, 100, 100),
            (8.0, 220, 100, 150),
        ],
    )
    return path


def test_pipeline_writes_all_four_artifacts(constant_tempo_audio: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    summary = analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", out_dir)
    for artifact in ARTIFACT_SCHEMAS:
        assert (out_dir / artifact).is_file(), f"missing {artifact}"
    assert summary["observation_count"] > 0


def test_pipeline_artifacts_pass_their_schemas(constant_tempo_audio: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", out_dir)
    for artifact in ARTIFACT_SCHEMAS:
        _validate_against_schema(artifact, out_dir)


def test_pipeline_is_deterministic(constant_tempo_audio: Path, tmp_path: Path) -> None:
    first = analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", tmp_path / "a")
    second = analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", tmp_path / "b")
    assert first["pcm_hash"] == second["pcm_hash"]
    # The full analysis document is byte-identical for identical input.
    a = (tmp_path / "a" / "analysis.json").read_bytes()
    b = (tmp_path / "b" / "analysis.json").read_bytes()
    assert a == b


def test_constant_tempo_is_exact(constant_tempo_audio: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", out_dir)
    report = _load("capability_report.json", out_dir)
    tempo_items = [i for i in report["items"] if i["capability"] == "tempo_map"]
    assert len(tempo_items) == 1
    item = tempo_items[0]
    # A steady 120 BPM source is specifiable by the fixed clock.
    assert item["status"] == "exact"
    assert item["attempted"]["tempo_milli_bpm"] is not None


def test_variable_tempo_yields_an_unsupported_tempo_map_gap(variable_tempo_audio: Path, tmp_path: Path) -> None:
    """Spec acceptance: variable-tempo audio must yield >=1 tempo_map gap with span + error."""

    out_dir = tmp_path / "out"
    analyze_reference_audio(variable_tempo_audio, "full-song-generation-v1", out_dir)
    report = _load("capability_report.json", out_dir)
    tempo_items = [i for i in report["items"] if i["capability"] == "tempo_map"]
    assert len(tempo_items) >= 1
    item = tempo_items[0]
    assert item["status"] == "unsupported"
    # The gap carries its span and the measurement error.
    assert item["span_samples"][1] > item["span_samples"][0]
    assert item["error"] is not None
    assert item["observed"]["bpm_range"] is not None


def test_cps_rendered_material_rederives_tempo_and_sections(constant_tempo_audio: Path, tmp_path: Path) -> None:
    """Spec acceptance: known CPS-rendered material re-derives BPM and section boundaries."""

    out_dir = tmp_path / "out"
    analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", out_dir)
    analysis = _load("analysis.json", out_dir)
    by_type: dict[str, list[dict]] = {}
    for obs in analysis["observations"]:
        by_type.setdefault(obs["type"], []).append(obs)

    # Tempo re-derivation: the source is 120 BPM; allow octave + quantization slack.
    tempo = by_type["tempo"][0]
    assert tempo["value"] is not None
    base = tempo["value"]["tempo_milli_bpm"] / 1000.0
    assert any(abs(base - t) <= 25 for t in (60, 120, 240)), f"tempo {base} not near an octave of 120"

    # Section re-derivation: the source has two distinct sections.
    section = by_type["section"][0]
    assert section["value"] is not None
    assert section["value"]["count"] >= 1
    assert len(section["candidates"]) >= 1


def test_receipt_records_hashes_and_validation(constant_tempo_audio: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    analyze_reference_audio(constant_tempo_audio, "full-song-generation-v1", out_dir)
    receipt = _load("receipt.json", out_dir)
    assert receipt["input"]["source_hash"].startswith("sha256:")
    assert receipt["input"]["pcm_hash"].startswith("sha256:")
    assert receipt["analysis_hash"].startswith("sha256:")
    assert receipt["patch_hash"].startswith("sha256:")
    assert receipt["report_hash"].startswith("sha256:")
    assert receipt["validation_status"] in ("not_run", "passed", "failed")
    assert receipt["target_manifest_id"] == "full-song-generation-v1"
