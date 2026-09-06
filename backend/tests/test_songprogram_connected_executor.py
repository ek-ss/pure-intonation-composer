from __future__ import annotations

import json
from pathlib import Path

from app.songprogram.connected import ConnectedCache, execute_connected, run_connected_batch


FIXTURES = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "connected"


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_mutation_failure_is_a_cacheable_whole_connected_output() -> None:
    request = _json("mutation_failure_request.json")
    expected = _json("mutation_failure_cold_output.json")
    cache = ConnectedCache()

    cold = execute_connected(request, None, cache)
    hit = execute_connected(request, None, cache)

    assert cold.output == expected
    assert hit.output == expected
    assert cold.telemetry == {"lookups": 1, "hits": 0, "misses": 1, "corrupt_entries": 0, "recomputations": 1}
    assert hit.telemetry == {"lookups": 1, "hits": 1, "misses": 0, "corrupt_entries": 0, "recomputations": 0}


def test_corrupt_whole_entry_recomputes_without_changing_semantic_output() -> None:
    request = _json("mutation_failure_request.json")
    corrupt = _json("mutation_failure_corrupt_entry.json")
    expected = _json("mutation_failure_cold_output.json")
    cache = ConnectedCache()
    cache.preseed_raw(request, corrupt)

    result = execute_connected(request, None, cache)

    assert result.output == expected
    assert result.telemetry == {"lookups": 1, "hits": 0, "misses": 0, "corrupt_entries": 1, "recomputations": 1}


def test_runner_publishes_in_ordinal_order_with_global_budget() -> None:
    first_request = _json("gen0b_identity_request.json")
    second_request = _json("mutation_failure_request.json")
    wire = _json("global_budget_short_by_one_request_core.json")
    wire["execution"] = {"worker_count": 8, "cache_mode": "hit", "corruption_id": None}
    cache = ConnectedCache()
    cache.preseed_raw(first_request, _json("gen0b_identity_cache_entry.json"))
    cache.preseed_raw(second_request, _json("mutation_failure_cache_entry.json"))

    result, telemetry = run_connected_batch(
        wire,
        [("gen0b_identity_success", first_request), ("mutation_operation_mismatch", second_request)],
        None,
        cache,
    )

    assert result == _json("global_budget_short_by_one_expected.json")
    assert telemetry == [{"lookups": 1, "hits": 1, "misses": 0, "corrupt_entries": 0, "recomputations": 0,
                          "schema": "cps.connected-execution-telemetry", "schema_version": "1.0.0",
                          "cache_mode": "hit", "worker_count": 8, "physical_completed_ordinals": [0]}]
