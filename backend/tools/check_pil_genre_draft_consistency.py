"""Check internal consistency of the PIL genre-interpretation design drafts.

The draft JSON schemas in ``docs/pil_genre_draft/`` are non-normative design
material for contract section 7 (blockers G1-G7, see
``docs/song_program_pil_genre_interpretation_draft.md``).  This tool verifies
that the drafts stay aligned with the *authoritative* report/manifest schemas
they propose to extend, and reports which blockers are still open.

It never writes anything and never touches the protected
``backend/songprogram_conformance/`` tree.

Run from the backend directory:

    python tools/check_pil_genre_draft_consistency.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
DRAFT_DIR = REPO / "docs" / "pil_genre_draft"
SCHEMA_DIR = BACKEND / "songprogram_conformance" / "schemas"
DRAFT_DOC = REPO / "docs" / "song_program_pil_genre_interpretation_draft.md"

FAILURES: list[str] = []
NOTES: list[str] = []


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _fail(message: str) -> None:
    FAILURES.append(message)


def _note(message: str) -> None:
    NOTES.append(message)


# ---------------------------------------------------------------------------
# Minimal validator for the JSON-Schema subset used by the draft schemas.
# Supports: type, const, enum, pattern, minimum, maximum, minItems, maxItems,
# uniqueItems, items, required, properties, additionalProperties, local $ref.
# ---------------------------------------------------------------------------


def _resolve(root: dict, node: dict) -> dict:
    ref = node.get("$ref")
    if not ref:
        return node
    if not ref.startswith("#/$defs/"):
        raise ValueError(f"unsupported $ref: {ref}")
    return _resolve(root, root["$defs"][ref.split("/")[-1]])


def _validate(root: dict, schema: dict, value, path: str, errors: list[str]) -> None:
    schema = _resolve(root, schema)
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']!r}")
        return
    stype = schema.get("type")
    if stype == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object")
            return
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: unexpected key {key!r}")
        for key, sub in props.items():
            if key in value:
                _validate(root, sub, value[key], f"{path}.{key}", errors)
    elif stype == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array")
            return
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems") and len(set(map(repr, value))) != len(value):
            errors.append(f"{path}: items not unique")
        for index, item in enumerate(value):
            _validate(root, schema.get("items", {}), item, f"{path}[{index}]", errors)
    elif stype == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string")
            return
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} fails pattern {schema['pattern']!r}")
    elif stype == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}: expected integer")
            return
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")


def _check_schema_well_formed(name: str, schema: dict) -> None:
    for key in ("$id", "title", "type"):
        if key not in schema:
            _fail(f"{name}: missing top-level {key!r}")
    if schema.get("type") != "object":
        _fail(f"{name}: top-level type must be 'object'")
    if "contract" in str(schema.get("$id", "")):
        _fail(f"{name}: draft $id must not claim contract status")


def _sample_model() -> dict:
    return {
        "schema": "cps.perceptual-genre-model",
        "schema_version": "1.0.0",
        "algorithm": "pil-genre-prototype-l1/v1",
        "model_schema_hash": "sha256:" + "00" * 32,
        "feature_spec_hash": "sha256:" + "11" * 32,
        "vocabulary_hash": "sha256:" + "22" * 32,
        "trajectory_template_set_hash": "sha256:" + "33" * 32,
        "required_groups": ["harmony"],
        "entries": [
            {
                "genre_id": "draft.example",
                "ordinal": 0,
                "chord_vocabulary_targets": [
                    {"vocabulary_ordinal": 0, "weight_q31": 2147483647}
                ],
                "progression_targets": [
                    {"template_ordinal": 0, "weight_q31": 2147483647}
                ],
                "function_profile_q": [10000, 0],
                "voice_leading_profile_q": [5000],
                "harmonic_rhythm_profile_q": [0, 10000],
            }
        ],
        "model_hash": "sha256:" + "44" * 32,
    }


def _sample_feature_record() -> dict:
    return {
        "schema": "cps.perceptual-genre-feature-record",
        "schema_version": "1.0.0",
        "group": "harmony",
        "source_report_hash": "sha256:" + "55" * 32,
        "vocabulary_hash": "sha256:" + "22" * 32,
        "trajectory_template_set_hash": "sha256:" + "33" * 32,
        "chord_vocabulary_histogram_q31": [
            {"vocabulary_ordinal": 0, "weight_q31": 2147483647}
        ],
        "trajectory_histogram_q31": [
            {"template_ordinal": 0, "weight_q31": 2147483647}
        ],
        "function_profile_q": [10000, 0],
        "voice_leading_profile_q": [5000],
        "harmonic_rhythm_profile_q": [0, 10000],
        "record_hash": "sha256:" + "66" * 32,
    }


def _sample_interpretation() -> dict:
    return {
        "genre_id": "draft.example",
        "typicality_q": 8000,
        "idiomaticity_q": 7000,
        "cliche_dependence_q": 1000,
        "novelty_q": 500,
    }


def main() -> int:
    report_schema = _load(SCHEMA_DIR / "perceptual_interpretation_report.schema.json")
    manifest_schema = _load(SCHEMA_DIR / "perceptual_interpretation_manifest.schema.json")
    model_draft = _load(DRAFT_DIR / "genre_model.draft.schema.json")
    record_draft = _load(DRAFT_DIR / "genre_feature_record.draft.schema.json")
    interp_draft = _load(DRAFT_DIR / "genre_interpretation.draft.schema.json")

    for name, draft in (
        ("genre_model.draft.schema.json", model_draft),
        ("genre_feature_record.draft.schema.json", record_draft),
        ("genre_interpretation.draft.schema.json", interp_draft),
    ):
        _check_schema_well_formed(name, draft)

    # 1. GenreInterpretation draft must mirror the authoritative report $defs/genre.
    report_genre = report_schema["$defs"]["genre"]
    for key in ("required", "properties"):
        draft_view = interp_draft.get(key)
        report_view = report_genre.get(key)
        if key == "properties":
            draft_keys = sorted(draft_view)
            report_keys = sorted(report_view)
            if draft_keys != report_keys:
                _fail(f"genre_interpretation properties {draft_keys} != report {report_keys}")
        elif sorted(draft_view) != sorted(report_view):
            _fail(f"genre_interpretation required {draft_view} != report {report_view}")
    if interp_draft.get("additionalProperties") != report_genre.get("additionalProperties"):
        _fail("genre_interpretation additionalProperties mismatch with report $defs/genre")
    if interp_draft["$defs"]["q"] != report_schema["$defs"]["q"]:
        _fail("genre_interpretation q range differs from report $defs/q")

    # 2. Group vocabulary must match the authoritative missing_groups enum.
    report_groups = report_schema["properties"]["missing_groups"]["items"]["enum"]
    draft_groups = model_draft["$defs"]["group"]["enum"]
    if sorted(report_groups) != sorted(draft_groups):
        _fail(f"group enum {draft_groups} != report missing_groups enum {report_groups}")

    # 3. Sample instances must validate against the drafts.
    for name, draft, sample in (
        ("genre_model", model_draft, _sample_model()),
        ("genre_feature_record", record_draft, _sample_feature_record()),
        ("genre_interpretation", interp_draft, _sample_interpretation()),
    ):
        errors: list[str] = []
        _validate(draft, draft, sample, name, errors)
        for error in errors:
            _fail(f"sample {name}: {error}")

    # 4. Blocker status (informational; never fails the check).
    completed = report_schema["properties"]["completed_phase"]["enum"]
    if "genre_interpretation" in completed:
        _note("G6 appears CLOSED: completed_phase already includes 'genre_interpretation'")
    else:
        _note("G6 OPEN: completed_phase has no 'genre_interpretation' yet")
    gmh = manifest_schema["properties"].get("genre_model_hash")
    if gmh and any(branch.get("type") == "null" for branch in gmh.get("oneOf", [])):
        _note("G1 binding point present: manifest genre_model_hash is nullable sha256")
    else:
        _fail("manifest genre_model_hash missing or no longer nullable")
    if not DRAFT_DOC.exists():
        _fail(f"draft document missing: {DRAFT_DOC}")

    for note in NOTES:
        print(f"note: {note}")
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}")
        return 1
    print("pil genre draft consistency: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
