"""Read-only validator for the owner-promoted render matrix fixture."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from .build_render_determinism_matrix_fixture import (
    _silent_result,
    canonical_lf,
    domain_hash,
    project_hash,
    sha,
)


class MatrixFixtureError(ValueError):
    pass


def _load_canonical(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_lf(value):
        raise MatrixFixtureError("non-canonical fixture JSON")
    return value, raw


def validate(root: Path) -> None:
    manifest, _ = _load_canonical(root / "matrix_manifest.json")
    receipt, _ = _load_canonical(root / "matrix_receipt.json")
    fixture_set, fixture_raw = _load_canonical(root / "fixture_set.json")
    if manifest["fixture_set_hash"] != sha(fixture_raw):
        raise MatrixFixtureError("fixture-set hash mismatch")
    repo = root.parents[3]
    paths = [row["path"] for row in fixture_set["files"]]
    if paths != sorted(paths, key=lambda value: value.encode()) or len(paths) != len(set(paths)):
        raise MatrixFixtureError("fixture paths not ordered/unique")
    forbidden = {"fixture_set.json", "matrix_manifest.json", "matrix_receipt.json"}
    for row in fixture_set["files"]:
        if (
            Path(row["path"]).name in forbidden
            or unicodedata.normalize("NFC", row["path"]) != row["path"]
        ):
            raise MatrixFixtureError("invalid fixture-set member")
        raw = (repo / row["path"]).read_bytes()
        if row["byte_length"] != len(raw) or row["sha256"] != sha(raw):
            raise MatrixFixtureError("fixture member mismatch")
    render_manifest, _ = _load_canonical(
        repo / "backend/songprogram_conformance/fixtures/render/render_manifest.json"
    )
    catalog_raw = (
        repo / "backend/songprogram_conformance/fixtures/render/catalog.json"
    ).read_bytes()
    catalog_digest = sha(b"cps.instrument-catalog/v1\0" + catalog_raw)
    if (
        manifest["catalog_digest"] != catalog_digest
        or manifest["render_manifest_digest"] != render_manifest["render_manifest_digest"]
        or manifest["renderer_build_hash"] != render_manifest["renderer_build"]["source_sha256"]
    ):
        raise MatrixFixtureError("render authority binding mismatch")
    renderer_source = repo / render_manifest["renderer_build"]["source_artifact"]
    if sha(renderer_source.read_bytes()) != manifest["renderer_build_hash"]:
        raise MatrixFixtureError("renderer build hash mismatch")
    project_schema = (
        repo / "backend/songprogram_conformance/schemas/arrangement_project_1_2.schema.json"
    )
    if manifest["project_schema_hash"] != sha(project_schema.read_bytes()):
        raise MatrixFixtureError("project schema hash mismatch")
    if manifest["manifest_hash"] != domain_hash(
        "cps.render-determinism-matrix-manifest/v1",
        {k: v for k, v in manifest.items() if k != "manifest_hash"},
    ):
        raise MatrixFixtureError("manifest hash mismatch")
    case_ids = [row["case_id"] for row in manifest["cases"]]
    if case_ids != sorted(case_ids, key=str.encode) or len(case_ids) != len(set(case_ids)):
        raise MatrixFixtureError("case order invalid")
    for row in manifest["cases"]:
        project, _ = _load_canonical(root / "projects" / f"{row['case_id']}.json")
        if row["project_hash"] != project_hash(project):
            raise MatrixFixtureError("project hash mismatch")
        if project["events"] and not (
            len(project["events"]) == 1
            and project["events"][0]["kind"] == "drum"
            and project["events"][0]["drum_note"] == 36
            and project["events"][0]["velocity"] == 127
        ):
            raise MatrixFixtureError("oracle fixture is outside closed boundary profile")
        expected = _silent_result(project, manifest["render_manifest_digest"])
        if any(row[key] != expected[key] for key in expected):
            raise MatrixFixtureError("authoritative case hash mismatch")
    invocations = [
        [
            i,
            manifest["cases"][i % len(case_ids)]["case_id"],
            *[
                manifest["cases"][i % len(case_ids)][k]
                for k in ("wav_hash", "pcm_hash", "report_hash", "track_set_hash")
            ],
        ]
        for i in range(100)
    ]
    sequence = domain_hash("cps.render-determinism-sequence/v1", invocations)
    expected_coords = [(s, w) for s in (0, 1, 7, 42) for w in (1, 2, 4, 8)]
    if [
        (r["python_hash_seed"], r["workers"]) for r in receipt["process_coordinates"]
    ] != expected_coords:
        raise MatrixFixtureError("coordinate order invalid")
    if receipt["baseline_sequence_hash"] != sequence or any(
        r["sequence_hash"] != sequence for r in receipt["process_coordinates"]
    ):
        raise MatrixFixtureError("sequence mismatch")
    case_results = [
        [r[k] for k in ("case_id", "wav_hash", "pcm_hash", "report_hash", "track_set_hash")]
        for r in manifest["cases"]
    ]
    result_set = domain_hash("cps.render-block-case-result-set/v1", case_results)
    if [r["block_size"] for r in receipt["block_coordinates"]] != [64, 256, 1024] or any(
        r["case_result_set_hash"] != result_set for r in receipt["block_coordinates"]
    ):
        raise MatrixFixtureError("block result mismatch")
    if receipt["receipt_hash"] != domain_hash(
        "cps.render-determinism-matrix-receipt/v1",
        {k: v for k, v in receipt.items() if k != "receipt_hash"},
    ):
        raise MatrixFixtureError("receipt hash mismatch")
