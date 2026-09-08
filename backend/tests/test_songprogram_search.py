from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.songprogram.search import (
    ArchiveCandidate,
    LocalRunStore,
    ProductionSearchLoop,
    SearchLoopSeams,
    SearchArtifactError,
    action_id,
    canonical_bytes,
    descriptor_values,
    descriptor_result_from_project,
    fingerprint_distance_q,
    fingerprint_payloads_from_project,
    fingerprint_record,
    fingerprint_record_from_project,
    manifest_digest,
    sampler_choice,
    seal_record,
    stream_draw,
    stream_key,
    update_archive_record,
)
from app.songprogram.compiler import CompilerIdentity, build_lineage_index, compile_direct_sp0
from app.songprogram.connected import executor_manifest_digest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "songprogram_conformance" / "fixtures" / "search"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_sampler_stream_matches_independent_trace() -> None:
    sampler = _fixture("sampler_manifest.json")
    trace = _fixture("sampler_trace.json")
    assert manifest_digest("cps.sampler-manifest/v1", sampler) == trace["sampler_manifest_hash"]
    table = sampler["tables"]["section_count"]
    for expected in trace["traces"]:
        key = stream_key(trace["root_seed"], trace["cohort_index"], trace["path"])
        assert key.hex() == expected["stream_key_hex"]
        assert stream_draw(key, expected["counter"]) == expected["draw_u64"]
        assert sampler_choice(trace["root_seed"], trace["cohort_index"], trace["path"], expected["counter"], table) == (expected["choice_index"], expected["value"])


def test_archive_selection_matches_checked_in_record() -> None:
    fixture = _fixture("qd_archive_record.json")
    candidates = [fixture["champion"], *fixture["runners"]]
    record = update_archive_record(
        fixture["qd_manifest_hash"], fixture["cell"], fixture["revision"],
        [ArchiveCandidate(item["program_hash"], item["project_hash"], item["lineage_root_hash"], tuple(item["quality"])) for item in candidates],
        fixture["previous_record_hash"],
    )
    assert record == fixture
    assert update_archive_record(
        fixture["qd_manifest_hash"], fixture["cell"], fixture["revision"],
        [ArchiveCandidate(item["program_hash"], item["project_hash"], item["lineage_root_hash"], tuple(item["quality"])) for item in reversed(candidates)],
        fixture["previous_record_hash"],
    ) == fixture


def test_record_identity_and_local_cas_match_fixture(tmp_path: Path) -> None:
    run = _fixture("run_manifest.json")
    expected = _fixture("run_record_000.json")
    run_hash = manifest_digest("cps.search-run-manifest/v1", run)
    assert action_id(run_hash, 0, 0, 0) == expected["action_id"]
    assert seal_record(expected) == expected
    store = LocalRunStore(tmp_path, run_hash)
    payload_hex = expected["payload_hash"].removeprefix("sha256:")
    payload = (FIXTURES / "cas" / "sha256" / payload_hex[:2] / payload_hex[2:]).read_bytes()
    assert store.put(payload) == expected["payload_hash"]
    assert store.put(payload) == expected["payload_hash"]
    assert store.append({key: value for key, value in expected.items() if key != "record_hash"}) == expected
    assert store.records_path.read_bytes() == (FIXTURES / "records.log").read_bytes()


def test_local_run_store_rejects_stale_concurrent_append(tmp_path: Path) -> None:
    run_hash = "sha256:" + "1" * 64
    first = LocalRunStore(tmp_path, run_hash)
    stale = LocalRunStore(tmp_path, run_hash)
    payload_hash = first.put(canonical_bytes({"value": 1}))
    core = {
        "schema": "cps.search-run-record",
        "schema_version": "1.0.0",
        "run_hash": run_hash,
        "sequence": 0,
        "action_id": action_id(run_hash, 0, 0, 0),
        "round": 0,
        "phase_ordinal": 0,
        "candidate_ordinal": 0,
        "kind": "run",
        "payload_hash": payload_hash,
        "previous_record_hash": None,
    }
    first.append(core)
    with pytest.raises(SearchArtifactError, match="RUN_RECORD_APPEND_CONFLICT"):
        stale.append(core)


def test_sampler_and_action_boundaries_reject_without_fallback() -> None:
    with pytest.raises(SearchArtifactError, match="SAMPLER_WEIGHT_SUM_INVALID"):
        sampler_choice(0, 0, ["x"], 0, [{"value": 1, "weight": 0}])
    with pytest.raises(SearchArtifactError, match="ACTION_RANGE_INVALID"):
        action_id("sha256:" + "0" * 64, 0, 8, 0)


