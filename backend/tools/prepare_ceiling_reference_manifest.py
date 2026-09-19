"""Select a fixed G2 ceiling cohort from rights-cleared local-authority clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-directory", type=Path, required=True)
    parser.add_argument("--partition", default="calibration")
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    transfer_path = arguments.authority_directory / "transfer_manifest.json"
    transfer = json.loads(transfer_path.read_text(encoding="utf-8"))
    selected = sorted(
        (row for row in transfer["entries"] if row["partition"] == arguments.partition),
        key=lambda row: row["id"],
    )[: arguments.count]
    if len(selected) != arguments.count:
        parser.error("authority does not contain enough clips in the requested partition")
    entries = [
        {
            "candidate_id": f"ceiling-{row['id']}",
            "lineage_id": f"external-authority-{row['id']}",
            "audio_path": str(arguments.authority_directory / row["clip_relative_path"]),
            "audio_hash": row["clip_wav_sha256"],
            "source_receipt_hash": row["receipt_sha256"],
        }
        for row in selected
    ]
    manifest = {
        "schema": "cps.composition-ceiling-reference-manifest",
        "schema_version": "1.0.0",
        "source_set_id": transfer["set_id"],
        "partition": arguments.partition,
        "usage": "g2_perceptual_ceiling_only",
        "g1_symbolic_features_available": False,
        "entries": entries,
        "manifest_hash": "",
    }
    manifest["manifest_hash"] = "sha256:" + hashlib.sha256(
        b"cps.composition-ceiling-reference-manifest/v1\0"
        + canonical_bytes({key: value for key, value in manifest.items() if key != "manifest_hash"})
    ).hexdigest()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(canonical_bytes(manifest))
    print(json.dumps({"count": len(entries), "manifest_hash": manifest["manifest_hash"]}))


if __name__ == "__main__":
    main()
