"""Independent Search Decision Contract oracles; imports no production app code."""

from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes


class DecisionContractError(ValueError):
    """Stable semantic-validation failure with an error code."""

    def __init__(self, code: str, pointer: str = "") -> None:
        super().__init__(code)
        self.code, self.pointer = code, pointer


def artifact_hash(artifact: Mapping[str, Any], self_member: str | None = None) -> str:
    value = copy.deepcopy(dict(artifact))
    if self_member is not None:
        value.pop(self_member, None)
    prefix = (
        "cps-artifact-hash/v1\0"
        + value["schema"] + "\0" + value["schema_version"] + "\0"
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()


def action_id(run_hash: str, round_: int, phase: int, candidate: int) -> str:
    if not (0 <= round_ < 2**64 and 0 <= phase <= 13 and 0 <= candidate < 2**64):
        raise DecisionContractError("INVALID_ACTION_COORDINATE")
    payload = (
        b"cps-action-id/v1\0" + run_hash.encode("ascii")
        + round_.to_bytes(8, "big") + bytes([phase]) + candidate.to_bytes(8, "big")
    )
    encoded = base64.b32encode(hashlib.sha256(payload).digest()).decode().lower()
    return "act_" + encoded[:26]


def validate_action(record: Mapping[str, Any]) -> None:
    expected = action_id(record["run_hash"], record["round"], record["phase_ordinal"], record["candidate_ordinal"])
    if record["action_id"] != expected:
        raise DecisionContractError("ACTION_ID_MISMATCH", "/action_id")


def validate_components(components: Sequence[Mapping[str, Any]]) -> None:
    ids = [item["id"] for item in components]
    if len(ids) != len(set(ids)):
        raise DecisionContractError("DUPLICATE_COMPONENT_ID")
    ordinals = [item.get("ordinal") for item in components if "ordinal" in item]
    if len(ordinals) != len(set(ordinals)) or (
        ordinals and ordinals != list(range(len(ordinals)))
    ):
        raise DecisionContractError("INVALID_COMPONENT_ORDINAL")
    for item in components:
        source = item.get("source")
        if not source or not all(k in source for k in ("artifact_kind", "schema_hash", "json_pointer")):
            raise DecisionContractError("UNBOUND_COMPONENT_SOURCE")


def resolve_component(source: Mapping[str, str], artifacts: Mapping[str, Mapping[str, Any]]) -> int:
    artifact = artifacts.get(source["artifact_kind"])
    if artifact is None or artifact.get("schema_hash") != source["schema_hash"]:
        raise DecisionContractError("COMPONENT_SOURCE_SCHEMA_MISMATCH")
    value: Any = artifact.get("document")
    for token in source["json_pointer"].split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError):
            raise DecisionContractError("COMPONENT_SOURCE_MISSING") from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DecisionContractError("COMPONENT_SOURCE_NOT_INTEGER")
    return value


def archive_admission(
    directions: Sequence[str], candidate_quality: Sequence[int], candidate_hash: str,
    incumbent_quality: Sequence[int] | None, incumbent_hash: str | None, eligible: bool,
) -> tuple[str, bool, str | None]:
    if len(directions) != len(candidate_quality):
        raise DecisionContractError("QUALITY_ARITY_MISMATCH")
    if not eligible:
        return "ineligible", False, incumbent_hash
    if incumbent_quality is None:
        return "empty_cell", True, candidate_hash
    if len(incumbent_quality) != len(directions) or incumbent_hash is None:
        raise DecisionContractError("INVALID_INCUMBENT")
    def key(values: Sequence[int]) -> tuple[int, ...]:
        return tuple(v if d == "maximize" else -v for d, v in zip(directions, values))
    ck, ik = key(candidate_quality), key(incumbent_quality)
    if ck > ik or (ck == ik and candidate_hash < incumbent_hash):
        return ("candidate_better" if ck != ik else "exact_tie"), True, candidate_hash
    return ("incumbent_better" if ck != ik else "exact_tie"), False, incumbent_hash


def validate_archive_decision(policy: Mapping[str, Any], decision: Mapping[str, Any]) -> None:
    validate_components(policy["quality_components"])
    previous = decision["previous_champion"]
    result = archive_admission(
        [item["direction"] for item in policy["quality_components"]],
        decision["candidate_quality"], decision["candidate_program_hash"],
        None if previous is None else previous["quality"],
        None if previous is None else previous["program_hash"], decision["eligible"],
    )
    resulting = decision["resulting_champion"]
    actual = (decision["comparator_result"], decision["admitted"], None if resulting is None else resulting["program_hash"])
    if actual != result:
        raise DecisionContractError("ARCHIVE_DECISION_MISMATCH")


