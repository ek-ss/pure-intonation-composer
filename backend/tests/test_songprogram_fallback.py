"""Production fallback/lowering regressions; conformance fixtures stay read-only."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from subprocess import run
import sys

from app.songprogram import fallback
from app.songprogram.fallback import (
    FallbackError,
    execute_broad_prior_production,
    execute_fallback,
    lower_broad_prior_choices,
    structural_lowering_manifest_hash,
    structural_program_hash,
)
from app.songprogram.mutation import program_hash
from app.songprogram.search import canonical_bytes


ROOT = Path(__file__).parents[1] / "songprogram_conformance" / "fixtures" / "fallback_sampler"
PROGRAM_PATH = Path(__file__).parents[1] / "songprogram_conformance" / "fixtures" / "pack" / "minimal_direct_song_program.json"


def _load(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text())


def _fallback_request() -> tuple[dict[str, object], dict[str, object]]:
    manifest = _load("fallback_manifest_semantic.json")
    program = json.loads(PROGRAM_PATH.read_text())
    digest = program_hash(program)
    request: dict[str, object] = {
        "schema": "cps.fallback-request", "schema_version": "1.0.0", "root_seed": 0,
        "action_coordinate": {"run_id": "test", "round": 2, "candidate": 3},
        "run_manifest_hash": "sha256:" + "a" * 64, "planner_manifest_hash": "sha256:" + "b" * 64,
        "fallback_manifest": manifest, "fallback_manifest_hash": "sha256:" + "c" * 64,
        "mutation_choice_catalog_hash": "sha256:" + "d" * 64, "program": program,
        "program_hash": digest, "locked_roots": [], "diagnostic_codes": [],
        "requested_mutation_count": 1, "request_hash": "sha256:" + "e" * 64,
    }
    application: dict[str, object] = {
        "schema": "cps.mutation-application-request", "schema_version": "1.1.0",
        "base_program": program, "base_program_hash": digest, "mutations": [], "locked_roots": [],
        "mutation_choice_catalog": {"schema": "cps.mutation-choice-catalog", "schema_version": "1.0.0", "entries": []},
        "instrument_catalog": {"entries": []},
    }
    return request, application


def _production_request() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manifest = _load("production_manifest.json")
    catalog = _load("production_catalog.json")
    program = json.loads(PROGRAM_PATH.read_text())
    program["lattice"]["base_frequency_millihz"] = 440000
    catalog_digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)).hexdigest()
    manifest["instrument_catalog_digest"] = catalog_digest
    manifest["maximum_production_rejections"] = 16
    request: dict[str, object] = {
        "schema": "cps.broad-prior-production-request", "schema_version": "1.0.0", "root_seed": 7,
        "cohort_index": 0, "production_rejection_ordinal": 0,
        "sampler_manifest_hash": manifest["sampler_manifest_hash"],
        "lowering_manifest_hash": fallback._artifact_hash("cps.production-lowering-manifest/v1", manifest),
        "instrument_catalog_digest": catalog_digest, "program": program,
        "structural_program_hash": program_hash(program), "active_roles": ["melody"],
        "lattice_equave": "2/1", "request_hash": "sha256:" + "f" * 64,
    }
    return request, manifest, catalog


def _structural_lowering_manifest() -> dict[str, object]:
    """A sealed boundary value; production must authenticate but not read it."""
    manifest: dict[str, object] = {
        "schema": "cps.structural-lowering-manifest", "schema_version": "1.0.0",
        "algorithm": "structural-song-program-lowering/v1",
        "structural_program_schema_hash": "sha256:" + "a" * 64,
        "id_policy": {}, "clock": {}, "lattice_constants": {}, "section_templates": {},
        "material_builders": {}, "chord_constants": {}, "realization_constants": {},
        "rhythm_position_policy": "ascending-even-grid-prefix/v1", "compile_policy": {},
        "limits": {}, "manifest_hash": "",
    }
    manifest["manifest_hash"] = structural_lowering_manifest_hash(manifest)
    return manifest


def _production_v11_request() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    legacy_request, manifest, catalog = _production_request()
    manifest.update({
        "schema": "cps.broad-prior-production-manifest", "schema_version": "1.0.0",
        "algorithm": "broad-prior-production-lowering/v1",
        "choice_algorithm": "sha256-u64-mod-cumulative/v1",
        "role_order": ["drums", "bass", "harmony", "melody", "texture"],
        "maximum_production_rejections": 16,
    })
    structural = deepcopy(legacy_request["program"])
    structural.pop("tracks")
    structural.pop("production")
    structural["schema"] = "cps.structural-song-program"
    structural["schema_version"] = "1.0.0"
    structural["realizations"] = [
        {**deepcopy(structural["realizations"][0]), "id": f"real_{role}", "role": role}
        for role in ("bass", "harmony", "melody")
    ]
    for realization in structural["realizations"]:
        realization.pop("track_id")
    structural_manifest = _structural_lowering_manifest()
    request: dict[str, object] = {
        "schema": "cps.broad-prior-production-request", "schema_version": "1.1.0",
        "run_hash": "sha256:" + "1" * 64, "context_hash": "sha256:" + "2" * 64,
        "source_decision_hash": "sha256:" + "3" * 64,
        "root_seed": 7, "cohort_index": 0, "production_rejection_ordinal": 0,
        "sampler_manifest_hash": manifest["sampler_manifest_hash"],
        "structural_lowering_manifest_hash": structural_manifest["manifest_hash"],
        "production_lowering_manifest_hash": fallback._artifact_hash("cps.production-lowering-manifest/v1", manifest),
        "instrument_catalog_digest": legacy_request["instrument_catalog_digest"],
        "structural_program_hash": structural_program_hash(structural),
        "structural_program": structural, "active_roles": ["bass", "harmony", "melody"],
        "lattice_equave": "2/1", "request_hash": "sha256:" + "4" * 64,
    }
    request["request_hash"] = fallback._search_decision_hash(request, "request_hash")
    return request, manifest, catalog, structural_manifest


def test_fallback_submits_one_atomic_application_batch(monkeypatch) -> None:
    request, application = _fallback_request()
    calls = 0
    original = fallback.apply_mutation_request

    def counted(batch: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return original(batch)  # type: ignore[arg-type]

    monkeypatch.setattr(fallback, "apply_mutation_request", counted)
    result = execute_fallback(request, application)
    assert calls == 1
    assert result["application"]["status"] == "success"
    mutations = result["result"]["mutations"]
    assert len(mutations) == 1
    assert mutations[0]["base_program_hash"] == request["program_hash"]


def test_fallback_is_cold_process_stable() -> None:
    request, application = _fallback_request()
    first = execute_fallback(request, application)
    payload = json.dumps(
        {"request": request, "application": application},
        sort_keys=True,
        separators=(",", ":"),
    )
    code = (
        "import json,sys; from app.songprogram.fallback import execute_fallback; "
        "x=json.loads(sys.stdin.read()); "
        "print(json.dumps(execute_fallback(x['request'],x['application']),"
        "sort_keys=True,separators=(',',':')))"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parents[1])
    second = run(
        [sys.executable, "-c", code],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    ).stdout
    assert json.loads(second) == first


def test_production_lowering_preserves_structure_and_is_cold_process_stable() -> None:
    request, manifest, catalog = _production_request()
    first = execute_broad_prior_production(request, manifest, catalog)
    lowered = first["output"]["program"]
    original = request["program"]
    assert [track["id"] for track in lowered["tracks"]] == [track["id"] for track in original["tracks"]]
    assert lowered["realizations"] == original["realizations"]
    assert lowered["materials"] == original["materials"]
    assert lowered["production"]["envelopes"] == []
    payload = json.dumps({"request": request, "manifest": manifest, "catalog": catalog}, sort_keys=True, separators=(",", ":"))
    code = "import json,sys; from app.songprogram.fallback import execute_broad_prior_production; x=json.loads(sys.stdin.read()); print(json.dumps(execute_broad_prior_production(x['request'],x['manifest'],x['catalog']),sort_keys=True,separators=(',',':')))"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parents[1])
    second = run([sys.executable, "-c", code], input=payload, text=True, capture_output=True, check=True, env=environment).stdout
    assert json.loads(second) == first


def test_production_rejects_missing_or_extra_role_shells() -> None:
    request, manifest, catalog = _production_request()
    missing = deepcopy(request)
    missing["program"]["tracks"] = []
    missing["structural_program_hash"] = program_hash(missing["program"])
    result = execute_broad_prior_production(missing, manifest, catalog)
    assert result["status"] == "failure"
    assert result["error"] == "SAMPLER_RESULT_INVALID"


def test_production_retries_rejections_and_keeps_trace_prefix() -> None:
    request, manifest, catalog = _production_request()
    manifest["maximum_production_rejections"] = 2
    manifest["instrument_entries_by_role"]["melody"] = [
        {"value": "melody_inst", "weight": 1},
        {"value": "missing", "weight": 1},
    ]
    manifest["instrument_catalog_digest"] = request["instrument_catalog_digest"]
    manifest_hash = fallback._artifact_hash("cps.production-lowering-manifest/v1", manifest)
    request["lowering_manifest_hash"] = manifest_hash
    for seed in range(10_000):
        request["root_seed"] = seed
        first = deepcopy(request)
        second = deepcopy(request)
        second["production_rejection_ordinal"] = 1
        try:
            lower_broad_prior_choices(first, manifest, catalog)
        except FallbackError:
            try:
                lower_broad_prior_choices(second, manifest, catalog)
            except FallbackError:
                continue
            break
    else:
        raise AssertionError("test manifest did not produce a retry path")
    result = execute_broad_prior_production(request, manifest, catalog)
    assert result["status"] == "success"
    assert result["rejections_consumed"] == 1
    assert [row["production_rejection_ordinal"] for row in result["decision_trace"]] == [
        *([0] * 2),
        *([1] * 6),
    ]


def test_production_rejection_ceiling_returns_typed_failure_and_trace_prefix() -> None:
    request, manifest, catalog = _production_request()
    manifest["maximum_production_rejections"] = 2
    manifest["instrument_entries_by_role"]["melody"] = [{"value": "missing", "weight": 1}]
    request["lowering_manifest_hash"] = fallback._artifact_hash("cps.production-lowering-manifest/v1", manifest)
    result = execute_broad_prior_production(request, manifest, catalog)
    assert result["status"] == "failure"
    assert result["error"] == "SAMPLER_NO_COMPATIBLE_INSTRUMENT"
    assert result["rejections_consumed"] == 2
    assert [row["production_rejection_ordinal"] for row in result["decision_trace"]] == [0, 0, 1, 1]


def test_production_failure_precedence_is_manifest_catalog_active_then_result() -> None:
    request, manifest, catalog = _production_request()
    malformed = deepcopy(request)
    malformed["lowering_manifest_hash"] = "sha256:" + "0" * 64
    malformed["instrument_catalog_digest"] = "sha256:" + "1" * 64
    assert execute_broad_prior_production(malformed, manifest, catalog)["error"] == "SAMPLER_PRODUCTION_MANIFEST_INVALID"
    catalog_first = deepcopy(request)
    catalog_first["instrument_catalog_digest"] = "sha256:" + "1" * 64
    catalog_first["active_roles"] = ["melody", "drums"]
    assert execute_broad_prior_production(catalog_first, manifest, catalog)["error"] == "SAMPLER_CATALOG_MISMATCH"
    active_first = deepcopy(request)
    active_first["active_roles"] = ["melody", "drums"]
    active_first["structural_program_hash"] = "sha256:" + "0" * 64
    assert execute_broad_prior_production(active_first, manifest, catalog)["error"] == "SAMPLER_ACTIVE_ROLE_INVALID"


def test_v11_production_creates_canonical_tracks_and_rebinds_structural_realizations() -> None:
    request, manifest, catalog, structural_manifest = _production_v11_request()
    result = execute_broad_prior_production(request, manifest, catalog, structural_manifest)
    assert result["status"] == "success"
    assert result["schema_version"] == "1.1.0"
    assert result["structural_program_hash"] == request["structural_program_hash"]
    program = result["output"]["program"]
    assert [track["id"] for track in program["tracks"]] == ["trk_bass", "trk_harmony", "trk_melody"]
    assert [track["role"] for track in program["tracks"]] == ["bass", "harmony", "melody"]
    assert [realization["track_id"] for realization in program["realizations"]] == [
        "trk_bass", "trk_harmony", "trk_melody",
    ]
    assert all("role" not in realization for realization in program["realizations"])
    assert program["production"]["tracks"].keys() == {"trk_bass", "trk_harmony", "trk_melody"}
    assert result["output"]["program_hash"] == program_hash(program)


def test_v11_production_requires_the_exact_structural_lowering_manifest_before_catalog() -> None:
    request, manifest, catalog, structural_manifest = _production_v11_request()
    request["instrument_catalog_digest"] = "sha256:" + "0" * 64
    request["request_hash"] = fallback._search_decision_hash(request, "request_hash")
    structural_manifest["manifest_hash"] = "sha256:" + "0" * 64
    result = execute_broad_prior_production(request, manifest, catalog, structural_manifest)
    assert result["status"] == "failure"
    assert result["error"] == "SAMPLER_PRODUCTION_MANIFEST_INVALID"
    assert result["decision_trace"] == []
