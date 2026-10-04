"""Versioned exact sparse chord binding for SongProgram 0.3.

The rectangular domain remains a legacy navigation/charging domain.  Sparse
voices are separately charged by their declared count, never by a Cartesian
product of axis search ranges.  This binding does not infer acoustic function.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from itertools import combinations
from math import isqrt
from typing import Any, Mapping

from .resolver import _complexity, _mc, _odd, _reduce

MAX_SPARSE_VOICES = 64


def variant_hash(variant: dict) -> str:
    body = {key: value for key, value in variant.items() if key != "variant_hash"}
    return "sha256:" + hashlib.sha256(
        b"cps.sparse-dictionary-variant/v1\0"
        + json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def exact_sparse_core(lattice: dict, intent: dict, anchor: list[int], anchor_exponent: int,
                      dictionary_authorities: dict | None = None) -> dict:
    """Validate each placed voice before making a single exact progression core."""
    from .compiler import CompileError

    def invalid() -> None:
        raise CompileError("SPARSE_VARIANT_INVALID")

    variant = intent.get("dictionary_variant")
    source_kind = variant.get("source_kind") if isinstance(variant, dict) else None
    expected_fields = {"source_kind", "source_chord_key", "voices", "variant_hash"}
    if source_kind == "sealed_dictionary":
        expected_fields.add("dictionary_hash")
    if not isinstance(variant, dict) or set(variant) != expected_fields:
        invalid()
    if (source_kind not in ("axis_search_candidate", "sealed_dictionary")
            or not isinstance(variant["source_chord_key"], str)
            or (source_kind == "axis_search_candidate" and not variant["source_chord_key"].startswith("axis-search/"))):
        invalid()
    if variant["variant_hash"] != variant_hash(variant):
        raise CompileError("SPARSE_VARIANT_HASH_MISMATCH")
    voices = variant["voices"]
    steps = intent["reference"]["steps"]
    window = 12 if lattice["equave"] == "2/1" else 24 if lattice["equave"] == "3/1" else 0
    if (not isinstance(voices, list) or not 3 <= len(voices) <= 4
            or len(voices) > MAX_SPARSE_VOICES or len(steps) != len(voices)
            or sorted(steps) != steps or steps[0] != 0
            or len(set(steps)) != len(steps) or any(type(step) is not int or not 0 <= step < window for step in steps)
            or intent["reference"]["equave"] != lattice["equave"]
            or intent["reference"]["divisions"] != window):
        invalid()
    equave = Fraction(lattice["equave"])
    generators = [Fraction(item) for item in lattice["generators"]]
    ratios = []
    vectors = []
    exponents = []
    for index, voice in enumerate(voices):
        if not isinstance(voice, dict) or set(voice) != {"vector", "equave_exponent", "exact_ratio"}:
            invalid()
        vector, exponent, text = voice["vector"], voice["equave_exponent"], voice["exact_ratio"]
        if (not isinstance(vector, list) or len(vector) != len(generators)
                or any(type(value) is not int or abs(value) > 256 for value in vector)
                or type(exponent) is not int or not -32 <= exponent <= 32
                or not isinstance(text, str)):
            invalid()
        try:
            ratio = Fraction(text)
            computed = equave**exponent
            for generator, power in zip(generators, vector, strict=True):
                computed *= generator**power
        except (ValueError, ZeroDivisionError, OverflowError):
            invalid()
        if ratio <= 0 or text != f"{ratio.numerator}/{ratio.denominator}" or ratio != computed:
            invalid()
        reduced = _reduce(ratio, equave)
        if (_odd(ratio, equave) > lattice["maximum_odd_limit"]
                or reduced.numerator.bit_length() + reduced.denominator.bit_length()
                > lattice["maximum_reduced_complexity_bits"]):
            raise CompileError("SPARSE_VARIANT_FILTER_REJECTED")
        if index == 0 and (vector != anchor or exponent != anchor_exponent):
            raise CompileError("SPARSE_VARIANT_ANCHOR_MISMATCH")
        ratios.append(ratio)
        vectors.append(vector)
        exponents.append(exponent)
    if len(set(ratios)) != len(ratios):
        invalid()
    if source_kind == "sealed_dictionary":
        authority = (dictionary_authorities or {}).get(variant["dictionary_hash"])
        if authority is None or authority.get("hash") != variant["dictionary_hash"] or authority.get("equave") != lattice["equave"]:
            raise CompileError("SPARSE_DICTIONARY_AUTHORITY_MISSING")
        # Recompute the seal even if the caller supplied a mutable Python dict.
        from app.harmony_dictionary.storage import seal
        if seal(authority, "harmony-dictionary/" + lattice["equave"])["hash"] != authority["hash"]:
            raise CompileError("SPARSE_DICTIONARY_HASH_MISMATCH")
        try:
            generator, count, entry_key, indices = variant["source_chord_key"].split("/", 3)
            entries = authority["dictionaries"][f"{generator}/{count}"]["entries"]
            entry = next(item for item in entries if item["key"] == entry_key)
            selected = next(item for item in entry["variants"]
                            if item["index_tuple"] == [int(value) for value in indices.split(",")])
        except (KeyError, StopIteration, ValueError, TypeError) as error:
            raise CompileError("SPARSE_DICTIONARY_KEY_INVALID") from error
        if (int(count) != len(voices) or int(generator) not in [int(g) for g in generators]
                or [ratio / ratios[0] for ratio in ratios]
                != [Fraction(text) for text in selected["ratios"]]):
            raise CompileError("SPARSE_DICTIONARY_VARIANT_MISMATCH")
    # Steps are absolute semitones in [0,23], not phase classes modulo 12.
    errors = [_mc(ratios[right] / ratios[left]) - (steps[right] - steps[left]) * 100_000
              for left, right in combinations(range(len(voices)), 2)]
    maximum = max(map(abs, errors))
    squared = sum(error * error for error in errors)
    floor = isqrt(squared // len(errors))
    rms = floor + int(4 * squared >= len(errors) * (2 * floor + 1) ** 2)
    complexity = _complexity(tuple(ratios), equave)
    if (maximum > intent["recognition"]["maximum_pair_error_millicents"]
            or rms > intent["recognition"]["maximum_pair_rms_millicents"]
            or complexity > intent["complexity_budget"]):
        raise CompileError("SPARSE_VARIANT_INTENT_REJECTED")
    cents = [_mc(ratio) for ratio in ratios]
    if (max(cents) - min(cents) > intent["voicing"]["maximum_span_millicents"]
            or any(abs(right - left) < intent["voicing"]["minimum_spacing_millicents"]
                   for left, right in combinations(cents, 2))
            or (intent["voicing"]["bass_policy"] == "preserve_target"
                and cents.index(min(cents)) != intent["voicing"]["bass_target_ordinal"])):
        raise CompileError("SPARSE_VARIANT_VOICING_REJECTED")
    return {
        "vectors": vectors, "equave_exponents": exponents,
        "exact_ratios": [str(ratio.numerator) + "/" + str(ratio.denominator) for ratio in ratios],
        "canonical_steps": steps, "pair_errors_millicents": errors,
        "pair_max_millicents": maximum, "pair_rms_millicents": rms,
        "complexity_score": complexity,
    }


# ---------------------------------------------------------------------------
# Versioned bounded register-lift policy


REGISTER_LIFT_POLICY_SCHEMA = "cps.register-lift-policy"
REGISTER_LIFT_POLICY_VERSION = "1.0.0"
REGISTER_LIFT_POLICY_ID = "piano-v3-register-lift/v1"


class RegisterLiftPolicyError(ValueError):
    """A stable register-lift policy failure with a machine-readable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def register_lift_policy_hash(policy: Mapping[str, Any]) -> str:
    body = {key: value for key, value in policy.items() if key != "policy_hash"}
    digest = hashlib.sha256(
        b"cps.register-lift-policy/v1\0" + _canonical(body)
    ).hexdigest()
    return "sha256:" + digest


