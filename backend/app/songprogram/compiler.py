"""Deterministic SP0 direct-vector compiler vertical slice."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any

from .resolver import resolve_joint_bnb, resolve_progression


class CompileError(ValueError):
    def __init__(self, code: str, pointer: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.pointer = pointer


_PROGRAM_PROJECT_VERSIONS = {"0.1.0": "1.2.0", "0.2.0": "1.3.0"}
_MAX_LATTICE_DIMENSIONS = 5


def _validate_lattice_dimensions(program: dict[str, Any]) -> None:
    """Reject ambiguous vector lengths and unbounded Cartesian domains early."""
    lattice = program.get("lattice", {})
    generators = lattice.get("generators")
    bounds = lattice.get("coordinate_bounds")
    if not isinstance(generators, list) or not isinstance(bounds, list):
        raise CompileError("LATTICE_DOMAIN_INVALID", "/lattice")
    dimension = len(generators)
    version_limit = 3 if program.get("schema_version") == "0.1.0" else _MAX_LATTICE_DIMENSIONS
    if not 1 <= dimension <= version_limit or len(bounds) != dimension:
        raise CompileError("VECTOR_DIMENSION_MISMATCH", "/lattice")
    try:
        generator_values = [_ratio(value) for value in generators]
        equave = _ratio(lattice.get("equave"))
    except (CompileError, TypeError) as error:
        raise CompileError("LATTICE_DOMAIN_INVALID", "/lattice/generators") from error
    if len(set(generator_values)) != dimension or equave in generator_values:
        raise CompileError("LATTICE_GENERATORS_DEGENERATE", "/lattice/generators")
    if any(
        not isinstance(bound, list)
        or len(bound) != 2
        or type(bound[0]) is not int
        or type(bound[1]) is not int
        or bound[0] > bound[1]
        for bound in bounds
    ):
        raise CompileError("LATTICE_DOMAIN_INVALID", "/lattice/coordinate_bounds")
    cardinality = math.prod(high - low + 1 for low, high in bounds)
    maximum = lattice.get("pitch_exploration", {}).get("maximum_domain_points")
    if type(maximum) is not int or cardinality > maximum:
        raise CompileError("LATTICE_DOMAIN_TOO_LARGE", "/lattice/coordinate_bounds")

    vectors: list[tuple[str, Any]] = []
    vectors.extend((f"/form/{index}/tonal_center", row.get("tonal_center")) for index, row in enumerate(program.get("form", [])))
    for material_index, material in enumerate(program.get("materials", [])):
        for field in ("vectors", "root_anchors"):
            vectors.extend(
                (f"/materials/{material_index}/{field}/{index}", vector)
                for index, vector in enumerate(material.get(field, []))
            )
    for pointer, vector in vectors:
        if not isinstance(vector, list) or len(vector) != dimension:
            raise CompileError("VECTOR_DIMENSION_MISMATCH", pointer)


@dataclass(frozen=True)
class CompilerIdentity:
    build_id: str
    resolver_build_id: str
    resolver_profile_hash: str
    budget_profile_digest: str
    instrument_catalog_digest: str
    numeric_contract: str = "cps-numeric/decimal-log2-rhe-v1"


def _reduced_anchor_exponent(lattice: dict[str, Any], anchor: list[int]) -> int:
    """Equave exponent that keeps the anchor within one octave of 1/1.

    A lattice anchor is a sum of (possibly distant) tonal-center and root
    coordinates; left unreduced its absolute pitch can drift many octaves from
    the reference and push every voice of the chord out of register.  Reducing
    it mod equave pins the chord to the reference register while preserving the
    exact intervallic content (the voices keep their lattice vectors).
    """
    if not lattice.get("reduce_anchor_mod_equave"):
        return 0
    equave = Fraction(lattice["equave"])
    value = Fraction(1)
    for generator, power in zip(lattice["generators"], anchor):
        value *= Fraction(generator) ** power
    exponent = 0
    while value >= equave:
        value /= equave
        exponent -= 1
    while value < 1:
        value *= equave
        exponent += 1
    return exponent


def resolve_single_harmony(
    program: dict[str, Any], intent: dict[str, Any], anchor: list[int]
) -> dict[str, Any]:
    """Build the frozen GEN0-A query and return its sole canonical winner.

    Lowering deliberately stays separate so no caller can substitute a
    per-note nearest fallback for the exact joint result.
    """
    lattice = program["lattice"]
    query = {
        "schema": "cps.sp0-oracle-query/v1",
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "domain": {
            "equave": lattice["equave"],
            "generators": lattice["generators"],
            "coordinate_bounds": lattice["coordinate_bounds"],
            "register_bounds": lattice["register_bounds"],
            "maximum_odd_limit": lattice["maximum_odd_limit"],
            "maximum_reduced_complexity_bits": lattice["pitch_exploration"][
                "maximum_reduced_complexity_bits"
            ],
        },
        "intent": {
            "reference_equave": intent["reference"]["equave"],
            "reference_divisions": intent["reference"].get("divisions"),
            "steps": intent["reference"].get("steps"),
            **({"ratios": intent["reference"]["ratios"]} if intent["reference"].get("ratios") else {}),
            "bass_policy": intent["voicing"]["bass_policy"],
            "bass_target_ordinal": intent["voicing"]["bass_target_ordinal"],
            "minimum_spacing_millicents": intent["voicing"]["minimum_spacing_millicents"],
            "maximum_span_millicents": intent["voicing"]["maximum_span_millicents"],
            "maximum_pair_error_millicents": intent["recognition"]["maximum_pair_error_millicents"],
            "maximum_pair_rms_millicents": intent["recognition"]["maximum_pair_rms_millicents"],
            "complexity_budget": intent["complexity_budget"],
        },
        "anchor": {
            "vector": anchor,
            "equave_exponent": _reduced_anchor_exponent(lattice, anchor),
        },
    }
    results = resolve_joint_bnb(query, 1)
    if not results:
        raise CompileError("NO_JOINT_CHORD_SOLUTION")
    return results[0]


def _harmony_query(
    program: dict[str, Any], intent: dict[str, Any], anchor: list[int]
) -> dict[str, Any]:
    """Lower one SongProgram chord occurrence to the frozen GEN0-A query."""
    lattice = program["lattice"]
    return {
        "schema": "cps.sp0-oracle-query/v1",
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "domain": {
            "equave": lattice["equave"],
            "generators": lattice["generators"],
            "coordinate_bounds": lattice["coordinate_bounds"],
            "register_bounds": lattice["register_bounds"],
            "maximum_odd_limit": lattice["maximum_odd_limit"],
            "maximum_reduced_complexity_bits": lattice["pitch_exploration"][
                "maximum_reduced_complexity_bits"
            ],
        },
        "intent": {
            "reference_equave": intent["reference"]["equave"],
            "reference_divisions": intent["reference"].get("divisions"),
            "steps": intent["reference"].get("steps"),
            **({"ratios": intent["reference"]["ratios"]} if intent["reference"].get("ratios") else {}),
            "bass_policy": intent["voicing"]["bass_policy"],
            "bass_target_ordinal": intent["voicing"]["bass_target_ordinal"],
            "minimum_spacing_millicents": intent["voicing"]["minimum_spacing_millicents"],
            "maximum_span_millicents": intent["voicing"]["maximum_span_millicents"],
            "maximum_pair_error_millicents": intent["recognition"]["maximum_pair_error_millicents"],
            "maximum_pair_rms_millicents": intent["recognition"]["maximum_pair_rms_millicents"],
            "complexity_budget": intent["complexity_budget"],
        },
        "anchor": {
            "vector": anchor,
            "equave_exponent": _reduced_anchor_exponent(lattice, anchor),
        },
    }


# Fraction of the 256 hash values that select the dissonant (second-closest)
# realization over the pure (closest) one. 128 gives a 50/50 split.
_DISSONANT_HASH_THRESHOLD = 128


def _select_realization(
    query_key: bytes, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Hash-addressed choice between the pure and dissonant realizations.

    The closest lattice chord is the pure-just realization; the second-closest
    is a near-miss that sounds slightly dissonant. Selecting between them by a
    hash of the query keeps the choice deterministic per (intent, anchor) while
    varying across chords, so both cases appear in the output. In progression
    handling both realizations carry the same intent identity, so switching
    between them is not a chord change.
    """
    if len(candidates) < 2:
        return candidates[0]
    digest = hashlib.sha256(b"cps.harmony-realization/v1\0" + query_key).digest()
    return candidates[1] if digest[0] < _DISSONANT_HASH_THRESHOLD else candidates[0]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(prefix: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(prefix + _canonical(value)).hexdigest()


def _b32(payload: bytes, length: int) -> str:
    return base64.b32encode(hashlib.sha256(payload).digest()).decode().lower().rstrip("=")[:length]


def _rhe(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    return sign * (
        quotient
        + int(
            remainder * 2 > value.denominator
            or (remainder * 2 == value.denominator and quotient % 2 == 1)
        )
    )


def _ratio(text: str) -> Fraction:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise CompileError("RATIO_INVALID") from error
    if value <= 0 or text != f"{value.numerator}/{value.denominator}":
        raise CompileError("RATIO_NOT_REDUCED")
    return value


def _ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _mc(value: Fraction) -> int:
    with localcontext() as context:
        context.prec = 112
        result = (
            Decimal(1_200_000)
            * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln())
            / Decimal(2).ln()
        )
        return int(result.to_integral_value(rounding=ROUND_HALF_EVEN))


def _vector_ratio(
    generators: list[Fraction], vector: list[int], equave: Fraction, exponent: int
) -> Fraction:
    value = Fraction(1)
    for generator, power in zip(generators, vector, strict=True):
        value *= generator**power
    return value * equave**exponent


def _semantic_address(
    section: str,
    realization: str,
    repeat: int,
    material: str,
    step: int,
    voice: int = 0,
) -> str:
    core = ["cps.semantic-address", 1, section, realization, repeat, material, step, voice]
    return "sa_" + _b32(_canonical(core), 26)


def _harmony_occurrence_id(
    section: str, realization: str, repeat: int, material: str, step: int
) -> str:
    core = [section, realization, repeat, material, step]
    return "hoc_" + _b32(b"cps.harmony-query-occurrence/v1\0" + _canonical(core) + b"\n", 26)


def _core_hash(chord: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            b"cps.resolved-chord/v1\0"
            + _canonical({key: value for key, value in chord.items() if key != "id"})
        ).hexdigest()
    )


