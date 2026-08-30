from __future__ import annotations

import pytest
import json
from pathlib import Path
from typing import Any

from songprogram_conformance.ledger import BudgetFailure, LEAF_COUNTERS, Ledger

BOUNDARIES = json.loads(
    (Path(__file__).resolve().parents[1] / "songprogram_conformance" / "fixtures" / "pack" / "budget_boundary_cases.json").read_text(encoding="utf-8")
)["cases"]


def _ceilings(value: int = 5, total: int = 100) -> dict[str, int]:
    return {**dict.fromkeys(LEAF_COUNTERS, value), "total_logical_units": total}


@pytest.mark.parametrize("case", BOUNDARIES, ids=lambda case: case["id"])
def test_every_leaf_has_inclusive_ceiling_and_atomic_plus_one(case: dict[str, Any]) -> None:
    counter = str(case["counter"])
    ledger = Ledger(_ceilings())
    ledger.reserve(counter, int(case["accepted_charge"]))
    before = ledger.snapshot()
    with pytest.raises(BudgetFailure) as caught:
        ledger.reserve(counter, int(case["rejected_charge"]))
    assert caught.value.counter == counter
    assert caught.value.code == case["expected_code"]
    assert ledger.snapshot() == before


def test_total_failure_is_atomic() -> None:
    ledger = Ledger(_ceilings(value=10, total=5))
    ledger.reserve("structural_items", 5)
    before = ledger.snapshot()
    with pytest.raises(BudgetFailure) as caught:
        ledger.reserve("validation_items", 1)
    assert caught.value.code == "BUDGET_TOTAL_EXCEEDED"
    assert ledger.snapshot() == before


def test_child_failure_is_atomic() -> None:
    ledger = Ledger(_ceilings(value=10), {"chord_search_nodes": 2})
    ledger.reserve("chord_search_nodes", 2, "query_a")
    before = ledger.snapshot()
    with pytest.raises(BudgetFailure) as caught:
        ledger.reserve("chord_search_nodes", 1, "query_a")
    assert caught.value.code == "BUDGET_CHILD_EXCEEDED"
    assert ledger.snapshot() == before