def build_register_lift_policy(
    *, allow_lifts: bool = False, max_lift: int = 1, max_variants: int = 8
) -> dict[str, Any]:
    """Assemble the (unsealed) versioned register-lift policy body.

    ``allow_lifts=False`` is the default and reproduces the exact-only path
    byte for byte; the policy object is what the trial records as provenance.
    """
    policy = {
        "schema": REGISTER_LIFT_POLICY_SCHEMA,
        "schema_version": REGISTER_LIFT_POLICY_VERSION,
        "policy_id": REGISTER_LIFT_POLICY_ID,
        "allow_lifts": allow_lifts,
        "max_lift": max_lift,
        "max_variants": max_variants,
        "policy_hash": "",
    }
    policy["policy_hash"] = register_lift_policy_hash(policy)
    return policy


def validate_register_lift_policy(policy: Mapping[str, Any]) -> None:
    """Fail closed on a malformed or tampered register-lift policy."""
    required = {
        "schema", "schema_version", "policy_id", "allow_lifts",
        "max_lift", "max_variants", "policy_hash",
    }
    if not isinstance(policy, Mapping) or set(policy) != required:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_FIELDS_INVALID")
    if policy["schema"] != REGISTER_LIFT_POLICY_SCHEMA:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_SCHEMA_INVALID")
    if policy["schema_version"] != REGISTER_LIFT_POLICY_VERSION:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_VERSION_UNSUPPORTED")
    if policy["policy_id"] != REGISTER_LIFT_POLICY_ID:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_ID_UNSUPPORTED")
    if not isinstance(policy["allow_lifts"], bool):
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_FLAGS_INVALID")
    if type(policy["max_lift"]) is not int or not 0 <= policy["max_lift"] <= 8:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_CAP_INVALID")
    if type(policy["max_variants"]) is not int or not 1 <= policy["max_variants"] <= MAX_SPARSE_VOICES:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_CAP_INVALID")
    if register_lift_policy_hash(policy) != policy["policy_hash"]:
        raise RegisterLiftPolicyError("REGISTER_LIFT_POLICY_HASH_MISMATCH")


