"""Build the Vital instruments used by the fractional-ratio J-pop composer."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "name": "PI 13 Fifth Keys",
        "file": "PI 13 Fifth Keys.vital",
        "template": "PI 02 Dream Chord.vital",
        "style": "Keys",
        "comments": "Clear J-pop A-melody keys optimized for pure-fifth stacks and exact external tuning.",
        "settings": {
            "env_1_attack": 0.025,
            "env_1_decay": 0.42,
            "env_1_sustain": 0.58,
            "env_1_release": 0.38,
            "filter_1_cutoff": 43.0,
            "filter_1_resonance": 0.025,
            "chorus_on": 1.0,
            "chorus_dry_wet": 0.12,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.13,
        },
    },
    {
        "name": "PI 14 Minor Third Pluck",
        "file": "PI 14 Minor Third Pluck.vital",
        "template": "PI 04 Gentle Pluck.vital",
        "style": "Pluck",
        "comments": "Focused B-melody pluck for pure 6/5 minor-third harmony and exact external tuning.",
        "settings": {
            "env_1_attack": 0.008,
            "env_1_decay": 0.28,
            "env_1_sustain": 0.1,
            "env_1_release": 0.3,
            "filter_1_cutoff": 39.0,
            "filter_1_resonance": 0.04,
            "chorus_on": 0.0,
            "delay_on": 1.0,
            "delay_dry_wet": 0.09,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.11,
        },
    },
    {
        "name": "PI 15 13-Limit Chorus Lead",
        "file": "PI 15 13-Limit Chorus Lead.vital",
        "template": "PI 01 Clear Supersaw.vital",
        "style": "Lead",
        "comments": "Wide but tuning-clear chorus lead for 3-by-13 lattice-shift harmony.",
        "settings": {
            "env_1_attack": 0.018,
            "env_1_decay": 0.5,
            "env_1_sustain": 0.72,
            "env_1_release": 0.48,
            "osc_1_unison_voices": 2.0,
            "osc_1_unison_detune": 0.035,
            "osc_1_stereo_spread": 0.38,
            "filter_1_cutoff": 52.0,
            "filter_1_resonance": 0.025,
            "compressor_on": 1.0,
            "compressor_mix": 0.3,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.16,
        },
    },
    {
        "name": "PI 16 Vocal Guide",
        "file": "PI 16 Vocal Guide.vital",
        "template": "PI 03 Air Pad.vital",
        "style": "Lead",
        "comments": "Monophonic vowel-like guide voice for the generated J-pop vocal melody; replace with a singer for production.",
        "settings": {
            "env_1_attack": 0.035,
            "env_1_decay": 0.3,
            "env_1_sustain": 0.8,
            "env_1_release": 0.24,
            "osc_1_level": 0.72,
            "osc_1_unison_voices": 1.0,
            "osc_1_unison_detune": 0.0,
            "osc_1_stereo_spread": 0.0,
            "filter_1_on": 1.0,
            "filter_1_cutoff": 47.0,
            "filter_1_resonance": 0.18,
            "chorus_on": 0.0,
            "delay_on": 1.0,
            "delay_dry_wet": 0.08,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.1,
            "polyphony": 1.0,
        },
    },
)


def build(source_pack: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for specification in PRESETS:
        preset = deepcopy(
            json.loads((source_pack / specification["template"]).read_text())
        )
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
        target = output / specification["file"]
        target.write_text(json.dumps(preset, separators=(",", ":")))
        written.append(target)
    archive = output / "PI JPop Vital Instruments.zip"
    with ZipFile(archive, "w") as bundle:
        for target in written:
            info = ZipInfo(target.name, date_time=(2026, 8, 1, 0, 0, 0))
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
