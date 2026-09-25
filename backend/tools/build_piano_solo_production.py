"""Build the piano-solo production manifest and instrument catalog.

The broad-prior production manifest must carry entries for every role in
``ROLES`` (the validator requires the full role order), but a piano-solo song
only activates ``harmony`` and ``melody``.  Both of those are pointed at the
shared piano timbre so the two tracks sound like one instrument.  The drum /
bass / texture entries are retained for schema shape but never selected.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.fallback import (  # noqa: E402
    FallbackError, _validate_v11_production_manifest,
)

PROFILES = BACKEND / "songprogram_conformance/profiles"
DESTINATION = PROFILES / "g1_experiments"
FIXTURES = (
    BACKEND / "songprogram_conformance" / "fixtures" / "search_loop_13"
    / "shared_authority" / "artifacts"
)

# Two catalog entries share the piano timbre but carry distinct instrument IDs
# so the production can bind one to each role (the validator requires the
# entry's ``role`` to match the track's role).
PIANO_INSTRUMENTS = {
    "harmony": "piano_solo_harmony",
    "melody": "piano_solo_melody",
}


def build_production_manifest(base: dict) -> dict:
    result = copy.deepcopy(base)
    for role, instrument_id in PIANO_INSTRUMENTS.items():
        result["instrument_entries_by_role"][role] = [
            {"value": instrument_id, "weight": 1},
        ]
    _validate_v11_production_manifest(result)
    return result


def build_catalog(base: dict, maximum_polyphony: int, frequency_range: list[int]) -> dict:
    """Replace the pitched entries with the two piano entries.

    The drum kit entry is retained (the production manifest still references a
    drum role for schema shape) but no drum track is realized in a piano song.
    """
    result = copy.deepcopy(base)
    piano_entries = []
    for role, instrument_id in PIANO_INSTRUMENTS.items():
        # Reuse the shape of an existing pitched entry, re-pointed at the piano.
        template = next(
            entry for entry in base["entries"] if entry.get("role") == role
        )
        entry = copy.deepcopy(template)
        entry["instrument_id"] = instrument_id
        entry["role"] = role
        entry["kind"] = "pitched"
        entry["maximum_polyphony"] = maximum_polyphony
        entry["allowed_frequency_millihz"] = list(frequency_range)
        piano_entries.append(entry)
    drum_entries = [
        entry for entry in base["entries"] if entry.get("kind") == "drum_kit"
    ]
    result["entries"] = sorted(
        [*piano_entries, *drum_entries],
        key=lambda entry: entry["instrument_id"].encode(),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    base_manifest = json.loads(
        (FIXTURES / "broad_prior_production_manifest.json").read_text()
    )
    base_catalog = json.loads((FIXTURES / "instrument_catalog.json").read_text())
    manifest = build_production_manifest(base_manifest)
    catalog = build_catalog(
        base_catalog, maximum_polyphony=64, frequency_range=[20000, 4000000]
    )
    if not args.check:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("piano_solo_production", manifest),
        ("piano_solo_catalog", catalog),
    ):
        path = DESTINATION / f"{name}.json"
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
        if args.check:
            if path.read_bytes() != data:
                parser.error(f"file differs from builder: {path}")
        else:
            path.write_bytes(data)
        print(f"{name}: written")


if __name__ == "__main__":
    main()
