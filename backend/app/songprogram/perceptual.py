"""Perceptual Interpretation Layer (PIL) 1.0 — pitch projection and segmentation.

PIL is a parallel interpretation of an immutable ArrangementProject 1.2.  It
never replaces, rewrites, or rounds the Project's ratios, vectors, equave
exponents, ResolvedChords, or Native JI evaluation evidence, and it never
consumes a Native JI report as a computation input.  ``native_ji_report_hash``
is nullable correlation metadata only.

Implemented scope (perceptual_interpretation_layer_contract.md sections 3-4):

- derive integer ``frequency_millihz`` from the exact event ratio and the
  Project base frequency (RHE, the only rounding primitive defined by the
  bound NumericContract ``cps-numeric/decimal-log2-rhe-v1``);
- derive ``absolute_millicents`` with the bound NumericContract;
- ``native_phase_millicents`` wraps by the Project lattice equave;
- ``interpretation_phase_millicents`` wraps by the manifest's explicit 2/1
  interpretation period;
- soft 12-TET mapping ``triangular-millicent-q31/v1`` with exact largest-
  remainder normalization to 2**31 - 1; hard nearest-note quantization is
  forbidden.
- manifest-bound deterministic harmonic segmentation with integer salience,
  globally merged boundaries, stable segment IDs, and Q31 distributions.

Adopted house rules where the PIL contract defers to existing conventions:

- canonical bytes are the existing NFC/sorted-key/integer/no-float JSON used
  across the repository;
- self-hashes use the generic artifact-hash preimage
  ``UTF8("cps-artifact-hash/v1\\0" + schema + "\\0" + schema_version + "\\0")
  || canonical_json(artifact without only its self-hash member)``;
- failure codes are the ordered namespace of contract section 8 spelled
  ``PIL_<NAMESPACE>``; binding and schema failures raise :class:`PilError`
  before any draw, while computation-stage failures produce a failed report.

The Phase 1 launch profile freezes the raw ArrangementProject schema and
Numeric Contract byte hashes. Phase 2+ asset hashes remain opaque but are
carried into the manifest/cache identity and are not consumed by Phase 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from .compiler import _canonical, _mc, _rhe

REPORT_SCHEMA = "cps.perceptual-interpretation-report"
REPORT_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA = "cps.perceptual-interpretation-manifest"
MANIFEST_SCHEMA_VERSION = "1.0.0"
PIL_ALGORITHM = "pil-parallel-interpretation/v1"
KERNEL_ALGORITHM = "triangular-millicent-q31/v1"
NUMERIC_CONTRACT_ID = "cps-numeric/decimal-log2-rhe-v1"
PIL_IMPLEMENTATION_BUILD_ID = "pil.phase3.1.0.0"
PROJECT_SCHEMA_HASH = "sha256:960891e2390acb2a3c14e35074de9a56bb0604c9098baff0aada3fbeeeeb167d"
NUMERIC_CONTRACT_HASH = "sha256:a24ed6cc9cd96f49792f553c52b6237afcad0c9a3172e6931bb65c3e30ed3abb"
SEGMENTATION_POLICY_SCHEMA_HASH = (
    "sha256:77559f2ad4f563c761be20505eec8af4c4a04e63b51b9201df680e280bfa370d"
)
CHORD_FEATURE_SPEC_SCHEMA_HASH = (
    "sha256:6744d7e50ce53046d497552d72d7bc2c747dd08650ebb75b00fba52978fec293"
)
CHORD_FEATURE_RECORD_SCHEMA_HASH = (
    "sha256:0e039841d18d1496161ba2283fdbd1dca743fd719288ca465823f03be0add1a6"
)
CHORD_VOCABULARY_SCHEMA_HASH = (
    "sha256:cd6741bcd4e94a03e7ce9bcbb6422d761108e9900191c6500c2775cdfefec11b"
)

Q31_TOTAL = 2**31 - 1
PITCH_CLASS_COUNT = 12
PITCH_CLASS_WIDTH_MC = 100_000
INTERPRETATION_PERIOD_MC = 1_200_000  # explicit 2/1 interpretation period
MAX_PITCH_RECORDS = 8192
MAX_SEGMENTS = 4096
U64_MAX = 2**64 - 1
BOUNDARY_PRIORITY = (
    "endpoint",
    "bass_change",
    "sustained_change",
    "pitch_distribution_change",
    "metrical",
)
TRACK_ROLES = ("drums", "bass", "harmony", "melody", "texture")

_SHA_PREFIX = "sha256:"
_SHA_HEX = 64


class PilError(Exception):
    """Stable PIL failure raised before a bound report can be produced."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise PilError(code)


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == len(_SHA_PREFIX) + _SHA_HEX
        and value.startswith(_SHA_PREFIX)
        and all(char in "0123456789abcdef" for char in value[len(_SHA_PREFIX) :])
    )


def _artifact_hash(value: Mapping[str, Any], self_member: str) -> str:
    """Generic ``cps-artifact-hash/v1`` preimage with only the self-hash removed."""
    body = {key: item for key, item in value.items() if key != self_member}
    try:
        prefix = (
            "cps-artifact-hash/v1\0" + value["schema"] + "\0" + value["schema_version"] + "\0"
        ).encode("utf-8")
    except (KeyError, TypeError) as error:
        raise PilError("PIL_SCHEMA_INVALID") from error
    return _SHA_PREFIX + hashlib.sha256(prefix + _canonical(body)).hexdigest()


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    return _artifact_hash(manifest, "manifest_hash")


def report_hash(report: Mapping[str, Any]) -> str:
    return _artifact_hash(report, "report_hash")


def segmentation_policy_hash(policy: Mapping[str, Any]) -> str:
    return _artifact_hash(policy, "policy_hash")


def chord_feature_spec_hash(spec: Mapping[str, Any]) -> str:
    return _artifact_hash(spec, "spec_hash")


def chord_feature_record_hash(record: Mapping[str, Any]) -> str:
    return _artifact_hash(record, "record_hash")


def chord_vocabulary_hash(vocabulary: Mapping[str, Any]) -> str:
    return _artifact_hash(vocabulary, "vocabulary_hash")


def canonical_report_bytes(report: Mapping[str, Any]) -> bytes:
    return _canonical(dict(report))


