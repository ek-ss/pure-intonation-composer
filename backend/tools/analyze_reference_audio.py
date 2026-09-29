"""Analyze a reference audio file into a CPS generation profile proposal.

Implements the CLI from docs/audio_reference_to_generation_profile_spec.md:

    analyze_reference_audio --input <file> --target <manifest-id>
        --output <directory> [--seed <u64>]

It decodes the input to canonical PCM, measures quality / time-axis / harmony /
acoustics observations, translates them into a typed profile patch plus a
capability report, and records a reproducibility receipt.  The four artifacts
(analysis.json, profile_patch.json, capability_report.json, receipt.json) are
written to --output as canonical JSON.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.audio_reference import (  # noqa: E402
    DecodeError,
    InputPolicyError,
    PipelineError,
    TargetError,
    analyze_reference_audio,
    default_policy,
    require_executable,
    resolve_target,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="reference audio file (WAV/FLAC/MP3/AAC)")
    parser.add_argument("--target", type=str, required=True, help="executable target manifest id")
    parser.add_argument("--output", type=Path, required=True, help="output directory for the four artifacts")
    parser.add_argument("--seed", type=int, default=0, help="uint64 seed (default 0)")
    arguments = parser.parse_args()

    if not 0 <= arguments.seed < 2**64:
        parser.error("--seed must fit uint64")
    if not arguments.input.is_file():
        parser.error(f"--input does not exist or is not a file: {arguments.input}")

    try:
        target = resolve_target(arguments.target)
        require_executable(target)
        summary = analyze_reference_audio(
            arguments.input,
            arguments.target,
            arguments.output,
            seed=arguments.seed,
            policy=default_policy(),
        )
    except (TargetError, InputPolicyError, DecodeError, PipelineError, OSError) as error:
        parser.error(str(error))

    print(f"target={summary.get('target_manifest_id', arguments.target)}")
    for key in ("analysis_path", "patch_path", "report_path", "receipt_path"):
        print(f"{key}={summary[key]}")
    print(f"pcm_hash={summary['pcm_hash']}")
    print(f"observation_count={summary['observation_count']}")
    print(f"validation_status={summary['validation_status']}")


if __name__ == "__main__":
    main()