def challenger_acceptance(
    metrics: Sequence[Mapping[str, Any]], challenger: Sequence[int], champion: Sequence[int] | None,
    challenger_hash: str, champion_hash: str | None, hard_checks_passed: bool,
) -> tuple[str, str, bool, str]:
    validate_components(metrics)
    if len(challenger) != len(metrics) or (champion is not None and len(champion) != len(metrics)):
        raise DecisionContractError("METRIC_ARITY_MISMATCH")
    if not hard_checks_passed:
        return "ineligible", "ineligible", False, champion_hash or challenger_hash
    if champion is None:
        return "no_champion", "not_needed", True, challenger_hash
    c_no_worse = p_no_worse = True
    c_strict = p_strict = False
    ckey: list[int] = []
    pkey: list[int] = []
    for spec, c, p in zip(metrics, challenger, champion):
        m = spec["margin_q"]
        if spec["direction"] == "maximize":
            c_no_worse &= c + m >= p; p_no_worse &= p + m >= c
            c_strict |= c > p + m; p_strict |= p > c + m
            ckey.append(c); pkey.append(p)
        else:
            c_no_worse &= c - m <= p; p_no_worse &= p - m <= c
            c_strict |= c + m < p; p_strict |= p + m < c
            ckey.append(-c); pkey.append(-p)
    if c_no_worse and c_strict:
        return "challenger_dominates", "not_needed", True, challenger_hash
    if p_no_worse and p_strict:
        return "champion_dominates", "not_needed", False, champion_hash  # type: ignore[return-value]
    accept = tuple(ckey) > tuple(pkey) or (ckey == pkey and challenger_hash < champion_hash)
    return "non_dominated", ("challenger" if accept else "champion"), accept, (challenger_hash if accept else champion_hash)  # type: ignore[return-value]


def validate_challenger_decision(policy: Mapping[str, Any], decision: Mapping[str, Any]) -> None:
    comparisons = decision["metric_comparisons"]
    values_c = [item["challenger_q"] for item in comparisons]
    values_p = None if decision["champion"] is None else [item["champion_q"] for item in comparisons]
    if values_p is not None and any(value is None for value in values_p):
        raise DecisionContractError("MISSING_CHAMPION_METRIC")
    expected = challenger_acceptance(
        policy["metrics"], values_c, values_p, decision["challenger"]["program_hash"],
        None if decision["champion"] is None else decision["champion"]["program_hash"],
        decision["hard_checks_passed"],
    )
    actual = (decision["pareto_result"], decision["tie_result"], decision["accepted"], decision["resulting_champion_program_hash"])
    if actual != expected:
        raise DecisionContractError("CHALLENGER_DECISION_MISMATCH")


def comparison_set_hash(program_hashes: Sequence[str]) -> str:
    if list(program_hashes) != sorted(program_hashes, key=lambda h: bytes.fromhex(h.removeprefix("sha256:"))):
        raise DecisionContractError("COMPARISON_SET_NOT_SORTED")
    if len(program_hashes) != len(set(program_hashes)):
        raise DecisionContractError("COMPARISON_SET_DUPLICATE")
    return artifact_hash({"schema": "cps.near-duplicate-comparison-set", "schema_version": "1.0.0", "program_hashes": list(program_hashes)})


def near_duplicate(candidate_hash: str, comparisons: Sequence[Mapping[str, Any]], threshold_q: int) -> tuple[str, str, Mapping[str, Any] | None]:
    hashes = [item["program_hash"] for item in comparisons]
    comparison_set_hash(hashes)
    for item in comparisons:
        if item["program_hash"] == candidate_hash:
            return "exact_duplicate", candidate_hash, item
    if not comparisons:
        return "distinct", candidate_hash, None
    nearest = min(comparisons, key=lambda x: (x["aggregate_distance_q"], tuple(x["component_distances_q"]), x["program_hash"]))
    if nearest["aggregate_distance_q"] <= threshold_q:
        return "near_duplicate", nearest["program_hash"], nearest
    return "distinct", candidate_hash, nearest


