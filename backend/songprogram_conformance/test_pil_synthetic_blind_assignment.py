from __future__ import annotations

import copy

import pytest

from .pil_synthetic_blind_assignment import (
    PILSyntheticAssignmentError,
    build_blind_assignment_set,
    replay_blind_assignment_set,
)


def _hash(character: str) -> str:
    return "sha256:" + character * 64


def test_assignment_is_worker_order_independent_and_replayable() -> None:
    arguments = {
        "scope": "genre_phase_5",
        "protocol_hash": _hash("a"),
        "cohort_manifest_hash": _hash("b"),
        "agent_manifest_hashes": [_hash("d"), _hash("c")],
        "sealed_context_hashes": [_hash("2"), _hash("1"), _hash("3")],
    }
    forward = build_blind_assignment_set(**arguments)
    arguments["agent_manifest_hashes"].reverse()
    arguments["sealed_context_hashes"].reverse()
    reverse = build_blind_assignment_set(**arguments)
    assert forward == reverse
    assert forward["assignment_count"] == 6
    assert replay_blind_assignment_set(forward) == forward["assignment_set_hash"]


def test_assignment_replay_rejects_order_or_label_tampering() -> None:
    value = build_blind_assignment_set(
        scope="phase_1_4",
        protocol_hash=_hash("a"),
        cohort_manifest_hash=_hash("b"),
        agent_manifest_hashes=[_hash("c")],
        sealed_context_hashes=[_hash("1"), _hash("2")],
    )
    tampered = copy.deepcopy(value)
    tampered["assignments"][0]["opaque_item_id"] = "item_" + "f" * 24
    with pytest.raises(PILSyntheticAssignmentError) as caught:
        replay_blind_assignment_set(tampered)
    assert caught.value.code == "PIL_SYNTHETIC_BLINDING_INVALID"


@pytest.mark.parametrize(
    "agents,contexts",
    [([], [_hash("1")]), ([_hash("a")], []), ([_hash("a"), _hash("a")], [_hash("1")])],
)
def test_assignment_rejects_empty_or_duplicate_inputs(agents, contexts) -> None:
    with pytest.raises(PILSyntheticAssignmentError):
        build_blind_assignment_set(
            scope="phase_1_4",
            protocol_hash=_hash("b"),
            cohort_manifest_hash=_hash("c"),
            agent_manifest_hashes=agents,
            sealed_context_hashes=contexts,
        )