def _chord_from_core(
    core: dict[str, Any],
    *,
    lattice: dict[str, Any],
    intent: dict[str, Any],
    anchor: list[int],
    identity: CompilerIdentity,
) -> dict[str, Any]:
    offsets = [
        [coordinate - origin for coordinate, origin in zip(vector, anchor, strict=True)]
        for vector in core["vectors"]
    ]
    chord = {
        "id": "",
        "domain_hash": lattice["domain_hash"],
        "intent_hash": _sha(b"cps.chord-intent/v1\0", intent),
        "resolver_build_id": identity.resolver_build_id,
        "numeric_contract": identity.numeric_contract,
        "search_completeness": "exact",
        "reference_equave": intent["reference"]["equave"],
        "reference_divisions": intent["reference"].get("divisions"),
        "canonical_steps": core["canonical_steps"],
        "eligibility_contract": {
            **intent["voicing"],
            **intent["recognition"],
            "complexity_budget": intent["complexity_budget"],
        },
        "anchor_vector": anchor,
        "voice_offsets": offsets,
        "equave_exponents": core["equave_exponents"],
        "exact_ratios": core["exact_ratios"],
        "target_voice_ordinals": list(range(len(core["vectors"]))),
        "pair_errors_millicents": core["pair_errors_millicents"],
        "maximum_pair_error_millicents": core["pair_max_millicents"],
        "pair_rms_error_millicents": core["pair_rms_millicents"],
        "complexity_score": core["complexity_score"],
    }
    chord["id"] = _resolved_chord_id(chord)
    return chord


def _progression_candidate(chord: dict[str, Any]) -> dict[str, Any]:
    voices = []
    for shape, target in enumerate(chord["target_voice_ordinals"]):
        vector = [
            a + b
            for a, b in zip(chord["anchor_vector"], chord["voice_offsets"][shape], strict=True)
        ]
        voices.append(
            {
                "target_ordinal": target,
                "absolute_vector": vector,
                "equave_exponent": chord["equave_exponents"][shape],
                "exact_ratio": chord["exact_ratios"][shape],
                "ratio_millicents": _mc(_ratio(chord["exact_ratios"][shape])),
            }
        )
    voices.sort(
        key=lambda voice: (
            voice["ratio_millicents"],
            voice["target_ordinal"],
            voice["absolute_vector"],
            voice["equave_exponent"],
            voice["exact_ratio"],
        )
    )
    return {
        "core_hash": _core_hash(chord),
        "resolved_chord": chord,
        "domain_hash": chord["domain_hash"],
        "intent_hash": chord["intent_hash"],
        "anchor_vector": chord["anchor_vector"],
        "voices": voices,
        "local_pair_rms_millicents": chord["pair_rms_error_millicents"],
        "local_pair_max_millicents": chord["maximum_pair_error_millicents"],
        "local_complexity": chord["complexity_score"],
    }


# Piano-solo harmony instrument: the only chord part that gets humanized.
_PIANO_HARMONY_INSTRUMENT = "piano_solo_harmony"
# Rolled-chord timing: base step (ticks) between successive voices plus the
# jitter range. Kept small so the per-measure rest-count rule still holds.
_HUMANIZE_ROLL_STEP = 2
_HUMANIZE_JITTER_RANGE = 3
# A voice is dropped (a rest) with this probability; rare enough that the
# melody line keeps every measure sounding.
_HUMANIZE_DROP_NUMERATOR = 12
_HUMANIZE_DROP_DENOMINATOR = 256


def _humanize_chord_onsets(draft_id: str, voice_count: int) -> list[tuple[int, bool]]:
    """Per-voice ``(onset_offset_ticks, dropped)`` for a humanized chord.

    Seeded by the draft identity so the humanization is deterministic per
    program but varies across chords.  Voices are rolled (lower voices start
    first) with a small jitter, and a rare voice is dropped to insert rests.
    """
    digest = hashlib.sha256(
        b"cps.piano-humanize/v1\0" + draft_id.encode("utf-8")
    ).digest()
    result: list[tuple[int, bool]] = []
    for index in range(voice_count):
        roll = index * _HUMANIZE_ROLL_STEP
        jitter = digest[(index * 7 + 1) % 32] % _HUMANIZE_JITTER_RANGE
        dropped = digest[(index * 7 + 2) % 32] < _HUMANIZE_DROP_NUMERATOR
        result.append((roll + jitter, dropped))
    return result


# Piano-solo melody instrument: the only melody part that gets figuration.
_PIANO_MELODY_INSTRUMENT = "piano_solo_melody"
# Melody figuration relation types and their selection weights (out of 256).
# chord_member keeps the arpeggiated core; passing/neighbor add stepwise
# figuration; scale_degree adds tonal-scale motion.
_MELODY_FIGURATION = (
    ("chord_member", 128),
    ("passing", 64),
    ("neighbor", 32),
    ("scale_degree", 32),
)
# A whole tone (9/8 ≈ 204 cents) is the default step for passing/neighbor.
_MELODY_STEP_MC = 204_000
# 12-TET step for scale-degree figuration.
_MELODY_TET_STEP_MC = 100_000
# Search window (± millicents) around the previous note for figuration.  One
# octave is wide enough that the sparse lattice always has a candidate inside,
# yet the nearest-point search keeps consecutive notes close (a flowing line).
_MELODY_WINDOW_MC = 1_200_000


def _lattice_points(lattice: dict[str, Any]) -> list[tuple[list[int], int, str, int]]:
    """Precompute every lattice point as ``(vector, exponent, ratio_text, mc)``.

    Enumerating the full coordinate domain across the register bounds gives a
    small table (a few thousand rows for the piano lattice) that the melody
    figuration resolves against by nearest-cent search.
    """
    equave = _ratio(lattice["equave"])
    generators = [_ratio(item) for item in lattice["generators"]]
    bounds = lattice["coordinate_bounds"]

    def axes(index: int) -> list[tuple[int, ...]]:
        if index == len(bounds):
            return [()]
        return [
            (value, *tail)
            for value in range(bounds[index][0], bounds[index][1] + 1)
            for tail in axes(index + 1)
        ]

    points: list[tuple[list[int], int, str, int]] = []
    for vector in axes(0):
        for exponent in range(
            lattice["register_bounds"][0], lattice["register_bounds"][1] + 1
        ):
            ratio = _vector_ratio(generators, list(vector), equave, exponent)
            points.append((list(vector), exponent, _ratio_text(ratio), _mc(ratio)))
    return points


def _nearest_lattice_point(
    points: list[tuple[list[int], int, str, int]],
    target_mc: int,
    register_millicents: list[int],
) -> tuple[list[int], int, str] | None:
    """The precomputed lattice point nearest ``target_mc`` inside the register."""
    best: tuple[list[int], int, str] | None = None
    best_error: int | None = None
    for vector, exponent, ratio_text, mc in points:
        if not register_millicents[0] <= mc <= register_millicents[1]:
            continue
        error = abs(mc - target_mc)
        if best_error is None or error < best_error:
            best = (vector, exponent, ratio_text)
            best_error = error
    return best


def _melody_figuration_relation(seed: int) -> str:
    """Weighted deterministic choice of a figuration relation."""
    value = seed % 256
    cumulative = 0
    for relation, weight in _MELODY_FIGURATION:
        cumulative += weight
        if value < cumulative:
            return relation
    return _MELODY_FIGURATION[0][0]


def _resolve_melody_pitch(
    lattice: dict[str, Any],
    points: list[tuple[list[int], int, str, int]],
    chord: dict[str, Any],
    point: dict[str, Any],
    track: dict[str, Any],
    seed: int,
    anchor_mc: int | None = None,
) -> dict[str, Any]:
    """Resolve one melody point to a pitch based on its figuration relation.

    ``chord_member`` keeps the point on its target chord voice; when an
    ``anchor_mc`` (the previous note's pitch) is given the voice is re-octaved
    to the octave nearest the anchor so the line stays in one register.  The
    other relations search the lattice for a nearby pitch: ``passing``/
    ``neighbor`` step a whole tone from the reference voice, and
    ``scale_degree`` targets a 12-TET degree of the reference.  With an
    ``anchor_mc`` the search is confined to a window around it so consecutive
    notes move by small intervals (a flowing melodic line).  The nearest
    in-register lattice point realizes each target as an exact ratio.
    """
    member = point["member"]
    try:
        shape = chord["target_voice_ordinals"].index(member)
    except ValueError:
        shape = 0
    ref_offset = chord["voice_offsets"][shape]
    ref_exponent = chord["equave_exponents"][shape]
    ref_ratio = Fraction(chord["exact_ratios"][shape])
    ref_mc = _mc(ref_ratio)
    anchor = chord["anchor_vector"]
    register = track["register_millicents"]

    relation = _melody_figuration_relation(seed)
    if relation == "chord_member":
        exponent = ref_exponent
        ratio_text = chord["exact_ratios"][shape]
        if anchor_mc is not None:
            # Re-octave the chord voice to the octave nearest the anchor.
            equave_mc = _mc(_ratio(lattice["equave"]))
            if equave_mc > 0:
                exponent = ref_exponent + round((anchor_mc - ref_mc) / equave_mc)
                low, high = lattice["register_bounds"]
                exponent = max(low, min(high, exponent))
            ratio = _vector_ratio(
                [_ratio(item) for item in lattice["generators"]],
                [a + o for a, o in zip(anchor, ref_offset)],
                _ratio(lattice["equave"]),
                exponent,
            )
            ratio_text = _ratio_text(ratio)
        else:
            ratio = ref_ratio
        vector = [a + o for a, o in zip(anchor, ref_offset)]
        return {
            "source_vector": ref_offset,
            "final_vector": vector,
            "equave_exponent": exponent,
            "final_ratio": ratio_text,
            "relation": relation,
        }

    direction = 1 if (seed >> 8) % 2 else -1
    if relation == "passing":
        target_mc = ref_mc + direction * _MELODY_STEP_MC
    elif relation == "neighbor":
        target_mc = ref_mc - direction * _MELODY_STEP_MC
    else:  # scale_degree
        degree = 1 + (seed >> 4) % 4
        target_mc = ref_mc + direction * degree * _MELODY_TET_STEP_MC

    if anchor_mc is not None:
        # Flowing line: search a window around the previous note, biased by
        # the figuration direction, instead of jumping to the reference voice.
        target_mc = anchor_mc + direction * _MELODY_STEP_MC
        window_lo = anchor_mc - _MELODY_WINDOW_MC
        window_hi = anchor_mc + _MELODY_WINDOW_MC
    else:
        window_lo, window_hi = register[0], register[1]

    found = _nearest_lattice_point(
        points, target_mc, [max(window_lo, register[0]), min(window_hi, register[1])]
    )
    if found is None:
        found = _nearest_lattice_point(points, target_mc, register)
    if found is None:
        return {
            "source_vector": ref_offset,
            "final_vector": [a + o for a, o in zip(anchor, ref_offset)],
            "equave_exponent": ref_exponent,
            "final_ratio": chord["exact_ratios"][shape],
            "relation": "chord_member",
        }
    final_vector, exponent, ratio_text = found
    source_vector = [fv - av for fv, av in zip(final_vector, anchor)]
    return {
        "source_vector": source_vector,
        "final_vector": final_vector,
        "equave_exponent": exponent,
        "final_ratio": ratio_text,
        "relation": relation,
    }