def project_hash(project: Mapping[str, Any]) -> str:
    """Recompute the ArrangementProject 1.2 artifact hash (spec section 17)."""
    try:
        build_id = project["compiler"]["build_id"]
    except (KeyError, TypeError) as error:
        raise PilError("PIL_SCHEMA_INVALID") from error
    if not isinstance(build_id, str):
        _fail("PIL_SCHEMA_INVALID")
    preimage = build_id.encode("utf-8") + b"\0project/1.2.0\0" + _canonical(dict(project))
    return _SHA_PREFIX + hashlib.sha256(preimage).hexdigest()


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the manifest subset Phase 1 depends on, before any draw."""
    if not isinstance(manifest, Mapping):
        _fail("PIL_SCHEMA_INVALID")
    consts = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "algorithm": PIL_ALGORITHM,
        "interpretation_period": "2/1",
    }
    for key, expected in consts.items():
        if manifest.get(key) != expected:
            _fail("PIL_SCHEMA_INVALID")
    build_id = manifest.get("implementation_build_id")
    if not isinstance(build_id, str) or not build_id or len(build_id) > 128:
        _fail("PIL_SCHEMA_INVALID")
    kernel = manifest.get("pitch_kernel")
    if not isinstance(kernel, Mapping):
        _fail("PIL_SCHEMA_INVALID")
    if kernel.get("algorithm") != KERNEL_ALGORITHM:
        _fail("PIL_SCHEMA_INVALID")
    radius = kernel.get("radius_millicents")
    if not isinstance(radius, int) or isinstance(radius, bool) or not 1 <= radius <= 600_000:
        _fail("PIL_SCHEMA_INVALID")
    if kernel.get("normalization_total") != Q31_TOTAL:
        _fail("PIL_SCHEMA_INVALID")
    hash_fields = (
        "project_schema_hash",
        "numeric_contract_hash",
        "segmentation_policy_schema_hash",
        "segmentation_policy_hash",
        "feature_spec_hash",
        "vocabulary_hash",
        "voice_matching_policy_hash",
        "trajectory_template_set_hash",
    )
    for field in hash_fields:
        if not _is_sha(manifest.get(field)):
            _fail("PIL_SCHEMA_INVALID")
    genre_model_hash = manifest.get("genre_model_hash")
    if genre_model_hash is not None and not _is_sha(genre_model_hash):
        _fail("PIL_SCHEMA_INVALID")
    if not _is_sha(manifest.get("manifest_hash")):
        _fail("PIL_SCHEMA_INVALID")


def _validate_project_binding(project: Mapping[str, Any]) -> None:
    if not isinstance(project, Mapping):
        _fail("PIL_SCHEMA_INVALID")
    if project.get("schema") != "cps.arrangement-project":
        _fail("PIL_SCHEMA_INVALID")
    if project.get("schema_version") != "1.2.0":
        _fail("PIL_SCHEMA_INVALID")
    compiler = project.get("compiler")
    lattice = project.get("lattice")
    events = project.get("events")
    if not isinstance(compiler, Mapping) or not isinstance(lattice, Mapping):
        _fail("PIL_SCHEMA_INVALID")
    if not isinstance(events, list) or len(events) > MAX_PITCH_RECORDS:
        _fail("PIL_SCHEMA_INVALID")
    base = lattice.get("base_frequency_millihz")
    if not isinstance(base, int) or isinstance(base, bool) or base < 1:
        _fail("PIL_SCHEMA_INVALID")
    equave = lattice.get("equave")
    if not isinstance(equave, str):
        _fail("PIL_SCHEMA_INVALID")
    try:
        equave_ratio = Fraction(equave)
    except (ValueError, ZeroDivisionError) as error:
        raise PilError("PIL_SCHEMA_INVALID") from error
    if equave_ratio <= 1 or equave != f"{equave_ratio.numerator}/{equave_ratio.denominator}":
        _fail("PIL_SCHEMA_INVALID")


def verify_binding(
    project: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    expected_project_hash: str | None = None,
    native_ji_report_hash: str | None = None,
) -> str:
    """Verify manifest/Project/NumericContract/build-ID binding before any draw.

    Returns the recomputed Project artifact hash.  ``native_ji_report_hash``
    is correlation metadata only and is never a computation input.
    """
    validate_manifest(manifest)
    _validate_project_binding(project)
    if manifest["manifest_hash"] != manifest_hash(manifest):
        _fail("PIL_BINDING_MISMATCH")
    compiler = project["compiler"]
    if compiler.get("numeric_contract") != NUMERIC_CONTRACT_ID:
        _fail("PIL_BINDING_MISMATCH")
    if manifest["implementation_build_id"] != PIL_IMPLEMENTATION_BUILD_ID:
        _fail("PIL_BINDING_MISMATCH")
    if manifest["project_schema_hash"] != PROJECT_SCHEMA_HASH:
        _fail("PIL_BINDING_MISMATCH")
    if manifest["numeric_contract_hash"] != NUMERIC_CONTRACT_HASH:
        _fail("PIL_BINDING_MISMATCH")
    if manifest["segmentation_policy_schema_hash"] != SEGMENTATION_POLICY_SCHEMA_HASH:
        _fail("PIL_BINDING_MISMATCH")
    digest = project_hash(project)
    if expected_project_hash is not None:
        if not _is_sha(expected_project_hash):
            _fail("PIL_SCHEMA_INVALID")
        if digest != expected_project_hash:
            _fail("PIL_BINDING_MISMATCH")
    if native_ji_report_hash is not None and not _is_sha(native_ji_report_hash):
        _fail("PIL_SCHEMA_INVALID")
    return digest


def triangular_mapping_q31(phase_mc: int, radius_millicents: int) -> list[dict[str, int]]:
    """Soft ``triangular-millicent-q31/v1`` mapping over 12 pitch classes.

    Raw weight is ``max(0, R - d)`` for circular distance ``d``; eligible raw
    weights normalize to exactly ``2**31 - 1`` by floor division, with the
    remaining units distributed one each by descending fractional remainder
    and pitch-class ordinal.  No hard nearest-note quantization occurs: every
    eligible candidate is retained.
    """
    if not 0 <= phase_mc < INTERPRETATION_PERIOD_MC:
        _fail("PIL_NUMERIC_OVERFLOW")
    if not 1 <= radius_millicents <= 600_000:
        _fail("PIL_SCHEMA_INVALID")
    eligible: list[tuple[int, int]] = []
    for ordinal in range(PITCH_CLASS_COUNT):
        center = ordinal * PITCH_CLASS_WIDTH_MC
        distance = abs(phase_mc - center)
        distance = min(distance, INTERPRETATION_PERIOD_MC - distance)
        raw = radius_millicents - distance
        if raw > 0:
            eligible.append((ordinal, raw))
    if not eligible:
        _fail("PIL_PITCH_SUPPORT_EMPTY")
    total = sum(raw for _, raw in eligible)
    rows = [
        (ordinal, (raw * Q31_TOTAL) // total, (raw * Q31_TOTAL) % total)
        for ordinal, raw in eligible
    ]
    remainder = Q31_TOTAL - sum(units for _, units, _ in rows)
    # ``remainder`` is the sum of fractional parts, hence 0 <= remainder < len(rows).
    distribution_order = sorted(rows, key=lambda row: (-row[2], row[0]))
    extra = {ordinal: 0 for ordinal, _, _ in rows}
    for index in range(remainder):
        extra[distribution_order[index][0]] += 1
    return [
        {"pitch_class_ordinal": ordinal, "weight_q31": units + extra[ordinal]}
        for ordinal, units, _ in rows
    ]


def compute_pitch_record(
    event: Mapping[str, Any],
    *,
    base_frequency_millihz: int,
    equave_period_mc: int,
    radius_millicents: int,
) -> dict[str, Any]:
    """Derive one Phase 1 pitch record from an immutable note event."""
    event_id = event.get("id")
    ratio_text = event.get("ratio")
    if not isinstance(event_id, str) or not isinstance(ratio_text, str):
        _fail("PIL_SCHEMA_INVALID")
    try:
        ratio = Fraction(ratio_text)
    except (ValueError, ZeroDivisionError) as error:
        raise PilError("PIL_SCHEMA_INVALID") from error
    if ratio <= 0 or ratio_text != f"{ratio.numerator}/{ratio.denominator}":
        _fail("PIL_SCHEMA_INVALID")
    frequency = _rhe(Fraction(base_frequency_millihz) * ratio)
    if frequency < 1:
        _fail("PIL_NUMERIC_OVERFLOW")
    absolute_mc = _mc(ratio)
    native_phase = absolute_mc % equave_period_mc
    interpretation_phase = absolute_mc % INTERPRETATION_PERIOD_MC
    return {
        "source_event_id": event_id,
        "source_ratio": ratio_text,
        "frequency_millihz": frequency,
        "absolute_millicents": absolute_mc,
        "native_phase_millicents": native_phase,
        "interpretation_phase_millicents": interpretation_phase,
        "mapping_q31": triangular_mapping_q31(interpretation_phase, radius_millicents),
    }


def _is_int(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def validate_segmentation_policy(policy: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    """Validate the closed SegmentationPolicy 1.0 payload and its bindings."""
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "project_schema_hash",
        "policy_schema_hash",
        "grid_divisions_per_beat",
        "minimum_segment_ticks",
        "sustained_minimum_ticks",
        "pitch_distribution_change_q",
        "duration_coefficient_q",
        "metrical_coefficient_q",
        "persistence_coefficient_q",
        "bass_coefficient_q",
        "role_gain_q",
        "bass_role_order",
        "boundary_priority",
        "boundary_confidence_q",
        "policy_hash",
    }
    if not isinstance(policy, Mapping) or set(policy) != required:
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    _validate_segmentation_policy_tail(policy, manifest)


def _validate_distribution(value: Any, code: str) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= PITCH_CLASS_COUNT:
        _fail(code)
    ordinals = []
    total = 0
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {"pitch_class_ordinal", "weight_q31"}:
            _fail(code)
        ordinal, weight = row["pitch_class_ordinal"], row["weight_q31"]
        if not _is_int(ordinal, 0, 11) or not _is_int(weight, 1, Q31_TOTAL):
            _fail(code)
        ordinals.append(ordinal)
        total += weight
    if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals) or total != Q31_TOTAL:
        _fail(code)


def validate_chord_feature_spec(
    spec: Mapping[str, Any], manifest: Mapping[str, Any], policy: Mapping[str, Any]
) -> None:
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "feature_spec_schema_hash",
        "feature_record_schema_hash",
        "project_schema_hash",
        "segmentation_policy_hash",
        "pitch_distribution_algorithm",
        "interval_distribution_algorithm",
        "bass_relative_algorithm",
        "register_profile_algorithm",
        "common_tone_algorithm",
        "similarity",
        "spec_hash",
    }
    constants = {
        "schema": "cps.perceptual-chord-feature-spec",
        "schema_version": "1.0.0",
        "algorithm": "pil-chord-features-12pc/v1",
        "feature_spec_schema_hash": CHORD_FEATURE_SPEC_SCHEMA_HASH,
        "feature_record_schema_hash": CHORD_FEATURE_RECORD_SCHEMA_HASH,
        "project_schema_hash": PROJECT_SCHEMA_HASH,
        "segmentation_policy_hash": policy.get("policy_hash"),
        "pitch_distribution_algorithm": "soft-event-mapping-weighted-q31/v1",
        "interval_distribution_algorithm": "circular-ordered-autocorrelation-q31/v1",
        "bass_relative_algorithm": "soft-bass-circular-correlation-q31/v1",
        "register_profile_algorithm": "segment-event-weighted-absolute-millicents/v1",
        "common_tone_algorithm": "histogram-intersection-q10000/v1",
    }
    if not isinstance(spec, Mapping) or set(spec) != required:
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    if any(spec.get(key) != value for key, value in constants.items()):
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    if spec.get("spec_hash") != manifest.get("feature_spec_hash") or (
        spec.get("spec_hash") != chord_feature_spec_hash(spec)
    ):
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    similarity = spec.get("similarity")
    required_similarity = {
        "algorithm",
        "pitch_weight",
        "interval_weight",
        "bass_relative_weight",
        "confidence_floor_q",
        "winner_margin_floor_q",
        "maximum_candidates",
    }
    if not isinstance(similarity, Mapping) or set(similarity) != required_similarity:
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    if similarity.get("algorithm") != "weighted-normalized-l1-q10000/v1":
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    for key in (
        "pitch_weight",
        "interval_weight",
        "bass_relative_weight",
        "confidence_floor_q",
        "winner_margin_floor_q",
    ):
        if not _is_int(similarity.get(key), 0, 10_000):
            _fail("PIL_FEATURE_EXTRACTION_FAILED")
    if similarity["pitch_weight"] == 0 or similarity["interval_weight"] == 0:
        _fail("PIL_FEATURE_EXTRACTION_FAILED")
    if not _is_int(similarity.get("maximum_candidates"), 1, 256):
        _fail("PIL_FEATURE_EXTRACTION_FAILED")


def validate_chord_vocabulary(
    vocabulary: Mapping[str, Any], manifest: Mapping[str, Any], feature_spec: Mapping[str, Any]
) -> None:
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "vocabulary_schema_hash",
        "interpretation_period",
        "feature_spec_hash",
        "entries",
        "vocabulary_hash",
    }
    if not isinstance(vocabulary, Mapping) or set(vocabulary) != required:
        _fail("PIL_VOCABULARY_FAILED")
    if (
        vocabulary.get("schema") != "cps.perceptual-chord-vocabulary"
        or vocabulary.get("schema_version") != "1.0.0"
        or vocabulary.get("algorithm") != "pil-chord-vocabulary-q31/v1"
        or vocabulary.get("vocabulary_schema_hash") != CHORD_VOCABULARY_SCHEMA_HASH
        or vocabulary.get("interpretation_period") != "2/1"
        or vocabulary.get("feature_spec_hash") != feature_spec.get("spec_hash")
        or vocabulary.get("vocabulary_hash") != manifest.get("vocabulary_hash")
        or vocabulary.get("vocabulary_hash") != chord_vocabulary_hash(vocabulary)
    ):
        _fail("PIL_VOCABULARY_FAILED")
    entries = vocabulary.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 256:
        _fail("PIL_VOCABULARY_FAILED")
    ids = []
    for ordinal, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != {
            "id",
            "ordinal",
            "pitch_distribution_q31",
            "interval_distribution_q31",
            "bass_relative_distribution_q31",
        }:
            _fail("PIL_VOCABULARY_FAILED")
        if not isinstance(entry["id"], str) or entry["ordinal"] != ordinal:
            _fail("PIL_VOCABULARY_FAILED")
        ids.append(entry["id"])
        _validate_distribution(entry["pitch_distribution_q31"], "PIL_VOCABULARY_FAILED")
        _validate_distribution(entry["interval_distribution_q31"], "PIL_VOCABULARY_FAILED")
        if entry["bass_relative_distribution_q31"] is not None:
            _validate_distribution(entry["bass_relative_distribution_q31"], "PIL_VOCABULARY_FAILED")
    if len(set(ids)) != len(ids):
        _fail("PIL_VOCABULARY_FAILED")


def _validate_segmentation_policy_tail(
    policy: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    if (
        policy.get("schema") != "cps.perceptual-segmentation-policy"
        or policy.get("schema_version") != "1.0.0"
        or policy.get("algorithm") != "pil-harmonic-segmentation-grid-events/v1"
        or policy.get("project_schema_hash") != PROJECT_SCHEMA_HASH
        or policy.get("policy_schema_hash") != SEGMENTATION_POLICY_SCHEMA_HASH
        or policy.get("policy_hash") != manifest.get("segmentation_policy_hash")
        or policy.get("policy_hash") != segmentation_policy_hash(policy)
    ):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if policy.get("grid_divisions_per_beat") not in {1, 2, 4, 8}:
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    for key in ("minimum_segment_ticks", "sustained_minimum_ticks"):
        if not _is_int(policy.get(key), 1, 61_440):
            _fail("PIL_SEGMENTATION_POLICY_INVALID")
    for key in (
        "pitch_distribution_change_q",
        "duration_coefficient_q",
        "metrical_coefficient_q",
        "persistence_coefficient_q",
        "bass_coefficient_q",
    ):
        if not _is_int(policy.get(key), 0, 10_000):
            _fail("PIL_SEGMENTATION_POLICY_INVALID")
    gains = policy.get("role_gain_q")
    confidence = policy.get("boundary_confidence_q")
    if not isinstance(gains, Mapping) or set(gains) != set(TRACK_ROLES):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if any(not _is_int(value, 0, 10_000) for value in gains.values()):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    roles = policy.get("bass_role_order")
    if not isinstance(roles, list) or not 1 <= len(roles) <= 5 or len(set(roles)) != len(roles):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if any(role not in TRACK_ROLES for role in roles):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if policy.get("boundary_priority") != list(BOUNDARY_PRIORITY):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if not isinstance(confidence, Mapping) or set(confidence) != set(BOUNDARY_PRIORITY):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    if confidence.get("endpoint") != 10_000 or any(
        not _is_int(value, 0, 10_000) for value in confidence.values()
    ):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")


def _normalize(values: Sequence[int], total_units: int) -> list[int]:
    total = sum(values)
    if total <= 0:
        return [0] * len(values)
    rows = [(value * total_units // total, value * total_units % total) for value in values]
    remainder = total_units - sum(units for units, _ in rows)
    order = sorted(range(len(rows)), key=lambda index: (-rows[index][1], index))
    result = [units for units, _ in rows]
    for index in order[:remainder]:
        result[index] += 1
    return result


def _checked_product(*values: int) -> int:
    result = 1
    for value in values:
        result *= value
        if result > U64_MAX:
            _fail("PIL_NUMERIC_OVERFLOW")
    return result


def _segment_id(project_digest: str, policy_digest: str, start: int, end: int) -> str:
    body = {
        "end_tick": end,
        "policy_hash": policy_digest,
        "project_hash": project_digest,
        "start_tick": start,
    }
    digest = hashlib.sha256(b"cps.pil-segment-id/v1\0" + _canonical(body)).hexdigest()
    return "seg_" + digest[:32]


def segment_harmony(
    project: Mapping[str, Any],
    pitch_records: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    project_digest: str,
) -> list[dict[str, Any]]:
    """Apply the exact grid/event SegmentationPolicy 1.0 operator."""
    clock = project.get("clock")
    tracks = project.get("tracks")
    if not isinstance(clock, Mapping) or not isinstance(tracks, list):
        _fail("PIL_SEGMENTATION_POLICY_INVALID")
    ticks_per_beat = clock.get("ticks_per_beat")
    total_ticks = clock.get("total_ticks")
    divisor = policy["grid_divisions_per_beat"]
    if (
        not _is_int(ticks_per_beat, 1, 737_280)
        or not _is_int(total_ticks, 1, 737_280)
        or ticks_per_beat % divisor
        or ticks_per_beat % 2
    ):
        _fail("PIL_SEGMENT_BOUNDARY_INVALID")
    track_roles: dict[str, str] = {}
    for track in tracks:
        if not isinstance(track, Mapping):
            _fail("PIL_SEGMENTATION_POLICY_INVALID")
        track_id, role = track.get("id"), track.get("role")
        if not isinstance(track_id, str) or track_id in track_roles or role not in TRACK_ROLES:
            _fail("PIL_SEGMENTATION_POLICY_INVALID")
        track_roles[track_id] = role
    record_by_id = {row["source_event_id"]: row for row in pitch_records}
    notes: list[dict[str, Any]] = []
    for event in sorted(
        project["events"],
        key=lambda row: (row.get("start_tick", -1), str(row.get("id", "")).encode()),
    ):
        if event.get("kind") != "note" or event.get("ratio") is None:
            continue
        event_id, track_id = event.get("id"), event.get("track_id")
        start, duration, velocity = (
            event.get("start_tick"),
            event.get("duration_ticks"),
            event.get("velocity"),
        )
        if (
            not isinstance(event_id, str)
            or event_id not in record_by_id
            or track_id not in track_roles
            or not _is_int(start, 0, total_ticks - 1)
            or not _is_int(duration, 1, 737_280)
            or not _is_int(velocity, 1, 127)
            or start + duration > total_ticks
        ):
            _fail("PIL_SEGMENTATION_POLICY_INVALID")
        notes.append(
            {
                **event,
                "end_tick": start + duration,
                "phase": record_by_id[event_id]["interpretation_phase_millicents"],
                "absolute_mc": record_by_id[event_id]["absolute_millicents"],
                "role": track_roles[track_id],
            }
        )
    elementary_ticks = sorted(
        {0, total_ticks, *(n["start_tick"] for n in notes), *(n["end_tick"] for n in notes)}
    )
    role_rank = {role: index for index, role in enumerate(policy["bass_role_order"])}

    def active_at(left: int, right: int) -> list[dict[str, Any]]:
        return [n for n in notes if n["start_tick"] < right and n["end_tick"] > left]

    def bass_of(active: Sequence[dict[str, Any]]) -> str | None:
        eligible = [n for n in active if n["role"] in role_rank]
        if not eligible:
            return None
        return min(
            eligible, key=lambda n: (role_rank[n["role"]], n["absolute_mc"], n["id"].encode())
        )["id"]

    def distribution(active: Sequence[dict[str, Any]], units: int) -> list[int]:
        bins = [0] * PITCH_CLASS_COUNT
        for note in active:
            bins[note["phase"] // PITCH_CLASS_WIDTH_MC] += (
                note["velocity"] * policy["role_gain_q"][note["role"]]
            )
        return _normalize(bins, units)

    spans = []
    for left, right in zip(elementary_ticks, elementary_ticks[1:]):
        active = active_at(left, right)
        spans.append((left, right, active, bass_of(active), distribution(active, 10_000)))
    reasons: dict[int, set[str]] = {0: {"endpoint"}, total_ticks: {"endpoint"}}
    for index in range(1, len(elementary_ticks) - 1):
        tick = elementary_ticks[index]
        left, right = spans[index - 1], spans[index]
        if left[3] != right[3]:
            reasons.setdefault(tick, set()).add("bass_change")
        changed = {n["id"] for n in left[2]} ^ {n["id"] for n in right[2]}
        if any(
            n["id"] in changed and n["duration_ticks"] >= policy["sustained_minimum_ticks"]
            for n in notes
        ):
            reasons.setdefault(tick, set()).add("sustained_change")
        distance = _rhe(Fraction(sum(abs(a - b) for a, b in zip(left[4], right[4])), 2))
        if distance >= policy["pitch_distribution_change_q"]:
            reasons.setdefault(tick, set()).add("pitch_distribution_change")
    grid = ticks_per_beat // divisor
    for tick in range(grid, total_ticks, grid):
        reasons.setdefault(tick, set()).add("metrical")
    rank = {reason: index for index, reason in enumerate(BOUNDARY_PRIORITY)}
    accepted = {0, total_ticks}
    candidates = sorted(
        (tick for tick in reasons if tick not in accepted),
        key=lambda tick: (min(rank[r] for r in reasons[tick]), tick),
    )
    for tick in candidates:
        if all(abs(tick - other) >= policy["minimum_segment_ticks"] for other in accepted):
            accepted.add(tick)
    boundaries = sorted(accepted)
    segments = []
    for start, end in zip(boundaries, boundaries[1:]):
        overlapping = [n for n in notes if n["start_tick"] < end and n["end_tick"] > start]
        first_nonempty = next(
            (span for span in spans if span[0] < end and span[1] > start and span[2]), None
        )
        bass_id = None if first_nonempty is None else first_nonempty[3]
        bins = [0] * PITCH_CLASS_COUNT
        source_ids = []
        for note in overlapping:
            overlap = max(0, min(note["end_tick"], end) - max(note["start_tick"], start))
            metrical_q = (
                10_000
                if note["start_tick"] % ticks_per_beat == 0
                else (5_000 if note["start_tick"] % (ticks_per_beat // 2) == 0 else 0)
            )
            persistence_q = _rhe(Fraction(10_000 * overlap, note["duration_ticks"]))
            bass_q = 10_000 if note["id"] == bass_id else 0
            factor = policy["duration_coefficient_q"]
            factor += _rhe(Fraction(policy["metrical_coefficient_q"] * metrical_q, 10_000))
            factor += _rhe(Fraction(policy["persistence_coefficient_q"] * persistence_q, 10_000))
            factor += _rhe(Fraction(policy["bass_coefficient_q"] * bass_q, 10_000))
            numerator = _checked_product(
                overlap, note["velocity"], policy["role_gain_q"][note["role"]], factor
            )
            weight = _rhe(Fraction(numerator, 10_000))
            if weight:
                bins[note["phase"] // PITCH_CLASS_WIDTH_MC] += weight
                source_ids.append(note["id"])
        normalized = _normalize(bins, Q31_TOTAL)
        if not source_ids or not any(normalized):
            _fail("PIL_SEGMENT_EMPTY")
        ordered_reasons = [reason for reason in BOUNDARY_PRIORITY if reason in reasons[start]]
        segments.append(
            {
                "segment_id": _segment_id(project_digest, policy["policy_hash"], start, end),
                "start_tick": start,
                "end_tick": end,
                "boundary_reasons": ordered_reasons,
                "source_event_ids": sorted(set(source_ids), key=lambda value: value.encode()),
                "weighted_pitch_distribution_q31": [
                    {"pitch_class_ordinal": index, "weight_q31": value}
                    for index, value in enumerate(normalized)
                    if value
                ],
                "bass_event_id": bass_id,
                "confidence_q": max(
                    policy["boundary_confidence_q"][reason] for reason in ordered_reasons
                ),
            }
        )
    if len(segments) > MAX_SEGMENTS:
        _fail("PIL_RESULT_VALIDATION")
    return segments


def _expand_distribution(rows: Sequence[Mapping[str, Any]]) -> list[int]:
    result = [0] * PITCH_CLASS_COUNT
    for row in rows:
        result[row["pitch_class_ordinal"]] = row["weight_q31"]
    return result


def _sparse_distribution(values: Sequence[int]) -> list[dict[str, int]]:
    return [
        {"pitch_class_ordinal": index, "weight_q31": value}
        for index, value in enumerate(values)
        if value > 0
    ]


def _event_weight_for_segment(
    event: Mapping[str, Any],
    role: str,
    segment: Mapping[str, Any],
    policy: Mapping[str, Any],
    ticks_per_beat: int,
) -> int:
    start = event["start_tick"]
    end = start + event["duration_ticks"]
    overlap = max(0, min(end, segment["end_tick"]) - max(start, segment["start_tick"]))
    metrical_q = (
        10_000
        if start % ticks_per_beat == 0
        else (5_000 if start % (ticks_per_beat // 2) == 0 else 0)
    )
    persistence_q = _rhe(Fraction(10_000 * overlap, event["duration_ticks"]))
    bass_q = 10_000 if event["id"] == segment["bass_event_id"] else 0
    factor = policy["duration_coefficient_q"]
    factor += _rhe(Fraction(policy["metrical_coefficient_q"] * metrical_q, 10_000))
    factor += _rhe(Fraction(policy["persistence_coefficient_q"] * persistence_q, 10_000))
    factor += _rhe(Fraction(policy["bass_coefficient_q"] * bass_q, 10_000))
    numerator = _checked_product(overlap, event["velocity"], policy["role_gain_q"][role], factor)
    return _rhe(Fraction(numerator, 10_000))


def extract_chord_features(
    project: Mapping[str, Any],
    pitch_records: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    feature_spec: Mapping[str, Any],
    native_ji_report_hash: str | None,
) -> list[dict[str, Any]]:
    """Create canonical continuous Phase 3 records without Native JI recomputation."""
    pitch_by_id = {row["source_event_id"]: row for row in pitch_records}
    events_by_id = {row["id"]: row for row in project["events"] if row.get("kind") == "note"}
    roles = {row["id"]: row["role"] for row in project["tracks"]}
    ticks_per_beat = project["clock"]["ticks_per_beat"]
    previous_pitch: list[int] | None = None
    records = []
    for segment in segments:
        weighted_register = []
        pitch_raw = [0] * PITCH_CLASS_COUNT
        for event_id in segment["source_event_ids"]:
            event = events_by_id.get(event_id)
            pitch_record = pitch_by_id.get(event_id)
            if event is None or pitch_record is None or event.get("track_id") not in roles:
                _fail("PIL_FEATURE_EXTRACTION_FAILED")
            weight = _event_weight_for_segment(
                event, roles[event["track_id"]], segment, policy, ticks_per_beat
            )
            if weight > 0:
                weighted_register.append((pitch_record["absolute_millicents"], weight))
                for row in pitch_record["mapping_q31"]:
                    pitch_raw[row["pitch_class_ordinal"]] += weight * row["weight_q31"]
        if not weighted_register or not any(pitch_raw):
            _fail("PIL_FEATURE_EXTRACTION_FAILED")
        pitch = _normalize(pitch_raw, Q31_TOTAL)
        interval_raw = [
            sum(
                pitch[index] * pitch[(index + offset) % PITCH_CLASS_COUNT]
                for index in range(PITCH_CLASS_COUNT)
            )
            for offset in range(PITCH_CLASS_COUNT)
        ]
        interval = _normalize(interval_raw, Q31_TOTAL)
        bass_relative = None
        if segment["bass_event_id"] is not None:
            bass_mapping = _expand_distribution(
                pitch_by_id[segment["bass_event_id"]]["mapping_q31"]
            )
            relative_raw = [
                sum(
                    bass_mapping[index] * pitch[(index + offset) % PITCH_CLASS_COUNT]
                    for index in range(PITCH_CLASS_COUNT)
                )
                for offset in range(PITCH_CLASS_COUNT)
            ]
            bass_relative = _sparse_distribution(_normalize(relative_raw, Q31_TOTAL))
        weight_total = sum(weight for _, weight in weighted_register)
        mean = _rhe(
            Fraction(sum(value * weight for value, weight in weighted_register), weight_total)
        )
        common = (
            None
            if previous_pitch is None
            else _rhe(
                Fraction(10_000 * sum(min(a, b) for a, b in zip(previous_pitch, pitch)), Q31_TOTAL)
            )
        )
        record = {
            "schema": "cps.perceptual-chord-feature-record",
            "schema_version": "1.0.0",
            "segment_id": segment["segment_id"],
            "feature_spec_hash": feature_spec["spec_hash"],
            "native_ji_report_hash": native_ji_report_hash,
            "pitch_distribution_q31": _sparse_distribution(pitch),
            "interval_distribution_q31": _sparse_distribution(interval),
            "bass_relative_distribution_q31": bass_relative,
            "register_profile": {
                "minimum_absolute_millicents": min(value for value, _ in weighted_register),
                "maximum_absolute_millicents": max(value for value, _ in weighted_register),
                "mean_absolute_millicents": mean,
            },
            "common_tone_with_previous_q": common,
        }
        record["record_hash"] = chord_feature_record_hash(record)
        records.append(record)
        previous_pitch = pitch
    return records


def _distribution_similarity(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]
) -> int:
    a, b = _expand_distribution(left), _expand_distribution(right)
    l1 = sum(abs(x - y) for x, y in zip(a, b))
    return 10_000 - _rhe(Fraction(10_000 * l1, 2 * Q31_TOTAL))


def interpret_chord_features(
    records: Sequence[Mapping[str, Any]],
    feature_spec: Mapping[str, Any],
    vocabulary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    similarity_spec = feature_spec["similarity"]
    results = []
    for record in records:
        candidates = []
        for entry in vocabulary["entries"]:
            components = [
                (
                    _distribution_similarity(
                        record["pitch_distribution_q31"], entry["pitch_distribution_q31"]
                    ),
                    similarity_spec["pitch_weight"],
                ),
                (
                    _distribution_similarity(
                        record["interval_distribution_q31"], entry["interval_distribution_q31"]
                    ),
                    similarity_spec["interval_weight"],
                ),
            ]
            if (
                record["bass_relative_distribution_q31"] is not None
                and entry["bass_relative_distribution_q31"] is not None
            ):
                components.append(
                    (
                        _distribution_similarity(
                            record["bass_relative_distribution_q31"],
                            entry["bass_relative_distribution_q31"],
                        ),
                        similarity_spec["bass_relative_weight"],
                    )
                )
            denominator = sum(weight for _, weight in components)
            score = _rhe(Fraction(sum(value * weight for value, weight in components), denominator))
            candidates.append((entry["ordinal"], entry["id"], score))
        candidates.sort(key=lambda row: (-row[2], row[0], row[1].encode()))
        candidates = candidates[: similarity_spec["maximum_candidates"]]
        confidence = candidates[0][2]
        runner_up = candidates[1][2] if len(candidates) > 1 else 0
        best = (
            candidates[0][1]
            if (
                confidence >= similarity_spec["confidence_floor_q"]
                and confidence - runner_up >= similarity_spec["winner_margin_floor_q"]
            )
            else None
        )
        results.append(
            {
                "segment_id": record["segment_id"],
                "feature_record_hash": record["record_hash"],
                "candidates": [
                    {"id": item_id, "similarity_q": score} for _, item_id, score in candidates
                ],
                "best_label": best,
                "confidence_q": confidence,
            }
        )
    return results


def cache_key(
    project_digest: str, manifest: Mapping[str, Any], completed_phase: str = "pitch_projection"
) -> str:
    """Bind Project hash, manifest hash, every bound asset hash, the Numeric
    Contract hash, and the implementation build ID (contract section 8)."""
    binding = {
        "project_hash": project_digest,
        "manifest_hash": manifest["manifest_hash"],
        "asset_hashes": [
            manifest["segmentation_policy_hash"],
            manifest["feature_spec_hash"],
            manifest["vocabulary_hash"],
            manifest["voice_matching_policy_hash"],
            manifest["trajectory_template_set_hash"],
            manifest["genre_model_hash"],
        ],
        "numeric_contract_hash": manifest["numeric_contract_hash"],
        "implementation_build_id": manifest["implementation_build_id"],
        "completed_phase": completed_phase,
    }
    return _SHA_PREFIX + hashlib.sha256(b"cps.pil-cache-key/v1\0" + _canonical(binding)).hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key[len(_SHA_PREFIX) :]}.json"


def _cache_read(
    cache_dir: Path,
    key: str,
    *,
    project_digest: str,
    manifest_digest: str,
    native_ji_report_hash: str | None,
    completed_phase: str,
) -> bytes | None:
    """Return cached canonical report bytes, or None for cold/corrupt entries.

    A corrupt entry (unreadable, non-canonical, or self-hash mismatch) is
    treated as a cold miss and never changes the recomputed report bytes.
    """
    try:
        raw = _cache_path(cache_dir, key).read_bytes()
    except OSError:
        return None
    try:
        cached = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict) or _canonical(cached) != raw:
        return None
    if (
        cached.get("status") != "success"
        or cached.get("project_hash") != project_digest
        or cached.get("manifest_hash") != manifest_digest
        or cached.get("native_ji_report_hash") != native_ji_report_hash
        or cached.get("completed_phase") != completed_phase
        or report_hash(cached) != cached.get("report_hash")
    ):
        return None
    return raw


def _cache_write(cache_dir: Path, key: str, payload: bytes) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = _cache_path(cache_dir, key)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=cache_dir)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _failure_report(
    project_digest: str,
    manifest_digest: str,
    native_ji_report_hash: str | None,
    code: str,
    completed_phase: str,
) -> dict[str, Any]:
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_hash": project_digest,
        "manifest_hash": manifest_digest,
        "native_ji_report_hash": native_ji_report_hash,
        "completed_phase": completed_phase,
        "status": "failure",
        "pitch_records": [],
        "segments": [],
        "feature_records": [],
        "segment_interpretations": [],
        "trajectory_interpretations": [],
        "genre_interpretations": [],
        "missing_groups": [],
        "error": code,
    }
    report["report_hash"] = report_hash(report)
    return report


def run_perceptual_interpretation(
    project: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    native_ji_report_hash: str | None = None,
    expected_project_hash: str | None = None,
    cache_dir: str | Path | None = None,
    segmentation_policy: Mapping[str, Any] | None = None,
    feature_spec: Mapping[str, Any] | None = None,
    chord_vocabulary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run PIL pitch projection and optional harmonic segmentation.

    The Project and any Native JI evidence are never mutated; a PIL failure
    report stays independent of the Native JI branch and cannot trigger a
    Native JI fallback.  Cache cold, hit, and corrupt executions return
    byte-identical reports.
    """
    project_digest = verify_binding(
        project,
        manifest,
        expected_project_hash=expected_project_hash,
        native_ji_report_hash=native_ji_report_hash,
    )
    manifest_digest = manifest["manifest_hash"]
    phase3_requested = feature_spec is not None or chord_vocabulary is not None
    completed_phase = (
        "chord_similarity"
        if phase3_requested
        else "harmonic_segmentation"
        if segmentation_policy is not None
        else "pitch_projection"
    )
    key = cache_key(project_digest, manifest, completed_phase)
    cache_path = Path(cache_dir) if cache_dir is not None else None
    if cache_path is not None:
        cached = _cache_read(
            cache_path,
            key,
            project_digest=project_digest,
            manifest_digest=manifest_digest,
            native_ji_report_hash=native_ji_report_hash,
            completed_phase=completed_phase,
        )
        if cached is not None:
            return json.loads(cached)

    radius = manifest["pitch_kernel"]["radius_millicents"]
    lattice = project["lattice"]
    equave_period_mc = _mc(Fraction(lattice["equave"]))
    base_frequency = lattice["base_frequency_millihz"]
    try:
        records = []
        for event in project["events"]:
            if not isinstance(event, Mapping):
                _fail("PIL_SCHEMA_INVALID")
            if event.get("kind") != "note" or event.get("ratio") is None:
                continue
            records.append(
                compute_pitch_record(
                    event,
                    base_frequency_millihz=base_frequency,
                    equave_period_mc=equave_period_mc,
                    radius_millicents=radius,
                )
            )
        records.sort(key=lambda record: record["source_event_id"].encode("utf-8"))
        segments: list[dict[str, Any]] = []
        feature_records: list[dict[str, Any]] = []
        interpretations: list[dict[str, Any]] = []
        if phase3_requested and segmentation_policy is None:
            _fail("PIL_FEATURE_EXTRACTION_FAILED")
        if segmentation_policy is not None:
            validate_segmentation_policy(segmentation_policy, manifest)
            segments = segment_harmony(project, records, segmentation_policy, project_digest)
        if phase3_requested:
            if feature_spec is None:
                _fail("PIL_FEATURE_EXTRACTION_FAILED")
            validate_chord_feature_spec(feature_spec, manifest, segmentation_policy)
            feature_records = extract_chord_features(
                project,
                records,
                segments,
                segmentation_policy,
                feature_spec,
                native_ji_report_hash,
            )
            if chord_vocabulary is None:
                _fail("PIL_VOCABULARY_FAILED")
            validate_chord_vocabulary(chord_vocabulary, manifest, feature_spec)
            interpretations = interpret_chord_features(
                feature_records, feature_spec, chord_vocabulary
            )
        report = {
            "schema": REPORT_SCHEMA,
            "schema_version": REPORT_SCHEMA_VERSION,
            "project_hash": project_digest,
            "manifest_hash": manifest_digest,
            "native_ji_report_hash": native_ji_report_hash,
            "completed_phase": completed_phase,
            "status": "success",
            "pitch_records": records,
            "segments": segments,
            "feature_records": feature_records,
            "segment_interpretations": interpretations,
            "trajectory_interpretations": [],
            "genre_interpretations": [],
            "missing_groups": [],
            "error": None,
        }
    except PilError as error:
        if error.code in ("PIL_BINDING_MISMATCH", "PIL_SCHEMA_INVALID"):
            raise
        report = _failure_report(
            project_digest, manifest_digest, native_ji_report_hash, error.code, completed_phase
        )
    report["report_hash"] = report_hash(report)
    _validate_report_bounds(report)
    if cache_path is not None and report["status"] == "success":
        _cache_write(cache_path, key, canonical_report_bytes(report))
    return report


