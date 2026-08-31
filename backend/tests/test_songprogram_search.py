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
    SearchArtifactError,
    action_id,
    descriptor_values,
    fingerprint_distance_q,
    fingerprint_record,
    manifest_digest,
    sampler_choice,
    seal_record,
    stream_draw,
    stream_key,
    update_archive_record,
)


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
    payload = (FIXTURES / "cas" / "sha256" / "32" / "b6e5c13ca4db2962b7d3ea1bc96127a74c9a839d365acb94028f727b3710e9").read_bytes()
    assert store.put(payload) == expected["payload_hash"]
    assert store.put(payload) == expected["payload_hash"]
    assert store.append({key: value for key, value in expected.items() if key != "record_hash"}) == expected
    assert store.records_path.read_bytes() == (FIXTURES / "records.log").read_bytes()


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