def _event_id(event: dict[str, Any]) -> str:
    source = event["source"]
    core = {
        key: event[key]
        for key in (
            "kind",
            "track_id",
            "section_id",
            "start_tick",
            "duration_ticks",
            "velocity",
            "articulation",
            "drum_note",
            "ratio",
            "chord_index",
            "pitch_provenance",
        )
    }
    core["source"] = {
        key: source[key]
        for key in ("material_instance_id", "source_step_ordinal", "emitted_voice_ordinal")
    }
    payload = b"cps.event-id/v1\0" + source["semantic_address"].encode() + b"\0" + _canonical(core)
    return "ev_" + _b32(payload, 20)


def _resolved_chord_id(chord: dict[str, Any]) -> str:
    fields = (
        "domain_hash",
        "intent_hash",
        "resolver_build_id",
        "numeric_contract",
        "search_completeness",
        "reference_equave",
        "reference_divisions",
        "canonical_steps",
        "eligibility_contract",
        "anchor_vector",
        "voice_offsets",
        "equave_exponents",
        "exact_ratios",
        "target_voice_ordinals",
        "pair_errors_millicents",
        "maximum_pair_error_millicents",
        "pair_rms_error_millicents",
        "complexity_score",
    )
    return "rc_" + _b32(
        b"cps.resolved-chord/v1\0" + _canonical({field: chord[field] for field in fields}), 26
    )


def _instance_id(realization_id: str, repeat: int) -> str:
    stem = realization_id[5:] if realization_id.startswith("real_") else realization_id
    value = "mi_" + stem + ("" if repeat == 0 else f"_{repeat}")
    if (
        not value
        or len(value) > 40
        or not value[0].islower()
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in value)
    ):
        raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
    return value


def _place_exponent(
    base_ratio: Fraction, equave: Fraction, requested: int, bounds: list[int], register: list[int]
) -> int:
    candidates = [
        exponent
        for exponent in range(bounds[0], bounds[1] + 1)
        if register[0] <= _mc(base_ratio * equave**exponent) <= register[1]
    ]
    if not candidates:
        raise CompileError("REGISTER_NO_PLACEMENT")
    return min(candidates, key=lambda exponent: (abs(exponent - requested), exponent))


