"""Extract one fixed-snapshot GenreFeatureRecord from PCM32 WAV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.audio_features import extract_genre_feature_record  # noqa: E402
from app.songprogram.connected import canonical_lf  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        manifest = json.loads(arguments.manifest.read_text())
        record = extract_genre_feature_record(arguments.wav.read_bytes(), manifest)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(getattr(error, "code", error)))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_lf(record))
    sys.stdout.buffer.write(canonical_lf(record))


if __name__ == "__main__":
    main()
