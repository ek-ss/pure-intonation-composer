"""Build four self-contained Vital drum presets from the existing PI pack."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "name": "PI 09 Pop Kick",
        "file": "PI 09 Pop Kick.vital",
        "template": "PI 05 Warm Bass.vital",
        "style": "Drums",
        "comments": "Short synthesized pop kick for the PI Vital arrangement pack. Trigger with MIDI note 36.",
        "settings": {
            "env_1_attack": 0.001,
            "env_1_decay": 0.22,
            "env_1_sustain": 0.0,
            "env_1_release": 0.08,
            "osc_1_level": 0.88,
            "osc_1_transpose": -12.0,
            "sample_on": 0.0,
            "filter_1_on": 1.0,
            "filter_1_cutoff": 31.0,
            "filter_1_resonance": 0.02,
            "distortion_on": 1.0,
            "distortion_drive": 0.16,
            "distortion_mix": 0.28,
            "compressor_on": 1.0,
            "compressor_mix": 0.42,
        },
    },
    {
        "name": "PI 10 Pop Snare",
        "file": "PI 10 Pop Snare.vital",
        "template": "PI 05 Warm Bass.vital",
        "style": "Drums",
        "comments": "Noise and oscillator pop snare for the PI Vital arrangement pack. Trigger with MIDI note 38.",
        "settings": {
            "env_1_attack": 0.001,
            "env_1_decay": 0.19,
            "env_1_sustain": 0.0,
            "env_1_release": 0.11,
            "osc_1_level": 0.24,
            "osc_1_transpose": 12.0,
            "sample_on": 1.0,
            "sample_level": 0.72,
            "sample_loop": 0.0,
            "sample_keytrack": 0.0,
            "filter_1_on": 0.0,
            "distortion_on": 1.0,
            "distortion_drive": 0.12,
            "distortion_mix": 0.22,
            "compressor_on": 1.0,
            "compressor_mix": 0.38,
        },
    },
    {
        "name": "PI 11 Pop Closed Hat",
        "file": "PI 11 Pop Closed Hat.vital",
        "template": "PI 05 Warm Bass.vital",
        "style": "Drums",
        "comments": "Compact noise-based closed hat for the PI Vital arrangement pack. Trigger with MIDI note 42.",
        "settings": {
            "env_1_attack": 0.001,
            "env_1_decay": 0.055,
            "env_1_sustain": 0.0,
            "env_1_release": 0.035,
            "osc_1_on": 0.0,
            "sample_on": 1.0,
            "sample_level": 0.56,
            "sample_loop": 0.0,
            "sample_keytrack": 0.0,
            "filter_1_on": 1.0,
            "filter_1_cutoff": 76.0,
            "filter_1_resonance": 0.08,
            "distortion_on": 1.0,
            "distortion_drive": 0.08,
            "distortion_mix": 0.18,
            "compressor_on": 1.0,
            "compressor_mix": 0.22,
        },
    },
    {
        "name": "PI 12 Pop Perc",
        "file": "PI 12 Pop Perc.vital",
        "template": "PI 06 Glass Bell.vital",
        "style": "Drums",
        "comments": "Short tonal pop percussion for the PI Vital arrangement pack. Trigger with MIDI note 39.",
        "settings": {
            "env_1_attack": 0.001,
            "env_1_decay": 0.14,
            "env_1_sustain": 0.0,
            "env_1_release": 0.1,
            "osc_1_level": 0.7,
            "osc_1_transpose": 12.0,
            "sample_on": 0.0,
            "filter_1_on": 1.0,
            "filter_1_cutoff": 53.0,
            "filter_1_resonance": 0.12,
            "delay_on": 0.0,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.08,
            "chorus_on": 0.0,
            "compressor_on": 1.0,
            "compressor_mix": 0.25,
        },
    },
)


def build(source_pack: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for specification in PRESETS:
        template = json.loads((source_pack / specification["template"]).read_text())
        preset = deepcopy(template)
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
                "osc_1_unison_voices": 1.0,
                "osc_1_unison_detune": 0.0,
                "osc_1_stereo_spread": 0.0,
                "osc_2_on": 0.0,
                "osc_3_on": 0.0,
                "delay_on": 0.0,
                "chorus_on": 0.0,
                "polyphony": 6.0,
            }
        )
        settings.update(specification["settings"])
        target = output / specification["file"]
        target.write_text(json.dumps(preset, separators=(",", ":")))
        written.append(target)
    archive = output / "PI Vital Pop Drums.zip"
    with ZipFile(archive, "w") as bundle:
        for target in written:
            info = ZipInfo(target.name, date_time=(2026, 7, 31, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            bundle.writestr(info, target.read_bytes())
    written.append(archive)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_pack", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for target in build(args.source_pack, args.output):
        print(target)


if __name__ == "__main__":
    main()
