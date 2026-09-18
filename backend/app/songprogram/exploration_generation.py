"""Closed configuration boundary for non-authoritative generation trials."""

from __future__ import annotations

import hashlib
from typing import Any

from .search import canonical_bytes


class ExplorationGenerationManifestError(ValueError):
    """A generation manifest is not safe to execute."""


def exploration_generation_manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return (
        "sha256:"
        + hashlib.sha256(
            b"cps.exploration-generation-manifest/v1\0" + canonical_bytes(payload)
        ).hexdigest()
    )


def validate_exploration_generation_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "manifest_id",
        "choice_algorithm",
        "sampler_tables",
        "lowering_choices",
        "production_policy",
        "render_catalog_policy",
        "evaluation_policy",
        "manifest_hash",
    }
    if set(manifest) != required:
        raise ExplorationGenerationManifestError("GENERATION_MANIFEST_FIELDS_INVALID")
    if manifest["schema"] != "cps.exploration-generation-manifest":
        raise ExplorationGenerationManifestError("GENERATION_MANIFEST_SCHEMA_INVALID")
    if manifest["schema_version"] != "1.0.0":
        raise ExplorationGenerationManifestError("GENERATION_MANIFEST_VERSION_UNSUPPORTED")
    if manifest["choice_algorithm"] != "seed-domain-sha256-mod/v1":
        raise ExplorationGenerationManifestError("GENERATION_CHOICE_ALGORITHM_UNSUPPORTED")
    if manifest["evaluation_policy"] != {"mode": "none"}:
        raise ExplorationGenerationManifestError("GENERATION_EVALUATION_UNAVAILABLE")

    tables = manifest["sampler_tables"]
    expected_tables = {"equave_domain", "chord_reference", "rhythm_grid", "rhythm_density"}
    if not isinstance(tables, dict) or set(tables) != expected_tables:
        raise ExplorationGenerationManifestError("GENERATION_SAMPLER_TABLES_INVALID")
    for name, table in tables.items():
        if not isinstance(table, list) or not table:
            raise ExplorationGenerationManifestError(f"GENERATION_TABLE_EMPTY:{name}")
        for item in table:
            if (
                set(item) != {"value", "weight"}
                or not isinstance(item["weight"], int)
                or item["weight"] < 1
            ):
                raise ExplorationGenerationManifestError(f"GENERATION_TABLE_ENTRY_INVALID:{name}")

    equaves = {item["value"]["equave"] for item in tables["equave_domain"]}
    chord_equaves = {item["value"]["equave"] for item in tables["chord_reference"]}
    if not chord_equaves.issubset(equaves) or not equaves.issubset(chord_equaves):
        raise ExplorationGenerationManifestError("GENERATION_CHORD_EQUAVE_COVERAGE_INVALID")

    choices = manifest["lowering_choices"]
    expected_choices = {
        "tempo_milli_bpm",
        "tonal_centers",
        "vector_walks",
        "rhythm_duration_ticks",
        "rhythm_accent_q",
        "maximum_domain_points",
        "chord_complexity_budget",
    }
    if not isinstance(choices, dict) or set(choices) != expected_choices:
        raise ExplorationGenerationManifestError("GENERATION_LOWERING_CHOICES_INVALID")
    for name in (
        "tempo_milli_bpm",
        "tonal_centers",
        "vector_walks",
        "rhythm_duration_ticks",
        "rhythm_accent_q",
    ):
        if not isinstance(choices[name], list) or not choices[name]:
            raise ExplorationGenerationManifestError(f"GENERATION_CHOICE_EMPTY:{name}")

    production = manifest["production_policy"]
    if set(production) != {"maximum_polyphony", "pitched_frequency_millihz", "register_millicents"}:
        raise ExplorationGenerationManifestError("GENERATION_PRODUCTION_POLICY_INVALID")
    if not 1 <= production["maximum_polyphony"] <= 256:
        raise ExplorationGenerationManifestError("GENERATION_POLYPHONY_INVALID")
    for field in ("pitched_frequency_millihz", "register_millicents"):
        bounds = production[field]
        if not isinstance(bounds, list) or len(bounds) != 2 or bounds[0] >= bounds[1]:
            raise ExplorationGenerationManifestError(f"GENERATION_BOUNDS_INVALID:{field}")

    catalog = manifest["render_catalog_policy"]
    if catalog.get("algorithm") != "deterministic-harmonic-trial-catalog/v1":
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_POLICY_UNSUPPORTED")
    if set(catalog) != {"algorithm", "drum_impulse_q31", "pitched_roles"}:
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_POLICY_INVALID")
    if set(catalog["pitched_roles"]) != {"bass", "harmony", "melody", "texture"}:
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_ROLES_INVALID")
    for role, policy in catalog["pitched_roles"].items():
        if set(policy) != {"partials", "partial_gains_q31", "gain_q14", "release_frames"}:
            raise ExplorationGenerationManifestError(f"GENERATION_CATALOG_ROLE_INVALID:{role}")
        if len(policy["partials"]) != len(policy["partial_gains_q31"]) or not policy["partials"]:
            raise ExplorationGenerationManifestError(f"GENERATION_CATALOG_PARTIALS_INVALID:{role}")

    if manifest["manifest_hash"] != exploration_generation_manifest_hash(manifest):
        raise ExplorationGenerationManifestError("GENERATION_MANIFEST_HASH_MISMATCH")
