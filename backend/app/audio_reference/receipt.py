"""Assemble the ``receipt.json`` document.

Records everything needed to reproduce a run: tool/build/model identity,
input and PCM hashes, decode and preprocessing parameters, the selected
reference profile and catalog hashes, the patch/report hashes, the seed, the
candidate-selection rationale, and the validation status with failure history.
Model outputs are pinned to the executing build and weight hashes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .observations import MODEL_ID, MODEL_VERSION

RECEIPT_SCHEMA = "cps.audio-reference-receipt"
RECEIPT_SCHEMA_VERSION = "0.1.0"

TOOL_ID = "cps.analyze-reference-audio"
TOOL_VERSION = "0.1.0"


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hash(artifact: dict[str, Any]) -> str:
    import json

    prefix = f"{artifact['schema']}/{artifact['schema_version']}\0".encode()
    canonical = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(prefix + canonical).hexdigest()


def build_receipt(
    *,
    source_path: str,
    source_hash: str,
    pcm_hash: str,
    decode: dict[str, Any],
    preprocessing: dict[str, Any],
    reference_profile_hash: str | None,
    generation_manifest_hash: str | None,
    catalog_hash: str | None,
    analysis: dict[str, Any],
    patch: dict[str, Any],
    report: dict[str, Any],
    seed: int,
    target_manifest_id: str,
    validation_status: str,
    failure_history: list[str],
    candidate_rationale: str | None,
) -> dict[str, Any]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "tool_id": TOOL_ID,
        "tool_version": TOOL_VERSION,
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "model_weights_hash": None,  # baseline uses no learned weights
        "input": {
            "path": source_path,
            "source_hash": source_hash,
            "pcm_hash": pcm_hash,
        },
        "decode": decode,
        "preprocessing": preprocessing,
        "target_manifest_id": target_manifest_id,
        "reference_profile_hash": reference_profile_hash,
        "generation_manifest_hash": generation_manifest_hash,
        "catalog_hash": catalog_hash,
        "analysis_hash": _artifact_hash(analysis),
        "patch_hash": _artifact_hash(patch),
        "report_hash": _artifact_hash(report),
        "seed": seed,
        "candidate_rationale": candidate_rationale,
        "validation_status": validation_status,
        "failure_history": failure_history,
    }
    return receipt
