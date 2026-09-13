from copy import deepcopy

import pytest

from .search_loop13_fixture_oracle import (
    action_id,
    artifact_hash,
    parity_group_hash,
    validate_parallel_matrix,
)


def _case(worker):
    case = {
        "case_id": f"parallel_{worker}",
        "case_hash": "sha256:" + "0" * 64,
        "root_seed": 7,
        "expected": {"transcript_root_hash": "sha256:" + "1" * 64},
        "parallel_scenario": {
            "worker_count": worker,
            "scheduled_action_ids": ["act_" + "a" * 26, "act_" + "b" * 26],
            "completion_permutation": ["act_" + "a" * 26, "act_" + "b" * 26],
            "parity_group_hash": "",
        },
    }
    return case


def test_parallel_projection_ignores_only_envelope_and_physical_order():
    cases = [_case(worker) for worker in (1, 2, 4, 8)]
    digest = parity_group_hash(cases[0])
    for index, case in enumerate(cases):
        case["parallel_scenario"]["completion_permutation"] = (
            list(reversed(case["parallel_scenario"]["completion_permutation"]))
            if index % 2
            else case["parallel_scenario"]["completion_permutation"]
        )
        case["parallel_scenario"]["parity_group_hash"] = digest
    validate_parallel_matrix(cases)

    changed = deepcopy(cases)
    changed[3]["root_seed"] = 8
    with pytest.raises(ValueError, match="projections differ"):
        validate_parallel_matrix(changed)


def test_independent_identity_primitives_are_stable():
    value = {"schema": "cps.example", "schema_version": "1.0.0", "value": 3, "hash": "ignored"}
    assert artifact_hash(value, "hash") == artifact_hash({**value, "hash": "different"}, "hash")
    result = action_id("sha256:" + "a" * 64, 0, 0, 0, 2)
    assert result.startswith("act_") and len(result) == 30