def _validate_report_bounds(report: Mapping[str, Any]) -> None:
    """Result-validation stage: re-check the report's integer bounds."""
    status = report.get("status")
    error = report.get("error")
    if status not in {"success", "failure"}:
        _fail("PIL_RESULT_VALIDATION")
    if report.get("completed_phase") not in {
        "pitch_projection",
        "harmonic_segmentation",
        "chord_similarity",
    }:
        _fail("PIL_RESULT_VALIDATION")
    if (status == "success" and error is not None) or (
        status == "failure" and (not isinstance(error, str) or not error.startswith("PIL_"))
    ):
        _fail("PIL_RESULT_VALIDATION")
    records = report["pitch_records"]
    if len(records) > MAX_PITCH_RECORDS:
        _fail("PIL_RESULT_VALIDATION")
    for record in records:
        if record["frequency_millihz"] < 1:
            _fail("PIL_RESULT_VALIDATION")
        if record["native_phase_millicents"] < 0:
            _fail("PIL_RESULT_VALIDATION")
        if not 0 <= record["interpretation_phase_millicents"] < INTERPRETATION_PERIOD_MC:
            _fail("PIL_RESULT_VALIDATION")
        weights = record["mapping_q31"]
        if not 1 <= len(weights) <= PITCH_CLASS_COUNT:
            _fail("PIL_RESULT_VALIDATION")
        if sum(row["weight_q31"] for row in weights) != Q31_TOTAL:
            _fail("PIL_RESULT_VALIDATION")
        if any(row["weight_q31"] < 1 for row in weights):
            _fail("PIL_RESULT_VALIDATION")
        ordinals = [row["pitch_class_ordinal"] for row in weights]
        if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
            _fail("PIL_RESULT_VALIDATION")
    segments = report["segments"]
    if len(segments) > MAX_SEGMENTS:
        _fail("PIL_RESULT_VALIDATION")
    if report["completed_phase"] == "pitch_projection" and segments:
        _fail("PIL_RESULT_VALIDATION")
    if report["completed_phase"] != "chord_similarity" and (
        report["feature_records"] or report["segment_interpretations"]
    ):
        _fail("PIL_RESULT_VALIDATION")
    previous_end = None
    for segment in segments:
        if segment["start_tick"] >= segment["end_tick"] or (
            previous_end is not None and segment["start_tick"] != previous_end
        ):
            _fail("PIL_RESULT_VALIDATION")
        previous_end = segment["end_tick"]
        weights = segment["weighted_pitch_distribution_q31"]
        if sum(row["weight_q31"] for row in weights) != Q31_TOTAL:
            _fail("PIL_RESULT_VALIDATION")
        ordinals = [row["pitch_class_ordinal"] for row in weights]
        if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
            _fail("PIL_RESULT_VALIDATION")
    if report["completed_phase"] == "chord_similarity" and report["status"] == "success":
        if not (
            len(report["segments"])
            == len(report["feature_records"])
            == len(report["segment_interpretations"])
        ):
            _fail("PIL_RESULT_VALIDATION")
        segment_ids = [segment["segment_id"] for segment in report["segments"]]
        if [record.get("segment_id") for record in report["feature_records"]] != segment_ids:
            _fail("PIL_RESULT_VALIDATION")
        if [row.get("segment_id") for row in report["segment_interpretations"]] != segment_ids:
            _fail("PIL_RESULT_VALIDATION")
        for record, interpretation in zip(
            report["feature_records"], report["segment_interpretations"]
        ):
            if record.get("record_hash") != chord_feature_record_hash(record):
                _fail("PIL_RESULT_VALIDATION")
            _validate_distribution(record.get("pitch_distribution_q31"), "PIL_RESULT_VALIDATION")
            _validate_distribution(record.get("interval_distribution_q31"), "PIL_RESULT_VALIDATION")
            if record.get("bass_relative_distribution_q31") is not None:
                _validate_distribution(
                    record["bass_relative_distribution_q31"], "PIL_RESULT_VALIDATION"
                )
            if interpretation.get("feature_record_hash") != record["record_hash"]:
                _fail("PIL_RESULT_VALIDATION")
            candidates = interpretation.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                _fail("PIL_RESULT_VALIDATION")
            if any(not _is_int(row.get("similarity_q"), 0, 10_000) for row in candidates):
                _fail("PIL_RESULT_VALIDATION")
            scores = [row["similarity_q"] for row in candidates]
            if (
                scores != sorted(scores, reverse=True)
                or interpretation.get("confidence_q") != scores[0]
            ):
                _fail("PIL_RESULT_VALIDATION")


