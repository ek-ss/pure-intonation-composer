"""End-to-end orchestration: audio file -> analysis + patch + report + receipt.

Wires the stages in spec section 3 order: decode, quality, time-axis, harmony,
acoustics, then translation, capability, and receipt.  The shared STFT is
computed once and reused by the onset and chroma stages.  All four artifacts
are written as canonical JSON (integer-only) into the output directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import acoustics, capability, decode, dsp, harmony, quality, time_axis, translation
from .analysis import build_analysis
from .canonical import canonical_bytes
from .input_policy import InputPolicy, default_policy
from .observations import MODEL_ID, MODEL_VERSION
from .receipt import build_receipt
from .targets import resolve_target

from app.songprogram.composition_generation import (
    CompositionGenerationError,
    composition_profile_hash,
    validate_composition_profile,
)


class PipelineError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PipelineError("JSON_OBJECT_EXPECTED", str(path))
    return value


def _write_artifact(output_dir: Path, name: str, document: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / name).write_bytes(canonical_bytes(document) + b"\n")


def analyze_reference_audio(
    input_path: Path,
    target_id: str,
    output_dir: Path,
    seed: int = 0,
    policy: InputPolicy | None = None,
) -> dict[str, Any]:
    """Run the full analysis and write the four artifacts to ``output_dir``.

    Returns a summary dict with the artifact paths and key hashes.
    """

    if not 0 <= seed < 2**64:
        raise PipelineError("SEED_INVALID", f"{seed} outside uint64")
    policy = policy or default_policy()
    target = resolve_target(target_id)

    failure_history: list[str] = []
    decoded = decode.decode_audio(input_path, policy)

    counter: dict[str, int] = {}
    mono = decoded.mono_floats()
    spectra, starts = dsp.stft_magnitudes(mono, time_axis.FRAME_SIZE, time_axis.HOP)

    quality_obs, pitch_unsuitable = quality.analyze_quality(decoded)
    time_obs, intermediates = time_axis.analyze_time_axis(decoded, spectra, starts, counter)

    chroma_frames = harmony.compute_chroma(
        spectra, starts, decoded.sample_rate, time_axis.FRAME_SIZE
    )
    chord_obs = harmony.estimate_chords(
        chroma_frames,
        starts,
        intermediates["beat_samples"],
        decoded.sample_rate,
        pitch_unsuitable,
        counter,
    )
    key_obs = harmony.estimate_key(chroma_frames, starts, decoded.sample_rate, counter)

    energy_obs, energy_q14 = acoustics.energy_curve(mono, intermediates["beat_samples"], counter)
    density_obs, density_q14 = acoustics.onset_density(
        intermediates["onset_samples"], intermediates["beat_samples"], counter
    )
    register_obs = acoustics.register_estimate(
        chroma_frames, starts, decoded.sample_rate, counter
    )
    stereo_obs = acoustics.stereo_balance(decoded, intermediates["beat_samples"], counter)

    observations = quality_obs + time_obs + chord_obs + key_obs + energy_obs + density_obs + register_obs + stereo_obs
    analysis = build_analysis(decoded, policy, observations)

    # Load the reference profile and generation manifest for the target.
    reference_profile: dict[str, Any] | None = None
    generation_manifest: dict[str, Any] | None = None
    reference_profile_hash: str | None = None
    generation_manifest_hash: str | None = None
    if target.composition_profile_path is not None and target.composition_profile_path.is_file():
        reference_profile = _load_json(target.composition_profile_path)
        reference_profile_hash = reference_profile.get("profile_hash")
    if target.generation_manifest_path is not None and target.generation_manifest_path.is_file():
        generation_manifest = _load_json(target.generation_manifest_path)
        generation_manifest_hash = generation_manifest.get("manifest_hash")

    patch = translation.build_profile_patch(analysis, target, reference_profile or {}, generation_manifest)

    # Merge the patch into the reference profile and validate the result.
    validation_status = "not_run"
    merged_profile: dict[str, Any] | None = None
    if reference_profile is not None and patch["settings"]:
        merged_profile, _merged_manifest = translation.merge_profile_patch(
            reference_profile, generation_manifest, patch
        )
        try:
            merged_profile["profile_hash"] = composition_profile_hash(merged_profile)
            validate_composition_profile(merged_profile)
            validation_status = "passed"
        except (CompositionGenerationError, ValueError, KeyError, TypeError) as error:
            validation_status = "failed"
            failure_history.append(f"profile_validation:{error}")
    elif reference_profile is None:
        validation_status = "not_run"
        failure_history.append("profile_validation:no_reference_profile")

    report = capability.build_capability_report(analysis, target, validation_status)
    receipt = build_receipt(
        source_path=decoded.source_path,
        source_hash=decoded.source_hash,
        pcm_hash=decoded.pcm_hash,
        decode=decode.decode_conditions(decoded),
        preprocessing={
            "frame_size": time_axis.FRAME_SIZE,
            "hop": time_axis.HOP,
            "model_id": MODEL_ID,
            "model_version": MODEL_VERSION,
        },
        reference_profile_hash=reference_profile_hash,
        generation_manifest_hash=generation_manifest_hash,
        catalog_hash=None,
        analysis=analysis,
        patch=patch,
        report=report,
        seed=seed,
        target_manifest_id=target.manifest_id,
        validation_status=validation_status,
        failure_history=failure_history,
        candidate_rationale=None,
    )

    _write_artifact(output_dir, "analysis.json", analysis)
    _write_artifact(output_dir, "profile_patch.json", patch)
    _write_artifact(output_dir, "capability_report.json", report)
    _write_artifact(output_dir, "receipt.json", receipt)

    return {
        "target_manifest_id": target.manifest_id,
        "analysis_path": str(output_dir / "analysis.json"),
        "patch_path": str(output_dir / "profile_patch.json"),
        "report_path": str(output_dir / "capability_report.json"),
        "receipt_path": str(output_dir / "receipt.json"),
        "pcm_hash": decoded.pcm_hash,
        "validation_status": validation_status,
        "observation_count": len(observations),
    }
