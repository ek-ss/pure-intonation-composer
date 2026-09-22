"""Closed configuration boundary for non-authoritative generation trials."""

from __future__ import annotations

import hashlib
from fractions import Fraction
from itertools import product
from math import prod
from typing import Any

from .compiler import _mc
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


def derive_lattice_navigation(domain: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Map 12-TET navigation targets to canonical vectors in an equave domain."""
    if policy.get("algorithm") != "nearest-12tet-vector/v1":
        raise ExplorationGenerationManifestError("GENERATION_NAVIGATION_POLICY_INVALID")
    try:
        generators = [Fraction(value) for value in domain["generators"]]
        equave = Fraction(domain["equave"])
    except (ValueError, ZeroDivisionError) as error:
        raise ExplorationGenerationManifestError("GENERATION_GENERATOR_INVALID") from error
    if (
        any(
            f"{value.numerator}/{value.denominator}" != source
            for value, source in zip(generators, domain["generators"], strict=True)
        )
        or f"{equave.numerator}/{equave.denominator}" != domain["equave"]
        or equave <= 1
        or any(value <= 0 or value == equave for value in generators)
        or len(set(generators)) != len(generators)
    ):
        raise ExplorationGenerationManifestError("GENERATION_GENERATOR_INVALID")
    bounds = domain["coordinate_bounds"]
    generator_primes = {
        prime
        for value in generators
        for prime in _prime_factors(value.numerator) | _prime_factors(value.denominator)
    }
    generator_primes |= _prime_factors(equave.numerator) | _prime_factors(equave.denominator)
    dimension = len(generators)
    required_primes = set(policy["required_prime_factors"])
    if (
        not 1 <= dimension <= 5
        or dimension != len(bounds)
        or not required_primes.issubset(generator_primes)
    ):
        raise ExplorationGenerationManifestError("GENERATION_GENERATOR_COVERAGE_INVALID")
    # Navigation occupies the centered half-domain so that adding a tonal
    # center to a walk/root vector remains inside the full compiler domain.
    navigation_bounds = [((low + 1) // 2, high // 2) for low, high in bounds]
    navigation_cardinality = prod(high - low + 1 for low, high in navigation_bounds)
    if navigation_cardinality > policy["maximum_navigation_points"]:
        raise ExplorationGenerationManifestError("GENERATION_NAVIGATION_DOMAIN_TOO_LARGE")

    def vectors():
        # Do not materialize the Cartesian domain: this must remain safe when
        # the schema is promoted from three to as many as five dimensions.
        return product(*(range(low, high + 1) for low, high in navigation_bounds))

    def nearest(step: int) -> list[int]:
        target = step % 12 * 100_000
        ranked = []
        for vector in vectors():
            ratio = Fraction(1)
            for generator, exponent in zip(generators, vector, strict=True):
                ratio *= generator**exponent
            absolute = _mc(ratio)
            phase = absolute % 1_200_000
            distance = abs(phase - target)
            distance = min(distance, 1_200_000 - distance)
            if distance <= policy["maximum_error_millicents"]:
                ranked.append((abs(absolute - target), distance, sum(abs(value) for value in vector), max(abs(value) for value in vector), vector))
        if not ranked:
            raise ExplorationGenerationManifestError("GENERATION_12TET_COVERAGE_INSUFFICIENT")
        _, error, _, _, selected = min(ranked)
        if error > policy["maximum_error_millicents"]:
            raise ExplorationGenerationManifestError("GENERATION_12TET_COVERAGE_INSUFFICIENT")
        return list(selected)

    return {
        "tonal_centers": [nearest(step) for step in policy["tonal_center_steps"]],
        "vector_walks": [
            [nearest(step) for step in pattern] for pattern in policy["walk_step_patterns"]
        ],
        "harmony_root_anchors": [nearest(step) for step in policy["harmony_root_steps"]],
    }


def _prime_factors(value: int) -> set[int]:
    factors: set[int] = set()
    divisor = 2
    while divisor * divisor <= value:
        while value % divisor == 0:
            factors.add(divisor)
            value //= divisor
        divisor += 1
    if value > 1:
        factors.add(value)
    return factors


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

    for item in tables["equave_domain"]:
        domain = item["value"]
        generators = domain.get("generators")
        bounds = domain.get("coordinate_bounds")
        if (
            not isinstance(generators, list)
            or not 1 <= len(generators) <= 5
            or not isinstance(bounds, list)
            or len(bounds) != len(generators)
        ):
            raise ExplorationGenerationManifestError("GENERATION_DOMAIN_DIMENSION_INVALID")

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
        "lattice_navigation",
        "maximum_odd_limit",
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
    navigation = choices["lattice_navigation"]
    if (
        not isinstance(navigation, dict)
        or set(navigation)
        != {
            "algorithm",
            "target_divisions",
            "maximum_error_millicents",
            "maximum_navigation_points",
            "required_prime_factors",
            "tonal_center_steps",
            "walk_step_patterns",
            "harmony_root_steps",
        }
        or navigation.get("algorithm") != "nearest-12tet-vector/v1"
        or navigation.get("target_divisions") != 12
        or type(navigation.get("maximum_error_millicents")) is not int
        or not 1 <= navigation["maximum_error_millicents"] <= 100_000
        or type(navigation.get("maximum_navigation_points")) is not int
        or not 1 <= navigation["maximum_navigation_points"] <= 65_535
        or not isinstance(navigation.get("required_prime_factors"), list)
        or not navigation["required_prime_factors"]
        or navigation["required_prime_factors"] != sorted(set(navigation["required_prime_factors"]))
        or any(type(value) is not int or value < 2 for value in navigation["required_prime_factors"])
    ):
        raise ExplorationGenerationManifestError("GENERATION_NAVIGATION_POLICY_INVALID")
    if type(choices["maximum_odd_limit"]) is not int or not 7 <= choices["maximum_odd_limit"] <= 65535:
        raise ExplorationGenerationManifestError("GENERATION_ODD_LIMIT_INVALID")
    for domain in tables["equave_domain"]:
        derive_lattice_navigation(domain["value"], navigation)

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
    if set(catalog) != {"algorithm", "drum_lanes", "pitched_roles"}:
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_POLICY_INVALID")
    if set(catalog["drum_lanes"]) != {
        "kick", "snare", "clap", "closed_hat", "open_hat", "fill"
    }:
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_ROLES_INVALID")
    for lane, policy in catalog["drum_lanes"].items():
        if (
            set(policy) != {"drum_note", "samples_q31"}
            or type(policy["drum_note"]) is not int
            or not 0 <= policy["drum_note"] <= 127
            or not isinstance(policy["samples_q31"], list)
            or not policy["samples_q31"]
            or any(type(value) is not int or not -(2**31) <= value < 2**31 for value in policy["samples_q31"])
        ):
            raise ExplorationGenerationManifestError(f"GENERATION_CATALOG_DRUM_INVALID:{lane}")
    if set(catalog["pitched_roles"]) != {"bass", "harmony", "melody", "texture"}:
        raise ExplorationGenerationManifestError("GENERATION_CATALOG_ROLES_INVALID")
    for role, policy in catalog["pitched_roles"].items():
        if set(policy) != {"partials", "partial_gains_q31", "gain_q14", "release_frames"}:
            raise ExplorationGenerationManifestError(f"GENERATION_CATALOG_ROLE_INVALID:{role}")
        if len(policy["partials"]) != len(policy["partial_gains_q31"]) or not policy["partials"]:
            raise ExplorationGenerationManifestError(f"GENERATION_CATALOG_PARTIALS_INVALID:{role}")

    if manifest["manifest_hash"] != exploration_generation_manifest_hash(manifest):
        raise ExplorationGenerationManifestError("GENERATION_MANIFEST_HASH_MISMATCH")
