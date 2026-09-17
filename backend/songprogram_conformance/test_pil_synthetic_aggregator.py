from __future__ import annotations

import copy

from .pil_synthetic_aggregator import aggregate, build_evaluation_policy
from .pil_synthetic_authority_validator import artifact_hash
from .test_pil_synthetic_authority_validator import H, _chain


def test_policy_payload_and_aggregation_are_deterministic() -> None:
    chain = _chain()
    metric_id = chain["registry"]["metrics"][0]["metric_id"]
    policy = build_evaluation_policy(
        scope="genre_phase_5", metric_registry_hash=chain["registry"]["registry_hash"],
        minimum_agent_count=2,
        metrics=[{"metric_id": metric_id, "acceptance_threshold_q": 5000}],
    )
    protocol = copy.deepcopy(chain["protocol"])
    protocol["evaluation_policy_hash"] = policy["policy_hash"]
    protocol["protocol_hash"] = artifact_hash(protocol, "protocol_hash")
    result = aggregate(
        protocol=protocol, cohort=chain["cohort"], assignment_set=chain["assignment_set"],
        responses=chain["responses"], registry=chain["registry"], policy=policy,
        expected_bindings=chain["expected_bindings"], sealed_context_set_hash=H,
        partition_membership_hash=H,
    )
    assert result["evidence_summary"]["metrics"][0]["observed_q"] == 2500
    assert result["evidence_summary"]["all_required_metrics_passed"] is True
    assert result["decision"]["promotion_eligible"] is False
    assert result == aggregate(
        protocol=protocol, cohort=chain["cohort"], assignment_set=chain["assignment_set"],
        responses=list(reversed(chain["responses"])), registry=chain["registry"], policy=policy,
        expected_bindings=chain["expected_bindings"], sealed_context_set_hash=H,
        partition_membership_hash=H,
    )
