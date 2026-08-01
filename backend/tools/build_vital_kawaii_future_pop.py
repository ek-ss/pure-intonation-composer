"""Build Vital presets for the Kawaii Fractional Future Pop composer."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "name": "PI 17 Candy Pluck",
        "file": "PI 17 Candy Pluck.vital",
        "template": "PI 14 Minor Third Pluck.vital",
        "style": "Pluck",
        "comments": "Bright kawaii pop pluck with a short exact-tuning-safe transient.",
        "settings": {
            "env_1_attack": 0.004,
            "env_1_decay": 0.2,
            "env_1_sustain": 0.06,
            "env_1_release": 0.24,
            "filter_1_cutoff": 55.0,
            "delay_on": 1.0,
            "delay_dry_wet": 0.13,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.1,
        },
    },
    {
        "name": "PI 18 Future Chord Stack",
        "file": "PI 18 Future Chord Stack.vital",
        "template": "PI 15 13-Limit Chorus Lead.vital",
        "style": "Synth",
        "comments": "Compact future-bass chord stack for exact-ratio MPE voicings and external sidechain.",
        "settings": {
            "env_1_attack": 0.012,
            "env_1_decay": 0.36,
            "env_1_sustain": 0.7,
            "env_1_release": 0.3,
            "osc_1_unison_voices": 3.0,
            "osc_1_unison_detune": 0.026,
            "osc_1_stereo_spread": 0.46,
            "filter_1_cutoff": 57.0,
            "compressor_on": 1.0,
            "compressor_mix": 0.4,
            "reverb_dry_wet": 0.12,
        },
    },
    {
        "name": "PI 19 Fractional Vocal Guide",
        "file": "PI 19 Fractional Vocal Guide.vital",
        "template": "PI 16 Vocal Guide.vital",
        "style": "Lead",
        "comments": "Mono vowel-like guide for exact-ratio kawaii hooks and short vocal chops.",
        "settings": {
            "env_1_attack": 0.018,
            "env_1_decay": 0.24,
            "env_1_sustain": 0.76,
            "env_1_release": 0.18,
            "filter_1_cutoff": 51.0,
            "filter_1_resonance": 0.21,
            "delay_dry_wet": 0.1,
            "reverb_dry_wet": 0.14,
            "polyphony": 1.0,
        },
    },
    {
        "name": "PI 20 Minimal Pulse",
        "file": "PI 20 Minimal Pulse.vital",
        "template": "PI 13 Fifth Keys.vital",
        "style": "Sequence",
        "comments": "Dry, stable pulse for repeated exact-ratio cells and phase-shift patterns.",
        "settings": {
            "env_1_attack": 0.003,
            "env_1_decay": 0.14,
            "env_1_sustain": 0.02,
            "env_1_release": 0.12,
            "osc_1_unison_voices": 1.0,
            "osc_1_unison_detune": 0.0,
            "osc_1_stereo_spread": 0.0,
            "filter_1_cutoff": 45.0,
            "chorus_on": 0.0,
            "delay_on": 0.0,
            "reverb_dry_wet": 0.04,
        },
    },
    {
        "name": "PI 21 Sparkle Bell",
        "file": "PI 21 Sparkle Bell.vital",
        "template": "PI 14 Minor Third Pluck.vital",
        "style": "Bell",
        "comments": "High-register sparkle accent for 7-limit and 13-limit kawaii color tones.",
        "settings": {
            "env_1_attack": 0.002,
            "env_1_decay": 0.55,
            "env_1_sustain": 0.0,
            "env_1_release": 0.72,
            "filter_1_cutoff": 63.0,
            "filter_1_resonance": 0.08,
            "delay_on": 1.0,
            "delay_dry_wet": 0.16,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.2,
        },
    },
)


def build(preset_directory: Path) -> list[Path]:
    written: list[Path] = []
    for specification in PRESETS:
        preset = deepcopy(json.loads((preset_directory / specification["template"]).read_text()))
        preset.update(
            author="Pure Intonation Composer",
            comments=specification["comments"],
            preset_name=specification["name"],
            preset_style=specification["style"],
        )
        settings = preset["settings"]
        for index in range(1, 65):
            settings[f"modulation_{index}_amount"] = 0.0
        settings["modulations"] = [
            {"destination": "", "source": ""} for _ in settings["modulations"]
        ]
        settings.update(
            {
                "osc_2_on": 0.0,
                "osc_3_on": 0.0,
                "sample_on": 0.0,
                "osc_1_random_phase": 0.0,
            }
        )
        settings.update(specification["settings"])
        target = preset_directory / specification["file"]
        target.write_text(json.dumps(preset, separators=(",", ":")))
        written.append(target)
    archive = preset_directory / "PI Kawaii Future Pop Vital Pack.zip"
    with ZipFile(archive, "w") as bundle:
        for target in written:
            info = ZipInfo(target.name, date_time=(2026, 8, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            bundle.writestr(info, target.read_bytes())
    written.append(archive)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset_directory", type=Path)
    args = parser.parse_args()
    for target in build(args.preset_directory):
        print(target)


if __name__ == "__main__":
    main()
