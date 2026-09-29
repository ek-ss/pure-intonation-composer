"""Cadence-driven piano-solo v3: five-dimensional dictionary-bound generation.

Implements the v3 spec (``docs/piano_solo_v3_cadence_profile_spec.md``) on
top of the committed v1 pipeline:

* ``PIANO_V3_DOMAINS`` — five-dimensional lattice domains (``[0, 3]^5`` =
  1024 coordinate points, register width 4 → 4096 placed points; exactly at
  the GEN0-B coordinate/placed budgets) for both equaves, with axes matching
  the sealed five-dimensional harmony dictionary.  No two-dimensional domain
  exists in v3 generation.
* ``CadencePolicy`` — versioned, per-equave cadence policy (sealed JSON),
  bound to the dictionary hash and the stability profile hash.
* ``generate_cadence_plan`` — one slot per bar; each slot selects a
  dictionary variant (12-EDO candidate search only, exact ratios at
  performance) that is embeddable in the five-dimensional domain at the
  slot's function, ranked by stability, and capped by voice leading against
  the previous slot.  A variant that cannot be embedded is a typed failure,
  never a silent two-dimensional fallback.
* ``lower_cadence_plan`` — independent v3 lowering: the committed v1
  lowering as a base, then clone-on-write harmony materials bound to the
  cadence plan's dictionary variants (no v2 retrofit).
* ``cadence_impact_report`` — reconciles the plan against the compiled
  project across Plan/Program/Project; typed failures.

The v1/v2 sealed files and hashes are untouched; v3 adds its own manifests,
receipts, and artifacts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from fractions import Fraction
from itertools import product
from typing import Any, Mapping

from ..harmony_dictionary.authority import reduce_on_equave
from ..harmony_dictionary.storage import seal
from ..harmony_dictionary.stability import (
    ClassificationThresholds,
    StabilityProfile,
    classify_with_context,
    stability_q,
)
from ..tuning.ratios import ratio_text
from .compiler import _mc
from .composition_generation import composition_plan_hash

SCHEMA_VERSION = "1.0.0"
CADENCE_ALGORITHM_ID = "piano-v3-cadence/v1"

# GEN0-B domain budgets (conformance manifest fixture): the v3 domain sits
# exactly at the coordinate and placed cardinality limits.
GEN0B_COORDINATE_BUDGET = 1024
GEN0B_PLACED_BUDGET = 4096

# The v3 structural lowering manifest raises the shared fixture's odd limit
# (31) to 4096 so that every single-axis [0, 3]^5 point (maximum odd part
# 13^3 = 2197) can host a voice; the shared fixture itself is untouched.
V3_MAXIMUM_ODD_LIMIT = 4096
V3_MAXIMUM_COMPLEXITY_BITS = 4096

# Five-dimensional domains, one per equave.  The axes match the sealed
# dictionary (AXES_BY_EQUAVE); the octave lattice excludes 2/1 (the equave)
# and the tritave lattice excludes 3/1.
PIANO_V3_DOMAINS: dict[str, dict[str, Any]] = {
    "2/1": {
        "equave": "2/1",
        "generators": ["3/1", "5/1", "7/1", "11/1", "13/1"],
    "coordinate_bounds": [[-1, 2]] * 5,
        "register_bounds": [-2, 1],
        "reduce_anchor_mod_equave": True,
    },
    "3/1": {
        "equave": "3/1",
        "generators": ["2/1", "5/1", "7/1", "11/1", "13/1"],
    "coordinate_bounds": [[-1, 2]] * 5,
        "register_bounds": [-2, 1],
        "reduce_anchor_mod_equave": True,
    },
}

# Function root vectors in the five-dimensional lattice (tonic = 1/1 = zero
# vector).  The compiler anchor is exempt from coordinate bounds (it checks
# vector length only), so the S root may sit one step below the domain on
# the 3-axis (octave) and the D root one step below on the 2-axis (tritave).
FUNCTION_ROOT_VECTORS: dict[str, dict[str, list[int]]] = {
    "2/1": {"T": [0, 0, 0, 0, 0], "D": [1, 0, 0, 0, 0], "S": [-1, 0, 0, 0, 0]},
    "3/1": {"T": [0, 0, 0, 0, 0], "D": [-1, 0, 0, 0, 0], "S": [2, 0, 0, 0, 0]},
}

# Function roots relative to the tonic (reduced on the equave at use time).
FUNCTION_ROOTS = {"T": Fraction(1), "D": Fraction(3, 2), "S": Fraction(4, 3)}

EXPECTATIONS = ("stable", "depart", "prepare", "arrive", "open")
FUNCTION_BY_EXPECTATION = {
    "stable": "T",
    "arrive": "T",
    "depart": "S",
    "prepare": "D",
    "open": "D",
}

# Per-section-function open/closed placement (spec §3 section design table).
SECTION_PLACEMENT = {
    "opening": "closed",
    "statement": "open",
    "preparation": "open",
    "arrival": "closed",
    "contrast": "open",
    "return": "open",
    "closure": "closed",
}


class PianoV3Error(ValueError):
    """A stable v3 failure with a machine-readable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


# ---------------------------------------------------------------------------
# Domains and navigation coverage


def validate_v3_domain(domain: Mapping[str, Any]) -> None:
    """Check the v3 domain against the GEN0-B budgets and the dictionary axes."""
    if set(domain) != {
        "equave",
        "generators",
        "coordinate_bounds",
        "register_bounds",
        "reduce_anchor_mod_equave",
    }:
        raise PianoV3Error("V3_DOMAIN_FIELDS_INVALID")
    if domain["equave"] not in PIANO_V3_DOMAINS:
        raise PianoV3Error("V3_EQUAVE_UNSUPPORTED", str(domain["equave"]))
    if domain != PIANO_V3_DOMAINS[domain["equave"]]:
        raise PianoV3Error("V3_DOMAIN_MISMATCH", domain["equave"])
    cardinality = math.prod(high - low + 1 for low, high in domain["coordinate_bounds"])
    if cardinality > GEN0B_COORDINATE_BUDGET:
        raise PianoV3Error("V3_DOMAIN_TOO_LARGE", f"{cardinality} > {GEN0B_COORDINATE_BUDGET}")
    register_width = domain["register_bounds"][1] - domain["register_bounds"][0] + 1
    if cardinality * register_width > GEN0B_PLACED_BUDGET:
        raise PianoV3Error("V3_PLACED_TOO_LARGE")


