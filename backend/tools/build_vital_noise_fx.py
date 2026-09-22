"""Build filtered-white-noise Vital presets for drums and transition FX."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "name": "PI 23 Noise Clap", "style": "Drums",
        "comments": "Short filtered-white-noise clap layer for pop and future-bass backbeats.",
        "settings": {"env_1_attack": 0.001, "env_1_decay": 0.16, "env_1_sustain": 0.0,
                     "env_1_release": 0.12, "filter_1_cutoff": 67.0,
                     "filter_1_resonance": 0.12, "filter_1_drive": 1.4,
                     "distortion_on": 1.0, "distortion_drive": 1.8,
                     "distortion_mix": 0.16, "reverb_on": 1.0,
                     "reverb_dry_wet": 0.08},
    },
    {
        "name": "PI 24 Noise Open Hat", "style": "Drums",
        "comments": "Longer filtered-white-noise hat with an MPE-safe one-shot envelope.",
        "settings": {"env_1_attack": 0.001, "env_1_decay": 0.32, "env_1_sustain": 0.0,
                     "env_1_release": 0.22, "filter_1_cutoff": 79.0,
                     "filter_1_resonance": 0.07, "reverb_on": 1.0,
                     "reverb_dry_wet": 0.045},
    },
    {
        "name": "PI 25 Noise Impact", "style": "Effects",
        "comments": "Filtered-white-noise impact body for drop and final-section boundaries.",
        "settings": {"env_1_attack": 0.001, "env_1_decay": 0.52, "env_1_sustain": 0.0,
                     "env_1_release": 0.75, "filter_1_cutoff": 48.0,
                     "filter_1_resonance": 0.18, "filter_1_drive": 2.0,
                     "compressor_on": 1.0, "compressor_mix": 0.42,
                     "reverb_on": 1.0, "reverb_dry_wet": 0.28},
    },
    {
        "name": "PI 26 Noise Riser", "style": "Effects",
        "comments": "Sustained filtered-white-noise source for host-automated build risers.",
        "settings": {"env_1_attack": 0.08, "env_1_decay": 1.0, "env_1_sustain": 1.0,
                     "env_1_release": 0.5, "filter_1_cutoff": 43.0,
                     "filter_1_resonance": 0.2, "filter_1_drive": 0.7,
                     "reverb_on": 1.0, "reverb_dry_wet": 0.22},
    },
    {
        "name": "PI 27 Noise Transition Tail", "style": "Effects",
        "comments": "Long filtered-white-noise release and reverb tail for outro transitions.",
        "settings": {"env_1_attack": 0.006, "env_1_decay": 2.4, "env_1_sustain": 0.0,
                     "env_1_release": 3.5, "filter_1_cutoff": 58.0,
                     "filter_1_resonance": 0.09, "reverb_on": 1.0,
                     "reverb_dry_wet": 0.58},
    },
)


def build(preset_directory: Path) -> list[Path]:
    source = json.loads((preset_directory / "PI 11 Pop Closed Hat.vital").read_text())
    written: list[Path] = []
    for specification in PRESETS:
        preset = deepcopy(source)
        preset.update(
            author="Pure Intonation Composer",
            comments=specification["comments"],
            preset_name=specification["name"],
            preset_style=specification["style"],
        )
        settings = preset["settings"]
        settings.update(
            {
                "mpe_enabled": 1.0,
                "pitch_bend_range": 2.0,
                "osc_1_on": 0.0,
                "osc_2_on": 0.0,
                "osc_3_on": 0.0,
                "sample_on": 1.0,
                "sample_destination": 3.0,
                "sample_keytrack": 0.0,
                "sample_random_phase": 0.0,
                "filter_1_on": 1.0,
                "filter_1_mix": 1.0,
                "polyphony": 16.0,
            }
        )
        settings.update(specification["settings"])
        target = preset_directory / f"{specification['name']}.vital"
        target.write_text(json.dumps(preset, separators=(",", ":")))
        written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset_directory", type=Path)
    arguments = parser.parse_args()
    for target in build(arguments.preset_directory):
        print(target)


if __name__ == "__main__":
    main()
