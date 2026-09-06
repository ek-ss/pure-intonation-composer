from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from songprogram_conformance.connected_oracle import (
    ConnectedOracleError,
    artifact_hash,
    build_runner_result,
    cache_entry_hash,
    cache_key,
    canonical_lf,
    connected_request_hash,
    executor_manifest_digest,
    json_pointer_replace,
    logical_output_hash,
    raw_hash,
    replay_cache_mode,
    semantic_input_hash,
    semantic_runner_request_hash,
    validate_cache_entry,
)


ROOT = Path(__file__).resolve().parents[1] / "songprogram_conformance"
CONNECTED = ROOT / "fixtures" / "connected"


def test_connected_hashes_include_domain_and_final_lf() -> None:
    value = {"z": 1, "a": [True, None]}
    assert artifact_hash("example/v1", value) != artifact_hash("example/v2", value)
    assert artifact_hash("example/v1", value) == artifact_hash("example/v1", deepcopy(value))
    key = cache_key("sha256:" + "1" * 64, "sha256:" + "2" * 64)
    assert key["cache_key_hash"].startswith("sha256:")


def test_json_pointer_corruption_is_exact_and_non_mutating() -> None:
    original = {"a": [{"b": 1}]}
    changed = json_pointer_replace(original, "/a/0/b", 2)
    assert original == {"a": [{"b": 1}]}
    assert changed == {"a": [{"b": 2}]}
    with pytest.raises(ConnectedOracleError):
        json_pointer_replace(original, "/a/0/missing", 2)


def test_runner_publish_budget_is_atomic_and_ordered() -> None:
    request = {
        "schema": "cps.connected-runner-request",
        "schema_version": "1.0.0",
        "contract": "cps-connected-runner/v1",
        "fixture_set_hash": "sha256:" + "3" * 64,
        "case_ids": ["first", "second"],
        "semantic_input_hash": semantic_input_hash(
            [
                {"case_id": "first", "connected_request_hash": "sha256:" + "4" * 64},
                {"case_id": "second", "connected_request_hash": "sha256:" + "5" * 64},
            ],
            4,
        ),
        "execution": {"worker_count": 8, "cache_mode": "hit", "corruption_id": None},
        "global_compile_logical_ceiling": 4,
    }

    def output(identifier: str, charge: int) -> dict:
        return {
            "logical_output_hash": "sha256:" + identifier * 64,
            "compile_report": {"receipt": {"usage": {"total_logical_units": charge}}},
        }

    result = build_runner_result(request, [("first", output("a", 3)), ("second", output("b", 2))])
    assert result["status"] == "failure"
    assert [item["case_id"] for item in result["published_results"]] == ["first"]
    assert result["global_budget_used"] == 3
    assert result["failure"] == {
        "task_ordinal": 1,
        "case_id": "second",
        "code": "RUN_COMPILE_BUDGET_EXCEEDED",
        "stage": "publish_budget",
        "counter": "total_logical_units",
        "requested": 2,
        "used": 3,
        "ceiling": 4,
    }


def test_checked_in_connected_fixture_and_matrix_are_self_consistent() -> None:
    manifest = json.loads((CONNECTED / "manifest.json").read_text())
    assert manifest["manifest_hash"] == artifact_hash(
        "cps.connected-fixture-manifest/v1", manifest, omit="manifest_hash"
    )
    authorities = {}
    for case in manifest["cases"]:
        for name in ("request", "cold_output", "valid_cache_entry"):
            path = CONNECTED / case[name]["path"]
            assert case[name]["sha256"] == raw_hash(path.read_bytes())
        bundle = None
        if case["opcode_stream_bundle"] is not None:
            bundle_path = CONNECTED / case["opcode_stream_bundle"]["path"]
            assert case["opcode_stream_bundle"]["sha256"] == raw_hash(bundle_path.read_bytes())
            bundle = json.loads(bundle_path.read_text())
        corrupted_path = CONNECTED / case["corruption"]["corrupted_entry"]["path"]
        assert case["corruption"]["corrupted_entry"]["sha256"] == raw_hash(corrupted_path.read_bytes())
        request = json.loads((CONNECTED / case["request"]["path"]).read_text())
        output = json.loads((CONNECTED / case["cold_output"]["path"]).read_text())
        entry = json.loads((CONNECTED / case["valid_cache_entry"]["path"]).read_text())
        assert case["connected_request_hash"] == connected_request_hash(request)
        assert request["executor_manifest_digest"] == executor_manifest_digest(request["executor_manifest"])
        assert output["logical_output_hash"] == logical_output_hash(output)
        assert entry["entry_hash"] == cache_entry_hash(entry)
        assert validate_cache_entry(entry, request) == (output, bundle)
        corrupted = json.loads(corrupted_path.read_text())
        with pytest.raises(ConnectedOracleError, match=case["corruption"]["expected_first_failed_check"]):
            validate_cache_entry(corrupted, request)
        cold = replay_cache_mode("cold", request, output, bundle, None)
        hit = replay_cache_mode("hit", request, output, bundle, entry)
        corrupt = replay_cache_mode("corrupt", request, output, bundle, corrupted)
        assert cold[:2] == hit[:2] == corrupt[:2] == (output, bundle)
        assert (cold[2]["recomputations"], hit[2]["recomputations"], corrupt[2]["recomputations"]) == (1, 0, 1)
        authorities[case["case_id"]] = output

    matrix = json.loads((CONNECTED / "matrix.json").read_text())
    assert matrix["fixture_set_hash"] == manifest["manifest_hash"]
    assert matrix["matrix_hash"] == artifact_hash(
        "cps.connected-runner-matrix/v1", matrix, omit="matrix_hash"
    )
    for matrix_case in matrix["cases"]:
        request_core = json.loads((CONNECTED / matrix_case["request_core"]["path"]).read_text())
        assert matrix_case["request_core"]["sha256"] == raw_hash(
            (CONNECTED / matrix_case["request_core"]["path"]).read_bytes()
        )
        assert matrix_case["semantic_input_hash"] == request_core["semantic_input_hash"]
        outputs = [(case_id, authorities[case_id]) for case_id in request_core["case_ids"]]
        observed_cells = []
        for cell in matrix_case["cells"]:
            wire_path = CONNECTED / cell["request"]["path"]
            wire = json.loads(wire_path.read_text())
            assert cell["request"]["sha256"] == raw_hash(wire_path.read_bytes())
            assert {key: value for key, value in wire.items() if key != "execution"} == request_core
            assert wire["execution"] == {
                "worker_count": cell["worker_count"], "cache_mode": cell["cache_mode"],
                "corruption_id": cell["corruption_id"],
            }
            result = build_runner_result(wire, outputs)
            assert result["result_hash"] == matrix_case["expected_result_hash"]
            assert raw_hash(canonical_lf(result)) == matrix_case["expected_stdout_sha256"]
            assert semantic_runner_request_hash(wire) == matrix_case["semantic_request_hash"]
            observed_cells.append((cell["worker_count"], cell["cache_mode"]))
        assert observed_cells == [
            (workers, mode) for workers in (1, 2, 4, 8) for mode in ("cold", "hit", "corrupt")
        ]
