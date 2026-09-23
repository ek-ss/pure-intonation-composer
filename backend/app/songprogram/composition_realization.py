"""Versioned section role-mask and density realization policy."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .search import canonical_bytes

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_FUNCTIONS = {
    "opening", "statement", "preparation", "arrival", "contrast", "return", "closure"
}
_ROLES = {"drums", "bass", "harmony", "melody", "texture"}
_TEXTURE_MODES = {
    "pad", "noise_riser", "fx_impact", "transition_tail", "arp",
    "vocal_chop", "counterline", "pluck",
}


class CompositionRealizationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def realization_profile_hash(profile: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in profile.items() if key != "profile_hash"}
    return "sha256:" + hashlib.sha256(
        b"cps.composition-realization-profile/2.1\0" + canonical_bytes(payload)
    ).hexdigest()


def validate_realization_profile(profile: Mapping[str, Any]) -> None:
    if (
        not isinstance(profile, Mapping)
        or set(profile) != {
            "schema", "schema_version", "profile_id", "choice_algorithm",
            "role_masks_by_function", "density_policy_by_role",
            "texture_modes_by_function", "profile_hash",
        }
        or profile.get("schema") != "cps.composition-realization-profile"
        or profile.get("schema_version") != "2.1.0"
        or profile.get("choice_algorithm") != "seed-domain-sha256-weighted/v1"
        or not isinstance(profile.get("profile_id"), str)
        or not profile["profile_id"]
        or _SHA256.fullmatch(str(profile.get("profile_hash"))) is None
        or profile["profile_hash"] != realization_profile_hash(profile)
    ):
        raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    masks = profile["role_masks_by_function"]
    density = profile["density_policy_by_role"]
    texture_modes = profile["texture_modes_by_function"]
    if not isinstance(masks, Mapping) or set(masks) != _FUNCTIONS:
        raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    if not isinstance(density, Mapping) or set(density) != {"drums", "bass", "harmony", "melody"}:
        raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    if not isinstance(texture_modes, Mapping) or set(texture_modes) != _FUNCTIONS:
        raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    for function, rows in masks.items():
        if not isinstance(rows, list) or not rows:
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
        seen: set[tuple[str, ...]] = set()
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != {"roles", "weight"}:
                raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
            roles = row["roles"]
            if (
                not isinstance(roles, list) or not roles
                or any(role not in _ROLES for role in roles)
                or len(roles) != len(set(roles))
                or tuple(roles) in seen
                or type(row["weight"]) is not int or not 1 <= row["weight"] <= 2**31 - 1
            ):
                raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
            seen.add(tuple(roles))
        if function == "arrival" and not any(
            {"drums", "bass", "harmony", "melody"}.issubset(row["roles"]) for row in rows
        ):
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    for rows in texture_modes.values():
        if not isinstance(rows, list) or not rows:
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
        modes = [row.get("mode") for row in rows if isinstance(row, Mapping)]
        if (
            len(modes) != len(rows) or len(modes) != len(set(modes))
            or any(
                set(row) != {"mode", "weight"}
                or row["mode"] not in _TEXTURE_MODES
                or type(row["weight"]) is not int
                or not 1 <= row["weight"] <= 2**31 - 1
                for row in rows
            )
        ):
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
    for role, policy in density.items():
        if not isinstance(policy, Mapping) or set(policy) != {
            "minimum_events_per_bar", "maximum_events_per_bar", "candidate_positions_q",
            "mandatory_positions_q",
        }:
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")
        minimum = policy["minimum_events_per_bar"]
        maximum = policy["maximum_events_per_bar"]
        candidates = policy["candidate_positions_q"]
        mandatory = policy["mandatory_positions_q"]
        if (
            type(minimum) is not int or type(maximum) is not int
            or not 0 <= minimum <= maximum <= 32
            or not isinstance(candidates, list) or len(candidates) != maximum
            or candidates != sorted(set(candidates))
            or any(type(value) is not int or not 0 <= value < 10000 for value in candidates)
            or not isinstance(mandatory, list) or mandatory != sorted(set(mandatory))
            or any(value not in candidates for value in mandatory)
            or len(mandatory) > minimum
            or (role in {"bass", "harmony", "melody"} and minimum < 1)
        ):
            raise CompositionRealizationError("COMPOSITION_REALIZATION_PROFILE_INVALID")


def _digest(seed: int, domain: str, value: str) -> bytes:
    return hashlib.sha256(
        b"cps.composition-realization-choice/2.1\0"
        + seed.to_bytes(8, "big") + domain.encode() + b"\0" + value.encode()
    ).digest()


def choose_role_mask(
    profile: Mapping[str, Any], seed: int, section_id: str, function: str
) -> tuple[str, ...]:
    rows = profile["role_masks_by_function"][function]
    total = sum(row["weight"] for row in rows)
    point = int.from_bytes(_digest(seed, f"role-mask/{section_id}", function)[:8], "big") % total
    cumulative = 0
    for row in rows:
        cumulative += row["weight"]
        if point < cumulative:
            return tuple(row["roles"])
    raise AssertionError("unreachable weighted choice")


def choose_texture_mode(
    profile: Mapping[str, Any], seed: int, section_id: str, function: str
) -> str:
    rows = profile["texture_modes_by_function"][function]
    total = sum(row["weight"] for row in rows)
    point = int.from_bytes(
        _digest(seed, f"texture-mode/{section_id}", function)[:8], "big"
    ) % total
    cumulative = 0
    for row in rows:
        cumulative += row["weight"]
        if point < cumulative:
            return str(row["mode"])
    raise AssertionError("unreachable weighted choice")


def density_target_count(policy: Mapping[str, Any], density_q: int) -> int:
    minimum = policy["minimum_events_per_bar"]
    maximum = policy["maximum_events_per_bar"]
    return minimum + round(density_q * (maximum - minimum) / 10000)


def choose_density_positions(
    profile: Mapping[str, Any], role: str, density_q: int, seed: int, domain: str,
    preferred_positions: Sequence[int] = (),
) -> list[int]:
    policy = profile["density_policy_by_role"][role]
    count = density_target_count(policy, density_q)
    mandatory = list(policy["mandatory_positions_q"])
    remaining = [value for value in policy["candidate_positions_q"] if value not in mandatory]
    preferred = set(preferred_positions)
    remaining.sort(key=lambda value: (value not in preferred,
                                      _digest(seed, domain, str(value)), value))
    return sorted(mandatory + remaining[: max(0, count - len(mandatory))])


def thin_phrase_events(
    events: Sequence[Mapping[str, Any]], density_q: int, seed: int, domain: str
) -> list[dict[str, Any]]:
    if not events:
        return []
    minimum = min(2, len(events))
    count = minimum + round(density_q * (len(events) - minimum) / 10000)
    mandatory_indexes = {0, len(events) - 1}
    remaining = [index for index in range(len(events)) if index not in mandatory_indexes]
    remaining.sort(key=lambda index: (_digest(seed, domain, str(index)), index))
    selected = mandatory_indexes | set(remaining[: max(0, count - len(mandatory_indexes))])
    return [dict(event) for index, event in enumerate(events) if index in selected]