def test_production_stream_is_cross_process_and_hash_seed_invariant() -> None:
    sampler = _fixture("sampler_manifest.json")
    source = (
        "from app.songprogram.search import canonical_bytes, sampler_choice; "
        "import json; "
        f"table=json.loads({json.dumps(json.dumps(sampler['tables']['section_count']))}); "
        "print(canonical_bytes({'choice': list(sampler_choice(7, 0, ['form', 'section_count'], 0, table))}).decode(), end='')"
    )
    outputs = []
    for workers in (1, 2, 4, 8):
        for worker in range(workers):
            environment = dict(os.environ, PYTHONHASHSEED=str(worker))
            outputs.append(subprocess.check_output([sys.executable, "-c", source], cwd=ROOT, env=environment))
    assert len(set(outputs)) == 1


def test_descriptor_aggregation_matches_checked_in_case() -> None:
    case = _fixture("descriptor_case.json")
    result = _fixture("descriptor_result.json")
    actual = descriptor_values(
        [item["contribution"] for item in case["eligible_events"]],
        [item["weighted_jaccard_q"] for item in case["lineage_pairs"]],
    )
    assert actual == (result["rhythmic_syncopation_q"], result["material_recurrence_distance_q"])
    assert descriptor_values([], []) == (None, None)
    assert descriptor_values([], [1, 2]) == (None, 2)


def test_fingerprint_record_matches_independent_fixture() -> None:
    spec = _fixture("fingerprint_spec.json")
    case = _fixture("fingerprint_case.json")
    expected = _fixture("fingerprint_record.json")
    payloads = {item["id"]: item["payload"] for item in case["components"]}
    actual = fingerprint_record(
        spec, payloads, expected["project_hash"], expected["lineage_index_hash"]
    )
    assert actual == expected


def test_fingerprint_distances_cover_frozen_algorithms() -> None:
    spec = _fixture("fingerprint_spec.json")
    case = _fixture("fingerprint_case.json")
    original = {item["id"]: item["payload"] for item in case["components"]}
    assert fingerprint_distance_q(spec, original, original) == 0
    changed = {key: list(value) for key, value in original.items()}
    changed["section_bars"] = [4, 8]
    changed["role_time_grid"] = [["melody", 0, 4], ["melody", 0, 4]]
    changed["root_anchor_deltas"] = [[0, 0]]
    distance = fingerprint_distance_q(spec, original, changed)
    assert 0 < distance <= 10_000
    assert distance == fingerprint_distance_q(spec, changed, original)


def test_project_descriptor_extraction_uses_compiler_lineage() -> None:
    pack = ROOT / "songprogram_conformance" / "fixtures" / "pack"
    program = json.loads((pack / "minimal_direct_song_program.json").read_text())
    identity = CompilerIdentity("fixture-build", "fixture-resolver", "sha256:" + "0" * 64, "sha256:" + "0" * 64, "sha256:" + "0" * 64)
    project = compile_direct_sp0(program, identity)
    lineage = build_lineage_index(program, project)
    result = descriptor_result_from_project(project, lineage, _fixture("descriptor_spec.json"))
    assert (result["rhythmic_syncopation_q"], result["eligible_syncopation_events"]) == (0, 1)
    assert (result["material_recurrence_distance_q"], result["recurrence_pair_count"]) == (None, 0)


def test_project_descriptor_recurrence_compares_cross_section_instances() -> None:
    pack = ROOT / "songprogram_conformance" / "fixtures" / "pack"
    program = json.loads((pack / "minimal_direct_song_program.json").read_text())
    second = dict(program["form"][0], id="sec_b")
    program["form"].append(second)
    program["realizations"].append(dict(program["realizations"][0], id="real_b", section_id="sec_b"))
    identity = CompilerIdentity("fixture-build", "fixture-resolver", "sha256:" + "0" * 64, "sha256:" + "0" * 64, "sha256:" + "0" * 64)
    project = compile_direct_sp0(program, identity)
    lineage = build_lineage_index(program, project)
    result = descriptor_result_from_project(project, lineage, _fixture("descriptor_spec.json"))
    assert (result["material_recurrence_distance_q"], result["recurrence_pair_count"]) == (0, 1)


