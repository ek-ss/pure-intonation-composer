"""Deterministic Search RunManifest 1.3 decision primitives.

The legacy :mod:`app.songprogram.search` loop remains a RunManifest 1.2
implementation.  This module deliberately keeps the 1.3 action namespace and
decision-artifact identity separate, so a 1.2 record chain cannot accidentally
be interpreted as a 1.3 one.
"""

from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any, Mapping, Sequence

from .search import SearchArtifactError, _canonical_json


def _artifact_bytes(value: Any) -> bytes:
    """Canonical JSON for decision hashes (the contract has no trailing LF)."""
    return _canonical_json(value).encode("utf-8")


def decision_artifact_hash(artifact: Mapping[str, Any], self_member: str | None = None) -> str:
    """Return the Search Decision Contract artifact hash.

    Only the named self-hash is excluded; nested hashes are evidence and stay
    in the preimage.
    """
    value = copy.deepcopy(dict(artifact))
    if self_member is not None:
        value.pop(self_member, None)
    try:
        prefix = (
            "cps-artifact-hash/v1\0" + value["schema"] + "\0" + value["schema_version"] + "\0"
        ).encode("utf-8")
    except (KeyError, TypeError) as error:
        raise SearchArtifactError("DECISION_ARTIFACT_INVALID") from error
    return "sha256:" + hashlib.sha256(prefix + _artifact_bytes(value)).hexdigest()


def decision_action_id(run_hash: str, round_: int, phase_ordinal: int, candidate_ordinal: int) -> str:
    """Derive a v1.3 action ID from its canonical coordinate."""
    if not (0 <= round_ < 2**64 and 0 <= phase_ordinal <= 13 and 0 <= candidate_ordinal < 2**64):
        raise SearchArtifactError("INVALID_ACTION_COORDINATE")
    try:
        encoded_hash = run_hash.encode("ascii")
    except UnicodeEncodeError as error:
        raise SearchArtifactError("INVALID_ACTION_COORDINATE") from error
    payload = (
        b"cps-action-id/v1\0" + encoded_hash + round_.to_bytes(8, "big")
        + bytes([phase_ordinal]) + candidate_ordinal.to_bytes(8, "big")
    )
    encoded = base64.b32encode(hashlib.sha256(payload).digest()).decode("ascii").lower()
    return "act_" + encoded[:26]


def validate_decision_components(components: Sequence[Mapping[str, Any]]) -> None:
    """Validate the common policy component identity/source constraints."""
    ids = [item.get("id") for item in components]
    if len(ids) != len(set(ids)):
        raise SearchArtifactError("DUPLICATE_COMPONENT_ID")
    ordinals = [item["ordinal"] for item in components if "ordinal" in item]
    if len(ordinals) != len(set(ordinals)) or (ordinals and ordinals != list(range(len(ordinals)))):
        raise SearchArtifactError("INVALID_COMPONENT_ORDINAL")
    for item in components:
        source = item.get("source")
        if not isinstance(source, Mapping) or not all(key in source for key in ("artifact_kind", "schema_hash", "json_pointer")):
            raise SearchArtifactError("UNBOUND_COMPONENT_SOURCE")


def resolve_decision_component(source: Mapping[str, str], artifacts: Mapping[str, Mapping[str, Any]]) -> int:
    """Resolve an integer policy component through its bound producer schema."""
    artifact = artifacts.get(source["artifact_kind"])
    if artifact is None or artifact.get("schema_hash") != source["schema_hash"]:
        raise SearchArtifactError("COMPONENT_SOURCE_SCHEMA_MISMATCH")
    value: Any = artifact.get("document")
    for token in source["json_pointer"].split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError):
            raise SearchArtifactError("COMPONENT_SOURCE_MISSING") from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SearchArtifactError("COMPONENT_SOURCE_NOT_INTEGER")
    return value


