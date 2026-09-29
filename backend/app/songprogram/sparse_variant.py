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
