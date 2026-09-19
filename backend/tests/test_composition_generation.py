from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.songprogram.composition_generation import (
    CompositionGenerationError,
    composition_plan_hash,
    composition_profile_hash,
    generate_composition_plan,
    validate_composition_profile,
)


PROFILE_PATH = (
    Path(__file__).resolve().parents[1]
    / "songprogram_conformance"
    / "profiles"
    / "composition_generation_v2.json"
)
BACKEND = PROFILE_PATH.parents[2]
CASES_PATH = (
    PROFILE_PATH.parents[1]
    / "fixtures"
    / "composition_generation"
    / "ordered_form_phrase_cases.json"
)


def _profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def test_checked_profile_is_closed_and_self_hashed() -> None:
    profile = _profile()
    validate_composition_profile(profile)
    schema = json.loads(
        (
            PROFILE_PATH.parents[1]
            / "schemas"
            / "composition_generation_profile_2_0.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema"]["const"] == profile["schema"]
    assert composition_profile_hash(profile) == profile["profile_hash"]


def test_ordered_form_and_phrase_generation_is_deterministic() -> None:
    profile = _profile()
    first = generate_composition_plan(profile, 23)
    assert first == generate_composition_plan(profile, 23)
    assert composition_plan_hash(first) == first["plan_hash"]
    assert [section["ordinal"] for section in first["sections"]] == list(
        range(len(first["sections"]))
    )
    assert first["sections"][0]["function"] == "opening"
    assert first["sections"][-1]["function"] == "closure"
    assert first["sections"][-1]["cadence_target"] == "home"
    schema = json.loads(
        (PROFILE_PATH.parents[1] / "schemas" / "composition_plan_2_0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["schema"]["const"] == first["schema"]


def test_phrases_exactly_partition_each_section_and_end_in_cadence() -> None:
    profile = _profile()
    for seed in range(64):
        plan = generate_composition_plan(profile, seed)
        assert plan["total_bars"] == sum(section["bars"] for section in plan["sections"])
        for section in plan["sections"]:
            cursor = 0
            for ordinal, phrase in enumerate(section["phrases"]):
                assert phrase["ordinal"] == ordinal
                assert phrase["start_bar"] == cursor
                assert len(phrase["slots"]) == phrase["length_bars"]
                assert phrase["slots"][-1] == "cadence"
                cursor += phrase["length_bars"]
            assert cursor == section["bars"]
            assert section["phrases"][-1]["cadence_target"] == section["cadence_target"]
            assert all(
                phrase["cadence_target"] == "continuation"
                for phrase in section["phrases"][:-1]
            )


def test_form_selection_reaches_both_sealed_templates() -> None:
    profile = _profile()
    selected = {generate_composition_plan(profile, seed)["form_template_id"] for seed in range(64)}
    assert selected == {template["template_id"] for template in profile["form_templates"]}


def test_checked_cases_bind_form_phrase_shape_and_hash() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert cases["profile_hash"] == _profile()["profile_hash"]
    for case in cases["cases"]:
        plan = generate_composition_plan(_profile(), case["seed"])
        assert plan["form_template_id"] == case["form_template_id"]
        assert plan["total_bars"] == case["total_bars"]
        assert [
            [phrase["length_bars"] for phrase in section["phrases"]]
            for section in plan["sections"]
        ] == case["phrase_lengths_by_section"]
        assert [row["state_id"] for row in plan["harmonic_trajectory"]] == case[
            "harmonic_state_ids"
        ]
        assert plan["motif_plan"]["template_id"] == case["motif_template_id"]
        assert [row["operation"] for row in plan["motif_plan"]["occurrences"]] == case[
            "motif_operations"
        ]
        assert plan["plan_hash"] == case["plan_hash"]


def test_harmonic_trajectory_is_phrase_complete_and_policy_constrained() -> None:
    profile = _profile()
    policy = profile["harmonic_trajectory_policy"]
    transitions = {
        (row["from_state_id"], row["to_state_id"]) for row in policy["transitions"]
    }
    state_by_id = {row["state_id"]: row for row in policy["states"]}
    for seed in range(64):
        plan = generate_composition_plan(profile, seed)
        phrases = [
            (section, phrase)
            for section in plan["sections"]
            for phrase in section["phrases"]
        ]
        trajectory = plan["harmonic_trajectory"]
        assert len(trajectory) == len(phrases)
        assert trajectory[0]["state_id"] == policy["home_state_id"]
        for index, ((section, phrase), row) in enumerate(zip(phrases, trajectory)):
            assert row["phrase_id"] == phrase["phrase_id"]
            assert row["state_id"] in policy["eligible_state_ids_by_section_function"][
                section["function"]
            ]
            assert row["state_id"] in policy["terminal_state_ids_by_cadence_target"][
                phrase["cadence_target"]
            ]
            assert row["harmonic_function"] == state_by_id[row["state_id"]][
                "harmonic_function"
            ]
            if index:
                assert (trajectory[index - 1]["state_id"], row["state_id"]) in transitions
        assert trajectory[-1]["harmonic_function"] in {"home", "arrival", "return"}


def test_motif_plan_is_phrase_complete_bounded_and_lineage_traceable() -> None:
    for seed in range(256):
        plan = generate_composition_plan(_profile(), seed)
        phrase_ids = [
            phrase["phrase_id"]
            for section in plan["sections"]
            for phrase in section["phrases"]
        ]
        motif = plan["motif_plan"]
        occurrences = motif["occurrences"]
        assert [row["phrase_id"] for row in occurrences] == phrase_ids
        statements = [row for row in occurrences if row["operation"] == "statement"]
        assert len(statements) == 1
        assert motif["root_phrase_id"] == statements[0]["phrase_id"]
        source_ids = {event["event_id"] for event in statements[0]["events"]}
        assert source_ids
        for occurrence in occurrences:
            if occurrence["operation"] == "rest":
                assert occurrence["lineage_id"] is None
                assert occurrence["source_phrase_id"] is None
                assert occurrence["events"] == []
                continue
            assert occurrence["lineage_id"] == "motif_000"
            assert occurrence["events"]
            positions = [event["position_q"] for event in occurrence["events"]]
            assert positions == sorted(positions)
            assert all(
                0 <= event["position_q"]
                and event["position_q"] + event["duration_q"] <= 10000
                for event in occurrence["events"]
            )
            if occurrence["operation"] != "statement":
                assert occurrence["source_phrase_id"] == motif["root_phrase_id"]
                assert all(event["source_event_id"] in source_ids for event in occurrence["events"])
        assert any(
            row["operation"] not in {"statement", "recall", "rest"}
            for row in occurrences
        )


def test_cli_is_cross_process_and_hash_seed_invariant() -> None:
    outputs = []
    tool = BACKEND / "tools" / "generate_composition_plan.py"
    for hash_seed in ("0", "1", "123456"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        outputs.append(
            subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--profile",
                    str(PROFILE_PATH),
                    "--seed",
                    "23",
                ],
                cwd=BACKEND,
                env=environment,
                check=True,
                capture_output=True,
            ).stdout
        )
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].endswith(b"\n")
    assert json.loads(outputs[0])["plan_hash"] == generate_composition_plan(
        _profile(), 23
    )["plan_hash"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"unknown": True}),
        lambda value: value["form_templates"][0]["sections"].reverse(),
        lambda value: value["phrase_policy"]["slots_by_length_bars"]["4"].__setitem__(3, "body"),
        lambda value: value["phrase_policy"]["length_choices_by_function"]["opening"].append(
            {"length_bars": 2, "weight": 2}
        ),
        lambda value: value["harmonic_trajectory_policy"]["states"][0].update(
            {"harmonic_function": "departure"}
        ),
        lambda value: value["harmonic_trajectory_policy"]["transitions"].append(
            {
                "from_state_id": "harm_home",
                "to_state_id": "harm_home",
                "weight": 1,
            }
        ),
        lambda value: value["part_coordination_policy"].update(
            {"bass_onsets_q": [1250]}
        ),
    ],
)
def test_profile_rejects_unknown_invalid_or_ambiguous_payload(mutate) -> None:
    profile = _profile()
    mutate(profile)
    profile["profile_hash"] = composition_profile_hash(profile)
    with pytest.raises(CompositionGenerationError, match="COMPOSITION_PROFILE_INVALID"):
        validate_composition_profile(profile)


