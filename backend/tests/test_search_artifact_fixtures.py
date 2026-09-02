from __future__ import annotations

import hashlib
import base64
import json
import math
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

from songprogram_conformance.build_search_fixtures import build
from songprogram_conformance.search_oracle import (
    action_id,
    canonical_bytes,
    choose,
    draw,
    manifest_digest,
    seal_record,
    sha,
    stream_key,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "songprogram_conformance" / "fixtures" / "search"


def _json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_clean_search_fixture_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "search"
    build(rebuilt)
    assert _tree(rebuilt) == _tree(FIXTURES)


def test_sampler_manifest_and_trace_use_frozen_stream_oracle() -> None:
    sampler = _json("sampler_manifest.json")
    trace = _json("sampler_trace.json")
    assert trace["sampler_manifest_hash"] == manifest_digest("cps.sampler-manifest/v1", sampler)
    table = sampler["tables"]["section_count"]
    key = stream_key(trace["root_seed"], trace["cohort_index"], trace["path"])
    for expected in trace["traces"]:
        number = draw(key, expected["counter"])
        index, value = choose(table, number)
        assert (key.hex(), number, index, value) == (
            expected["stream_key_hex"], expected["draw_u64"], expected["choice_index"], expected["value"]
        )
    for name, choices in sampler["tables"].items():
        total = sum(choice["weight"] for choice in choices)
        assert 1 <= total <= (1 << 64) - 1, name
        assert sum(choice["weight"] > 0 for choice in choices) >= 1, name


def test_mutation_vocabulary_is_one_closed_shared_set() -> None:
    schema = json.loads((ROOT / "songprogram_conformance" / "schemas" / "mutation.schema.json").read_text())
    operations = schema["properties"]["operation"]["enum"]
    planner = _json("planner_manifest.json")
    assert planner["allowed_operations"] == operations
    positive = _json("mutation_cases.json")["positive"][0]
    assert positive["operation"] == positive["parameters"]["kind"] == "rotate_rhythm"


def test_mutation_choice_catalog_is_content_addressed_and_run_bound() -> None:
    catalog = _json("mutation_choice_catalog.json")
    run = _json("run_manifest.json")
    assert run["schema_version"] == "1.2.0"
    assert run["mutation_choice_catalog_hash"] == manifest_digest("cps.mutation-choice-catalog/v1", catalog)
    observed = []
    for entry in catalog["entries"]:
        core = {key: entry[key] for key in ("owner_kind", "field", "value")}
        digest = hashlib.sha256(b"cps.mutation-choice/v1\0" + canonical_bytes(core)).digest()
        choice_id = "choice_" + base64.b32encode(digest).decode("ascii").lower().rstrip("=")[:20]
        assert entry["choice_id"] == choice_id
        observed.append((entry["owner_kind"].encode(), entry["field"].encode(), choice_id.encode()))
    assert observed == sorted(observed)
    assert len(observed) == len(set(observed))


def test_mutation_rotation_and_lineage_preimages_are_frozen() -> None:
    cases = _json("mutation_semantics_cases.json")
    rotation = cases["rotation"]
    onsets = sorted({step["at_tick"] for step in rotation["steps"]})
    gaps = [right - left for left, right in zip(onsets, onsets[1:])] + [rotation["length_ticks"] + onsets[0] - onsets[-1]]
    quantum = math.gcd(rotation["length_ticks"], *(step["duration_ticks"] for step in rotation["steps"]), *(gap for gap in gaps if gap > 0))
    assert quantum == rotation["expected_quantum_ticks"]
    assert sorted((step["at_tick"] + rotation["displacement_steps"] * quantum) % rotation["length_ticks"] for step in rotation["steps"]) == rotation["expected_onsets"]
    lineage = cases["lineage_creation"]
    preimage = b"cps.mutation-lineage-root/v1\0" + lineage["action_id"].encode() + b"\0" + lineage["mutation_id"].encode() + b"\0" + struct.pack(">I", lineage["creation_ordinal"]) + canonical_bytes(lineage["material_core"])
    assert sha(preimage) == lineage["expected_root_hash"]
    assert lineage["expected_edge_operation"] == f"mutation/rotate_rhythm/{lineage['mutation_id']}"


def test_run_record_action_hash_chain_and_framing() -> None:
    run = _json("run_manifest.json")
    run_hash = manifest_digest("cps.search-run-manifest/v1", run)
    record = _json("run_record_000.json")
    assert record["action_id"] == action_id(run_hash, 0, 0, 0)
    assert record == seal_record(record)
    framed = (FIXTURES / "records.log").read_bytes()
    length = struct.unpack(">Q", framed[:8])[0]
    assert length == len(framed) - 8
    assert framed[8:] == canonical_bytes(record)
    checkpoint = _json("checkpoint.json")
    assert checkpoint["last_record_hash"] == record["record_hash"]
    assert checkpoint["next_action_id"] == action_id(run_hash, 0, 0, 1)


def test_cas_and_fixture_set_are_content_addressed() -> None:
    fixture_set = _json("fixture_set.json")
    for record in fixture_set["files"]:
        raw = (FIXTURES / record["path"]).read_bytes()
        assert record["byte_length"] == len(raw)
        assert record["sha256"] == sha(raw)
    for path in (FIXTURES / "cas" / "sha256").glob("*/*"):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.parent.name + path.name


def test_qd_runners_have_distinct_lineage_roots_in_total_order() -> None:
    record = _json("qd_archive_record.json")
    roots = [record["champion"]["lineage_root_hash"], *(item["lineage_root_hash"] for item in record["runners"])]
    assert len(roots) == len(set(roots))
    qualities = [tuple(item["quality"]) for item in record["runners"]]
    assert qualities == sorted(qualities, reverse=True)


def test_descriptor_and_fingerprint_fixture_arithmetic() -> None:
    descriptor = _json("descriptor_case.json")
    assert round(10_000 * descriptor["syncopation_numerator"] / descriptor["syncopation_maximum"]) == descriptor["rhythmic_syncopation_q"]
    fingerprint = _json("fingerprint_case.json")
    hashes = []
    for component in fingerprint["components"]:
        observed = manifest_digest("cps.fingerprint-component/v1", {"id": component["id"], "payload": component["payload"]})
        assert observed == component["component_hash"]
        hashes.append(observed)
    assert fingerprint["fingerprint_hash"] == manifest_digest("cps.musical-fingerprint/v1", hashes)


def test_sidecar_is_cross_process_and_hash_seed_invariant() -> None:
    sampler = _json("sampler_manifest.json")
    request = canonical_bytes({"operation":"stream","root_seed":7,"cohort_index":0,"path":["form","section_count"],"counter":0,"table":sampler["tables"]["section_count"]})
    outputs = []
    for worker_count in (1, 2, 4, 8):
        processes = []
        for worker in range(worker_count):
            env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONHASHSEED=str(worker))
            processes.append(subprocess.Popen(
                [sys.executable, "-m", "songprogram_conformance.search_sidecar"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=env,
            ))
        for process in processes:
            stdout, stderr = process.communicate(request)
            assert process.returncode == 0, stderr.decode()
            outputs.append(stdout)
    assert len(set(outputs)) == 1