def compile_sp0(
    program: dict[str, Any],
    identity: CompilerIdentity,
    stochastic_realization: bool = True,
) -> dict[str, Any]:
    """Compile SP 0.1/0.2 to its matching Project 1.2/1.3 envelope.

    The progression resolver always runs over the full candidate set so that
    voice-leading validity is preserved. When ``stochastic_realization`` is
    true (the production default), the emitted realization of each occurrence
    is then chosen by a hash of the harmony query between the pure (closest)
    and the dissonant (second-closest) lattice core, so both cases appear in
    the output. The GEN0-B conformance path passes ``False`` to retain the
    exact top-K contract and emit the resolver's own selection.
    """
    if (
        program.get("schema") != "cps.song-program"
        or program.get("schema_version") not in _PROGRAM_PROJECT_VERSIONS
    ):
        raise CompileError("SCHEMA_VERSION_UNSUPPORTED")
    _validate_lattice_dimensions(program)
    if any(
        material.get("kind")
        not in {"rhythm_cell", "direct_vector_cell", "harmony_intent_cell", "melody_intent"}
        for material in program["materials"]
    ):
        raise CompileError("UNSUPPORTED_COMPILER_SLICE")
    if any(
        material.get("kind") == "melody_intent"
        and not {"id", "rhythm_id", "points", "mapping"}.issubset(material)
        for material in program["materials"]
    ):
        raise CompileError("UNSUPPORTED_COMPILER_SLICE")
    if any(realization["pitch_transforms"] for realization in program["realizations"]):
        raise CompileError("UNSUPPORTED_SP0_TRANSFORM")
    sections = {section["id"]: section for section in program["form"]}
    tracks = {track["id"]: track for track in program["tracks"]}
    materials = {material["id"]: material for material in program["materials"]}
    if (
        len(sections) != len(program["form"])
        or len(tracks) != len(program["tracks"])
        or len(materials) != len(program["materials"])
    ):
        raise CompileError("SYMBOL_DUPLICATE")
    ticks_per_bar = program["clock"]["beats_per_bar"] * program["clock"]["ticks_per_beat"]
    form = []
    start_bar = 0
    for section in program["form"]:
        form.append(
            {
                "id": section["id"],
                "role": section["role"],
                "start_bar": start_bar,
                "bars": section["bars"],
            }
        )
        start_bar += section["bars"]
    lattice_source = program["lattice"]
    lattice = {
        "domain_hash": "",
        "base_frequency_millihz": lattice_source["base_frequency_millihz"],
        "equave": lattice_source["equave"],
        "generators": lattice_source["generators"],
        "coordinate_bounds": lattice_source["coordinate_bounds"],
        "register_bounds": lattice_source["register_bounds"],
        "maximum_odd_limit": lattice_source["maximum_odd_limit"],
        "maximum_reduced_complexity_bits": lattice_source["pitch_exploration"][
            "maximum_reduced_complexity_bits"
        ],
    }
    lattice["domain_hash"] = _sha(
        b"cps.lattice-domain/v1\0",
        {key: value for key, value in lattice.items() if key != "domain_hash"},
    )
    project: dict[str, Any] = {
        "schema": "cps.arrangement-project",
        "schema_version": _PROGRAM_PROJECT_VERSIONS[program["schema_version"]],
        "source_program": {
            "hash": _sha(
                f"cps.song-program/{program['schema_version'].rsplit('.', 1)[0]}\0".encode(),
                {key: value for key, value in program.items() if key != "program_id"},
            ),
            "schema": "cps.song-program",
            "schema_version": program["schema_version"],
        },
        "compiler": {
            "build_id": identity.build_id,
            "numeric_contract": identity.numeric_contract,
            "resolver_build_id": identity.resolver_build_id,
            "resolver_profile_hash": identity.resolver_profile_hash,
            "budget_profile_digest": identity.budget_profile_digest,
            "instrument_catalog_digest": identity.instrument_catalog_digest,
        },
        "lattice": lattice,
        "clock": {**program["clock"], "bars": start_bar, "total_ticks": start_bar * ticks_per_bar},
        "tracks": sorted(deepcopy(program["tracks"]), key=lambda item: item["id"].encode()),
        "form": form,
        "material_instances": [],
        "resolved_chords": [],
        "harmony_occurrences": [],
        "events": [],
        "mix": deepcopy(program["production"]["tracks"]),
        "render_settings": {"sample_rate": 48_000, "channel_layout": "stereo"},
    }
    equave = _ratio(lattice["equave"])
    generators = [_ratio(item) for item in lattice["generators"]]
    section_starts = {item["id"]: item["start_bar"] * ticks_per_bar for item in form}
    used_instances: set[str] = set()
    harmony_drafts: list[dict[str, Any]] = []
    melody_drafts: list[dict[str, Any]] = []
    harmony_cache: dict[bytes, list[dict[str, Any]]] = {}
    for realization_index, realization in enumerate(program["realizations"]):
        try:
            section, track, material = (
                sections[realization["section_id"]],
                tracks[realization["track_id"]],
                materials[realization["material_id"]],
            )
            rhythm = (
                material if material["kind"] == "rhythm_cell" else materials[material["rhythm_id"]]
            )
        except KeyError as error:
            raise CompileError("REFERENCE_NOT_FOUND") from error
        if rhythm["kind"] != "rhythm_cell":
            raise CompileError("UNSUPPORTED_COMPILER_SLICE")
        if track["role"] == "drums" and material["kind"] == "rhythm_cell":
            rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
            for repeat in range(realization["repeat"]):
                instance_id = _instance_id(realization["id"], repeat)
                if instance_id in used_instances:
                    raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
                used_instances.add(instance_id)
                instance_tick = (
                    section_starts[section["id"]]
                    + realization["at_tick"]
                    + repeat * realization["every_ticks"]
                )
                project["material_instances"].append(
                    {
                        "id": instance_id,
                        "material_id": material["id"],
                        "realization_id": realization["id"],
                        "section_id": section["id"],
                        "track_id": track["id"],
                        "repeat_ordinal": repeat,
                        "at_tick": instance_tick,
                        "source_program_path": f"/realizations/{realization_index}",
                    }
                )
                for step_index, step in enumerate(rhythm["steps"]):
                    lane = step.get("lane_id")
                    if lane is None or lane not in track["drum_map"]:
                        raise CompileError(
                            "UNKNOWN_DRUM_LANE",
                            f"/materials/{program['materials'].index(material)}/steps/{step_index}/lane_id",
                        )
                    onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                    duration = max(
                        1,
                        _rhe(
                            Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)
                        ),
                    )
                    if (
                        onset + duration
                        > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                    ):
                        raise CompileError("EVENT_SECTION_OVERFLOW")
                    address = _semantic_address(
                        section["id"], realization["id"], repeat, material["id"], step_index
                    )
                    event = {
                        "id": "",
                        "kind": "drum",
                        "track_id": track["id"],
                        "section_id": section["id"],
                        "start_tick": onset,
                        "duration_ticks": duration,
                        "velocity": min(
                            127,
                            max(
                                1,
                                _rhe(
                                    Fraction(
                                        125 * step["accent_q"] * realization["velocity_scale_q"],
                                        100_000_000,
                                    )
                                ),
                            ),
                        ),
                        "articulation": "normal",
                        "drum_note": track["drum_map"][lane],
                        "ratio": None,
                        "chord_index": None,
                        "pitch_provenance": None,
                        "source": {
                            "material_instance_id": instance_id,
                            "source_step_ordinal": step_index,
                            "emitted_voice_ordinal": 0,
                            "semantic_address": address,
                        },
                    }
                    event["id"] = _event_id(event)
                    project["events"].append(event)
            continue
        if material["kind"] == "harmony_intent_cell" and track["role"] in {"harmony", "texture"}:
            rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
            intents = {intent["id"]: intent for intent in program["chord_intents"]}
            for repeat in range(realization["repeat"]):
                instance_id = _instance_id(realization["id"], repeat)
                if instance_id in used_instances:
                    raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
                used_instances.add(instance_id)
                instance_tick = (
                    section_starts[section["id"]]
                    + realization["at_tick"]
                    + repeat * realization["every_ticks"]
                )
                project["material_instances"].append(
                    {
                        "id": instance_id,
                        "material_id": material["id"],
                        "realization_id": realization["id"],
                        "section_id": section["id"],
                        "track_id": track["id"],
                        "repeat_ordinal": repeat,
                        "at_tick": instance_tick,
                        "source_program_path": f"/realizations/{realization_index}",
                    }
                )
                for step_index, step in enumerate(rhythm["steps"]):
                    if material["mapping"] == "zip" and (
                        step_index >= len(material["root_anchors"])
                        or step_index >= len(material["chord_intent_ids"])
                    ):
                        raise CompileError("MAPPING_LENGTH_MISMATCH")
                    item_index = step_index % len(material["root_anchors"])
                    intent_index = step_index % len(material["chord_intent_ids"])
                    try:
                        intent = intents[material["chord_intent_ids"][intent_index]]
                    except KeyError as error:
                        raise CompileError("REFERENCE_NOT_FOUND") from error
                    anchor = [
                        left + right
                        for left, right in zip(
                            material["root_anchors"][item_index],
                            section["tonal_center"],
                            strict=True,
                        )
                    ]
                    query = _harmony_query(program, intent, anchor)
                    query_key = _canonical(query)
                    if query_key not in harmony_cache:
                        cores = resolve_joint_bnb(query, 24)
                        if not cores:
                            raise CompileError("NO_JOINT_CHORD_SOLUTION")
                        chords = [
                            _chord_from_core(
                                core,
                                lattice=lattice,
                                intent=intent,
                                anchor=anchor,
                                identity=identity,
                            )
                            for core in cores
                        ]
                        harmony_cache[query_key] = chords
                    onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                    duration = max(
                        1,
                        _rhe(
                            Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)
                        ),
                    )
                    if (
                        onset + duration
                        > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                    ):
                        raise CompileError("EVENT_SECTION_OVERFLOW")
                    velocity = min(
                        127,
                        max(
                            1,
                            _rhe(
                                Fraction(
                                    125 * step["accent_q"] * realization["velocity_scale_q"],
                                    100_000_000,
                                )
                            ),
                        ),
                    )
                    harmony_drafts.append(
                        {
                            "id": _harmony_occurrence_id(
                                section["id"], realization["id"], repeat, material["id"], step_index
                            ),
                            "section": section,
                            "track": track,
                            "material": material,
                            "realization": realization,
                            "repeat": repeat,
                            "instance_id": instance_id,
                            "step_index": step_index,
                            "onset": onset,
                            "duration": duration,
                            "velocity": velocity,
                            "anchor": anchor,
                            "candidates": harmony_cache[query_key],
                            "query_key": query_key,
                        }
                    )
            continue
        if material["kind"] == "melody_intent" and track["role"] in {"melody", "texture"}:
            rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
            for repeat in range(realization["repeat"]):
                instance_id = _instance_id(realization["id"], repeat)
                if instance_id in used_instances:
                    raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
                used_instances.add(instance_id)
                instance_tick = (
                    section_starts[section["id"]]
                    + realization["at_tick"]
                    + repeat * realization["every_ticks"]
                )
                project["material_instances"].append(
                    {
                        "id": instance_id,
                        "material_id": material["id"],
                        "realization_id": realization["id"],
                        "section_id": section["id"],
                        "track_id": track["id"],
                        "repeat_ordinal": repeat,
                        "at_tick": instance_tick,
                        "source_program_path": f"/realizations/{realization_index}",
                    }
                )
                for step_index, step in enumerate(rhythm["steps"]):
                    if material["mapping"] == "zip" and step_index >= len(material["points"]):
                        raise CompileError("MAPPING_LENGTH_MISMATCH")
                    onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                    duration = max(
                        1,
                        _rhe(
                            Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000)
                        ),
                    )
                    if (
                        onset + duration
                        > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                    ):
                        raise CompileError("EVENT_SECTION_OVERFLOW")
                    melody_drafts.append(
                        {
                            "section": section,
                            "track": track,
                            "material": material,
                            "realization": realization,
                            "repeat": repeat,
                            "instance_id": instance_id,
                            "step_index": step_index,
                            "point": material["points"][step_index % len(material["points"])],
                            "onset": onset,
                            "duration": duration,
                            "velocity": min(
                                127,
                                max(
                                    1,
                                    _rhe(
                                        Fraction(
                                            125
                                            * step["accent_q"]
                                            * realization["velocity_scale_q"],
                                            100_000_000,
                                        )
                                    ),
                                ),
                            ),
                        }
                    )
            continue
        if material["kind"] != "direct_vector_cell" or track["role"] == "drums":
            raise CompileError("UNSUPPORTED_COMPILER_SLICE")
        rotations = sum(transform["ticks"] for transform in realization["rhythm_transforms"])
        for repeat in range(realization["repeat"]):
            instance_id = _instance_id(realization["id"], repeat)
            if instance_id in used_instances:
                raise CompileError("MATERIAL_INSTANCE_ID_INVALID")
            used_instances.add(instance_id)
            instance_tick = (
                section_starts[section["id"]]
                + realization["at_tick"]
                + repeat * realization["every_ticks"]
            )
            project["material_instances"].append(
                {
                    "id": instance_id,
                    "material_id": material["id"],
                    "realization_id": realization["id"],
                    "section_id": section["id"],
                    "track_id": track["id"],
                    "repeat_ordinal": repeat,
                    "at_tick": instance_tick,
                    "source_program_path": f"/realizations/{realization_index}",
                }
            )
            for step_index, step in enumerate(rhythm["steps"]):
                if material["mapping"] == "zip" and step_index >= len(material["vectors"]):
                    raise CompileError("MAPPING_LENGTH_MISMATCH")
                vector = material["vectors"][step_index % len(material["vectors"])]
                final_vector = [
                    left + right
                    for left, right in zip(vector, section["tonal_center"], strict=True)
                ]
                if any(
                    not bound[0] <= coordinate <= bound[1]
                    for coordinate, bound in zip(
                        final_vector, lattice["coordinate_bounds"], strict=True
                    )
                ):
                    raise CompileError("LATTICE_COORDINATE_OUT_OF_RANGE")
                base_ratio = _vector_ratio(generators, final_vector, equave, 0)
                exponent = _place_exponent(
                    base_ratio,
                    equave,
                    material["register_delta"],
                    lattice["register_bounds"],
                    track["register_millicents"],
                )
                ratio = _ratio_text(base_ratio * equave**exponent)
                onset = instance_tick + (step["at_tick"] + rotations) % rhythm["length_ticks"]
                duration = max(
                    1, _rhe(Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000))
                )
                if (
                    onset + duration
                    > section_starts[section["id"]] + section["bars"] * ticks_per_bar
                ):
                    raise CompileError("EVENT_SECTION_OVERFLOW")
                velocity = min(
                    127,
                    max(
                        1,
                        _rhe(
                            Fraction(
                                125 * step["accent_q"] * realization["velocity_scale_q"],
                                100_000_000,
                            )
                        ),
                    ),
                )
                address = _semantic_address(
                    section["id"], realization["id"], repeat, material["id"], step_index
                )
                event = {
                    "id": "",
                    "kind": "note",
                    "track_id": track["id"],
                    "section_id": section["id"],
                    "start_tick": onset,
                    "duration_ticks": duration,
                    "velocity": velocity,
                    "articulation": "normal",
                    "drum_note": None,
                    "ratio": ratio,
                    "chord_index": None,
                    "pitch_provenance": {
                        "kind": "direct_vector",
                        "material_vector": vector,
                        "tonal_center": section["tonal_center"],
                        "register_delta": material["register_delta"],
                        "register_shift_equaves": 0,
                        "placed_equave_exponent": exponent - material["register_delta"],
                        "final_vector": final_vector,
                        "equave_exponent": exponent,
                        "final_ratio": ratio,
                    },
                    "source": {
                        "material_instance_id": instance_id,
                        "source_step_ordinal": step_index,
                        "emitted_voice_ordinal": 0,
                        "semantic_address": address,
                    },
                }
                event["id"] = _event_id(event)
                project["events"].append(event)
    # GEN0-B resolves whole harmony tracks jointly.  Candidates are generated by
    # GEN0-A, then the exact progression resolver picks one core per occurrence
    # before any harmony or melody event is emitted.
    selected_drafts: list[tuple[dict[str, Any], dict[str, Any]]] = []
    drafts_by_track: dict[str, list[dict[str, Any]]] = {}
    for draft in harmony_drafts:
        drafts_by_track.setdefault(draft["track"]["id"], []).append(draft)
    for track_id in sorted(drafts_by_track, key=lambda item: item.encode()):
        drafts = sorted(
            drafts_by_track[track_id], key=lambda item: (item["onset"], item["id"].encode())
        )
        query = {
            "schema": "cps.progression-query",
            "schema_version": (
                "2.0.0" if program["schema_version"] == "0.2.0" else "1.2.0"
            ),
            "algorithm": "gen0-progression-exact/v1",
            "numeric_contract": identity.numeric_contract,
            "budget_profile": "gen0-progression-exact-v1",
            "domain_hash": lattice["domain_hash"],
            "domain_equave": lattice["equave"],
            "maximum_voice_motion_millicents": 2_400_000,
            "crossing_policy": "forbid",
            "occurrences": [],
        }
        for draft in drafts:
            query["occurrences"].append(
                {
                    "id": draft["id"],
                    "start_tick": draft["onset"],
                    "duration_ticks": draft["duration"],
                    "track_id": track_id,
                    "register_millicents": draft["track"]["register_millicents"],
                    "maximum_polyphony": draft["track"]["maximum_polyphony"],
                    "overlapping_nonprogression_pitched_events": 0,
                    "intent_hash": draft["candidates"][0]["intent_hash"],
                    "root_anchor": draft["anchor"],
                    "candidate_cores": [
                        _progression_candidate(chord) for chord in draft["candidates"]
                    ],
                }
            )
        try:
            path = resolve_progression(query)
        except ValueError as error:
            raise CompileError("PROGRESSION_NO_PATH") from error
        for draft, core_hash in zip(drafts, path["selected_core_hashes"], strict=True):
            selected = next(
                (chord for chord in draft["candidates"] if _core_hash(chord) == core_hash), None
            )
            if selected is None:  # Defensive: resolver output is always a candidate core.
                raise CompileError("PROGRESSION_NO_PATH")
            if stochastic_realization:
                # The resolver ran over the full candidate set for voice-leading
                # validity; the emitted realization is then chosen stochastically
                # between the pure (closest) and dissonant (second-closest) core.
                selected = _select_realization(draft["query_key"], draft["candidates"])
            selected_drafts.append((draft, selected))

    selected_drafts.sort(
        key=lambda item: (item[0]["onset"], item[0]["track"]["id"].encode(), item[0]["id"].encode())
    )
    for chord_index, (draft, chord) in enumerate(selected_drafts):
        if all(existing["id"] != chord["id"] for existing in project["resolved_chords"]):
            project["resolved_chords"].append(chord)
        project["harmony_occurrences"].append(
            {
                "chord_index": chord_index,
                "section_id": draft["section"]["id"],
                "start_tick": draft["onset"],
                "duration_ticks": draft["duration"],
                "resolved_chord_id": chord["id"],
            }
        )
        humanized = (
            _humanize_chord_onsets(draft["id"], len(chord["voice_offsets"]))
            if draft["track"]["instrument_id"] == _PIANO_HARMONY_INSTRUMENT
            else None
        )
        for shape, (offset, exponent, ratio, target) in enumerate(
            zip(
                chord["voice_offsets"],
                chord["equave_exponents"],
                chord["exact_ratios"],
                chord["target_voice_ordinals"],
                strict=True,
            )
        ):
            onset_offset = 0
            duration = draft["duration"]
            if humanized is not None:
                onset_offset, dropped = humanized[shape]
                if dropped:
                    continue
                # Roll the chord in without extending it past the draft's end.
                duration = max(1, draft["duration"] - onset_offset)
            vector = [
                left + right for left, right in zip(chord["anchor_vector"], offset, strict=True)
            ]
            address = _semantic_address(
                draft["section"]["id"],
                draft["realization"]["id"],
                draft["repeat"],
                draft["material"]["id"],
                draft["step_index"],
                shape,
            )
            event = {
                "id": "",
                "kind": "note",
                "track_id": draft["track"]["id"],
                "section_id": draft["section"]["id"],
                "start_tick": draft["onset"] + onset_offset,
                "duration_ticks": duration,
                "velocity": draft["velocity"],
                "articulation": "normal",
                "drum_note": None,
                "ratio": ratio,
                "chord_index": chord_index,
                "pitch_provenance": {
                    "kind": "resolved_chord_voice",
                    "resolved_chord_id": chord["id"],
                    "target_voice_ordinal": target,
                    "shape_voice_ordinal": shape,
                    "anchor_vector": chord["anchor_vector"],
                    "offset_vector": offset,
                    "final_vector": vector,
                    "equave_exponent": exponent,
                    "final_ratio": ratio,
                },
                "source": {
                    "material_instance_id": draft["instance_id"],
                    "source_step_ordinal": draft["step_index"],
                    "emitted_voice_ordinal": shape,
                    "semantic_address": address,
                },
            }
            event["id"] = _event_id(event)
            project["events"].append(event)

    chords_by_id = {chord["id"]: chord for chord in project["resolved_chords"]}
    melody_points = (
        _lattice_points(lattice)
        if any(
            draft["track"]["instrument_id"] == _PIANO_MELODY_INSTRUMENT
            for draft in melody_drafts
        )
        else None
    )
    # Process in time order so the figuration can anchor on the previous note.
    melody_drafts.sort(
        key=lambda item: (item["onset"], item["track"]["id"].encode(), item["step_index"])
    )
    previous_note_mc: dict[str, int] = {}
    for draft in melody_drafts:
        end = draft["onset"] + draft["duration"]
        active = [
            occurrence
            for occurrence in project["harmony_occurrences"]
            if occurrence["section_id"] == draft["section"]["id"]
            and occurrence["start_tick"] <= draft["onset"]
            and end <= occurrence["start_tick"] + occurrence["duration_ticks"]
        ]
        if len(active) != 1:
            raise CompileError("MELODY_HARMONY_CONFLICT")
        occurrence = active[0]
        chord = chords_by_id[occurrence["resolved_chord_id"]]
        member = draft["point"]["member"]
        if (
            melody_points is not None
            and draft["track"]["instrument_id"] == _PIANO_MELODY_INSTRUMENT
        ):
            seed = int.from_bytes(
                hashlib.sha256(
                    b"cps.piano-melody/v1\0"
                    + draft["instance_id"].encode()
                    + b"\0"
                    + str(draft["step_index"]).encode()
                    + b"\0"
                    + str(draft["repeat"]).encode()
                ).digest()[:8],
                "big",
            )
            resolved = _resolve_melody_pitch(
                lattice, melody_points, chord, draft["point"], draft["track"], seed,
                anchor_mc=previous_note_mc.get(draft["track"]["id"]),
            )
            offset = resolved["source_vector"]
            vector = resolved["final_vector"]
            exponent = resolved["equave_exponent"]
            ratio = resolved["final_ratio"]
            relation = resolved["relation"]
            previous_note_mc[draft["track"]["id"]] = _mc(_ratio(ratio))
        else:
            try:
                shape = chord["target_voice_ordinals"].index(member)
            except ValueError as error:
                raise CompileError("MELODY_HARMONY_CONFLICT") from error
            offset, exponent, ratio = (
                chord["voice_offsets"][shape],
                chord["equave_exponents"][shape],
                chord["exact_ratios"][shape],
            )
            vector = [
                left + right for left, right in zip(chord["anchor_vector"], offset, strict=True)
            ]
            relation = "chord_member"
        address = _semantic_address(
            draft["section"]["id"],
            draft["realization"]["id"],
            draft["repeat"],
            draft["material"]["id"],
            draft["step_index"],
        )
        event = {
            "id": "",
            "kind": "note",
            "track_id": draft["track"]["id"],
            "section_id": draft["section"]["id"],
            "start_tick": draft["onset"],
            "duration_ticks": draft["duration"],
            "velocity": draft["velocity"],
            "articulation": "normal",
            "drum_note": None,
            "ratio": ratio,
            "chord_index": occurrence["chord_index"],
            "pitch_provenance": {
                "kind": "resolved_melody",
                "melody_intent_id": draft["material"]["id"],
                "relation": relation,
                "active_resolved_chord_id": chord["id"],
                "active_target_voice_ordinal": member,
                "next_resolved_chord_id": None,
                "source_vector": offset,
                "relation_delta_vector": [0 for _ in offset],
                "tonal_center_delta_vector": [0 for _ in offset],
                "final_vector": vector,
                "equave_exponent": exponent,
                "final_ratio": ratio,
            },
            "source": {
                "material_instance_id": draft["instance_id"],
                "source_step_ordinal": draft["step_index"],
                "emitted_voice_ordinal": 0,
                "semantic_address": address,
            },
        }
        event["id"] = _event_id(event)
        project["events"].append(event)

    if not project["events"] or len(project["events"]) > program["limits"]["max_events"]:
        raise CompileError("EVENT_LIMIT_EXCEEDED")
    project["material_instances"].sort(key=lambda item: item["id"].encode())
    project["resolved_chords"].sort(key=lambda item: item["id"].encode())
    project["events"].sort(
        key=lambda item: (
            item["start_tick"],
            item["track_id"].encode(),
            0 if item["kind"] == "drum" else 1,
            item["drum_note"] if item["kind"] == "drum" else item["ratio"],
            item["source"]["semantic_address"],
            item["id"],
        )
    )
    return project