def validate_calibration_rank_policy(policy: Mapping[str, Any]) -> None:
    """Validate the cross-field bootstrap rank bounds omitted by JSON Schema."""
    try:
        lower_num, lower_den = policy["lower_rank_numerator"], policy["lower_rank_denominator"]
        upper_num, upper_den = policy["upper_rank_numerator"], policy["upper_rank_denominator"]
    except KeyError as error:
        raise SearchArtifactError("CALIBRATION_RANK_INVALID") from error
    values = (lower_num, lower_den, upper_num, upper_den)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise SearchArtifactError("CALIBRATION_RANK_INVALID")
    if not (0 <= lower_num <= lower_den and 0 <= upper_num <= upper_den):
        raise SearchArtifactError("CALIBRATION_RANK_INVALID")
    if lower_num * upper_den > upper_num * lower_den:
        raise SearchArtifactError("CALIBRATION_RANK_INVALID")


def validate_parallel_scenario(scenario: Mapping[str, Any], action_coordinates: Mapping[str, Sequence[int]]) -> None:
    """Authenticate a fixture's complete scheduled set and completion order."""
    scheduled, completed = scenario.get("scheduled_action_ids"), scenario.get("completion_permutation")
    if not isinstance(scheduled, list) or not scheduled or not isinstance(completed, list):
        raise SearchArtifactError("FIXTURE_PARALLEL_SCENARIO_INVALID")
    if len(scheduled) != len(set(scheduled)) or len(completed) != len(set(completed)):
        raise SearchArtifactError("FIXTURE_PARALLEL_SCENARIO_INVALID")
    if set(scheduled) != set(completed) or set(scheduled) != set(action_coordinates):
        raise SearchArtifactError("FIXTURE_PARALLEL_SCENARIO_INVALID")
    try:
        expected = sorted(scheduled, key=lambda action_id: tuple(action_coordinates[action_id]))
    except (KeyError, TypeError) as error:
        raise SearchArtifactError("FIXTURE_PARALLEL_SCENARIO_INVALID") from error
    if scheduled != expected:
        raise SearchArtifactError("FIXTURE_PARALLEL_SCENARIO_INVALID")


def validate_cancellation_scenario(scenario: Mapping[str, Any], stop_branch: str) -> None:
    """Validate fixture arrival order at deterministic pre-work barriers."""
    arrivals = scenario.get("arrivals")
    if not isinstance(arrivals, list) or (stop_branch == "cancelled" and not arrivals):
        raise SearchArtifactError("FIXTURE_CANCELLATION_SCENARIO_INVALID")
    previous: tuple[int, int, int, int] | None = None
    hashes: set[str] = set()
    for row in arrivals:
        try:
            digest, coordinate = row["inbox_record_hash"], row["arrival_barrier_coordinate"]
            key = tuple(coordinate[name] for name in ("round", "phase_ordinal", "candidate_ordinal", "event_ordinal"))
        except (KeyError, TypeError) as error:
            raise SearchArtifactError("FIXTURE_CANCELLATION_SCENARIO_INVALID") from error
        if digest in hashes or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in key):
            raise SearchArtifactError("FIXTURE_CANCELLATION_SCENARIO_INVALID")
        if previous is not None and key < previous:
            raise SearchArtifactError("FIXTURE_CANCELLATION_SCENARIO_INVALID")
        hashes.add(digest)
        previous = key


def archive_admission(
    directions: Sequence[str], candidate_quality: Sequence[int], candidate_hash: str,
    incumbent_quality: Sequence[int] | None, incumbent_hash: str | None, eligible: bool,
) -> tuple[str, bool, str | None]:
    """Apply the ArchiveAdmissionPolicy total comparator."""
    if len(directions) != len(candidate_quality):
        raise SearchArtifactError("QUALITY_ARITY_MISMATCH")
    if not eligible:
        return "ineligible", False, incumbent_hash
    if incumbent_quality is None:
        return "empty_cell", True, candidate_hash
    if len(incumbent_quality) != len(directions) or incumbent_hash is None:
        raise SearchArtifactError("INVALID_INCUMBENT")

    def key(values: Sequence[int]) -> tuple[int, ...]:
        return tuple(value if direction == "maximize" else -value for direction, value in zip(directions, values))

    candidate_key, incumbent_key = key(candidate_quality), key(incumbent_quality)
    if candidate_key > incumbent_key or (candidate_key == incumbent_key and candidate_hash < incumbent_hash):
        return ("candidate_better" if candidate_key != incumbent_key else "exact_tie"), True, candidate_hash
    return ("incumbent_better" if candidate_key != incumbent_key else "exact_tie"), False, incumbent_hash


