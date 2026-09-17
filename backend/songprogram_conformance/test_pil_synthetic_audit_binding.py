from __future__ import annotations

import copy

import pytest

from .pil_synthetic_audit_binding import (
    PILSyntheticAuditBindingError,
    build_audit_binding,
    require_permitted_use,
    validate_audit_binding,
)


H = "sha256:" + "a" * 64


def _decision() -> dict:
    return {
        "schema": "cps.pil-synthetic-provisional-decision",
        "authority_effect": "audit_only",
        "promotion_eligible": False,
        "human_authority_compatible": False,
        "decision_hash": "sha256:" + "b" * 64,
    }


def test_binding_is_out_of_band_and_exactly_replayable() -> None:
    decision = _decision()
    value = build_audit_binding(
        run_context_hash=H,
        decision=decision,
        assignment_set_hash="sha256:" + "c" * 64,
    )
    assert validate_audit_binding(value, run_context_hash=H, decision=decision) == value[
        "binding_hash"
    ]
    require_permitted_use(value, "soft_reranking")


@pytest.mark.parametrize(
    "forbidden",
    ["gen0_gate", "hard_validity", "production_archive", "production_stopping", "native_ji"],
)
def test_binding_rejects_authoritative_uses(forbidden: str) -> None:
    value = build_audit_binding(
        run_context_hash=H,
        decision=_decision(),
        assignment_set_hash="sha256:" + "c" * 64,
    )
    with pytest.raises(PILSyntheticAuditBindingError, match="PIL_SYNTHETIC_USE_FORBIDDEN"):
        require_permitted_use(value, forbidden)


def test_binding_rejects_context_tampering_and_human_substitution() -> None:
    decision = _decision()
    value = build_audit_binding(
        run_context_hash=H,
        decision=decision,
        assignment_set_hash="sha256:" + "c" * 64,
    )
    tampered = copy.deepcopy(value)
    tampered["run_context_hash"] = "sha256:" + "d" * 64
    with pytest.raises(PILSyntheticAuditBindingError, match="PIL_SYNTHETIC_CONTEXT_MISMATCH"):
        validate_audit_binding(tampered, run_context_hash=H, decision=decision)

    human = dict(decision, schema="cps.pil-calibration-decision", promotion_eligible=True)
    with pytest.raises(PILSyntheticAuditBindingError, match="PIL_SYNTHETIC_AUTHORITY_KIND_MISMATCH"):
        build_audit_binding(
            run_context_hash=H,
            decision=human,
            assignment_set_hash="sha256:" + "c" * 64,
        )
