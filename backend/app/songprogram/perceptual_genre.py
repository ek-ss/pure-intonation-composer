"""PIL Phase 5 genre/style interpretation — production implementation.

Normative source: ``docs/song_program_pil_genre_phase5_contract.md`` 1.0.
This module is the production counterpart of the independent conformance
oracle (``songprogram_conformance.pil_genre_phase5_oracle``); it never imports
that oracle, and it never reads Native JI values.  ``native_ji_report_hash``
remains correlation metadata only.

Scope of the 1.0 launch profile (build identity ``pil.phase5.1.0.0``):

- harmony-only: the bound ``PerceptualGenreModel 1.0`` MUST declare
  ``required_groups: ["harmony"]`` and every result reports exactly
  ``["melody", "rhythm", "form", "instrumentation", "production"]`` as
  ``missing_groups``;
- the feature record is derived from one successful Phase 4 report
  (``completed_phase == "functional_trajectory"``) without recomputing any
  Phase 1-4 quantity with new approximations;
- all arithmetic is checked integer arithmetic; overflow is
  ``PIL_NUMERIC_OVERFLOW`` and every other Phase 5 failure is
  ``PIL_GENRE_FAILED``;
- all Phase 5 metrics stay audit-only until an exact CalibrationDecision
  promotes them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from .compiler import _canonical, _rhe
from .perceptual import (
    Q31_TOTAL,
    U64_MAX,
    PilError,
    _artifact_hash,
    _is_int,
    report_hash,
)

GENRE_MODEL_SCHEMA = "cps.perceptual-genre-model"
GENRE_FEATURE_RECORD_SCHEMA = "cps.perceptual-genre-feature-record"
GENRE_RESULT_SCHEMA = "cps.perceptual-genre-result"
GENRE_SCHEMA_VERSION = "1.0.0"
GENRE_MODEL_ALGORITHM = "pil-genre-prototype-l1/v1"
GENRE_EXTRACT_ALGORITHM = "pil-genre-harmony-extract/v1"
PHASE5_BUILD_ID = "pil.phase5.1.0.0"
PHASE5_COMPLETED_PHASE = "genre_interpretation"

# Frozen raw schema bytes of the Phase 5 launch profile, recorded by the
# authoritative suite index (contract section 1).
GENRE_FEATURE_RECORD_SCHEMA_HASH = (
    "sha256:91b455778c2af0182bec7f77e34a5439667d7a1dee11311dc91ceaf86a9545ca"
)

MISSING_GROUPS = ("melody", "rhythm", "form", "instrumentation", "production")
_DETAIL_KEYS = ("chord_vocabulary", "progression", "function", "voice_leading", "harmonic_rhythm")
_SHA_PREFIX = "sha256:"
_GENRE_ID_RE = re.compile(r"[a-z][a-z0-9_.-]{0,127}")


def _fail(code: str = "PIL_GENRE_FAILED") -> None:
    raise PilError(code)


def genre_model_hash(model: Mapping[str, Any]) -> str:
    return _artifact_hash(model, "model_hash")


def genre_feature_record_hash(record: Mapping[str, Any]) -> str:
    return _artifact_hash(record, "record_hash")


def genre_result_hash(result: Mapping[str, Any]) -> str:
    return _artifact_hash(result, "result_hash")


def canonical_results_bytes(results: Sequence[Mapping[str, Any]]) -> bytes:
    return _canonical(list(results))


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _checked_sum(values: Sequence[int]) -> int:
    total = 0
    for value in values:
        total += value
        if total > U64_MAX:
            _fail("PIL_NUMERIC_OVERFLOW")
    return total


def _validate_hist(value: Any) -> list[dict[str, int]]:
    """Validate a sparse Q31 histogram: strictly increasing ordinals, positive
    weights, exact total ``2**31 - 1``."""
    if not isinstance(value, list) or not 1 <= len(value) <= 4096:
        _fail()
    previous = -1
    weights: list[int] = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {"ordinal", "weight_q31"}:
            _fail()
        ordinal, weight = row["ordinal"], row["weight_q31"]
        if not _is_int(ordinal, 0, 4095):
            _fail()
        if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
            _fail()
        if weight > Q31_TOTAL:
            _fail("PIL_NUMERIC_OVERFLOW")
        if ordinal <= previous:
            _fail()
        previous = ordinal
        weights.append(weight)
    if _checked_sum(weights) != Q31_TOTAL:
        _fail()
    return value


def _validate_profile(value: Any, length: int) -> list[int | None]:
    if not isinstance(value, list) or len(value) != length:
        _fail()
    for item in value:
        if item is not None and not _is_int(item, 0, 10_000):
            _fail()
    return value


def _validate_genre_id(value: Any) -> str:
    if not isinstance(value, str) or not _GENRE_ID_RE.fullmatch(value):
        _fail()
    return value


def validate_genre_model(model: Mapping[str, Any], manifest: Mapping[str, Any] | None = None) -> None:
    """Model schema stage, then model binding stage (contract section 5)."""
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "feature_record_schema_hash",
        "vocabulary_hash",
        "trajectory_template_set_hash",
        "required_groups",
        "entries",
        "model_hash",
    }
    if not isinstance(model, Mapping) or set(model) != required:
        _fail()
    if (
        model["schema"] != GENRE_MODEL_SCHEMA
        or model["schema_version"] != GENRE_SCHEMA_VERSION
        or model["algorithm"] != GENRE_MODEL_ALGORITHM
        or model["feature_record_schema_hash"] != GENRE_FEATURE_RECORD_SCHEMA_HASH
        or model["required_groups"] != ["harmony"]
    ):
        _fail()
    for key in ("vocabulary_hash", "trajectory_template_set_hash"):
        field = model[key]
        if not isinstance(field, str) or not field.startswith(_SHA_PREFIX):
            _fail()
    entries = model["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
        _fail()
    entry_required = {
        "genre_id",
        "ordinal",
        "chord_vocabulary_target_q31",
        "progression_target_q31",
        "function_target_q",
        "voice_leading_target_q",
        "harmonic_rhythm_target_q",
        "detail_weights_q",
        "cliche_template_ordinals",
        "novelty_exemplars_q31",
    }
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != entry_required:
            _fail()
        _validate_genre_id(entry["genre_id"])
        if not _is_int(entry["ordinal"], 0, 63):
            _fail()
        _validate_hist(entry["chord_vocabulary_target_q31"])
        _validate_hist(entry["progression_target_q31"])
        _validate_profile(entry["function_target_q"], 5)
        _validate_profile(entry["voice_leading_target_q"], 3)
        _validate_profile(entry["harmonic_rhythm_target_q"], 4)
        weights = entry["detail_weights_q"]
        if not isinstance(weights, list) or len(weights) != 5:
            _fail()
        if any(not _is_int(item, 0, 10_000) for item in weights):
            _fail()
        if _checked_sum(weights) != 10_000:
            _fail()
        cliche = entry["cliche_template_ordinals"]
        if not isinstance(cliche, list) or len(cliche) > 256:
            _fail()
        if any(not _is_int(item, 0, 4095) for item in cliche) or len(set(cliche)) != len(cliche):
            _fail()
        exemplars = entry["novelty_exemplars_q31"]
        if not isinstance(exemplars, list) or not 1 <= len(exemplars) <= 256:
            _fail()
        for histogram in exemplars:
            _validate_hist(histogram)
    # Binding stage: self hash and (when a manifest is supplied) the exact
    # manifest genre_model_hash binding.
    if model["model_hash"] != genre_model_hash(model):
        _fail()
    if manifest is not None and model["model_hash"] != manifest.get("genre_model_hash"):
        _fail()


def validate_genre_feature_record(
    record: Mapping[str, Any],
    model: Mapping[str, Any] | None = None,
    phase4_report: Mapping[str, Any] | None = None,
) -> None:
    """Feature extraction/schema stage validation (contract section 5)."""
    required = {
        "schema",
        "schema_version",
        "algorithm",
        "source_phase4_report_hash",
        "vocabulary_hash",
        "trajectory_template_set_hash",
        "chord_vocabulary_histogram_q31",
        "progression_histogram_q31",
        "function_profile_q",
        "voice_leading_profile_q",
        "harmonic_rhythm_profile_q",
        "record_hash",
    }
    if not isinstance(record, Mapping) or set(record) != required:
        _fail()
    if (
        record["schema"] != GENRE_FEATURE_RECORD_SCHEMA
        or record["schema_version"] != GENRE_SCHEMA_VERSION
        or record["algorithm"] != GENRE_EXTRACT_ALGORITHM
    ):
        _fail()
    for key in ("source_phase4_report_hash", "vocabulary_hash", "trajectory_template_set_hash"):
        field = record[key]
        if not isinstance(field, str) or not field.startswith(_SHA_PREFIX):
            _fail()
    _validate_hist(record["chord_vocabulary_histogram_q31"])
    _validate_hist(record["progression_histogram_q31"])
    _validate_profile(record["function_profile_q"], 5)
    _validate_profile(record["voice_leading_profile_q"], 3)
    _validate_profile(record["harmonic_rhythm_profile_q"], 4)
    if record["record_hash"] != genre_feature_record_hash(record):
        _fail()
    if model is not None and (
        record["vocabulary_hash"] != model["vocabulary_hash"]
        or record["trajectory_template_set_hash"] != model["trajectory_template_set_hash"]
    ):
        _fail()
    if phase4_report is not None and record["source_phase4_report_hash"] != report_hash(
        phase4_report
    ):
        _fail()


# ---------------------------------------------------------------------------
# Feature extraction (contract section 2)
# ---------------------------------------------------------------------------


def _normalize_q31_sparse(raw: Mapping[int, int]) -> list[dict[str, int]]:
    """Floor + largest-remainder (smaller ordinal first) to exactly Q31,
    emitted as sparse positive bins."""
    total = sum(raw.values())
    if total <= 0:
        _fail()
    rows = []
    for ordinal in sorted(raw):
        units = raw[ordinal] * Q31_TOTAL // total
        rows.append([ordinal, units, raw[ordinal] * Q31_TOTAL % total])
    remainder = Q31_TOTAL - sum(row[1] for row in rows)
    order = sorted(range(len(rows)), key=lambda index: (-rows[index][2], rows[index][0]))
    for index in order[:remainder]:
        rows[index][1] += 1
    return [
        {"ordinal": ordinal, "weight_q31": units}
        for ordinal, units, _ in rows
        if units > 0
    ]


def _normalize_q10000_dense(raw: Sequence[int]) -> list[int]:
    total = sum(raw)
    if total <= 0:
        _fail()
    units = [value * 10_000 // total for value in raw]
    remainder = 10_000 - sum(units)
    order = sorted(
        range(len(raw)),
        key=lambda index: (-(raw[index] * 10_000 % total), index),
    )
    for index in order[:remainder]:
        units[index] += 1
    return units


def _rhe_mean(values: Sequence[int]) -> int | None:
    if not values:
        return None
    return _rhe(Fraction(sum(values), len(values)))


def extract_genre_feature_record(
    project: Mapping[str, Any],
    phase4_report: Mapping[str, Any],
    chord_vocabulary: Mapping[str, Any],
    trajectory_template_set: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive the harmony ``PerceptualGenreFeatureRecord 1.0`` from one
    successful Phase 4 report (contract section 2)."""
    if (
        phase4_report.get("status") != "success"
        or phase4_report.get("completed_phase") != "functional_trajectory"
        or report_hash(phase4_report) != phase4_report.get("report_hash")
    ):
        _fail()
    clock = project.get("clock")
    ticks_per_beat = clock.get("ticks_per_beat") if isinstance(clock, Mapping) else None
    if not _is_int(ticks_per_beat, 1, 737_280):
        _fail()

    vocabulary_ordinals = {entry["id"]: entry["ordinal"] for entry in chord_vocabulary["entries"]}
    template_ordinals = {
        template["id"]: template["ordinal"] for template in trajectory_template_set["templates"]
    }

    segments = phase4_report["segments"]
    interpretations = phase4_report["segment_interpretations"]
    if len(segments) != len(interpretations) or not segments:
        _fail()

    chord_raw: dict[int, int] = {}
    for segment, interpretation in zip(segments, interpretations):
        duration = segment["end_tick"] - segment["start_tick"]
        if duration <= 0:
            _fail()
        for candidate in interpretation["candidates"]:
            ordinal = vocabulary_ordinals.get(candidate["id"])
            if ordinal is None:
                _fail()
            product = duration * candidate["similarity_q"]
            if product > U64_MAX:
                _fail("PIL_NUMERIC_OVERFLOW")
            chord_raw[ordinal] = chord_raw.get(ordinal, 0) + product
            if chord_raw[ordinal] > U64_MAX:
                _fail("PIL_NUMERIC_OVERFLOW")

    progression_raw: dict[int, int] = {}
    for result in phase4_report["trajectory_interpretations"]:
        ordinal = template_ordinals.get(result["template_id"])
        if ordinal is None:
            _fail()
        progression_raw[ordinal] = progression_raw.get(ordinal, 0) + result["similarity_q"]
        if progression_raw[ordinal] > U64_MAX:
            _fail("PIL_NUMERIC_OVERFLOW")

    transitions = phase4_report["transition_feature_records"]
    function_components: list[list[int]] = [[], [], [], [], []]
    for record in transitions:
        for index, key in ((0, "bass_fifth_likeness_q"), (1, "bass_fourth_likeness_q")):
            value = record[key]
            if value is not None:
                function_components[index].append(value)
        function_components[2].append(record["step_up_resolution_q"])
        function_components[3].append(record["step_down_resolution_q"])
        function_components[4].append(10_000 - abs(record["directed_tension_change_q"]))
    function_profile = [_rhe_mean(values) for values in function_components]

    matching = phase4_report["voice_matching_records"]
    voice_components: list[list[int]] = [[], [], []]
    for record in matching:
        voice_components[0].append(10_000 - record["total_cost_q"])
        voice_components[1].append(record["common_tone_q"])
        voice_components[2].append(record["contrary_motion_q"])
    voice_profile = [_rhe_mean(values) for values in voice_components]

    rhythm_raw = [0, 0, 0, 0]
    for segment in segments:
        duration = segment["end_tick"] - segment["start_tick"]
        if duration * 2 < ticks_per_beat:
            rhythm_raw[0] += duration
        elif duration < ticks_per_beat:
            rhythm_raw[1] += duration
        elif duration < 2 * ticks_per_beat:
            rhythm_raw[2] += duration
        else:
            rhythm_raw[3] += duration
    rhythm_profile = _normalize_q10000_dense(rhythm_raw)

    record = {
        "schema": GENRE_FEATURE_RECORD_SCHEMA,
        "schema_version": GENRE_SCHEMA_VERSION,
        "algorithm": GENRE_EXTRACT_ALGORITHM,
        "source_phase4_report_hash": phase4_report["report_hash"],
        "vocabulary_hash": chord_vocabulary["vocabulary_hash"],
        "trajectory_template_set_hash": trajectory_template_set["template_set_hash"],
        "chord_vocabulary_histogram_q31": _normalize_q31_sparse(chord_raw),
        "progression_histogram_q31": _normalize_q31_sparse(progression_raw),
        "function_profile_q": function_profile,
        "voice_leading_profile_q": voice_profile,
        "harmonic_rhythm_profile_q": rhythm_profile,
    }
    record["record_hash"] = genre_feature_record_hash(record)
    validate_genre_feature_record(record)
    return record