def challenger_acceptance(
    metrics: Sequence[Mapping[str, Any]], challenger: Sequence[int], champion: Sequence[int] | None,
    challenger_hash: str, champion_hash: str | None, hard_checks_passed: bool,
) -> tuple[str, str, bool, str]:
    """Apply margin-aware Pareto comparison and its canonical tie rule."""
    validate_decision_components(metrics)
    if len(challenger) != len(metrics) or (champion is not None and len(champion) != len(metrics)):
        raise SearchArtifactError("METRIC_ARITY_MISMATCH")
    if not hard_checks_passed:
        return "ineligible", "ineligible", False, champion_hash or challenger_hash
    if champion is None:
        return "no_champion", "not_needed", True, challenger_hash
    if champion_hash is None:
        raise SearchArtifactError("INVALID_CHAMPION")

    challenger_no_worse = champion_no_worse = True
    challenger_strict = champion_strict = False
    challenger_key: list[int] = []
    champion_key: list[int] = []
    for spec, challenger_value, champion_value in zip(metrics, challenger, champion):
        margin = spec["margin_q"]
        if spec["direction"] == "maximize":
            challenger_no_worse &= challenger_value + margin >= champion_value
            champion_no_worse &= champion_value + margin >= challenger_value
            challenger_strict |= challenger_value > champion_value + margin
            champion_strict |= champion_value > challenger_value + margin
            challenger_key.append(challenger_value)
            champion_key.append(champion_value)
        else:
            challenger_no_worse &= challenger_value - margin <= champion_value
            champion_no_worse &= champion_value - margin <= challenger_value
            challenger_strict |= challenger_value + margin < champion_value
            champion_strict |= champion_value + margin < challenger_value
            challenger_key.append(-challenger_value)
            champion_key.append(-champion_value)
    if challenger_no_worse and challenger_strict:
        return "challenger_dominates", "not_needed", True, challenger_hash
    if champion_no_worse and champion_strict:
        return "champion_dominates", "not_needed", False, champion_hash
    accepted = tuple(challenger_key) > tuple(champion_key) or (
        tuple(challenger_key) == tuple(champion_key) and challenger_hash < champion_hash
    )
    return "non_dominated", "challenger" if accepted else "champion", accepted, challenger_hash if accepted else champion_hash


def comparison_set_hash(program_hashes: Sequence[str]) -> str:
    """Hash the exact, raw-digest sorted comparison population."""
    try:
        sorted_hashes = sorted(program_hashes, key=lambda value: bytes.fromhex(value.removeprefix("sha256:")))
    except ValueError as error:
        raise SearchArtifactError("COMPARISON_SET_HASH_INVALID") from error
    if list(program_hashes) != sorted_hashes:
        raise SearchArtifactError("COMPARISON_SET_NOT_SORTED")
    if len(program_hashes) != len(set(program_hashes)):
        raise SearchArtifactError("COMPARISON_SET_DUPLICATE")
    return decision_artifact_hash({
        "schema": "cps.near-duplicate-comparison-set",
        "schema_version": "1.0.0",
        "program_hashes": list(program_hashes),
    })


def near_duplicate(
    candidate_hash: str, comparisons: Sequence[Mapping[str, Any]], threshold_q: int,
) -> tuple[str, str, Mapping[str, Any] | None]:
    """Classify an exact or threshold-inclusive fingerprint duplicate."""
    hashes = [item["program_hash"] for item in comparisons]
    comparison_set_hash(hashes)
    for item in comparisons:
        if item["program_hash"] == candidate_hash:
            return "exact_duplicate", candidate_hash, item
    if not comparisons:
        return "distinct", candidate_hash, None
    nearest = min(
        comparisons,
        key=lambda item: (item["aggregate_distance_q"], tuple(item["component_distances_q"]), item["program_hash"]),
    )
    if nearest["aggregate_distance_q"] <= threshold_q:
        return "near_duplicate", nearest["program_hash"], nearest
    return "distinct", candidate_hash, nearest