def v3_domain_cardinalities(domain: Mapping[str, Any]) -> tuple[int, int]:
    """Return ``(coordinate_cardinality, placed_cardinality)``."""
    validate_v3_domain(domain)
    coordinate = math.prod(high - low + 1 for low, high in domain["coordinate_bounds"])
    register_width = domain["register_bounds"][1] - domain["register_bounds"][0] + 1
    return coordinate, coordinate * register_width


def measure_navigation_coverage(domain: Mapping[str, Any]) -> dict[str, Any]:
    """Measure 12-TET coverage of the domain's navigation half-domain.

    Mirrors ``derive_lattice_navigation``'s nearest-vector search over the
    centered half-domain and records the per-step error.  The v3 builder
    seals the range only when every step is covered within the 50-cent
    budget (spec §2: measure navigation coverage before sealing range).
    """
    validate_v3_domain(domain)
    generators = [Fraction(text) for text in domain["generators"]]
    bounds = [((low + 1) // 2, high // 2) for low, high in domain["coordinate_bounds"]]
    vectors = list(product(*(range(low, high + 1) for low, high in bounds)))
    steps: dict[int, dict[str, Any]] = {}
    for step in range(12):
        target = step * 100_000
        best_key: tuple[int, int, int, int] | None = None
        best_vector: list[int] | None = None
        smallest_distance: int | None = None
        for vector in vectors:
            ratio = Fraction(1)
            for generator, exponent in zip(generators, vector):
                ratio *= generator**exponent
            absolute = _mc(ratio)
            phase = absolute % 1_200_000
            distance = abs(phase - target)
            distance = min(distance, 1_200_000 - distance)
            if smallest_distance is None or distance < smallest_distance:
                smallest_distance = distance
            # The real navigation derives its vector from eligible candidates
            # only.  Ranking an out-of-gate vector by absolute height first
            # incorrectly fails even a fully covered octave domain.
            if distance > 50_000:
                continue
            key = (
                abs(absolute - target),
                distance,
                sum(abs(value) for value in vector),
                max(abs(value) for value in vector),
            )
            if best_key is None or key < best_key:
                best_key, best_vector = key, list(vector)
        steps[step] = {
            "vector": best_vector,
            "error_millicents": best_key[1] if best_key is not None else smallest_distance,
            "covered": best_key is not None,
        }
    maximum = max(row["error_millicents"] for row in steps.values())
    return {
        "algorithm": "nearest-12tet-vector/v1",
        "target_divisions": 12,
        "maximum_error_millicents": 50_000,
        "steps": steps,
        "maximum_error_millicents_measured": maximum,
        "covered": all(row["covered"] for row in steps.values()),
    }


def compare_navigation_coverage(domain: Mapping[str, Any]) -> dict[str, Any]:
    """Compare local coverage measurement with the production navigation API.

    A coverage measurement is retained even if the production policy rejects
    the domain, so a failed step is diagnosable and cannot be sealed by
    confusing modulo-12 navigation with an absolute 24-step search.
    """
    from .exploration_generation import (
        ExplorationGenerationManifestError,
        derive_lattice_navigation,
    )

    measured = measure_navigation_coverage(domain)
    policy = {
        "algorithm": "nearest-12tet-vector/v1",
        "target_divisions": 12,
        "maximum_error_millicents": 50_000,
        "maximum_navigation_points": 16_384,
        "required_prime_factors": [2, 3, 5, 7, 11, 13],
        "tonal_center_steps": list(range(12)),
        "harmony_root_steps": list(range(12)),
        "walk_step_patterns": [[0, 2, 4, 6], [0, 10, 6, 2]],
    }
    result: dict[str, Any] = {
        "policy": policy,
        "measurement": measured,
        "actual_status": "not_evaluated",
        "actual_vectors": None,
        "vectors_match": None,
        "seal_eligible": False,
    }
    try:
        actual = derive_lattice_navigation(domain, policy)
    except ExplorationGenerationManifestError as error:
        result["actual_status"] = str(error)
        return result
    vectors = actual["tonal_centers"][:12]
    measured_vectors = [measured["steps"][step]["vector"] for step in range(12)]
    result.update({
        "actual_status": "covered",
        "actual_vectors": vectors,
        "vectors_match": vectors == measured_vectors,
        "seal_eligible": measured["covered"] and vectors == measured_vectors,
    })
    return result


# ---------------------------------------------------------------------------
# Cadence policy (sealed per equave)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def cadence_policy_hash(policy: Mapping[str, Any]) -> str:
    body = {key: value for key, value in policy.items() if key != "policy_hash"}
    digest = hashlib.sha256(
        b"cps.piano-cadence-policy/v1\0" + _canonical(body)
    ).hexdigest()
    return "sha256:" + digest


def build_cadence_policy(
    equave: str,
    dictionary_hash: str,
    stability_profile_hash: str,
    thresholds_version: str,
) -> dict[str, Any]:
    """Assemble the (unsealed) per-equave cadence policy body."""
    if equave not in PIANO_V3_DOMAINS:
        raise PianoV3Error("V3_EQUAVE_UNSUPPORTED", equave)
    policy = {
        "schema": "cps.piano-cadence-policy",
        "schema_version": SCHEMA_VERSION,
        "policy_id": f"piano-v3-cadence-policy-{equave.replace('/', '-')}",
        "cadence_algorithm_id": CADENCE_ALGORITHM_ID,
        "equave": equave,
        "dictionary_hash": dictionary_hash,
        "stability_profile_hash": stability_profile_hash,
        "thresholds_version": thresholds_version,
        "voice_counts": [3, 4],
        "candidate_budget": 32,
        "max_changes_per_bar": 2,
        "voice_leading_cap_cents": 400.0,
        "section_placement": dict(SECTION_PLACEMENT),
        "cycle_repeat_bars": 2,
        "policy_hash": "",
    }
    policy["policy_hash"] = cadence_policy_hash(policy)
    return policy


def validate_cadence_policy(policy: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "schema_version",
        "policy_id",
        "cadence_algorithm_id",
        "equave",
        "dictionary_hash",
        "stability_profile_hash",
        "thresholds_version",
        "voice_counts",
        "candidate_budget",
        "max_changes_per_bar",
        "voice_leading_cap_cents",
        "section_placement",
        "cycle_repeat_bars",
        "policy_hash",
    }
    if not isinstance(policy, Mapping) or set(policy) != required:
        raise PianoV3Error("CADENCE_POLICY_FIELDS_INVALID")
    if policy["schema"] != "cps.piano-cadence-policy":
        raise PianoV3Error("CADENCE_POLICY_SCHEMA_INVALID")
    if policy["schema_version"] != SCHEMA_VERSION:
        raise PianoV3Error("CADENCE_POLICY_VERSION_UNSUPPORTED")
    if policy["cadence_algorithm_id"] != CADENCE_ALGORITHM_ID:
        raise PianoV3Error("CADENCE_POLICY_ALGORITHM_UNSUPPORTED")
    if policy["equave"] not in PIANO_V3_DOMAINS:
        raise PianoV3Error("CADENCE_POLICY_EQUAVE_UNSUPPORTED", str(policy["equave"]))
    if not isinstance(policy["voice_counts"], list) or not policy["voice_counts"]:
        raise PianoV3Error("CADENCE_POLICY_VOICE_COUNTS_INVALID")
    if any(count not in (3, 4) for count in policy["voice_counts"]):
        raise PianoV3Error("CADENCE_POLICY_VOICE_COUNTS_INVALID")
    if not 1 <= policy["candidate_budget"] <= 256:
        raise PianoV3Error("CADENCE_POLICY_BUDGET_INVALID")
    if not 1 <= policy["max_changes_per_bar"] <= 8:
        raise PianoV3Error("CADENCE_POLICY_CHANGES_INVALID")
    if not 0 < policy["voice_leading_cap_cents"] <= 1200:
        raise PianoV3Error("CADENCE_POLICY_CAP_INVALID")
    if set(policy["section_placement"]) != set(SECTION_PLACEMENT):
        raise PianoV3Error("CADENCE_POLICY_PLACEMENT_INVALID")
    if any(value not in ("open", "closed") for value in policy["section_placement"].values()):
        raise PianoV3Error("CADENCE_POLICY_PLACEMENT_INVALID")
    if not 1 <= policy["cycle_repeat_bars"] <= 8:
        raise PianoV3Error("CADENCE_POLICY_CYCLE_INVALID")
    if cadence_policy_hash(policy) != policy["policy_hash"]:
        raise PianoV3Error("CADENCE_POLICY_HASH_MISMATCH")


# ---------------------------------------------------------------------------
# Domain point set and embeddability


def _vector_ratio(generators: list[Fraction], vector: list[int], equave: Fraction, exponent: int) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector):
        value *= generator**power
    return value * equave**exponent


def _prime_factors(value: int) -> dict[int, int]:
    """Prime factorization of a positive integer (trial division)."""
    if value < 1:
        raise PianoV3Error("V3_FACTORIZATION_INVALID", str(value))
    factors: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= value:
        while value % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            value //= divisor
        divisor += 1 if divisor == 2 else 2
    if value > 1:
        factors[value] = factors.get(value, 0) + 1
    return factors


def _place_voice(
    ratio: Fraction, generators: list[Fraction], equave: Fraction
) -> tuple[list[int], int] | None:
    """Express ``ratio`` as ``equave**exponent * product(generator**v)``.

    Returns the lattice ``(vector, exponent)`` or ``None`` when the ratio has
    a prime that is neither the equave nor a generator (i.e. it is not a point
    of this lattice).  The equave's prime is folded into the exponent so that
    ``product(generator**vector)`` carries no equave factor; this is exactly the
    convention ``_reduced_anchor_exponent`` inverts, so a voice placed here at
    the anchor reproduces the compiler's anchor exponent.
    """
    if ratio <= 0:
        return None
    numerator = _prime_factors(ratio.numerator)
    denominator = _prime_factors(ratio.denominator)
    primes = sorted(set(numerator) | set(denominator))
    equave_prime = _prime_factors(equave.numerator)
    for prime, power in _prime_factors(equave.denominator).items():
        equave_prime[prime] = equave_prime.get(prime, 0) - power
    generator_primes: list[dict[int, int]] = []
    for generator in generators:
        table = _prime_factors(generator.numerator)
        for prime, power in _prime_factors(generator.denominator).items():
            table[prime] = table.get(prime, 0) - power
        generator_primes.append(table)
    vector = [0] * len(generators)
    exponent = 0
    for prime in primes:
        power = numerator.get(prime, 0) - denominator.get(prime, 0)
        equave_power = equave_prime.get(prime, 0)
        if equave_power:
            if power % equave_power != 0:
                return None
            exponent += power // equave_power
            continue
        matched = False
        for index, table in enumerate(generator_primes):
            generator_power = table.get(prime, 0)
            if generator_power:
                if power % generator_power != 0:
                    return None
                vector[index] += power // generator_power
                matched = True
                break
        if not matched:
            return None
    return vector, exponent


def _odd_part(value: int) -> int:
    while value % 2 == 0:
        value //= 2
    return value


def _odd(value: Fraction, equave: Fraction) -> int:
    reduced = reduce_on_equave(value, equave)[0]
    return max(_odd_part(reduced.numerator), _odd_part(reduced.denominator))


def domain_point_set(
    domain: Mapping[str, Any],
    *,
    maximum_odd_limit: int = V3_MAXIMUM_ODD_LIMIT,
    maximum_complexity_bits: int = V3_MAXIMUM_COMPLEXITY_BITS,
) -> dict[Fraction, tuple[list[int], int]]:
    """The resolver's placed pool as a reduced-ratio lookup.

    Enumerates every (vector, exponent) in the domain and keeps the points
    that pass the odd-limit / complexity-bits filter, keyed by reduced
    ratio.  This is exactly the membership test the GEN0-A resolver applies,
    so a voice whose reduced ratio is in this set resolves with zero error.
    """
    validate_v3_domain(domain)
    equave = Fraction(domain["equave"])
    generators = [Fraction(text) for text in domain["generators"]]
    points: dict[Fraction, tuple[list[int], int]] = {}
    for vector in product(*(range(low, high + 1) for low, high in domain["coordinate_bounds"])):
        for exponent in range(domain["register_bounds"][0], domain["register_bounds"][1] + 1):
            ratio = _vector_ratio(generators, list(vector), equave, exponent)
            reduced = reduce_on_equave(ratio, equave)[0]
            if _odd(ratio, equave) <= maximum_odd_limit:
                bits = reduced.numerator.bit_length() + reduced.denominator.bit_length()
                if bits <= maximum_complexity_bits:
                    points.setdefault(reduced, (list(vector), exponent))
    return points


def _steps_valid(ratios: list[Fraction], window: int) -> bool:
    """The sparse contract: sorted, distinct steps inside the window (root-relative)."""
    if not ratios or window <= 0:
        return False
    base = _mc(ratios[0])
    steps = [round((_mc(ratio) - base) / 100_000) for ratio in ratios]
    return (sorted(steps) == steps and len(set(steps)) == len(steps)
            and all(0 <= step < window for step in steps))


def _variant_pool(
    dictionary_file: Mapping[str, Any],
    voice_counts: list[int],
    equave: Fraction,
) -> list[dict[str, Any]]:
    """Flatten the sealed dictionary into candidate chords with provenance.

    Variants whose root-relative steps are not sorted / distinct / in-window
    are dropped: the exact sparse path requires that step order, so a cadence
    slot bound to such a variant could never compile.
    """
    window = 12 if equave == Fraction(2) else 24 if equave == Fraction(3) else 0
    pool: list[dict[str, Any]] = []
    for key in sorted(dictionary_file["dictionaries"]):
        generator_text, count_text = key.split("/")
        voice_count = int(count_text)
        if voice_count not in voice_counts:
            continue
        dictionary = dictionary_file["dictionaries"][key]
        if int(dictionary["generator"]) != int(generator_text):
            raise PianoV3Error("DICTIONARY_KEY_MISMATCH", key)
        for entry in dictionary["entries"]:
            for variant in entry["variants"]:
                ratios = [Fraction(text) for text in variant["ratios"]]
                reduced = [reduce_on_equave(ratio, equave)[0] for ratio in ratios]
                if not _steps_valid(reduced, window):
                    continue
                pool.append(
                    {
                        "source_chord_key": f"{key}/{','.join(str(i) for i in variant['index_tuple'])}",
                        "generator": int(generator_text),
                        "voice_count": voice_count,
                        "index_tuple": list(variant["index_tuple"]),
                        "ratios": reduced,
                        "template": variant["template"],
                    }
                )
    return pool


def _embeddable(
    variant: Mapping[str, Any],
    function: str,
    equave: Fraction,
    points: Mapping[Fraction, Any],
) -> bool:
    """Whether every voice of the variant placed at ``function`` is a domain point.

    The variant's ratios are root-relative (root = 1/1); placing the root at
    the function position multiplies every voice by the function root.  A
    voice is embeddable iff its reduced absolute ratio is in the placed pool
    (exact membership: the resolver then matches it with zero error).
    """
    root, _ = reduce_on_equave(FUNCTION_ROOTS[function], equave)
    for ratio in variant["ratios"]:
        reduced = reduce_on_equave(root * ratio, equave)[0]
        if reduced not in points:
            return False
    return True


def _voice_leading_ok(
    previous_root: Fraction,
    previous_ratios: list[Fraction],
    root: Fraction,
    ratios: list[Fraction],
    equave: Fraction,
    cap_cents: float,
) -> bool:
    """Sorted-neighbor voice leading within the cap (deterministic).

    Voices are reduced on the equave and sorted by pitch; each voice of the
    shorter chord must land within ``cap_cents`` of its sorted counterpart.
    """
    previous_pitches = sorted(
        _mc(reduce_on_equave(previous_root * ratio, equave)[0]) for ratio in previous_ratios
    )
    new_pitches = sorted(_mc(reduce_on_equave(root * ratio, equave)[0]) for ratio in ratios)
    period = _mc(equave)
    count = min(len(previous_pitches), len(new_pitches))
    for old, new in zip(previous_pitches[:count], new_pitches[:count]):
        distance = abs(new - old) % period
        distance = min(distance, period - distance)
        if distance / 10 > cap_cents:
            return False
    return True


# ---------------------------------------------------------------------------
# Cadence plan


def _slot_expectation(phrase: Mapping[str, Any], local_bar: int) -> str:
    """Map a phrase bar to a cadence expectation (spec §3 slot mapping).

    Final bar of the phrase: home/arrival → arrive, open → open, otherwise
    stable.  The bar before an arrival is prepare.  Mid-phrase bars hold the
    tonic (home/none) or depart toward the phrase's target.
    """
    target = phrase["cadence_target"]
    last = local_bar == phrase["length_bars"] - 1
    if last:
        if target in ("home", "arrival"):
            return "arrive"
        if target == "open":
            return "open"
        return "stable"
    if target in ("home", "arrival") and local_bar == phrase["length_bars"] - 2:
        return "prepare"
    if target in ("arrival", "open", "continuation"):
        return "depart"
    return "stable"


def _stability_profile_from_file(dictionary_file: Mapping[str, Any]) -> StabilityProfile:
    profile = dictionary_file["stability_profile"]
    return StabilityProfile(
        version=profile["version"],
        weights=tuple(profile["weights"]),
        root_proximity_half_width_cents=profile["root_proximity_half_width_cents"],
        voice_movement_half_width_cents=profile["voice_movement_half_width_cents"],
        template_similarity_full_error_cents=profile["template_similarity_full_error_cents"],
        tonic_chord=tuple(profile["tonic_chord"]),
    )


def _thresholds_from_file(dictionary_file: Mapping[str, Any]) -> ClassificationThresholds:
    thresholds = dictionary_file["thresholds"]
    return ClassificationThresholds(
        version=thresholds["version"],
        T_high=thresholds["T_high"],
        D_low=thresholds["D_low"],
        margin=thresholds["margin"],
    )


def _slot_digest(seed: int, section_id: str, slot_id: str, policy_hash: str) -> bytes:
    payload = f"{CADENCE_ALGORITHM_ID}\0{seed}\0{section_id}\0{slot_id}\0{policy_hash}".encode("utf-8")
    return hashlib.sha256(payload).digest()


def _rank_candidates(
    eligible: list[dict[str, Any]],
    function: str,
    equave: Fraction,
    profile: StabilityProfile,
) -> list[tuple[int, dict[str, Any]]]:
    """Rank embeddable variants by stability for the slot's function.

    T slots take the most stable candidates, D slots the least stable, S
    slots the midpoint (spec §3 candidate selection).  Ties break on the
    dictionary address so the order is deterministic.
    """
    root, _ = reduce_on_equave(FUNCTION_ROOTS[function], equave)
    scored: list[tuple[int, dict[str, Any]]] = []
    for variant in eligible:
        value = stability_q(root, list(variant["ratios"]), Fraction(1), equave=equave, profile=profile)
        scored.append((value, variant))
    if function == "T":
        scored.sort(key=lambda item: (-item[0], item[1]["source_chord_key"]))
    elif function == "D":
        scored.sort(key=lambda item: (item[0], item[1]["source_chord_key"]))
    else:
        scored.sort(key=lambda item: (abs(item[0] - 5000), item[1]["source_chord_key"]))
    return scored


def _select_candidate(
    ranked: list[tuple[int, dict[str, Any]]],
    function: str,
    seed: int,
    section_id: str,
    slot_id: str,
    policy: Mapping[str, Any],
    previous_root: Fraction | None,
    previous_ratios: list[Fraction] | None,
    equave: Fraction,
) -> tuple[int, dict[str, Any], bool]:
    """Pick one candidate: domain-separated sample, then the voice-leading cap.

    Returns ``(stability_q, variant, leading_relaxed)``.  The cap is a soft
    preference: when no sampled candidate satisfies it, the best-ranked
    candidate is used and ``leading_relaxed`` records that (never silent).
    """
    budget = policy["candidate_budget"]
    cap = policy["voice_leading_cap_cents"]
    digest = _slot_digest(seed, section_id, slot_id, policy["policy_hash"])
    offset = int.from_bytes(digest[:8], "big") % len(ranked)
    considered = [ranked[(offset + index) % len(ranked)] for index in range(min(budget, len(ranked)))]
    root, _ = reduce_on_equave(FUNCTION_ROOTS[function], equave)
    for value, variant in considered:
        if previous_root is None or previous_ratios is None:
            return value, variant, False
        if _voice_leading_ok(previous_root, previous_ratios, root, list(variant["ratios"]), equave, cap):
            return value, variant, False
    return considered[0][0], considered[0][1], True


def generate_cadence_plan(
    plan: Mapping[str, Any],
    dictionary_file: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    tonic_ratio: Fraction = Fraction(1),
) -> dict[str, Any]:
    """Create a deterministic, dictionary-bound chord decision for every bar.

    The returned object is deliberately separate from ``CompositionPlan``;
    callers must pass it through the v3 lowering path rather than mutating the
    historical plan schema.
    """
    if (plan.get("schema") == "cps.composition-plan"
            and composition_plan_hash(plan) != plan.get("plan_hash")):
        raise PianoV3Error("CADENCE_COMPOSITION_PLAN_HASH_MISMATCH")
    validate_cadence_policy(policy)
    equave = Fraction(policy["equave"])
    if dictionary_file.get("equave") != policy["equave"]:
        raise PianoV3Error("CADENCE_EQUAVE_MISMATCH")
    if seal(dict(dictionary_file), f"harmony-dictionary/{policy['equave']}").get("hash") != dictionary_file.get("hash"):
        raise PianoV3Error("CADENCE_DICTIONARY_SEAL_INVALID")
    dictionary_hash = dictionary_file.get("hash")
    if dictionary_hash != policy["dictionary_hash"]:
        raise PianoV3Error("CADENCE_DICTIONARY_HASH_MISMATCH")
    stability_hash = dictionary_file.get("stability_profile_hash")
    if stability_hash != policy["stability_profile_hash"]:
        raise PianoV3Error("CADENCE_STABILITY_HASH_MISMATCH")
    validate_v3_domain(PIANO_V3_DOMAINS[policy["equave"]])
    pool = _variant_pool(dictionary_file, policy["voice_counts"], equave)
    if not pool:
        raise PianoV3Error("CADENCE_DICTIONARY_EMPTY")
    points = domain_point_set(PIANO_V3_DOMAINS[policy["equave"]])
    profile = _stability_profile_from_file(dictionary_file)
    thresholds = _thresholds_from_file(dictionary_file)
    tonic, _ = reduce_on_equave(tonic_ratio, equave)
    slots: list[dict[str, Any]] = []
    previous_root: Fraction | None = None
    previous_ratios: list[Fraction] | None = None
    section_phrases = [
        (section, phrase)
        for section in plan["sections"]
        for phrase in section["phrases"]
    ]
    if not section_phrases:
        raise PianoV3Error("CADENCE_PLAN_HAS_NO_PHRASES")
    for section, phrase in section_phrases:
        section_id = section["section_id"]
        for local_bar in range(phrase["length_bars"]):
            expectation = _slot_expectation(phrase, local_bar)
            function = FUNCTION_BY_EXPECTATION[expectation]
            root = reduce_on_equave(tonic * FUNCTION_ROOTS[function], equave)[0]
            eligible = [item for item in pool if _embeddable(item, function, equave, points)]
            if not eligible:
                raise PianoV3Error("CADENCE_NO_EMBEDDABLE_VARIANT", f"{section_id}/{phrase['phrase_id']}/{local_bar}")
            ranked = _rank_candidates(eligible, function, equave, profile)
            slot_id = f"{phrase['phrase_id']}/bar/{local_bar}"
            score, variant, relaxed = _select_candidate(
                ranked, function, int(plan["seed"]), section_id, slot_id,
                policy, previous_root, previous_ratios, equave,
            )
            classification = classify_with_context(
                root, list(variant["ratios"]), tonic, equave=equave,
                profile=profile, thresholds=thresholds,
            )
            slots.append({
                "section_id": section_id,
                "phrase_id": phrase["phrase_id"],
                "bar": phrase["start_bar"] + local_bar,
                "bar_in_phrase": local_bar,
                "expectation": expectation,
                "function": function,
                # The canonical SongProgram artifact encoding forbids floats.
                # Preserve the numerical evidence as integer millicents.
                "classification": {
                    "candidate": classification["candidate"],
                    "final": classification["final"],
                    "root_distance_millicents": round(
                        float(classification["root_distance_cents"]) * 1000
                    ),
                    "reasons": list(classification["reasons"]),
                },
                "stability_q": score,
                "source_chord_key": variant["source_chord_key"],
                "generator": variant["generator"],
                "voice_count": variant["voice_count"],
                "index_tuple": variant["index_tuple"],
                "root_vector": FUNCTION_ROOT_VECTORS[policy["equave"]][function],
                "root_ratio": ratio_text(root),
                "ratios": [ratio_text(item) for item in variant["ratios"]],
                "voice_leading_relaxed": relaxed,
                "resolve_into": None,
            })
            previous_root = root
            previous_ratios = list(variant["ratios"])
    for left, right in zip(slots, slots[1:]):
        left["resolve_into"] = f"{right['section_id']}/{right['bar']}"
    cadence = {
        "schema": "cps.piano-cadence-plan",
        "schema_version": SCHEMA_VERSION,
        "source_plan_hash": plan.get("plan_hash") or composition_plan_hash(plan),
        "dictionary_hash": dictionary_hash,
        "stability_profile_hash": stability_hash,
        "thresholds_version": thresholds.version,
        "cadence_algorithm_id": CADENCE_ALGORITHM_ID,
        "policy_hash": policy["policy_hash"],
        "equave": policy["equave"],
        "tonic": {"vector": [0, 0, 0, 0, 0], "ratio": ratio_text(tonic)},
        "slots": slots,
    }
    cadence["cadence_plan_hash"] = _cadence_plan_hash(cadence)
    return cadence


def _cadence_plan_hash(plan: Mapping[str, Any]) -> str:
    body = {key: value for key, value in plan.items() if key != "cadence_plan_hash"}
    return "sha256:" + hashlib.sha256(
        b"cps.piano-cadence-plan/v1\0" + _canonical(body)
    ).hexdigest()


def validate_cadence_plan(plan: Mapping[str, Any]) -> None:
    """Fail closed on altered or incomplete cadence decisions."""
    if (not isinstance(plan, Mapping)
            or plan.get("schema") != "cps.piano-cadence-plan"
            or plan.get("schema_version") != SCHEMA_VERSION
            or not isinstance(plan.get("slots"), list)
            or not plan["slots"]
            or plan.get("cadence_plan_hash") != _cadence_plan_hash(plan)):
        raise PianoV3Error("CADENCE_PLAN_INVALID")
    required = {"section_id", "phrase_id", "bar", "bar_in_phrase", "expectation",
                "function", "classification", "stability_q", "source_chord_key",
                "generator", "voice_count", "index_tuple", "root_vector", "root_ratio",
                "ratios", "voice_leading_relaxed", "resolve_into"}
    seen: set[tuple[str, int]] = set()
    for slot in plan["slots"]:
        if (not isinstance(slot, Mapping) or set(slot) != required
                or slot["expectation"] not in EXPECTATIONS
                or slot["function"] not in {"T", "D", "S"}
                or slot["voice_count"] not in (3, 4)
                or len(slot["ratios"]) != slot["voice_count"]
                or (slot["section_id"], slot["bar"]) in seen):
            raise PianoV3Error("CADENCE_SLOT_INVALID")
        seen.add((slot["section_id"], slot["bar"]))


def _binding_key(source_chord_key: Any) -> tuple[int, int, tuple[int, ...]] | None:
    """(generator, count, index_tuple) from a full sparse source key, or None."""
    if not isinstance(source_chord_key, str):
        return None
    parts = source_chord_key.split("/", 3)
    if len(parts) != 4:
        return None
    try:
        generator, count = int(parts[0]), int(parts[1])
        index_tuple = tuple(int(value) for value in parts[3].split(","))
    except ValueError:
        return None
    return generator, count, index_tuple


def cadence_impact_report(
    cadence_plan: Mapping[str, Any],
    program: Mapping[str, Any] | None = None,
    project: Mapping[str, Any] | None = None,
    *,
    ticks_per_bar: int | None = None,
) -> dict[str, Any]:
    """Report planned and compiled cadence evidence without inferring success.

    When a project is supplied each slot is reconciled *positionally*: the
    slot's ``(section_id, bar)`` maps to a tick range and the harmony
    occurrences that begin in that bar are compared against the slot's
    planned sounding ratios (the function root times the variant's
    root-relative ratios, preserving absolute equave lifts).  A slot matches only when a
    resolved chord in its bar carries exactly those ratios; a global ratio
    match elsewhere in the piece is not evidence for this slot.
    """
    validate_cadence_plan(cadence_plan)
    if ticks_per_bar is None and project is not None:
        clock = project.get("clock", {})
        beats, ticks = clock.get("beats_per_bar"), clock.get("ticks_per_beat")
        if isinstance(beats, int) and isinstance(ticks, int):
            ticks_per_bar = beats * ticks
    chords_by_id = (
        {chord["id"]: chord for chord in project.get("resolved_chords", [])}
        if project is not None else {}
    )
    occurrences_by_slot: dict[tuple[str, int], list[dict[str, Any]]] = {}
    section_start_bars: dict[str, int] = {}
    if program is not None:
        cursor = 0
        for section in program.get("form", []):
            section_start_bars[section["id"]] = cursor
            cursor += section["bars"]
    if project is not None and ticks_per_bar:
        for occurrence in project.get("harmony_occurrences", []):
            absolute_bar = occurrence["start_tick"] // ticks_per_bar
            bar = absolute_bar - section_start_bars.get(occurrence["section_id"], 0)
            occurrences_by_slot.setdefault(
                (occurrence["section_id"], bar), []
            ).append(occurrence)
    rows = []
    for slot in cadence_plan["slots"]:
        row: dict[str, Any] = {"section_id": slot["section_id"], "bar": slot["bar"],
                              "expectation": slot["expectation"], "function": slot["function"],
                              "planned_variant": slot["source_chord_key"],
                              "source_dictionary_hash": cadence_plan["dictionary_hash"],
                              "planned_root_ratio": slot["root_ratio"],
                              "planned_ratios": slot["ratios"],
                              "planned_absolute_ratios": [
                                  ratio_text(Fraction(slot["root_ratio"]) * Fraction(value))
                                  for value in slot["ratios"]
                              ],
                              "status": "planned"}
        slot_key = (slot["generator"], slot["voice_count"], tuple(slot["index_tuple"]))
        bound_intents = []
        if program is not None:
            # A 0.3 program binds the variant by its source key (the slot's
            # short key omits the entry key, so compare by binding identity);
            # a legacy program may only carry an EDO reference.
            bound_intents = [
                intent for intent in program.get("chord_intents", [])
                if _binding_key(intent.get("dictionary_variant", {}).get("source_chord_key")) == slot_key
                and intent.get("dictionary_variant", {}).get("dictionary_hash") == cadence_plan["dictionary_hash"]
            ]
            row["program_bound"] = bool(bound_intents)
            row["program_variant_hashes"] = sorted(
                intent["dictionary_variant"]["variant_hash"] for intent in bound_intents
            )
        if project is not None:
            occurrences = occurrences_by_slot.get((slot["section_id"], slot["bar"]), [])
            chord_ids = sorted({occurrence["resolved_chord_id"] for occurrence in occurrences})
            row["resolved_chord_ids"] = chord_ids
            root = Fraction(slot["root_ratio"])
            expected = sorted(root * Fraction(ratio) for ratio in slot["ratios"])
            matched = False
            for chord_id in chord_ids:
                chord = chords_by_id.get(chord_id)
                if chord is None:
                    continue
                actual = sorted(Fraction(ratio) for ratio in chord["exact_ratios"])
                if actual == expected:
                    matched = True
                row.setdefault("project_chords", []).append({
                    "resolved_chord_id": chord_id,
                    "exact_ratios": chord["exact_ratios"],
                    "anchor_vector": chord.get("anchor_vector"),
                    "ratio_match": actual == expected,
                    "root_vector_match": any(
                        chord.get("anchor_vector") == intent.get("dictionary_variant", {}).get("voices", [{}])[0].get("vector")
                        for intent in bound_intents
                    ) if program is not None else None,
                })
            row["status"] = "matched" if matched else "unmatched"
        rows.append(row)
    return {"schema": "cps.piano-cadence-impact-report", "schema_version": "1.0.0",
            "cadence_plan_hash": cadence_plan["cadence_plan_hash"],
            "program_checked": program is not None, "project_checked": project is not None,
            "ticks_per_bar": ticks_per_bar,
            "slots": rows}


# ---------------------------------------------------------------------------
# V3 lowering: bind the cadence plan to a SongProgram 0.3


def _variant_from_slot(
    slot: Mapping[str, Any],
    dictionary_file: Mapping[str, Any],
    generators: list[Fraction],
    equave: Fraction,
) -> dict[str, Any]:
    """Build a sealed-dictionary ``dictionary_variant`` for one cadence slot.

    The slot's root-relative ratios are multiplied by the function root and
    each voice is placed in the lattice.  Voice 0 is the root, so its placed
    vector becomes the harmony cell's anchor and its exponent reproduces the
    compiler's reduced anchor exponent.
    """
    from .sparse_variant import variant_hash

    root = Fraction(slot["root_ratio"])
    ratios = [root * Fraction(text) for text in slot["ratios"]]
    voices: list[dict[str, Any]] = []
    for ratio in ratios:
        placed = _place_voice(ratio, generators, equave)
        if placed is None:
            raise PianoV3Error("LOWER_VOICE_UNPLACED", ratio_text(ratio))
        vector, exponent = placed
        voices.append({
            "vector": vector, "equave_exponent": exponent,
            "exact_ratio": f"{ratio.numerator}/{ratio.denominator}",
        })
    # The slot's key omits the entry key; exact_sparse_core requires the full
    # generator/count/entry_key/index_tuple form, so recover it from the seal.
    index_tuple = [int(value) for value in slot["index_tuple"]]
    entries = dictionary_file["dictionaries"][
        f"{slot['generator']}/{slot['voice_count']}"
    ]["entries"]
    entry_key = next(
        (entry["key"] for entry in entries
         if any(list(variant["index_tuple"]) == index_tuple
                for variant in entry["variants"])),
        None,
    )
    if entry_key is None:
        raise PianoV3Error("LOWER_VARIANT_NOT_FOUND", slot["source_chord_key"])
    source_chord_key = (
        f"{slot['generator']}/{slot['voice_count']}/{entry_key}/"
        + ",".join(str(value) for value in index_tuple)
    )
    variant = {
        "source_kind": "sealed_dictionary",
        "dictionary_hash": dictionary_file["hash"],
        "source_chord_key": source_chord_key,
        "voices": voices,
    }
    variant["variant_hash"] = variant_hash(variant)
    return {**variant, "anchor_vector": voices[0]["vector"]}


def _chord_intent_from_variant(
    intent_id: str, variant: Mapping[str, Any], lattice: Mapping[str, Any]
) -> dict[str, Any]:
    """A SongProgram 0.3 chord intent bound to a placed sparse variant."""
    equave = lattice["equave"]
    window = 12 if equave == "2/1" else 24 if equave == "3/1" else 0
    ratios = [Fraction(voice["exact_ratio"]) for voice in variant["voices"]]
    base = _mc(ratios[0])
    steps = [round((_mc(ratio) - base) / 100_000) for ratio in ratios]
    if (sorted(steps) != steps or steps[0] != 0
            or len(set(steps)) != len(steps)
            or any(not 0 <= step < window for step in steps)):
        raise PianoV3Error("LOWER_STEPS_INVALID", str(steps))
    return {
        "id": intent_id,
        "reference": {"temperament": "edo", "equave": equave,
                      "divisions": window, "steps": steps},
        "dictionary_variant": {key: value for key, value in variant.items()
                               if key != "anchor_vector"},
        "recognition": {"maximum_pair_error_millicents": 120_000,
                        "maximum_pair_rms_millicents": 120_000},
        "voicing": {"maximum_span_millicents": 2_500_000,
                    "minimum_spacing_millicents": 1,
                    "bass_policy": "preserve_target", "bass_target_ordinal": 0},
        "complexity_budget": 256,
    }


def lower_cadence_plan(
    base_program: Mapping[str, Any],
    cadence_plan: Mapping[str, Any],
    dictionary_file: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the cadence plan's dictionary variants to a SongProgram 0.3.

    The committed v1 lowering supplies the clock, lattice, tracks, melody, and
    form.  This rewrites only the harmony: one clone-on-write cell per bar whose
    single chord intent is bound to the slot's sealed-dictionary variant, plus a
    per-bar downbeat rhythm cell.  The result compiles through the exact sparse
    path and reconciles against ``cadence_impact_report``.
    """
    validate_cadence_plan(cadence_plan)
    program = copy.deepcopy(dict(base_program))
    program["schema_version"] = "0.3.0"
    lattice = program["lattice"]
    if lattice.get("equave") != cadence_plan["equave"]:
        raise PianoV3Error(
            "LOWER_EQUAVE_MISMATCH", f"{lattice.get('equave')} != {cadence_plan['equave']}"
        )
    generators = [Fraction(text) for text in lattice["generators"]]
    equave = Fraction(cadence_plan["equave"])
    clock = program["clock"]
    ticks_per_bar = clock["beats_per_bar"] * clock["ticks_per_beat"]
    # Drop the base's harmony cells/realizations; keep melody, rhythm, tracks.
    program["materials"] = [
        material for material in program["materials"]
        if material.get("kind") != "harmony_intent_cell"
    ]
    program["realizations"] = [
        realization for realization in program["realizations"]
        if realization.get("track_id") != "harmony"
    ]
    program["chord_intents"] = []
    rhythm_id = "rhy_v3_bar"
    program["materials"].append({
        "id": rhythm_id, "kind": "rhythm_cell", "length_ticks": ticks_per_bar,
        "steps": [{"at_tick": 0, "duration_ticks": ticks_per_bar,
                   "accent_q": 10_000, "lane_id": None}],
    })
    slots_by_section: dict[str, list[dict[str, Any]]] = {}
    for slot in cadence_plan["slots"]:
        slots_by_section.setdefault(slot["section_id"], []).append(slot)
    for section in program["form"]:
        section_id = section["id"]
        slots = sorted(slots_by_section.get(section_id, []), key=lambda item: item["bar"])
        for slot in slots:
            # CadencePlan bars are section-relative.  Keeping that convention
            # makes the slot identity stable when earlier sections change size.
            local_bar = slot["bar"]
            if not 0 <= local_bar < section["bars"]:
                raise PianoV3Error("LOWER_SLOT_OUT_OF_RANGE", f"{section_id}/{slot['bar']}")
            variant = _variant_from_slot(slot, dictionary_file, generators, equave)
            suffix = f"{section_id}_{local_bar:02d}"
            intent_id = f"ci_v3_{suffix}"
            program["chord_intents"].append(
                _chord_intent_from_variant(intent_id, variant, lattice)
            )
            cell_id = f"mat_v3_{suffix}"
            program["materials"].append({
                "id": cell_id, "kind": "harmony_intent_cell", "rhythm_id": rhythm_id,
                "root_anchors": [variant["anchor_vector"]],
                "anchor_equave_exponent": variant["voices"][0]["equave_exponent"],
                "chord_intent_ids": [intent_id], "mapping": "zip",
            })
            program["realizations"].append({
                "id": f"real_v3_{suffix}", "section_id": section_id,
                "track_id": "harmony", "material_id": cell_id,
                "at_tick": local_bar * ticks_per_bar, "repeat": 1,
                "every_ticks": ticks_per_bar, "rhythm_transforms": [],
                "pitch_transforms": [], "velocity_scale_q": 10_000,
                "gate_scale_q": 10_000,
            })
    return program


# ---------------------------------------------------------------------------
# GEN0-B sparse charge receipt


def sparse_charge_receipt(
    declared_voices: int,
    rectangular_coordinate_points: int,
    rectangular_placed_points: int,
    *,
    maximum_declared_voices: int = 64,
    coordinate_budget: int = GEN0B_COORDINATE_BUDGET,
    placed_budget: int = GEN0B_PLACED_BUDGET,
) -> dict[str, Any]:
    """Sparse candidate cardinality budget assessment for experimental trials.

    The rectangular domain is a legacy navigation/charging domain; the sparse
    path charges declared voices, never the Cartesian product of axis ranges.
    This checks the rectangular limits (1024 coordinate / 4096 placed) and
    declared voice cap. It does not run the GEN0-B logical opcode emitter or
    establish a conformance charge receipt for the sparse resolver.
    """
    quantities = (declared_voices, rectangular_coordinate_points,
                  rectangular_placed_points, maximum_declared_voices,
                  coordinate_budget, placed_budget)
    if any(type(value) is not int or value < 0 for value in quantities):
        raise PianoV3Error("SPARSE_CHARGE_INVALID")
    if not all(value > 0 for value in quantities[3:]):
        raise PianoV3Error("SPARSE_CHARGE_INVALID")
    within_coordinate = rectangular_coordinate_points <= coordinate_budget
    within_placed = rectangular_placed_points <= placed_budget
    within_voices = declared_voices <= maximum_declared_voices
    body = {
        "contract": "trial-sparse-bounds/v1",
        "scope": "bounds_only_not_gen0b_opcode_receipt",
        "declared_voices": declared_voices,
        "maximum_declared_voices": maximum_declared_voices,
        "rectangular_coordinate_points": rectangular_coordinate_points,
        "rectangular_placed_points": rectangular_placed_points,
        "coordinate_budget": coordinate_budget,
        "placed_budget": placed_budget,
        "within_coordinate_budget": within_coordinate,
        "within_placed_budget": within_placed,
        "within_voice_budget": within_voices,
        "accepted": within_coordinate and within_placed and within_voices,
    }
    receipt = dict(body)
    receipt["receipt_hash"] = "sha256:" + hashlib.sha256(
        b"cps.trial-sparse-bounds/v1\0" + _canonical(body)
    ).hexdigest()
    return receipt