def sparse_core_variants(
    lattice: dict, intent: dict, anchor: list[int], anchor_exponent: int,
    dictionary_authorities: dict | None = None, policy: dict | None = None,
) -> list[dict]:
    """Exact sparse core plus bounded register-lift variants for voice leading.

    The exact core (voice 0 pinned to the anchor) is always first. When
    ``policy`` allows lifts, each non-root voice is shifted by +/-1..max_lift
    equaves; a lift is kept only if the resulting ratios still satisfy the
    intent's pair-error, span, spacing, and complexity constraints and every
    exponent stays within the lattice bounds.  Pair errors are measured
    **absolutely** against the intent's reference steps -- the same contract
    ``exact_sparse_core`` enforces (canonical_steps are absolute reference
    steps).  A whole-equave lift therefore grows the absolute pair error by one
    full equave: an octave lift adds 1,200,000 mc and a tritave lift adds
    1,901,955 mc -- both far over the 120,000 pair-error budget, so no register
    lift is a candidate under the absolute contract (only the exact core
    survives).  This preserves the SongProgram 0.3 absolute eligibility meaning:
    a lift that would violate the pair-error budget is excluded, never silently
    wrapped back into range.  The policy provides the *mechanism* for register
    alternatives, but the absolute budget excludes every lift; it is the
    crossing edge-matching policy (not lifts) that repairs voice crossings.
    """
    exact = exact_sparse_core(lattice, intent, anchor, anchor_exponent, dictionary_authorities)
    variants = [exact]
    if policy is None:
        return variants
    validate_register_lift_policy(policy)
    if not policy["allow_lifts"]:
        return variants
    max_lift = policy["max_lift"]
    max_variants = policy["max_variants"]
    equave = Fraction(lattice["equave"])
    generators = [Fraction(item) for item in lattice["generators"]]
    steps = intent["reference"]["steps"]
    base_vectors = [list(vector) for vector in exact["vectors"]]
    base_exponents = list(exact["equave_exponents"])

    def _ratios_for(exponents: list[int]) -> list[Fraction]:
        ratios = []
        for vector, exponent in zip(base_vectors, exponents):
            value = equave ** exponent
            for generator, power in zip(generators, vector):
                value *= generator ** power
            ratios.append(value)
        return ratios

    def _metrics(ratios: list[Fraction]) -> tuple[list[int], int, int, int]:
        # Absolute pair error against the intent's reference steps -- the same
        # contract ``exact_sparse_core`` enforces (canonical_steps are absolute
        # reference steps, and the pair-error budget is absolute).  A register
        # lift shifts a voice by whole equaves, so the absolute error grows with
        # the lift; a lift that would exceed the intent's pair-error / rms budget
        # is rejected rather than silently wrapped back into range modulo the
        # equave (which would let a whole-tritave lift masquerade as in-budget).
        errors = [
            _mc(ratios[right] / ratios[left]) - (steps[right] - steps[left]) * 100_000
            for left, right in combinations(range(len(ratios)), 2)
        ]
        maximum = max(map(abs, errors))
        squared = sum(error * error for error in errors)
        floor = isqrt(squared // len(errors))
        rms = floor + int(4 * squared >= len(errors) * (2 * floor + 1) ** 2)
        return errors, maximum, rms, _complexity(tuple(ratios), equave)

    def _constraints_ok(ratios: list[Fraction]) -> bool:
        if len(set(ratios)) != len(ratios):
            return False
        errors, maximum, rms, complexity = _metrics(ratios)
        if (maximum > intent["recognition"]["maximum_pair_error_millicents"]
                or rms > intent["recognition"]["maximum_pair_rms_millicents"]
                or complexity > intent["complexity_budget"]):
            return False
        cents = [_mc(ratio) for ratio in ratios]
        return not (
            max(cents) - min(cents) > intent["voicing"]["maximum_span_millicents"]
            or any(abs(right - left) < intent["voicing"]["minimum_spacing_millicents"]
                   for left, right in combinations(cents, 2))
            or (intent["voicing"]["bass_policy"] == "preserve_target"
                and cents.index(min(cents)) != intent["voicing"]["bass_target_ordinal"])
        )

    seen = {tuple(exact["exact_ratios"])}
    for index in range(1, len(base_vectors)):
        if len(variants) >= max_variants:
            break
        for delta in range(-max_lift, max_lift + 1):
            if delta == 0 or len(variants) >= max_variants:
                continue
            exponents = list(base_exponents)
            exponents[index] += delta
            if any(not -32 <= exponent <= 32 for exponent in exponents):
                continue
            ratios = _ratios_for(exponents)
            if not _constraints_ok(ratios):
                continue
            key = tuple(str(r.numerator) + "/" + str(r.denominator) for r in ratios)
            if key in seen:
                continue
            seen.add(key)
            errors, maximum, rms, complexity = _metrics(ratios)
            variants.append({
                "vectors": [list(vector) for vector in base_vectors],
                "equave_exponents": exponents,
                "exact_ratios": [str(r.numerator) + "/" + str(r.denominator) for r in ratios],
                "canonical_steps": list(steps),
                "pair_errors_millicents": errors,
                "pair_max_millicents": maximum,
                "pair_rms_millicents": rms,
                "complexity_score": complexity,
            })
    return variants[:max_variants]
