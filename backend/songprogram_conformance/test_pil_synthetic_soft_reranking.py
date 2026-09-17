from __future__ import annotations

import copy

import pytest

from .pil_synthetic_audit_binding import build_audit_binding
from .pil_synthetic_soft_reranking import (
    PILSyntheticRerankingError,
    build_policy,
    rerank,
)
from .pil_synthetic_authority_validator import decision_hash


def _hash(character: str) -> str:
    return "sha256:" + character * 64


def _candidate(context: str, score: int | None) -> tuple[dict, dict]:
    decision = {
        "schema": "cps.pil-synthetic-provisional-decision",
        "authority_effect": "audit_only",
        "promotion_eligible": False,
        "human_authority_compatible": False,
        "decision_hash": "",
        "provisional_metrics": [
            {"metric_id": "pil.genre.typicality", "observed_q": score}
        ],
    }
    decision["decision_hash"] = decision_hash(decision)
    binding = build_audit_binding(
        run_context_hash=_hash("a"),
        sealed_context_hash=_hash(context),
        decision=decision,
        assignment_set_hash=_hash("f"),
    )
    return binding, decision


def test_reranking_is_soft_deterministic_and_unavailable_last() -> None:
    policy = build_policy(
        [{"metric_id": "pil.genre.typicality", "direction": "maximize"}]
    )
    candidates = [_candidate("b", 7000), _candidate("c", None), _candidate("d", 9000)]
    forward = rerank(run_context_hash=_hash("a"), policy=policy, candidates=candidates)
    reverse = rerank(
        run_context_hash=_hash("a"), policy=policy, candidates=list(reversed(candidates))
    )
    assert forward == reverse
    assert forward["shadow_order"] == [_hash("d"), _hash("b"), _hash("c")]
    assert forward["authority_effect"] == "audit_only"


def test_reranking_rejects_context_mismatch_and_policy_tampering() -> None:
    policy = build_policy(
        [{"metric_id": "pil.genre.typicality", "direction": "maximize"}]
    )
    with pytest.raises(PILSyntheticRerankingError, match="PIL_SYNTHETIC_CONTEXT_MISMATCH"):
        rerank(run_context_hash=_hash("9"), policy=policy, candidates=[_candidate("b", 7000)])
    tampered = copy.deepcopy(policy)
    tampered["metric_priorities"][0]["direction"] = "minimize"
    with pytest.raises(PILSyntheticRerankingError, match="PIL_SYNTHETIC_RERANK_POLICY_INVALID"):
        rerank(run_context_hash=_hash("a"), policy=tampered, candidates=[_candidate("b", 7000)])
