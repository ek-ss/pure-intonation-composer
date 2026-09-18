from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.exploration_generation import (
    ExplorationGenerationManifestError,
    exploration_generation_manifest_hash,
    validate_exploration_generation_manifest,
)


MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "songprogram_conformance"
    / "profiles"
    / "full_song_generation_v1.json"
)


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def test_checked_generation_manifest_is_closed_and_self_hashed() -> None:
    manifest = _manifest()
    validate_exploration_generation_manifest(manifest)
    assert exploration_generation_manifest_hash(manifest) == manifest["manifest_hash"]


def test_manifest_rejects_unknown_fields_before_execution() -> None:
    manifest = _manifest()
    manifest["ignored_option"] = True
    with pytest.raises(
        ExplorationGenerationManifestError,
        match="GENERATION_MANIFEST_FIELDS_INVALID",
    ):
        validate_exploration_generation_manifest(manifest)


def test_manifest_rejects_unimplemented_evaluation() -> None:
    manifest = _manifest()
    manifest["evaluation_policy"] = {"mode": "pil"}
    manifest["manifest_hash"] = exploration_generation_manifest_hash(manifest)
    with pytest.raises(
        ExplorationGenerationManifestError,
        match="GENERATION_EVALUATION_UNAVAILABLE",
    ):
        validate_exploration_generation_manifest(manifest)


def test_manifest_requires_chord_reference_for_every_equave() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["sampler_tables"]["chord_reference"] = manifest["sampler_tables"]["chord_reference"][
        :1
    ]
    manifest["manifest_hash"] = exploration_generation_manifest_hash(manifest)
    with pytest.raises(
        ExplorationGenerationManifestError,
        match="GENERATION_CHORD_EQUAVE_COVERAGE_INVALID",
    ):
        validate_exploration_generation_manifest(manifest)
