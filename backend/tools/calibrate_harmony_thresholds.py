"""Evaluate T/D/S thresholds on independently labeled train/held-out observations.

Input JSON: [{"id": str, "split": "train"|"held_out",
              "label": "tonic"|"dominant"|"subdominant",
              "stability_q": 0..10000, "label_source": "independent_listening"}]
The resulting thresholds are evaluations, not sealed production authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.harmony_dictionary.calibration import calibrate_thresholds  # noqa: E402
from app.harmony_dictionary.storage import canonical_bytes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = calibrate_thresholds(json.loads(args.observations.read_text()))
    args.output.write_bytes(canonical_bytes(result))
    print(f"held-out {result['held_out_accuracy_q']}/10000 ({result['held_out_count']} observations)")


if __name__ == "__main__":
    main()
