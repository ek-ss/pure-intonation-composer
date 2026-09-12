from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from app.songprogram.compiler import CompilerIdentity
from app.songprogram.connected import artifact_hash, canonical_lf
from app.songprogram.unscored_generation import (
    UnscoredGenerationError,
    generate_unscored,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "songprogram_conformance/fixtures/pack"
RENDER = ROOT / "songprogram_conformance/fixtures/render"


def _inputs():
    catalog_bytes = (RENDER / "catalog.json").read_bytes()
    catalog_digest = (
        "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
    )
    program = json.loads((PACK / "minimal_direct_song_program.json").read_text())
    program["tracks"][0]["instrument_id"] = "pitched_fixture_2_1"
    program["production"]["catalog_digest"] = catalog_digest
    identity = CompilerIdentity(
        build_id="unscored-test",
        resolver_build_id="fixture-resolver",
        resolver_profile_hash="sha256:" + "10" * 32,
        budget_profile_digest="sha256:" + "11" * 32,
        instrument_catalog_digest=catalog_digest,
    )
    render_manifest = json.loads((RENDER / "render_manifest.json").read_text())
    return program, identity, catalog_bytes, render_manifest["render_manifest_digest"]


def _asset(uri: str) -> bytes:
    return (RENDER / "assets" / f"{uri.rsplit('/', 1)[1]}.wav").read_bytes()


def test_harness_writes_playable_artifacts_without_evaluation(tmp_path, monkeypatch) -> None:
    program, identity, catalog, render_manifest_digest = _inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr("app.songprogram.perceptual.run_perceptual_interpretation", forbidden)
    receipt = generate_unscored(
        program,
        seed=7,
        compiler_identity=identity,
        catalog_bytes=catalog,
        resolve_asset=_asset,
        render_manifest_digest=render_manifest_digest,
        output_directory=tmp_path,
    )
    assert receipt["evaluation_performed"] is False
    assert (tmp_path / "preview.wav").read_bytes().startswith(b"RIFF")
    assert (tmp_path / "song_program.json").read_bytes() == canonical_lf(program)
    assert json.loads((tmp_path / "receipt.json").read_bytes()) == receipt
    assert receipt["receipt_hash"] == artifact_hash(
        "cps.unscored-generation-receipt/v1", receipt, omit="receipt_hash"
    )

    with pytest.raises(UnscoredGenerationError, match="UNSCORED_OUTPUT_EXISTS"):
        generate_unscored(
            program,
            seed=7,
            compiler_identity=identity,
            catalog_bytes=catalog,
            resolve_asset=_asset,
            render_manifest_digest=render_manifest_digest,
            output_directory=tmp_path,
        )


def test_harness_rejects_catalog_identity_mismatch(tmp_path) -> None:
    program, identity, catalog, render_manifest_digest = _inputs()
    wrong = CompilerIdentity(
        identity.build_id,
        identity.resolver_build_id,
        identity.resolver_profile_hash,
        identity.budget_profile_digest,
        "sha256:" + "00" * 32,
    )
    with pytest.raises(UnscoredGenerationError, match="UNSCORED_CATALOG_MISMATCH"):
        generate_unscored(
            program,
            seed=0,
            compiler_identity=wrong,
            catalog_bytes=catalog,
            resolve_asset=_asset,
            render_manifest_digest=render_manifest_digest,
            output_directory=tmp_path,
        )


def test_cli_writes_the_same_evaluation_free_bundle(tmp_path) -> None:
    program, identity, _, _ = _inputs()
    program_path = tmp_path / "program.json"
    identity_path = tmp_path / "identity.json"
    program_path.write_text(json.dumps(program), encoding="utf-8")
    identity_path.write_text(json.dumps(asdict(identity)), encoding="utf-8")
    output = tmp_path / "result"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/generate_unscored.py",
            "--program",
            str(program_path),
            "--compiler-identity",
            str(identity_path),
            "--catalog",
            str(RENDER / "catalog.json"),
            "--asset-directory",
            str(RENDER / "assets"),
            "--render-manifest",
            str(RENDER / "render_manifest.json"),
            "--seed",
            "9",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    receipt = json.loads(completed.stdout)
    assert receipt["seed"] == 9
    assert receipt["evaluation_performed"] is False
    assert (output / "preview.wav").read_bytes().startswith(b"RIFF")
