from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.exploration_generation import (
    ExplorationGenerationManifestError,
    derive_lattice_navigation,
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


def test_every_domain_is_357_limit_and_derives_non_fixed_navigation() -> None:
    manifest = _manifest()
    policy = manifest["lowering_choices"]["lattice_navigation"]
    for row in manifest["sampler_tables"]["equave_domain"]:
        domain = row["value"]
        primes = {int(domain["equave"].split("/")[0])}
        primes.update(int(value.split("/")[0]) for value in domain["generators"])
        assert {3, 5, 7}.issubset(primes)
        navigation = derive_lattice_navigation(domain, policy)
        assert len(navigation["tonal_centers"]) > 1
        assert navigation["harmony_root_anchors"] != [[0, 0, 0]]
        assert any(
            sum(abs(value) for value in right) > 1
            for walk in navigation["vector_walks"]
            for left, right in zip(walk, walk[1:])
        )
        for family in ("tonal_centers", "harmony_root_anchors"):
            assert all(len(vector) == 3 for vector in navigation[family])


def test_navigation_rejects_domain_without_prime_seven() -> None:
    manifest = _manifest()
    domain = copy.deepcopy(manifest["sampler_tables"]["equave_domain"][0]["value"])
    domain["generators"][-1] = "11/1"
    with pytest.raises(
        ExplorationGenerationManifestError,
        match="GENERATION_GENERATOR_COVERAGE_INVALID",
    ):
        derive_lattice_navigation(domain, manifest["lowering_choices"]["lattice_navigation"])


def test_navigation_accepts_five_variable_generators_without_materializing_domain() -> None:
    manifest = _manifest()
    domain = {
        "equave": "2/1",
        "generators": ["3/1", "5/1", "7/1", "11/1", "13/1"],
        "coordinate_bounds": [[-4, 4], [-4, 4], [-4, 4], [0, 0], [0, 0]],
        "register_bounds": [-2, 2],
    }
    result = derive_lattice_navigation(
        domain, manifest["lowering_choices"]["lattice_navigation"]
    )
    assert all(len(vector) == 5 for vector in result["tonal_centers"])


def test_navigation_rejects_more_than_five_dimensions() -> None:
    manifest = _manifest()
    domain = copy.deepcopy(manifest["sampler_tables"]["equave_domain"][0]["value"])
    domain["generators"] += ["11/1", "13/1", "17/1"]
    domain["coordinate_bounds"] += [[0, 0], [0, 0], [0, 0]]
    with pytest.raises(
        ExplorationGenerationManifestError,
        match="GENERATION_GENERATOR_COVERAGE_INVALID",
    ):
        derive_lattice_navigation(domain, manifest["lowering_choices"]["lattice_navigation"])