def test_unpartitionable_section_fails_with_stable_code() -> None:
    profile = copy.deepcopy(_profile())
    profile["form_templates"][0]["sections"][0]["bars"] = 3
    profile["form_templates"] = profile["form_templates"][:1]
    profile["profile_hash"] = composition_profile_hash(profile)
    validate_composition_profile(profile)
    with pytest.raises(
        CompositionGenerationError,
        match="COMPOSITION_PHRASE_PARTITION_UNAVAILABLE",
    ):
        generate_composition_plan(profile, 0)


def test_unreachable_harmonic_path_fails_with_stable_code() -> None:
    profile = copy.deepcopy(_profile())
    profile["harmonic_trajectory_policy"]["transitions"] = [
        {"from_state_id": "harm_home", "to_state_id": "harm_home", "weight": 1}
    ]
    profile["profile_hash"] = composition_profile_hash(profile)
    validate_composition_profile(profile)
    with pytest.raises(
        CompositionGenerationError,
        match="COMPOSITION_HARMONIC_PATH_UNAVAILABLE",
    ):
        generate_composition_plan(profile, 0)


@pytest.mark.parametrize("seed", [-1, 2**64, True])
def test_seed_boundary_is_closed(seed) -> None:
    with pytest.raises(CompositionGenerationError, match="COMPOSITION_SEED_INVALID"):
        generate_composition_plan(_profile(), seed)
