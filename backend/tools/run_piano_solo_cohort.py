"""Generate a deterministic multi-seed piano-solo (two-part) calibration cohort.

Mirrors ``run_composition_generation_cohort.py`` but drives the piano-solo
generator (two separate piano tracks on a small 2D lattice).  ``--skip-wav``
produces symbolic / MIDI artifacts only, which keeps a 1000-seed run practical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
GENERATOR = BACKEND / "tools" / "generate_piano_solo.py"
PROFILES = BACKEND / "songprogram_conformance" / "profiles" / "g1_experiments"
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402


def _generate(
    seed: int,
    output: str,
    profile: str,
    realization_profile: str,
    generation_manifest: str,
    skip_wav: bool,
) -> dict:
    directory = Path(output) / f"seed-{seed:04d}"
    receipt_path = directory / "receipt.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (receipt.get("render_status") == "skipped") != skip_wav:
            return {"seed": seed, "status": "failed", "error": "GENERATION_RECEIPT_MODE_MISMATCH"}
        if (receipt.get("profile_hash") != json.loads(Path(profile).read_text())["profile_hash"]
                or receipt.get("realization_profile_hash")
                != json.loads(Path(realization_profile).read_text())["profile_hash"]):
            return {"seed": seed, "status": "failed", "error": "GENERATION_RECEIPT_PROFILE_MISMATCH"}
        return {
            "seed": seed,
            "status": "success",
            "lineage_id": f"piano-solo-seed-{seed}",
            "artifact_directory": str(directory),
            "receipt": receipt,
        }
    command = [
        sys.executable,
        str(GENERATOR),
        "--seed",
        str(seed),
        "--profile",
        profile,
        "--realization-profile",
        realization_profile,
        "--generation-manifest",
        generation_manifest,
        "--output",
        str(directory),
    ]
    if skip_wav:
        command.append("--skip-wav")
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        return {"seed": seed, "status": "failed", "error": completed.stderr.strip()}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        "seed": seed,
        "status": "success",
        "lineage_id": f"piano-solo-seed-{seed}",
        "artifact_directory": str(directory),
        "receipt": receipt,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument(
        "--profile", type=Path, default=PROFILES / "piano_solo.json"
    )
    parser.add_argument(
        "--realization-profile", type=Path, default=PROFILES / "piano_solo_roles.json"
    )
    parser.add_argument(
        "--generation-manifest", type=Path, default=PROFILES / "piano_solo_generation.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-wav", action="store_true")
    arguments = parser.parse_args()
    if arguments.seeds < 1 or arguments.workers < 1:
        parser.error("--seeds and --workers must be positive")
    arguments.output.mkdir(parents=True, exist_ok=True)
    seeds = list(range(arguments.seed_offset, arguments.seed_offset + arguments.seeds))
    with ProcessPoolExecutor(max_workers=arguments.workers) as executor:
        rows = list(
            executor.map(
                _generate,
                seeds,
                [str(arguments.output)] * len(seeds),
                [str(arguments.profile)] * len(seeds),
                [str(arguments.realization_profile)] * len(seeds),
                [str(arguments.generation_manifest)] * len(seeds),
                [arguments.skip_wav] * len(seeds),
            )
        )
    report = {
        "schema": "cps.piano-solo-cohort-report",
        "schema_version": "1.0.0",
        "seed_offset": arguments.seed_offset,
        "seed_count": arguments.seeds,
        "workers": arguments.workers,
        "skip_wav": arguments.skip_wav,
        "success_count": sum(row["status"] == "success" for row in rows),
        "failure_count": sum(row["status"] == "failed" for row in rows),
        "rows": rows,
        "report_hash": "",
    }
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.piano-solo-cohort-report/v1\0"
        + canonical_bytes({key: value for key, value in report.items() if key != "report_hash"})
    ).hexdigest()
    (arguments.output / "cohort_report.json").write_bytes(canonical_bytes(report))
    print(json.dumps({key: report[key] for key in ("success_count", "failure_count", "report_hash")}))
    if report["failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
