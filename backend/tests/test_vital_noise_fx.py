from __future__ import annotations

import json
from pathlib import Path

from tools.build_vital_noise_fx import PRESETS, build
from tools.build_vital_preview_bundle import _reaper_script


def test_noise_fx_presets_use_filtered_white_noise(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app" / "static" / "vital_presets"
    (tmp_path / "PI 11 Pop Closed Hat.vital").write_bytes(
        (source / "PI 11 Pop Closed Hat.vital").read_bytes()
    )
    outputs = build(tmp_path)
    assert len(outputs) == len(PRESETS)
    for output in outputs:
        preset = json.loads(output.read_text())
        settings = preset["settings"]
        assert settings["sample"]["name"] == "White Noise"
        assert settings["sample_on"] == 1.0
        assert settings["sample_destination"] == 3.0
        assert settings["filter_1_on"] == 1.0
        assert settings["mpe_enabled"] == 1.0
        assert settings["pitch_bend_range"] == 2.0
        assert settings["osc_1_on"] == settings["osc_2_on"] == settings["osc_3_on"] == 0.0


def test_reaper_bootstrap_loads_vital_native_state_chunk(tmp_path: Path) -> None:
    script = _reaper_script(
        [
            {
                "stem": "melody",
                "midi_path": "midi/melody.mid",
                "preset_path": "backend/app/static/vital_presets/PI 15 13-Limit Chorus Lead.vital",
                "preset_installed": True,
            }
        ],
        tmp_path,
    )
    assert 'TrackFX_GetNamedConfigParm(track, fx, "vst_chunk")' in script
    assert 'TrackFX_SetNamedConfigParm(track, fx, "vst_chunk"' in script
    assert "TrackFX_SetPreset(" not in script
    assert "reaper.Main_OnCommand(40859, 0)" in script
