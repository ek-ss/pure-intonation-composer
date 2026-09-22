from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.songprogram.composition_realization import (
    CompositionRealizationError,
    choose_density_positions,
    choose_role_mask,
    choose_texture_mode,
    density_target_count,
    realization_profile_hash,
    thin_phrase_events,
    validate_realization_profile,
)

BACKEND = Path(__file__).resolve().parents[1]
PROFILE = (
    BACKEND / "songprogram_conformance" / "profiles" / "composition_realization_v2_1.json"
)


def _profile() -> dict:
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def test_checked_profile_is_closed_self_hashed_and_deterministic() -> None:
    profile = _profile()
    validate_realization_profile(profile)
    assert realization_profile_hash(profile) == profile["profile_hash"]
    assert choose_role_mask(profile, 4, "sec_001", "statement") == choose_role_mask(
        profile, 4, "sec_001", "statement"
    )
    assert choose_density_positions(profile, "drums", 7000, 4, "test") == (
        choose_density_positions(profile, "drums", 7000, 4, "test")
    )
    assert choose_texture_mode(profile, 4, "sec_001", "preparation") in {
        "noise_riser", "arp"
    }


def test_density_formula_changes_counts_and_retains_mandatory_anchor() -> None:
    profile = _profile()
    policy = profile["density_policy_by_role"]["drums"]
    assert density_target_count(policy, 0) == 1
    assert density_target_count(policy, 10000) == 8
    low = choose_density_positions(profile, "drums", 2500, 3, "low")
    high = choose_density_positions(profile, "drums", 9000, 3, "high")
    assert len(low) < len(high)
    assert 0 in low and 0 in high


def test_phrase_thinning_keeps_terminal_event() -> None:
    events = [{"id": f"event_{index}"} for index in range(4)]
    assert thin_phrase_events(events, 0, 1, "phrase") == [
        {"id": "event_0"},
        {"id": "event_3"},
    ]
    assert thin_phrase_events(events, 10000, 1, "phrase") == events


def test_tampered_profile_is_rejected() -> None:
    profile = copy.deepcopy(_profile())
    profile["density_policy_by_role"]["bass"]["candidate_positions_q"] = [0, 0, 5000, 7500]
    with pytest.raises(
        CompositionRealizationError, match="COMPOSITION_REALIZATION_PROFILE_INVALID"
    ):
        validate_realization_profile(profile)
