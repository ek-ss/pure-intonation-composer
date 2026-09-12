"""Perceptual Interpretation Layer (PIL) 1.0 — Phase 1 pitch projection.

PIL is a parallel interpretation of an immutable ArrangementProject 1.2.  It
never replaces, rewrites, or rounds the Project's ratios, vectors, equave
exponents, ResolvedChords, or Native JI evaluation evidence, and it never
consumes a Native JI report as a computation input.  ``native_ji_report_hash``
is nullable correlation metadata only.

Phase 1 scope (perceptual_interpretation_layer_contract.md section 3):

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
PIL_IMPLEMENTATION_BUILD_ID = "pil.phase1.1.0.0"
PROJECT_SCHEMA_HASH = "sha256:960891e2390acb2a3c14e35074de9a56bb0604c9098baff0aada3fbeeeeb167d"
NUMERIC_CONTRACT_HASH = "sha256:a24ed6cc9cd96f49792f553c52b6237afcad0c9a3172e6931bb65c3e30ed3abb"

Q31_TOTAL = 2**31 - 1
PITCH_CLASS_COUNT = 12
PITCH_CLASS_WIDTH_MC = 100_000
INTERPRETATION_PERIOD_MC = 1_200_000  # explicit 2/1 interpretation period
MAX_PITCH_RECORDS = 8192

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


def cache_key(project_digest: str, manifest: Mapping[str, Any]) -> str:
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
) -> dict[str, Any]:
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_hash": project_digest,
        "manifest_hash": manifest_digest,
        "native_ji_report_hash": native_ji_report_hash,
        "status": "failure",
        "pitch_records": [],
        "segments": [],
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
) -> dict[str, Any]:
    """Run PIL Phase 1 and return a PerceptualInterpretationReport 1.0.

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
    key = cache_key(project_digest, manifest)
    cache_path = Path(cache_dir) if cache_dir is not None else None
    if cache_path is not None:
        cached = _cache_read(
            cache_path,
            key,
            project_digest=project_digest,
            manifest_digest=manifest_digest,
            native_ji_report_hash=native_ji_report_hash,
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
        report = {
            "schema": REPORT_SCHEMA,
            "schema_version": REPORT_SCHEMA_VERSION,
            "project_hash": project_digest,
            "manifest_hash": manifest_digest,
            "native_ji_report_hash": native_ji_report_hash,
            "status": "success",
            "pitch_records": records,
            "segments": [],
            "segment_interpretations": [],
            "trajectory_interpretations": [],
            "genre_interpretations": [],
            "missing_groups": [],
            "error": None,
        }
    except PilError as error:
        if error.code in ("PIL_BINDING_MISMATCH", "PIL_SCHEMA_INVALID"):
            raise
        report = _failure_report(project_digest, manifest_digest, native_ji_report_hash, error.code)
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
    if (status == "success" and error is not None) or (
        status == "failure"
        and (not isinstance(error, str) or not error.startswith("PIL_"))
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


__all__: Sequence[str] = (
    "INTERPRETATION_PERIOD_MC",
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
    "cache_key",
    "canonical_report_bytes",
    "compute_pitch_record",
    "manifest_hash",
    "project_hash",
    "report_hash",
    "run_perceptual_interpretation",
    "triangular_mapping_q31",
    "validate_manifest",
    "verify_binding",
)