def make_near_duplicate_decision(
    run_hash: str, fingerprint_spec_hash: str, candidate_ordinal: int, candidate_program_hash: str,
    candidate_fingerprint_hash: str, comparisons: Sequence[Mapping[str, Any]], threshold_q: int,
) -> dict[str, Any]:
    """Build the committed duplicate decision before render selection."""
    hashes = [item["program_hash"] for item in comparisons]
    classification, representative, nearest = near_duplicate(candidate_program_hash, comparisons, threshold_q)
    decision = {
        "schema": "cps.near-duplicate-decision", "schema_version": "1.0.0", "run_hash": run_hash,
        "fingerprint_spec_hash": fingerprint_spec_hash, "candidate_ordinal": candidate_ordinal,
        "candidate_program_hash": candidate_program_hash, "candidate_fingerprint_hash": candidate_fingerprint_hash,
        "comparison_set_hash": comparison_set_hash(hashes), "comparison_program_hashes": hashes,
        "nearest": nearest, "threshold_q": threshold_q, "classification": classification,
        "representative_program_hash": representative,
    }
    decision["decision_hash"] = decision_artifact_hash(decision)
    return decision


def make_archive_admission_decision(
    run_hash: str, policy: Mapping[str, Any], policy_hash: str, candidate_program_hash: str,
    project_hash: str, evaluation_report_hash: str, near_duplicate_decision_hash: str,
    cell: Sequence[int], previous_champion: Mapping[str, Any] | None,
    candidate_quality: Sequence[int], eligible: bool,
) -> dict[str, Any]:
    """Build an ArchiveAdmissionDecision from already-bound eligibility evidence."""
    components = policy["quality_components"]
    validate_decision_components(components)
    comparator, admitted, _ = archive_admission(
        [item["direction"] for item in components], candidate_quality, candidate_program_hash,
        None if previous_champion is None else previous_champion["quality"],
        None if previous_champion is None else previous_champion["program_hash"], eligible,
    )
    candidate = {
        "program_hash": candidate_program_hash, "project_hash": project_hash,
        "evaluation_report_hash": evaluation_report_hash, "quality": list(candidate_quality),
    }
    decision = {
        "schema": "cps.archive-admission-decision", "schema_version": "1.0.0", "run_hash": run_hash,
        "policy_hash": policy_hash, "candidate_program_hash": candidate_program_hash, "project_hash": project_hash,
        "evaluation_report_hash": evaluation_report_hash, "near_duplicate_decision_hash": near_duplicate_decision_hash,
        "cell": list(cell), "previous_champion": copy.deepcopy(previous_champion),
        "candidate_quality": list(candidate_quality), "eligible": eligible, "comparator_result": comparator,
        "admitted": admitted, "resulting_champion": candidate if admitted else copy.deepcopy(previous_champion),
    }
    decision["decision_hash"] = decision_artifact_hash(decision)
    return decision


def _metric_relation(spec: Mapping[str, Any], challenger_value: int, champion_value: int | None) -> str:
    if champion_value is None:
        return "no_champion"
    margin = spec["margin_q"]
    if spec["direction"] == "maximize":
        if challenger_value > champion_value + margin:
            return "better_beyond_margin"
        if challenger_value + margin < champion_value:
            return "worse_beyond_margin"
    else:
        if challenger_value + margin < champion_value:
            return "better_beyond_margin"
        if challenger_value - margin > champion_value:
            return "worse_beyond_margin"
    return "within_margin"


