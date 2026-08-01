"""Build a tuning-clear, piano-like Vital preset for exact-ratio scores."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PRESET_NAME = "PI 22 Fractional Piano"
PRESET_FILE = f"{PRESET_NAME}.vital"
ARCHIVE_FILE = "PI Fractional Piano.zip"


def build(preset_directory: Path) -> list[Path]:
    """Derive a compact synthetic piano from the tuning-safe PI13 keys."""
    source = preset_directory / "PI 13 Fifth Keys.vital"
    preset = deepcopy(json.loads(source.read_text()))
    preset.update(
        author="Pure Intonation Composer",
        comments=(
            "Velocity-responsive synthetic piano for exact-ratio scale runs, "
            "motifs, arpeggios, and compact chords. Use one MIDI channel per "
            "simultaneous bend when exporting MPE."
        ),
        macro1="Tone",
        macro2="Hammer",
        macro3="Room",
        macro4="Width",
        preset_name=PRESET_NAME,
        preset_style="Keys",
    )
    settings = preset["settings"]
    for index in range(1, 65):
        settings[f"modulation_{index}_amount"] = 0.0
    settings["modulations"] = [
        {"destination": "", "source": ""} for _ in settings["modulations"]
    ]
    settings.update(
        {
            "env_1_attack": 0.002,
            "env_1_decay": 0.72,
            "env_1_sustain": 0.16,
            "env_1_release": 0.82,
            "osc_1_level": 0.62,
            "osc_1_unison_voices": 1.0,
            "osc_1_unison_detune": 0.0,
            "osc_1_stereo_spread": 0.08,
            "osc_1_random_phase": 0.0,
            "osc_2_on": 1.0,
            "osc_2_level": 0.13,
            "osc_2_transpose": 12.0,
            "osc_2_tune": 0.0,
            "osc_2_unison_voices": 1.0,
            "osc_2_unison_detune": 0.0,
            "osc_2_stereo_spread": 0.0,
            "osc_2_random_phase": 0.0,
            "osc_3_on": 0.0,
            "sample_on": 0.0,
            "filter_1_on": 1.0,
            "filter_1_cutoff": 49.0,
            "filter_1_resonance": 0.035,
            "filter_1_keytrack": 0.58,
            "filter_1_drive": 1.2,
            "velocity_track": 0.48,
            "chorus_on": 0.0,
            "delay_on": 0.0,
            "reverb_on": 1.0,
            "reverb_dry_wet": 0.085,
            "compressor_on": 1.0,
            "compressor_mix": 0.24,
            "distortion_on": 0.0,
            "polyphony": 12.0,
        }
    )
    target = preset_directory / PRESET_FILE
    target.write_text(json.dumps(preset, separators=(",", ":")))

    archive = preset_directory / ARCHIVE_FILE
    with ZipFile(archive, "w") as bundle:
        info = ZipInfo(target.name, date_time=(2026, 8, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        bundle.writestr(info, target.read_bytes())
    return [target, archive]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset_directory", type=Path)
    args = parser.parse_args()
    for target in build(args.preset_directory):
        print(target)


if __name__ == "__main__":
    main()
