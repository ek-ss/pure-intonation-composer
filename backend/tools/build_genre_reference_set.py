"""Build a rights-checked genre ReferenceSetManifest and FeatureRecords."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCHEMAS = BACKEND / "songprogram_conformance" / "schemas"
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.genre_reference_intake import build_genre_reference_set  # noqa: E402


def _object(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _raw_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--extractor-manifest", type=Path, required=True)
    parser.add_argument("--license-policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        intake = _object(arguments.intake)
        expected = {"reference_set_id", "evaluation_epoch_day", "sources"}
        if set(intake) != expected or not isinstance(intake["sources"], list):
            raise ValueError("GENRE_REFERENCE_INTAKE_INVALID")
        sources = []
        for item in intake["sources"]:
            if not isinstance(item, dict) or set(item) != {"partition", "provenance", "wav"}:
                raise ValueError("GENRE_REFERENCE_INTAKE_INVALID")
            sources.append(
                (
                    item["partition"],
                    _object(Path(item["provenance"])),
                    Path(item["wav"]).read_bytes(),
                )
            )
        manifest, records = build_genre_reference_set(
            reference_set_id=intake["reference_set_id"],
            evaluation_epoch_day=intake["evaluation_epoch_day"],
            extractor_manifest=_object(arguments.extractor_manifest),
            license_policy=_object(arguments.license_policy),
            sources=sources,
            license_policy_schema_hash=_raw_hash(SCHEMAS / "genre_license_policy.schema.json"),
            source_provenance_schema_hash=_raw_hash(
                SCHEMAS / "reference_source_provenance.schema.json"
            ),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        parser.error(str(getattr(error, "code", error)))
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "genre_reference_set_manifest.json").write_bytes(canonical_lf(manifest))
    for member, record in zip(manifest["members"], records, strict=True):
        (arguments.output / f"{member['reference_id']}.feature.json").write_bytes(
            canonical_lf(record)
        )
    readiness = {
        "schema": "cps.genre-calibration-readiness",
        "schema_version": "1.0.0",
        "reference_set_manifest_hash": manifest["manifest_hash"],
        "feature_extractor_manifest_hash": manifest["feature_extractor_manifest_hash"],
        "status": "awaiting_external_calibration",
        "missing": [
            "listener_cohort",
            "blinded_assignments",
            "calibration_responses",
            "holdout_evidence",
            "maintainer_promotion_decision",
        ],
    }
    (arguments.output / "calibration_readiness.json").write_bytes(canonical_lf(readiness))
    sys.stdout.buffer.write(canonical_lf(readiness))


if __name__ == "__main__":
    main()