def compile_direct_sp0(program: dict[str, Any], identity: CompilerIdentity) -> dict[str, Any]:
    """Backward-compatible name for the original compiler vertical slice."""
    return compile_sp0(program, identity)


def initial_material_lineage_seeds(program: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Freeze v1 material lineage at a run's initial SongProgram boundary."""
    seeds: dict[str, dict[str, str]] = {}
    for material in program["materials"]:
        material_id = material["id"]
        if material_id in seeds:
            raise CompileError("SYMBOL_DUPLICATE")
        lineage_hash = _sha(
            b"cps.material-lineage/v1\0",
            {key: value for key, value in material.items() if key != "id"},
        )
        seeds[material_id] = {"lineage_hash": lineage_hash, "lineage_root_hash": lineage_hash}
    return seeds


def build_lineage_index(
    program: dict[str, Any],
    project: dict[str, Any],
    material_lineage_seeds: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a LineageIndex, optionally retaining initial material lineage seeds.

    All eight current Mutation v1 operations retain material identity; callers
    running a mutation search therefore pass the initial run seeds so a changed
    material core does not accidentally appear as a new lineage.
    """
    materials = {material["id"]: material for material in program["materials"]}
    realizations = {realization["id"]: realization for realization in program["realizations"]}
    seeds = (
        initial_material_lineage_seeds(program)
        if material_lineage_seeds is None
        else material_lineage_seeds
    )
    if set(seeds) != set(materials):
        raise CompileError("LINEAGE_SEED_SET_MISMATCH")
    lineage_by_material: dict[str, dict[str, str]] = {}
    for material_id in materials:
        seed = seeds[material_id]
        if set(seed) != {"lineage_hash", "lineage_root_hash"} or not all(
            isinstance(seed[key], str) and seed[key].startswith("sha256:") for key in seed
        ):
            raise CompileError("LINEAGE_SEED_INVALID")
        lineage_by_material[material_id] = seed
    instances = []
    by_lineage: dict[str, list[dict[str, Any]]] = {}
    for instance in project["material_instances"]:
        try:
            lineage = lineage_by_material[instance["material_id"]]
        except KeyError as error:
            raise CompileError("REFERENCE_NOT_FOUND") from error
        record = {
            "material_instance_id": instance["id"],
            "lineage_hash": lineage["lineage_hash"],
            "lineage_root_hash": lineage["lineage_root_hash"],
        }
        instances.append(record)
        by_lineage.setdefault(lineage["lineage_hash"], []).append(instance)
    instances.sort(key=lambda item: item["material_instance_id"].encode())
    edges = []
    for lineage_hash in sorted(by_lineage):
        ordered = sorted(
            by_lineage[lineage_hash], key=lambda item: (item["at_tick"], item["id"].encode())
        )
        for previous, current in zip(ordered, ordered[1:]):
            try:
                transforms = realizations[current["realization_id"]]["rhythm_transforms"]
            except KeyError as error:
                raise CompileError("REFERENCE_NOT_FOUND") from error
            rotate_total = sum(transform["ticks"] for transform in transforms)
            edges.append(
                {
                    "from_instance_id": previous["id"],
                    "to_instance_id": current["id"],
                    "operation": "identity"
                    if rotate_total == 0
                    else f"rotate_ticks:{rotate_total}",
                    "identity": rotate_total == 0,
                }
            )
    roots = sorted({seed["lineage_root_hash"] for seed in lineage_by_material.values()})
    project_bytes = _canonical(project)
    project_hash = (
        "sha256:"
        + hashlib.sha256(
            project["compiler"]["build_id"].encode()
            + f"\0project/{project['schema_version']}\0".encode()
            + project_bytes
        ).hexdigest()
    )
    return {
        "schema": "cps.lineage-index",
        "schema_version": "1.0.0",
        "project_hash": project_hash,
        "program_lineage_root_hash": _sha(b"cps.program-lineage-root/v1\0", roots),
        "instances": instances,
        "transform_edges": edges,
    }


# GEN0-B sidecars deliberately live beside the SP0 lowering entry point.  The
# Project compiler above remains the source of Project bytes; this layer only
# observes the same canonical lowering and constructs the separately hashed
# report/evidence/receipt artifacts required by the GEN0-B contract.
@dataclass(frozen=True)
class Gen0BCompileArtifacts:
    project: dict[str, Any] | None
    report: dict[str, Any]
    evidence: dict[str, Any] | None
    root_opcode_stream: dict[str, Any] | None
    child_opcode_streams: tuple[dict[str, Any], ...]


def _artifact_hash(domain: str, value: Any) -> str:
    """GEN0-B artifact hash (canonical JSON plus its required final LF)."""
    return (
        "sha256:"
        + hashlib.sha256(domain.encode("utf-8") + b"\0" + _canonical(value) + b"\n").hexdigest()
    )


def _bare_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _manifest_identity(manifest: dict[str, Any]) -> CompilerIdentity:
    try:
        return CompilerIdentity(
            manifest["build_id"],
            manifest["resolver"]["build_id"],
            manifest["resolver"]["profile_hash"],
            manifest["budget_profile"]["digest"],
            manifest["instrument_catalog_digest"],
            manifest["numeric_contract"],
        )
    except (KeyError, TypeError) as error:
        raise CompileError("COMPILER_MANIFEST_INVALID") from error


def _gen0b_validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate the subset that changes compiler observable semantics."""
    try:
        profile = manifest["budget_profile"]
        progression = manifest["progression_resolver"]
        required_root = {"progression_states", "progression_edges"}
        required_child = {"progression_states", "progression_edges"}
        version = manifest.get("schema_version")
        is_v2 = version == "2.0.0"
        if (
            manifest.get("schema") != "cps.compiler-manifest"
            or version not in {"1.1.0", "2.0.0"}
            or progression.get("algorithm") != "gen0-progression-exact/v1"
            or progression.get("search_completeness") != "exact"
            or not 1 <= progression["candidates_per_intent"] <= 24
            or profile.get("id")
            != ("gen0-progression-exact-v2" if is_v2 else "gen0-progression-exact-v1")
            or not required_root <= set(profile["root_ceilings"])
            or not required_child <= set(profile["child_ceilings"])
            or not {"progression_occurrences", "progression_candidates_per_occurrence"}
            <= set(profile["shape_limits"])
            or (
                is_v2
                and (
                    manifest.get("song_program_schema_versions") != ["0.2.0"]
                    or manifest.get("project_schema_version") != "1.3.0"
                    or manifest.get("progression_query_schema_version") != "2.0.0"
                    or manifest.get("gen0b_evidence_schema_version") != "2.0.0"
                    or manifest.get("melody_report_schema_version") != "2.0.0"
                )
            )
        ):
            raise KeyError
        if is_v2:
            limits = profile["domain_limits"]
            if (
                not 1 <= limits["dimensions"] <= 5
                or not 1 <= limits["axis_width"] <= 7
                or not 1 <= limits["coordinate_cardinality"] <= 1024
                or not 1 <= limits["register_width"] <= 8
                or not 1 <= limits["placed_cardinality"] <= 4096
                or profile["digest"] != _sha(
                    b"cps.budget-profile/v1\0",
                    {key: value for key, value in profile.items() if key != "digest"},
                )
            ):
                raise KeyError
        computed_build = "cb_" + _b32(
            b"cps.compiler-build/v1\0"
            + _canonical({key: value for key, value in manifest.items() if key != "build_id"}),
            26,
        )
        if manifest["build_id"] != computed_build:
            raise KeyError
    except (KeyError, TypeError):
        raise CompileError("COMPILER_MANIFEST_INVALID") from None


def _gen0b_harmony_expansion(
    program: dict[str, Any],
    project: dict[str, Any],
    identity: CompilerIdentity,
    candidates_per_intent: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]]]:
    """Reconstruct the immutable occurrence and progression payloads.

    This is intentionally independent of the Project's compact occurrence
    representation: evidence must retain all source occurrence fields.
    """
    materials = {item["id"]: item for item in program["materials"]}
    sections = {item["id"]: item for item in program["form"]}
    tracks = {item["id"]: item for item in program["tracks"]}
    intents = {item["id"]: item for item in program["chord_intents"]}
    ticks_per_bar = program["clock"]["beats_per_bar"] * program["clock"]["ticks_per_beat"]
    cursor = 0
    starts: dict[str, int] = {}
    for section in program["form"]:
        starts[section["id"]] = cursor
        cursor += section["bars"] * ticks_per_bar
    lattice = project["lattice"]
    cache: dict[bytes, list[dict[str, Any]]] = {}
    expanded: list[dict[str, Any]] = []
    for realization in program["realizations"]:
        material = materials[realization["material_id"]]
        track = tracks[realization["track_id"]]
        if material["kind"] != "harmony_intent_cell" or track["role"] not in {"harmony", "texture"}:
            continue
        rhythm = materials[material["rhythm_id"]]
        section = sections[realization["section_id"]]
        rotation = sum(item["ticks"] for item in realization["rhythm_transforms"])
        for repeat in range(realization["repeat"]):
            instance_tick = (
                starts[section["id"]] + realization["at_tick"] + repeat * realization["every_ticks"]
            )
            for step_ordinal, step in enumerate(rhythm["steps"]):
                if material["mapping"] == "zip" and (
                    step_ordinal >= len(material["root_anchors"])
                    or step_ordinal >= len(material["chord_intent_ids"])
                ):
                    raise CompileError("MAPPING_LENGTH_MISMATCH")
                anchor = [
                    a + b
                    for a, b in zip(
                        material["root_anchors"][step_ordinal % len(material["root_anchors"])],
                        section["tonal_center"],
                        strict=True,
                    )
                ]
                intent = intents[
                    material["chord_intent_ids"][step_ordinal % len(material["chord_intent_ids"])]
                ]
                oracle_query = _harmony_query(program, intent, anchor)
                key = _canonical(oracle_query)
                if key not in cache:
                    cores = resolve_joint_bnb(oracle_query, candidates_per_intent)
                    if not cores:
                        raise CompileError("NO_JOINT_CHORD_SOLUTION")
                    cache[key] = [
                        _chord_from_core(
                            core, lattice=lattice, intent=intent, anchor=anchor, identity=identity
                        )
                        for core in cores
                    ]
                onset = instance_tick + (step["at_tick"] + rotation) % rhythm["length_ticks"]
                duration = max(
                    1, _rhe(Fraction(step["duration_ticks"] * realization["gate_scale_q"], 10_000))
                )
                occurrence_id = _harmony_occurrence_id(
                    section["id"], realization["id"], repeat, material["id"], step_ordinal
                )
                expanded.append(
                    {
                        "occurrence_id": occurrence_id,
                        "section_id": section["id"],
                        "track_id": track["id"],
                        "realization_id": realization["id"],
                        "repeat_ordinal": repeat,
                        "material_id": material["id"],
                        "source_step_ordinal": step_ordinal,
                        "start_tick": onset,
                        "duration_ticks": duration,
                        "intent_id": intent["id"],
                        "intent_hash": cache[key][0]["intent_hash"],
                        "root_anchor": anchor,
                        "_candidates": cache[key],
                        "_track": track,
                    }
                )
    expanded.sort(
        key=lambda item: (
            item["track_id"].encode(),
            item["start_tick"],
            item["section_id"].encode(),
            item["realization_id"].encode(),
            item["repeat_ordinal"],
            item["source_step_ordinal"],
        )
    )
    public = [
        {key: value for key, value in item.items() if not key.startswith("_")} for item in expanded
    ]
    distinct: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for item in expanded:
        chord = item["_candidates"][0]
        key = (chord["domain_hash"], chord["intent_hash"], tuple(item["root_anchor"]))
        if key not in seen:
            seen.add(key)
            distinct.append((item, chord))
    distinct.sort(
        key=lambda item: (item[1]["domain_hash"], item[1]["intent_hash"], item[0]["root_anchor"])
    )
    return public, expanded, distinct


