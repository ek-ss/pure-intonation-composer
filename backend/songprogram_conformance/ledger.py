"""Independent atomic OperationBudgetLedger v1 state machine."""

from __future__ import annotations

from dataclasses import dataclass


LEAF_COUNTERS = (
    "structural_items",
    "placed_domain_points",
    "exact_arithmetic_units",
    "numeric_eval_units",
    "chord_search_nodes",
    "pair_relations",
    "ordering_units",
    "validation_items",
    "emitted_events",
)
U64_MAX = (1 << 64) - 1
ERROR_CODES = {
    "structural_items": "BUDGET_STRUCTURAL_EXCEEDED",
    "placed_domain_points": "BUDGET_PLACED_DOMAIN_EXCEEDED",
    "exact_arithmetic_units": "BUDGET_EXACT_ARITHMETIC_EXCEEDED",
    "numeric_eval_units": "BUDGET_NUMERIC_EVAL_EXCEEDED",
    "chord_search_nodes": "BUDGET_CHORD_SEARCH_EXCEEDED",
    "pair_relations": "BUDGET_PAIR_RELATIONS_EXCEEDED",
    "ordering_units": "BUDGET_ORDERING_EXCEEDED",
    "validation_items": "BUDGET_VALIDATION_EXCEEDED",
    "emitted_events": "BUDGET_EMITTED_EVENTS_EXCEEDED",
}


@dataclass(frozen=True)
class BudgetFailure(Exception):
    code: str
    counter: str
    requested: int
    used: int
    ceiling: int
    child_id: str | None = None


class Ledger:
    def __init__(self, ceilings: dict[str, int], child_ceilings: dict[str, int] | None = None):
        required = set(LEAF_COUNTERS) | {"total_logical_units"}
        if set(ceilings) != required or any(not 0 <= value <= U64_MAX for value in ceilings.values()):
            raise ValueError("invalid root ceilings")
        self.ceilings = dict(ceilings)
        self.used = dict.fromkeys(required, 0)
        self.child_ceilings = dict(child_ceilings or {})
        self.children: dict[str, dict[str, int]] = {}

    def reserve(self, counter: str, charge: int, child_id: str | None = None) -> None:
        if counter not in LEAF_COUNTERS or not 0 <= charge <= U64_MAX:
            raise ValueError("invalid reservation")
        root_next = self.used[counter] + charge
        total_next = self.used["total_logical_units"] + charge
        if root_next > U64_MAX or total_next > U64_MAX:
            raise OverflowError("checked u64 reservation overflow")
        child_next = 0
        if child_id is not None:
            child = self.children.setdefault(child_id, dict.fromkeys(LEAF_COUNTERS, 0))
            child_next = child[counter] + charge
            child_ceiling = self.child_ceilings.get(counter)
            if child_ceiling is not None and child_next > child_ceiling:
                raise BudgetFailure("BUDGET_CHILD_EXCEEDED", counter, charge, child[counter], child_ceiling, child_id)
        if root_next > self.ceilings[counter]:
            raise BudgetFailure(
                ERROR_CODES[counter], counter, charge, self.used[counter], self.ceilings[counter], child_id
            )
        if total_next > self.ceilings["total_logical_units"]:
            raise BudgetFailure(
                "BUDGET_TOTAL_EXCEEDED",
                "total_logical_units",
                charge,
                self.used["total_logical_units"],
                self.ceilings["total_logical_units"],
                child_id,
            )
        self.used[counter] = root_next
        self.used["total_logical_units"] = total_next
        if child_id is not None:
            self.children[child_id][counter] = child_next

    def snapshot(self) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
        return dict(self.used), {key: dict(value) for key, value in self.children.items()}