def test_project_fingerprint_extracts_direct_and_harmony_components() -> None:
    pack = ROOT / "songprogram_conformance" / "fixtures" / "pack"
    direct_program = json.loads((pack / "minimal_direct_song_program.json").read_text())
    direct_identity = CompilerIdentity("fixture-build", "fixture-resolver", "sha256:" + "0" * 64, "sha256:" + "0" * 64, "sha256:" + "0" * 64)
    direct = compile_direct_sp0(direct_program, direct_identity)
    direct_lineage = build_lineage_index(direct_program, direct)
    spec = _fixture("fingerprint_spec.json")
    payloads = fingerprint_payloads_from_project(direct, direct_lineage, spec)
    assert payloads["section_bars"] == [1]
    assert payloads["role_time_grid"] == [["melody", 0, 4]]
    assert payloads["root_anchor_deltas"] == []
    assert payloads["sounding_intervals"] == []
    record = fingerprint_record_from_project(direct, direct_lineage, spec)
    assert record["project_hash"] == direct_lineage["project_hash"]

    triad_program = json.loads((pack / "minimal_triad_song_program.json").read_text())
    manifest = json.loads((pack / "compiler_manifest_sp0.json").read_text())
    triad_identity = CompilerIdentity(manifest["build_id"], manifest["resolver"]["build_id"], manifest["resolver"]["profile_hash"], manifest["budget_profile"]["digest"], manifest["instrument_catalog_digest"])
    triad = compile_direct_sp0(triad_program, triad_identity)
    triad_lineage = build_lineage_index(triad_program, triad)
    payloads = fingerprint_payloads_from_project(triad, triad_lineage, spec)
    assert payloads["root_anchor_deltas"] == [[0, 0]]
    assert payloads["chord_steps"] == [[0, 4, 7]]
    assert payloads["sounding_intervals"] == ["3/2", "5/3", "5/4"]


def test_production_search_loop_records_connected_mutation_failure_and_checkpoint(tmp_path: Path) -> None:
    """The loop persists a typed candidate even when it has no Project output."""
    connected = ROOT / "songprogram_conformance" / "fixtures" / "connected"
    request = json.loads((connected / "mutation_failure_request.json").read_text())
    search = _fixture("run_manifest.json")
    descriptor, fingerprint, qd = _fixture("descriptor_spec.json"), _fixture("fingerprint_spec.json"), _fixture("qd_manifest.json")
    planner = _fixture("planner_manifest.json")
    search["compiler_manifest_hash"] = manifest_digest("cps.compiler-manifest/v1.1", request["compiler_manifest"])
    search["qd_manifest_hash"] = manifest_digest("cps.qd-manifest/v1", qd)
    search["planner_manifest_hash"] = manifest_digest("cps.planner-manifest/v1", planner)
    search["candidates_per_round"] = 1

    def propose(action: str, _round: int, _candidate: int, _program: dict[str, Any]) -> dict[str, Any]:
        proposal = dict(request["mutation_request"], action_id=action)
        return {"status": "success", "mutation_request": proposal}

    seams = SearchLoopSeams(
        propose=propose,
        evaluate=lambda *_values: {"quality": [0, 0, 0, 0, 0]},
    )
    loop = ProductionSearchLoop(
        tmp_path, search, executor_manifest=request["executor_manifest"], compiler_manifest=request["compiler_manifest"],
        descriptor_spec=descriptor, fingerprint_spec=fingerprint, qd_manifest=qd, planner_manifest=planner, seams=seams,
    )
    result = loop.run(request["mutation_request"]["base_program"], maximum_candidates=1)
    records = loop.store.records()

    assert result.completed_candidates == 1
    assert result.compile_logical_units == 0
    assert [record["kind"] for record in records] == ["run", "planner_response", "artifact_reference", "candidate", "failure", "checkpoint"]
    assert records[-1]["record_hash"] == result.last_checkpoint_hash
    checkpoint = json.loads(loop.store._cas_path(records[-1]["payload_hash"]).read_bytes())
    assert checkpoint["cursor"] == {"round": 1, "candidate_ordinal": 0, "phase_ordinal": 0}
    assert checkpoint["next_action_id"] == action_id(loop.run_hash, 1, 0, 0)

    candidate = ArchiveCandidate("sha256:" + "1" * 64, "sha256:" + "2" * 64, "sha256:" + "3" * 64, (1, 2, 3, 4, 5))
    loop._archive(candidate, (0, 0), 1, 0)
    loop._archive(candidate, (0, 0), 1, 0)
    archive_records = [record for record in loop.store.records() if record["kind"] == "archive_update"]
    revisions = [json.loads(loop.store._cas_path(record["payload_hash"]).read_bytes())["revision"] for record in archive_records]
    assert revisions == [0, 1]