def make_challenger_acceptance_decision(
    run_hash: str, policy: Mapping[str, Any], policy_hash: str, genre_intent_hash: str,
    challenger: Mapping[str, str], champion: Mapping[str, str] | None,
    challenger_metrics: Sequence[int], champion_metrics: Sequence[int] | None, hard_checks_passed: bool,
) -> dict[str, Any]:
    """Build a ChallengerAcceptanceDecision using policy metric order."""
    metrics = policy["metrics"]
    if champion is None:
        champion_metrics = None
    elif champion_metrics is None:
        raise SearchArtifactError("MISSING_CHAMPION_METRIC")
    pareto, tie, accepted, resulting = challenger_acceptance(
        metrics, challenger_metrics, champion_metrics, challenger["program_hash"],
        None if champion is None else champion["program_hash"], hard_checks_passed,
    )
    comparisons = [
        {
            "id": spec["id"], "challenger_q": challenger_value,
            "champion_q": None if champion_metrics is None else champion_metrics[index],
            "margin_q": spec["margin_q"],
            "relation": _metric_relation(spec, challenger_value, None if champion_metrics is None else champion_metrics[index]),
        }
        for index, (spec, challenger_value) in enumerate(zip(metrics, challenger_metrics))
    ]
    decision = {
        "schema": "cps.challenger-acceptance-decision", "schema_version": "1.0.0", "run_hash": run_hash,
        "policy_hash": policy_hash, "genre_intent_hash": genre_intent_hash, "challenger": copy.deepcopy(challenger),
        "champion": copy.deepcopy(champion), "metric_comparisons": comparisons,
        "hard_checks_passed": hard_checks_passed, "pareto_result": pareto, "tie_result": tie,
        "accepted": accepted, "resulting_champion_program_hash": resulting,
    }
    decision["decision_hash"] = decision_artifact_hash(decision)
    return decision


def round_decision(
    *, improved: bool, patience_before: int, patience_limit: int, round_: int,
    maximum_rounds: int, cancelled: bool, budget_exhausted: bool, accepted: bool,
) -> tuple[int, str | None]:
    """Return post-round patience and the fixed-precedence stop reason."""
    patience_after = 0 if improved else patience_before + 1
    reasons = (
        (cancelled, "cancelled"),
        (budget_exhausted, "logical_budget_exhausted"),
        (accepted, "accepted"),
        (round_ + 1 >= maximum_rounds, "maximum_rounds"),
        (patience_after >= patience_limit, "patience"),
    )
    return patience_after, next((name for applies, name in reasons if applies), None)


def make_round_decision(
    run_hash: str, stopping_policy_hash: str, round_: int, archive_heads_before_hash: str,
    archive_heads_after_hash: str, accepted_replacement_hashes: Sequence[str], new_cells: int,
    improved: bool, patience_before: int, patience_limit: int, maximum_rounds: int,
    cancelled: bool, budget_exhausted: bool, accepted: bool,
) -> dict[str, Any]:
    """Build the completed-round decision after archive updates are committed."""
    patience_after, stop_reason = round_decision(
        improved=improved, patience_before=patience_before, patience_limit=patience_limit,
        round_=round_, maximum_rounds=maximum_rounds, cancelled=cancelled,
        budget_exhausted=budget_exhausted, accepted=accepted,
    )
    decision = {
        "schema": "cps.round-decision", "schema_version": "1.0.0", "run_hash": run_hash,
        "stopping_policy_hash": stopping_policy_hash, "round": round_,
        "archive_heads_before_hash": archive_heads_before_hash,
        "archive_heads_after_hash": archive_heads_after_hash,
        "accepted_replacement_hashes": list(accepted_replacement_hashes), "new_cells": new_cells,
        "material_improvement": improved, "patience_before": patience_before,
        "patience_after": patience_after, "stop_reason": stop_reason,
    }
    decision["decision_hash"] = decision_artifact_hash(decision)
    return decision


def reserve_render(used_before: int, requested: int, ceiling: int) -> tuple[str, int]:
    """Atomically reserve output-frame budget with the inclusive boundary."""
    if min(used_before, requested, ceiling) < 0 or requested == 0 or used_before > ceiling:
        raise SearchArtifactError("INVALID_RENDER_BUDGET")
    if requested <= ceiling - used_before:
        return "reserved", used_before + requested
    return "rejected", used_before