__all__: Sequence[str] = (
    "INTERPRETATION_PERIOD_MC",
    "CHORD_FEATURE_RECORD_SCHEMA_HASH",
    "CHORD_FEATURE_SPEC_SCHEMA_HASH",
    "CHORD_VOCABULARY_SCHEMA_HASH",
    "KERNEL_ALGORITHM",
    "MANIFEST_SCHEMA",
    "MANIFEST_SCHEMA_VERSION",
    "NUMERIC_CONTRACT_ID",
    "NUMERIC_CONTRACT_HASH",
    "PIL_ALGORITHM",
    "PIL_IMPLEMENTATION_BUILD_ID",
    "PROJECT_SCHEMA_HASH",
    "PilError",
    "Q31_TOTAL",
    "REPORT_SCHEMA",
    "REPORT_SCHEMA_VERSION",
    "BOUNDARY_PRIORITY",
    "TRACK_ROLES",
    "SEGMENTATION_POLICY_SCHEMA_HASH",
    "cache_key",
    "canonical_report_bytes",
    "chord_feature_record_hash",
    "chord_feature_spec_hash",
    "chord_vocabulary_hash",
    "compute_pitch_record",
    "extract_chord_features",
    "manifest_hash",
    "interpret_chord_features",
    "project_hash",
    "report_hash",
    "segmentation_policy_hash",
    "segment_harmony",
    "run_perceptual_interpretation",
    "triangular_mapping_q31",
    "validate_manifest",
    "validate_chord_feature_spec",
    "validate_chord_vocabulary",
    "validate_segmentation_policy",
    "verify_binding",
)
