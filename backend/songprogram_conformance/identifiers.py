"""Independent SP0 identity and hash reference functions."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from typing import Any

from .canonical import canonical_bytes


def _sha256(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


def _hex(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _base32(payload: bytes, length: int) -> str:
    return base64.b32encode(payload).decode("ascii").lower().rstrip("=")[:length]


def program_hash(program: dict[str, Any]) -> str:
    core = deepcopy(program)
    core.pop("program_id", None)
    return _hex(b"cps.song-program/0.1\0" + canonical_bytes(core))


def lattice_domain_hash(lattice: dict[str, Any]) -> str:
    core = deepcopy(lattice)
    core.pop("domain_hash", None)
    return _hex(b"cps.lattice-domain/v1\0" + canonical_bytes(core))


def budget_profile_digest(profile: dict[str, Any]) -> str:
    core = deepcopy(profile)
    core.pop("digest", None)
    return _hex(b"cps.budget-profile/v1\0" + canonical_bytes(core))


def compiler_build_id(manifest: dict[str, Any]) -> str:
    core = deepcopy(manifest)
    core.pop("build_id", None)
    return "cb_" + _base32(_sha256(b"cps.compiler-build/v1\0" + canonical_bytes(core)), 26)


def chord_intent_hash(intent: dict[str, Any]) -> str:
    return _hex(b"cps.chord-intent/v1\0" + canonical_bytes(intent))


def resolved_chord_id(chord: dict[str, Any]) -> str:
    field_order = (
        "domain_hash",
        "intent_hash",
        "resolver_build_id",
        "numeric_contract",
        "search_completeness",
        "reference_equave",
        "reference_divisions",
        "canonical_steps",
        "eligibility_contract",
        "anchor_vector",
        "voice_offsets",
        "equave_exponents",
        "exact_ratios",
        "target_voice_ordinals",
        "pair_errors_millicents",
        "maximum_pair_error_millicents",
        "pair_rms_error_millicents",
        "complexity_score",
    )
    core = {field: chord[field] for field in field_order}
    digest = _sha256(b"cps.resolved-chord/v1\0" + canonical_bytes(core))
    return "rc_" + _base32(digest, 26)


def semantic_address(
    section_id: str,
    realization_id: str,
    repeat_ordinal: int,
    material_id: str,
    source_step_ordinal: int,
    emitted_voice_ordinal: int,
) -> str:
    core = [
        "cps.semantic-address",
        1,
        section_id,
        realization_id,
        repeat_ordinal,
        material_id,
        source_step_ordinal,
        emitted_voice_ordinal,
    ]
    return "sa_" + _base32(_sha256(canonical_bytes(core)), 26)


def event_id(event: dict[str, Any]) -> str:
    source = event["source"]
    core = {
        "kind": event["kind"],
        "track_id": event["track_id"],
        "section_id": event["section_id"],
        "start_tick": event["start_tick"],
        "duration_ticks": event["duration_ticks"],
        "velocity": event["velocity"],
        "articulation": event["articulation"],
        "drum_note": event["drum_note"],
        "ratio": event["ratio"],
        "chord_index": event["chord_index"],
        "pitch_provenance": event["pitch_provenance"],
        "source": {
            "material_instance_id": source["material_instance_id"],
            "source_step_ordinal": source["source_step_ordinal"],
            "emitted_voice_ordinal": source["emitted_voice_ordinal"],
        },
    }
    preimage = (
        b"cps.event-id/v1\0"
        + source["semantic_address"].encode("utf-8")
        + b"\0"
        + canonical_bytes(core)
    )
    return "ev_" + _base32(_sha256(preimage), 20)


def project_artifact_hash(project: dict[str, Any]) -> str:
    build_id = project["compiler"]["build_id"]
    preimage = (
        build_id.encode("utf-8")
        + b"\0project/1.2.0\0"
        + canonical_bytes(project)
    )
    return _hex(preimage)