def compile_gen0b(program: dict[str, Any], manifest: dict[str, Any]) -> Gen0BCompileArtifacts:
    """Compile a GEN0-B program and publish its verifiable 1.1 sidecars.

    ``compile_sp0`` retains its Project-only API.  Callers that need budget
    and resolver evidence use this explicit GEN0-B entry point.
    """
    from .gen0b_receipt import (
        OpcodeEmitter,
        child_stream,
        project_validation,
        trace_bnb,
        trace_event_lowering,
        trace_symbols_and_timeline,
        usage,
    )

    _gen0b_validate_manifest(manifest)
    manifest_version = manifest["schema_version"]
    expected_program_version = "0.2.0" if manifest_version == "2.0.0" else "0.1.0"
    if program.get("schema_version") != expected_program_version:
        raise CompileError("GEN0B_SCHEMA_VERSION_UNSUPPORTED")
    _validate_lattice_dimensions(program)
    limits = manifest["budget_profile"]["domain_limits"]
    coordinate_bounds = program["lattice"]["coordinate_bounds"]
    coordinate_cardinality = math.prod(high - low + 1 for low, high in coordinate_bounds)
    register_width = program["lattice"]["register_bounds"][1] - program["lattice"]["register_bounds"][0] + 1
    if (
        len(coordinate_bounds) > limits["dimensions"]
        or max(high - low + 1 for low, high in coordinate_bounds) > limits["axis_width"]
        or coordinate_cardinality > limits["coordinate_cardinality"]
        or register_width > limits["register_width"]
        or coordinate_cardinality * register_width > limits["placed_cardinality"]
    ):
        raise CompileError("GEN0B_DOMAIN_LIMIT_EXCEEDED")
    identity = _manifest_identity(manifest)
    program_hash_version = program["schema_version"].rsplit(".", 1)[0]
    source_hash = _sha(
        f"cps.song-program/{program_hash_version}\0".encode(),
        {key: value for key, value in program.items() if key != "program_id"},
    )
    manifest_hash = _artifact_hash(
        f"cps.compiler-manifest/v{manifest_version.rsplit('.', 1)[0]}", manifest
    )
    request = {
        "song_program": program,
        "compiler_manifest": manifest,
        "instrument_catalog_digest": manifest["instrument_catalog_digest"],
    }
    input_hash = _artifact_hash("cps.compile-request/v1", request)
    emitter = OpcodeEmitter(input_hash)
    emitter.structural_parse(program)
    trace_symbols_and_timeline(emitter, program)
    children: list[dict[str, Any]] = []
    streams: list[dict[str, Any]] = []
    evidence: dict[str, Any] | None = None
    project: dict[str, Any] | None = None
    try:
        # The GEN0-B conformance path retains the exact top-K contract; the
        # stochastic pure/dissonant realization is a production-only choice.
        project = compile_sp0(program, identity, stochastic_realization=False)
        occurrences, expanded, distinct = _gen0b_harmony_expansion(
            program, project, identity, manifest["progression_resolver"]["candidates_per_intent"]
        )
        emitter.charged_sort(len(occurrences))
        gen0a_summaries: list[dict[str, Any]] = []
        for occurrence, chord in distinct:
            query = _harmony_query(
                program,
                next(
                    item
                    for item in program["chord_intents"]
                    if _sha(b"cps.chord-intent/v1\0", item) == chord["intent_hash"]
                ),
                occurrence["root_anchor"],
            )
            query_hash = _bare_hash(query)
            child_id = "chord_" + query_hash[7:23]
            stats = trace_bnb(
                emitter,
                program["lattice"],
                next(
                    item
                    for item in program["chord_intents"]
                    if _sha(b"cps.chord-intent/v1\0", item) == chord["intent_hash"]
                ),
                occurrence["root_anchor"],
                child_id,
                manifest["progression_resolver"]["candidates_per_intent"],
                tuple(occurrence["_track"]["register_millicents"]),
            )
            emitter.charged_sort(len(_progression_candidate(chord)["voices"]), child_id)
            gen0a_summaries.append(
                {
                    "query_hash": query_hash,
                    "domain_hash": chord["domain_hash"],
                    "intent_hash": chord["intent_hash"],
                    "root_anchor": occurrence["root_anchor"],
                    "requested_k": manifest["progression_resolver"]["candidates_per_intent"],
                    "ordered_core_hashes": [
                        _core_hash(candidate) for candidate in occurrence["_candidates"]
                    ],
                    "_child_id": child_id,
                    "_stats": stats,
                }
            )
        runs: list[tuple[str, list[dict[str, Any]]]] = []
        for track_id in sorted(
            {item["track_id"] for item in expanded}, key=lambda item: item.encode()
        ):
            items = [item for item in expanded if item["track_id"] == track_id]
            current: list[dict[str, Any]] = []
            end = -1
            for item in items:
                if current and item["start_tick"] > end:
                    runs.append((track_id, current))
                    current = []
                current.append(item)
                end = max(end, item["start_tick"] + item["duration_ticks"])
            if current:
                runs.append((track_id, current))
        runs.sort(
            key=lambda item: (
                item[1][0]["start_tick"],
                item[0].encode(),
                item[1][0]["occurrence_id"].encode(),
            )
        )
        progression_runs: list[dict[str, Any]] = []
        for ordinal, (track_id, run) in enumerate(runs):
            query = {
                "schema": "cps.progression-query",
                "schema_version": (
                    manifest.get("progression_query_schema_version", "1.2.0")
                ),
                "algorithm": manifest["progression_resolver"]["algorithm"],
                "numeric_contract": identity.numeric_contract,
                "budget_profile": manifest["budget_profile"]["id"],
                "domain_hash": project["lattice"]["domain_hash"],
                "domain_equave": project["lattice"]["equave"],
                "maximum_voice_motion_millicents": manifest["progression_resolver"][
                    "maximum_voice_motion_millicents"
                ],
                "crossing_policy": manifest["progression_resolver"]["crossing_policy"],
                "occurrences": [],
            }
            for item in run:
                query["occurrences"].append(
                    {
                        "id": item["occurrence_id"],
                        "start_tick": item["start_tick"],
                        "duration_ticks": item["duration_ticks"],
                        "track_id": track_id,
                        "register_millicents": item["_track"]["register_millicents"],
                        "maximum_polyphony": item["_track"]["maximum_polyphony"],
                        "overlapping_nonprogression_pitched_events": 0,
                        "intent_hash": item["intent_hash"],
                        "root_anchor": item["root_anchor"],
                        "candidate_cores": [
                            _progression_candidate(chord) for chord in item["_candidates"]
                        ],
                    }
                )
            query_hash = _artifact_hash(
                f"cps.progression-query/v{query['schema_version'].split('.', 1)[0]}", query
            )
            child_id = "progression_" + query_hash[7:23]
            emitter.progression(
                [item["candidate_cores"] for item in query["occurrences"]], child_id
            )
            result = resolve_progression(query)
            result_hash = _artifact_hash("cps.progression-result/v1", result)
            progression_runs.append(
                {
                    "query_ordinal": ordinal,
                    "track_id": track_id,
                    "occurrence_ids": [item["occurrence_id"] for item in run],
                    "query": query,
                    "query_hash": query_hash,
                    "result": result,
                    "result_hash": result_hash,
                    "_child_id": child_id,
                }
            )
        emitter.charged_sort(len(project["resolved_chords"]))
        emitter.charged_sort(len(project["harmony_occurrences"]))
        bindings = [
            event
            for event in project["events"]
            if (event.get("pitch_provenance") or {}).get("kind") == "resolved_melody"
        ]
        emitter.charged_sort(len(bindings))
        trace_event_lowering(emitter, project)
        emitter.charged_sort(len(project["events"]))
        project_validation(emitter, project)
        root = emitter.stream()
        for summary in gen0a_summaries:
            stream = child_stream(root, summary["_child_id"], summary["query_hash"])
            streams.append(stream)
            counted = usage(stream["records"])
            names = (
                "chord_search_nodes",
                "pair_relations",
                "numeric_eval_units",
                "exact_arithmetic_units",
                "ordering_units",
            )
            child = {
                "kind": "chord_query",
                "query_id": summary["_child_id"],
                "input_hash": summary["query_hash"],
                "status": "complete",
                "usage": {name: counted[name] for name in names},
                "opcode_stream_hash": stream["stream_hash"],
            }
            child["usage"]["total_logical_units"] = sum(child["usage"].values())
            children.append(child)
            summary["child_receipt_digest"] = _artifact_hash("cps.charge-receipt-child/v1.1", child)
        for run in progression_runs:
            stream = child_stream(root, run["_child_id"], run["query_hash"])
            streams.append(stream)
            counted = usage(stream["records"])
            child = {
                "kind": "progression_query",
                "query_id": run["_child_id"],
                "input_hash": run["query_hash"],
                "status": "complete",
                "usage": {
                    name: counted[name] for name in ("progression_states", "progression_edges")
                },
                "opcode_stream_hash": stream["stream_hash"],
            }
            child["usage"]["total_logical_units"] = sum(child["usage"].values())
            children.append(child)
            run["child_receipt_digest"] = _artifact_hash("cps.charge-receipt-child/v1.1", child)
        receipt = {
            "schema": "cps.charge-receipt",
            "schema_version": "1.1.0",
            "budget_profile_id": manifest["budget_profile"]["id"],
            "budget_profile_digest": manifest["budget_profile"]["digest"],
            "input_hash": input_hash,
            "status": "complete",
            "usage": usage(root["records"]),
            "children": children,
            "opcode_stream_hash": root["stream_hash"],
        }
        project_hash = _sha(
            project["compiler"]["build_id"].encode()
            + f"\0project/{project['schema_version']}\0".encode(),
            project,
        )
        evidence = {
            "schema": "cps.gen0b-compiler-evidence",
            "schema_version": manifest.get("gen0b_evidence_schema_version", "1.0.0"),
            "source_program_hash": source_hash,
            "compiler_manifest_hash": manifest_hash,
            "occurrences": occurrences,
            "gen0a_results": [
                {key: value for key, value in summary.items() if not key.startswith("_")}
                for summary in gen0a_summaries
            ],
            "progression_runs": [],
            "resolved_chord_ids": [item["id"] for item in project["resolved_chords"]],
            "event_ids": [item["id"] for item in project["events"]],
            "project_hash": project_hash,
            "root_receipt_digest": _artifact_hash("cps.charge-receipt/v1.1", receipt),
        }
        chords_by_core = {_core_hash(chord): chord for chord in project["resolved_chords"]}
        occurrence_to_project = {
            item["start_tick"]: item for item in project["harmony_occurrences"]
        }
        for run in progression_runs:
            selected = []
            for item in run["query"]["occurrences"]:
                core_hash = next(
                    record["resolved_core_hash"]
                    for record in run["result"]["canonical_path_key"]
                    if record["occurrence_id"] == item["id"]
                )
                project_occurrence = occurrence_to_project[item["start_tick"]]
                selected.append(
                    {
                        "occurrence_id": item["id"],
                        "selected_core_hash": core_hash,
                        "resolved_chord_id": chords_by_core[core_hash]["id"],
                        "project_chord_index": project_occurrence["chord_index"],
                    }
                )
            evidence["progression_runs"].append(
                {key: value for key, value in run.items() if not key.startswith("_")}
                | {"selected": selected}
            )
        evidence_version = evidence["schema_version"].split(".", 1)[0]
        evidence["evidence_hash"] = _artifact_hash(
            f"cps.gen0b-compiler-evidence/v{evidence_version}", evidence
        )
        report = {
            "schema": "cps.compile-report",
            "schema_version": "1.1.0",
            "source_program_hash": source_hash,
            "compiler_manifest_hash": manifest_hash,
            "compiler_build_id": identity.build_id,
            "budget_profile_digest": identity.budget_profile_digest,
            "status": "success",
            "project_hash": project_hash,
            "evidence_hash": evidence["evidence_hash"],
            "receipt": receipt,
            "search_statistics": {
                "chord_query_count": len(gen0a_summaries),
                "chord_candidates_examined": sum(
                    item["_stats"]["complete_nodes"] for item in gen0a_summaries
                ),
                "chord_eligible_candidates": sum(
                    item["_stats"]["eligible"] for item in gen0a_summaries
                ),
                "progression_query_count": len(progression_runs),
                "progression_states": receipt["usage"]["progression_states"],
                "progression_edges": receipt["usage"]["progression_edges"],
            },
            "error": None,
        }
        return Gen0BCompileArtifacts(project, report, evidence, root, tuple(streams))
    except CompileError:
        root = emitter.stream()
        receipt = {
            "schema": "cps.charge-receipt",
            "schema_version": "1.1.0",
            "budget_profile_id": manifest["budget_profile"]["id"],
            "budget_profile_digest": manifest["budget_profile"]["digest"],
            "input_hash": input_hash,
            "status": "complete",
            "usage": usage(root["records"]),
            "children": children,
            "opcode_stream_hash": root["stream_hash"],
        }
        report = {
            "schema": "cps.compile-report",
            "schema_version": "1.1.0",
            "source_program_hash": source_hash,
            "compiler_manifest_hash": manifest_hash,
            "compiler_build_id": identity.build_id,
            "budget_profile_digest": identity.budget_profile_digest,
            "status": "failure",
            "project_hash": None,
            "evidence_hash": None,
            "receipt": receipt,
            "search_statistics": {
                "chord_query_count": 0,
                "chord_candidates_examined": 0,
                "chord_eligible_candidates": 0,
                "progression_query_count": 0,
                "progression_states": receipt["usage"]["progression_states"],
                "progression_edges": receipt["usage"]["progression_edges"],
            },
            "error": {
                "code": "COMPILATION_FAILED",
                "stage": "compile",
                "pointer": "",
                "counter": None,
                "requested": None,
                "used": None,
                "ceiling": None,
                "child_query_id": None,
                "snapshot": receipt["usage"],
                "partial_project": None,
            },
        }
        return Gen0BCompileArtifacts(None, report, None, root, tuple(streams))


