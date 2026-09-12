"""Evaluation-free SongProgram compilation and reference rendering harness."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from .compiler import CompilerIdentity, compile_sp0
from .connected import artifact_hash, canonical_lf
from .mutation import program_hash
from .perceptual import project_hash
from .renderer import render_reference
from .validator import validate_project


class UnscoredGenerationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _catalog_digest(catalog_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()


def _write_new(path: Path, payload: bytes) -> None:
    if path.exists():
        raise UnscoredGenerationError("UNSCORED_OUTPUT_EXISTS")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def generate_unscored(
    program: dict[str, Any],
    *,
    seed: int,
    compiler_identity: CompilerIdentity,
    catalog_bytes: bytes,
    resolve_asset: Callable[[str], bytes],
    render_manifest_digest: str,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Compile, render and persist one candidate without invoking evaluation."""
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**64:
        raise UnscoredGenerationError("UNSCORED_REQUEST_INVALID")
    catalog_digest = _catalog_digest(catalog_bytes)
    if compiler_identity.instrument_catalog_digest != catalog_digest:
        raise UnscoredGenerationError("UNSCORED_CATALOG_MISMATCH")
    output = Path(output_directory)
    if output.exists() and any(output.iterdir()):
        raise UnscoredGenerationError("UNSCORED_OUTPUT_EXISTS")
    output.mkdir(parents=True, exist_ok=True)

    project = compile_sp0(program, compiler_identity)
    validate_project(project)
    project_digest = project_hash(project)
    rendered = render_reference(
        project,
        catalog_bytes,
        resolve_asset,
        render_manifest_digest=render_manifest_digest,
        project_artifact_hash=project_digest,
    )
    render_report_hash = artifact_hash("cps.reference-render-report/v1.1", rendered.report)
    receipt = {
        "schema": "cps.unscored-generation-receipt",
        "schema_version": "1.0.0",
        "seed": seed,
        "program_hash": program_hash(program),
        "project_hash": project_digest,
        "catalog_digest": catalog_digest,
        "render_manifest_digest": render_manifest_digest,
        "render_report_hash": render_report_hash,
        "wav_hash": rendered.report["wav_hash"],
        "evaluation_performed": False,
        "artifact_paths": {
            "program": "song_program.json",
            "project": "project.json",
            "render_report": "render_report.json",
            "wav": "preview.wav",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = artifact_hash(
        "cps.unscored-generation-receipt/v1", receipt, omit="receipt_hash"
    )
    _write_new(output / "song_program.json", canonical_lf(program))
    _write_new(output / "project.json", canonical_lf(project))
    _write_new(output / "render_report.json", canonical_lf(rendered.report))
    _write_new(output / "preview.wav", rendered.wav)
    _write_new(output / "receipt.json", canonical_lf(receipt))
    return receipt


__all__ = ("UnscoredGenerationError", "generate_unscored")