def select_render_candidates(candidates: Sequence[Mapping[str, Any]], directions: Sequence[str], maximum: int) -> list[str]:
    """Order the policy-eligible candidate population for preview rendering."""
    if maximum < 1:
        raise SearchArtifactError("INVALID_RENDER_SELECTION_LIMIT")
    eligible = [item for item in candidates if item["compile_valid"] and item["distinct"]]
    if any(len(item["components"]) != len(directions) for item in eligible):
        raise SearchArtifactError("RENDER_COMPONENT_ARITY_MISMATCH")

    def key(item: Mapping[str, Any]) -> tuple[Any, ...]:
        directed = tuple(-value if direction == "maximize" else value for direction, value in zip(directions, item["components"]))
        return directed + (item["program_hash"],)

    return [item["program_hash"] for item in sorted(eligible, key=key)[:maximum]]


def cancellation_cutoff_action_id(run_hash: str, coordinate: Mapping[str, int]) -> str:
    """Resolve the cancellation barrier's action coordinate."""
    return decision_action_id(run_hash, coordinate["round"], coordinate["phase_ordinal"], coordinate["candidate_ordinal"])


def make_cancellation_decision(
    run_hash: str, request_hash: str, cutoff_coordinate: Mapping[str, int],
    last_committable_action_id: str | None, champion_at_cutoff: Mapping[str, str] | None,
    archive_heads_hash: str,
) -> dict[str, Any]:
    """Build the immutable cancellation barrier decision."""
    decision = {
        "schema": "cps.cancellation-decision", "schema_version": "1.0.0", "run_hash": run_hash,
        "request_hash": request_hash, "effective_cutoff_action_id": cancellation_cutoff_action_id(run_hash, cutoff_coordinate),
        "cutoff_coordinate": dict(cutoff_coordinate), "last_committable_action_id": last_committable_action_id,
        "status": "accepted", "champion_at_cutoff": copy.deepcopy(champion_at_cutoff),
        "archive_heads_hash": archive_heads_hash,
    }
    decision["decision_hash"] = decision_artifact_hash(decision)
    return decision


def make_render_charge(
    run_hash: str, request_hash: str, requested_frames: int, used_before: int, ceiling: int,
) -> dict[str, Any]:
    """Build and self-hash an immutable RenderCharge artifact."""
    status, used_after = reserve_render(used_before, requested_frames, ceiling)
    charge = {
        "schema": "cps.render-charge", "schema_version": "1.0.0", "run_hash": run_hash,
        "request_hash": request_hash, "charge_unit": "output_frame", "requested_frames": requested_frames,
        "used_before": used_before, "ceiling": ceiling, "reservation_status": status, "used_after": used_after,
    }
    charge["charge_hash"] = decision_artifact_hash(charge)
    return charge


def make_render_result(
    run_hash: str, action: str, request_hash: str, charge_hash: str, outcome: str,
    *, cache_entry_hash: str | None = None, audio_artifact_hash: str | None = None,
    failure_hash: str | None = None,
) -> dict[str, Any]:
    """Build a terminal RenderResult and enforce its causal outcome shape."""
    expected = {
        "cancelled_before_dispatch": ("not_dispatched", False, False, False),
        "cache_hit": ("dispatched", True, True, False),
        "rendered": ("dispatched", False, True, False),
        "render_failed": ("dispatched", False, False, True),
    }
    try:
        dispatch_status, cache_needed, audio_needed, failure_needed = expected[outcome]
    except KeyError as error:
        raise SearchArtifactError("RENDER_RESULT_OUTCOME_INVALID") from error
    actual = (cache_entry_hash is not None, audio_artifact_hash is not None, failure_hash is not None)
    if actual != (cache_needed, audio_needed, failure_needed):
        raise SearchArtifactError("RENDER_RESULT_OUTCOME_MISMATCH")
    result = {
        "schema": "cps.render-result", "schema_version": "1.0.0", "run_hash": run_hash,
        "action_id": action, "request_hash": request_hash, "charge_hash": charge_hash,
        "dispatch_status": dispatch_status, "outcome": outcome, "cache_entry_hash": cache_entry_hash,
        "audio_artifact_hash": audio_artifact_hash, "failure_hash": failure_hash,
    }
    result["result_hash"] = decision_artifact_hash(result)
    return result