# ---------------------------------------------------------------------------
# Scoring (contract section 3)
# ---------------------------------------------------------------------------


def _dense(histogram: Sequence[Mapping[str, int]], size: int) -> list[int]:
    out = [0] * size
    for row in histogram:
        if row["ordinal"] >= size:
            _fail()
        out[row["ordinal"]] = row["weight_q31"]
    return out


def _hist_sim(left: Sequence[int], right: Sequence[int]) -> int:
    distance = _checked_sum([abs(a - b) for a, b in zip(left, right)])
    return 10_000 - _rhe(Fraction(10_000 * distance, 2 * Q31_TOTAL))


def _profile_sim(left: Sequence[int | None], right: Sequence[int | None]) -> int | None:
    values = [
        10_000 - abs(a - b)
        for a, b in zip(left, right)
        if a is not None and b is not None
    ]
    return _rhe_mean(values)


def evaluate_genre(
    model: Mapping[str, Any], feature_record: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Score every model entry against the feature record (contract section 3)."""
    validate_genre_model(model)
    validate_genre_feature_record(feature_record, model=model)

    max_vocab = 1 + max(
        [row["ordinal"] for row in feature_record["chord_vocabulary_histogram_q31"]]
        + [
            row["ordinal"]
            for entry in model["entries"]
            for row in entry["chord_vocabulary_target_q31"]
        ]
    )
    max_traj = 1 + max(
        [row["ordinal"] for row in feature_record["progression_histogram_q31"]]
        + [
            row["ordinal"]
            for entry in model["entries"]
            for histogram in (entry["progression_target_q31"], *entry["novelty_exemplars_q31"])
            for row in histogram
        ]
    )
    observed_vocab = _dense(feature_record["chord_vocabulary_histogram_q31"], max_vocab)
    observed_traj = _dense(feature_record["progression_histogram_q31"], max_traj)

    results = []
    for entry in model["entries"]:
        details = [
            _hist_sim(observed_vocab, _dense(entry["chord_vocabulary_target_q31"], max_vocab)),
            _hist_sim(observed_traj, _dense(entry["progression_target_q31"], max_traj)),
            _profile_sim(feature_record["function_profile_q"], entry["function_target_q"]),
            _profile_sim(feature_record["voice_leading_profile_q"], entry["voice_leading_target_q"]),
            _profile_sim(
                feature_record["harmonic_rhythm_profile_q"], entry["harmonic_rhythm_target_q"]
            ),
        ]
        weights = entry["detail_weights_q"]
        available = [(value, weight) for value, weight in zip(details, weights) if value is not None and weight]
        idiom = [
            (details[index], weights[index])
            for index in (2, 3, 4)
            if details[index] is not None and weights[index]
        ]
        if not available or not idiom:
            _fail()
        cliche_mass = _checked_sum(
            [observed_traj[index] for index in entry["cliche_template_ordinals"] if index < max_traj]
        )
        novelty = min(
            _rhe(
                Fraction(
                    10_000
                    * _checked_sum(
                        [
                            abs(a - b)
                            for a, b in zip(observed_traj, _dense(histogram, max_traj))
                        ]
                    ),
                    2 * Q31_TOTAL,
                )
            )
            for histogram in entry["novelty_exemplars_q31"]
        )
        result = {
            "schema": GENRE_RESULT_SCHEMA,
            "schema_version": GENRE_SCHEMA_VERSION,
            "genre_id": entry["genre_id"],
            "model_ordinal": entry["ordinal"],
            "model_hash": model["model_hash"],
            "feature_record_hash": feature_record["record_hash"],
            "harmonic_detail_q": dict(zip(_DETAIL_KEYS, details)),
            "typicality_q": _rhe(
                Fraction(
                    _checked_sum([value * weight for value, weight in available]),
                    sum(weight for _, weight in available),
                )
            ),
            "idiomaticity_q": _rhe(
                Fraction(
                    _checked_sum([value * weight for value, weight in idiom]),
                    sum(weight for _, weight in idiom),
                )
            ),
            "cliche_dependence_q": _rhe(Fraction(10_000 * cliche_mass, Q31_TOTAL)),
            "novelty_q": novelty,
            "missing_groups": list(MISSING_GROUPS),
        }
        result["result_hash"] = genre_result_hash(result)
        results.append(result)
    ordered = sorted(
        results, key=lambda row: (-row["typicality_q"], row["model_ordinal"], row["genre_id"].encode())
    )
    _validate_results(ordered)
    return ordered


def _validate_results(results: Sequence[Mapping[str, Any]]) -> None:
    """Genre scoring/result validation stage (contract section 5)."""
    if not 1 <= len(results) <= 64:
        _fail()
    for result in results:
        if result["result_hash"] != genre_result_hash(result):
            _fail()
        if result["missing_groups"] != list(MISSING_GROUPS):
            _fail()
        for key in ("typicality_q", "idiomaticity_q", "cliche_dependence_q", "novelty_q"):
            if not _is_int(result[key], 0, 10_000):
                _fail()
        for key in _DETAIL_KEYS:
            value = result["harmonic_detail_q"][key]
            if value is not None and not _is_int(value, 0, 10_000):
                _fail()


# ---------------------------------------------------------------------------
# Cache (contract section 5)
# ---------------------------------------------------------------------------


def phase5_cache_key(
    *,
    project_hash: str,
    phase4_report_hash: str,
    pil_manifest_hash: str,
    genre_model_hash_value: str,
    feature_record_hash: str,
    requested_phase: str = PHASE5_COMPLETED_PHASE,
) -> str:
    body = {
        "project_hash": project_hash,
        "phase4_report_hash": phase4_report_hash,
        "pil_manifest_hash": pil_manifest_hash,
        "genre_model_hash": genre_model_hash_value,
        "feature_record_hash": feature_record_hash,
        "implementation_build_id": PHASE5_BUILD_ID,
        "requested_phase": requested_phase,
    }
    digest = hashlib.sha256(b"cps.pil-phase5-cache-key/v1\0" + _canonical(body)).hexdigest()
    return _SHA_PREFIX + digest


def _cache_read(cache_dir: Path, key: str) -> bytes | None:
    """Return cached canonical result bytes; any malformed entry is a corrupt
    miss and is never repaired in place (contract section 5)."""
    try:
        raw = (cache_dir / f"{key[len(_SHA_PREFIX):]}.json").read_bytes()
    except OSError:
        return None
    try:
        entry = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(entry, dict) or _canonical(entry) != raw:
        return None
    payload_text = entry.get("canonical_results")
    digest = entry.get("canonical_results_sha256")
    if not isinstance(payload_text, str) or not isinstance(digest, str):
        return None
    payload = payload_text.encode("utf-8")
    if _SHA_PREFIX + hashlib.sha256(payload).hexdigest() != digest:
        return None
    try:
        results = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(results, list) or _canonical(results) != payload:
        return None
    return payload


def _cache_write(cache_dir: Path, key: str, payload: bytes) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "canonical_results": payload.decode("utf-8"),
        "canonical_results_sha256": _SHA_PREFIX + hashlib.sha256(payload).hexdigest(),
    }
    target = cache_dir / f"{key[len(_SHA_PREFIX):]}.json"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=cache_dir)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical(entry))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


# ---------------------------------------------------------------------------
# Run-level integration
# ---------------------------------------------------------------------------


def run_genre_interpretation(
    genre_model: Mapping[str, Any],
    genre_feature_record: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any] | None = None,
    phase4_report: Mapping[str, Any] | None = None,
    project_hash: str | None = None,
    cache_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Execute Phase 5 over complete bound payloads (contract section 1).

    A hash alone is never executable: both the model and the feature record
    payloads are required.  When ``manifest`` / ``phase4_report`` are given,
    their bindings are authenticated as well.  Cache cold, hit and corrupt
    executions return byte-identical results.
    """
    validate_genre_model(genre_model, manifest)
    validate_genre_feature_record(genre_feature_record, model=genre_model, phase4_report=phase4_report)

    key = None
    cache_path = Path(cache_dir) if cache_dir is not None else None
    if cache_path is not None:
        key = phase5_cache_key(
            project_hash=project_hash or (phase4_report or {}).get("project_hash", ""),
            phase4_report_hash=genre_feature_record["source_phase4_report_hash"],
            pil_manifest_hash=(manifest or {}).get("manifest_hash", ""),
            genre_model_hash_value=genre_model["model_hash"],
            feature_record_hash=genre_feature_record["record_hash"],
        )
        cached = _cache_read(cache_path, key)
        if cached is not None:
            return json.loads(cached)

    results = evaluate_genre(genre_model, genre_feature_record)
    if cache_path is not None and key is not None:
        _cache_write(cache_path, key, canonical_results_bytes(results))
    return results


__all__ = (
    "GENRE_EXTRACT_ALGORITHM",
    "GENRE_FEATURE_RECORD_SCHEMA",
    "GENRE_FEATURE_RECORD_SCHEMA_HASH",
    "GENRE_MODEL_ALGORITHM",
    "GENRE_MODEL_SCHEMA",
    "GENRE_RESULT_SCHEMA",
    "GENRE_SCHEMA_VERSION",
    "MISSING_GROUPS",
    "PHASE5_BUILD_ID",
    "PHASE5_COMPLETED_PHASE",
    "canonical_results_bytes",
    "evaluate_genre",
    "extract_genre_feature_record",
    "genre_feature_record_hash",
    "genre_model_hash",
    "genre_result_hash",
    "phase5_cache_key",
    "run_genre_interpretation",
    "validate_genre_feature_record",
    "validate_genre_model",
)