def validate_near_duplicate_decision(decision: Mapping[str, Any], comparisons: Sequence[Mapping[str, Any]]) -> None:
    hashes = [item["program_hash"] for item in comparisons]
    if decision["comparison_program_hashes"] != hashes:
        raise DecisionContractError("COMPARISON_SET_MEMBERS_MISMATCH")
    if decision["comparison_set_hash"] != comparison_set_hash(hashes):
        raise DecisionContractError("COMPARISON_SET_HASH_MISMATCH")
    classification, representative, nearest = near_duplicate(
        decision["candidate_program_hash"], comparisons, decision["threshold_q"]
    )
    if (decision["classification"], decision["representative_program_hash"], decision["nearest"]) != (classification, representative, nearest):
        raise DecisionContractError("NEAR_DUPLICATE_DECISION_MISMATCH")


def round_decision(*, improved: bool, patience_before: int, patience_limit: int, round_: int,
                   maximum_rounds: int, cancelled: bool, budget_exhausted: bool, accepted: bool) -> tuple[int, str | None]:
    patience_after = 0 if improved else patience_before + 1
    reasons = ((cancelled, "cancelled"), (budget_exhausted, "logical_budget_exhausted"),
               (accepted, "accepted"), (round_ + 1 >= maximum_rounds, "maximum_rounds"),
               (patience_after >= patience_limit, "patience"))
    return patience_after, next((name for hit, name in reasons if hit), None)


def reserve_render(used_before: int, requested: int, ceiling: int) -> tuple[str, int]:
    if min(used_before, requested, ceiling) < 0 or requested == 0 or used_before > ceiling:
        raise DecisionContractError("INVALID_RENDER_BUDGET")
    if requested <= ceiling - used_before:
        return "reserved", used_before + requested
    return "rejected", used_before


def validate_charge(charge: Mapping[str, Any]) -> None:
    status, used_after = reserve_render(charge["used_before"], charge["requested_frames"], charge["ceiling"])
    if charge["reservation_status"] != status or charge["used_after"] != used_after:
        raise DecisionContractError("RENDER_CHARGE_ARITHMETIC_MISMATCH")


def validate_render_result(result: Mapping[str, Any], charge: Mapping[str, Any]) -> None:
    validate_charge(charge)
    if result["request_hash"] != charge["request_hash"] or result["charge_hash"] != charge["charge_hash"]:
        raise DecisionContractError("RENDER_RESULT_CAUSAL_LINK_MISMATCH")
    if charge["reservation_status"] != "reserved":
        raise DecisionContractError("RENDER_RESULT_WITHOUT_RESERVATION")
    expected = {
        "cancelled_before_dispatch": ("not_dispatched", False, False, False),
        "cache_hit": ("dispatched", True, True, False),
        "rendered": ("dispatched", False, True, False),
        "render_failed": ("dispatched", False, False, True),
    }[result["outcome"]]
    actual = (result["dispatch_status"], result["cache_entry_hash"] is not None,
              result["audio_artifact_hash"] is not None, result["failure_hash"] is not None)
    if actual != expected:
        raise DecisionContractError("RENDER_RESULT_OUTCOME_MISMATCH")


def cancellation_cutoff(run_hash: str, coordinate: Mapping[str, int]) -> str:
    return action_id(run_hash, coordinate["round"], coordinate["phase_ordinal"], coordinate["candidate_ordinal"])


def validate_cancellation(decision: Mapping[str, Any]) -> None:
    if decision["effective_cutoff_action_id"] != cancellation_cutoff(decision["run_hash"], decision["cutoff_coordinate"]):
        raise DecisionContractError("CANCELLATION_CUTOFF_ID_MISMATCH")


def select_render_candidates(candidates: Sequence[Mapping[str, Any]], directions: Sequence[str], maximum: int) -> list[str]:
    if maximum < 1:
        raise DecisionContractError("INVALID_RENDER_SELECTION_LIMIT")
    eligible = [item for item in candidates if item["compile_valid"] and item["distinct"]]
    if any(len(item["components"]) != len(directions) for item in eligible):
        raise DecisionContractError("RENDER_COMPONENT_ARITY_MISMATCH")
    def key(item: Mapping[str, Any]) -> tuple[Any, ...]:
        directed = tuple(-v if d == "maximize" else v for d, v in zip(directions, item["components"]))
        return directed + (item["program_hash"],)
    return [item["program_hash"] for item in sorted(eligible, key=key)[:maximum]]


def validate_self_hash(artifact: Mapping[str, Any], member: str) -> None:
    if artifact.get(member) != artifact_hash(artifact, member):
        raise DecisionContractError("ARTIFACT_HASH_MISMATCH", "/" + member)