def compile_gen0b_report(program: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Convenience API for consumers that persist CompileReport only."""
    return compile_gen0b(program, manifest).report


def _gen0b_melody_report(
    program: dict[str, Any], artifacts: Gen0BCompileArtifacts
) -> dict[str, Any]:
    assert artifacts.project is not None and artifacts.evidence is not None
    project, evidence = artifacts.project, artifacts.evidence
    materials = {item["id"]: item for item in program["materials"]}
    occurrence_by_id = {item["occurrence_id"]: item for item in evidence["occurrences"]}
    selected = {
        item["occurrence_id"]: item
        for run in evidence["progression_runs"]
        for item in run["selected"]
    }
    project_occurrences = {item["chord_index"]: item for item in project["harmony_occurrences"]}
    bindings = []
    for event in project["events"]:
        provenance = event.get("pitch_provenance") or {}
        if provenance.get("kind") != "resolved_melody":
            continue
        material = materials[provenance["melody_intent_id"]]
        point_ordinal = event["source"]["source_step_ordinal"] % len(material["points"])
        point = material["points"][point_ordinal]
        occurrence = project_occurrences[event["chord_index"]]
        active_id = next(
            item["occurrence_id"]
            for item in evidence["occurrences"]
            if item["section_id"] == event["section_id"]
            and item["start_tick"] == occurrence["start_tick"]
            and item["duration_ticks"] == occurrence["duration_ticks"]
        )
        source = event["source"]
        bindings.append(
            {
                "binding_ordinal": len(bindings),
                "section_id": event["section_id"],
                "track_id": event["track_id"],
                "realization_id": next(
                    item["realization_id"]
                    for item in project["material_instances"]
                    if item["id"] == source["material_instance_id"]
                ),
                "repeat_ordinal": next(
                    item["repeat_ordinal"]
                    for item in project["material_instances"]
                    if item["id"] == source["material_instance_id"]
                ),
                "material_id": material["id"],
                "source_step_ordinal": source["source_step_ordinal"],
                "point_ordinal": point_ordinal,
                "start_tick": event["start_tick"],
                "duration_ticks": event["duration_ticks"],
                "member": point["member"],
                "active_occurrence_id": active_id,
                "active_track_id": occurrence_by_id[active_id]["track_id"],
                "project_chord_index": event["chord_index"],
                "selected_core_hash": selected[active_id]["selected_core_hash"],
                "resolved_chord_id": provenance["active_resolved_chord_id"],
                "shape_voice_ordinal": next(
                    chord["target_voice_ordinals"].index(point["member"])
                    for chord in project["resolved_chords"]
                    if chord["id"] == provenance["active_resolved_chord_id"]
                ),
                "source_vector": provenance["source_vector"],
                "equave_exponent": provenance["equave_exponent"],
                "exact_ratio": event["ratio"],
                "event_id": event["id"],
            }
        )
    report_version = "2.0.0" if project["schema_version"] == "1.3.0" else "1.0.0"
    report = {
        "schema": "cps.chord-member-melody-report",
        "schema_version": report_version,
        "source_program_hash": evidence["source_program_hash"],
        "gen0b_evidence_hash": evidence["evidence_hash"],
        "project_hash": evidence["project_hash"],
        "bindings": bindings,
    }
    report["report_hash"] = _artifact_hash(
        f"cps.chord-member-melody-report/v{report_version.split('.', 1)[0]}", report
    )
    return report


def compile_connected_gen0b(program: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Connected-executor adapter around the receipt-capable GEN0-B API."""
    artifacts = compile_gen0b(program, manifest)
    if artifacts.report["status"] != "success":
        return {
            "status": "compile_failure",
            "project": None,
            "compiler_evidence": None,
            "melody_report": None,
            "compile_report": artifacts.report,
            "opcode_stream_bundle": None,
            "error": artifacts.report["error"],
        }
    bundle = {
        "schema": "cps.opcode-stream-bundle",
        "schema_version": "1.0.0",
        "root": artifacts.root_opcode_stream,
        "children": [
            {"kind": child["kind"], "query_id": child["query_id"], "stream": stream}
            for child, stream in zip(
                artifacts.report["receipt"]["children"], artifacts.child_opcode_streams, strict=True
            )
        ],
    }
    bundle["bundle_hash"] = _artifact_hash("cps.opcode-stream-bundle/v1", bundle)
    return {
        "status": "success",
        "project": artifacts.project,
        "compiler_evidence": artifacts.evidence,
        "melody_report": _gen0b_melody_report(program, artifacts),
        "compile_report": artifacts.report,
        "opcode_stream_bundle": bundle,
        "error": None,
    }
