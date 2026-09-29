"""Capability registry and ``capability_report.json`` builder.

Implements spec sections 2 and 4.  The registry is versioned knowledge of
what the current schema/implementation can express; each observed pattern is
assigned ``exact`` / ``approximated`` / ``unsupported`` / ``uncertain`` /
``not_applicable`` against the target.  ``exact`` means the profile can state
the condition, not that the acoustics reproduce it.  Unsupported items are
reported with their span, observed value, attempted CPS value, cause,
severity and a suggested update rather than dropped.  ``not_run`` (validation
never executed) is distinct from ``unsupported``.
"""

from __future__ import annotations

from typing import Any

from .targets import Target

REPORT_SCHEMA = "cps.audio-profile-capability-report"
REPORT_SCHEMA_VERSION = "0.1.0-proposal"

STATUSES = ("exact", "approximated", "unsupported", "uncertain", "not_applicable")
SEVERITIES = ("none", "cosmetic", "structural")

# Versioned knowledge of the current CPS boundary (spec section 4 table).
CAPABILITY_REGISTRY: list[dict[str, Any]] = [
    {
        "capability": "tempo_map",
        "target_schema": "cps.song-program/0.2",
        "current_state": "single whole-song BPM clock (30..300), 480 ticks/beat",
        "registry_version": "1.0.0",
    },
    {
        "capability": "meter_map",
        "target_schema": "cps.song-program/0.2",
        "current_state": "beats_per_bar in {2,3,4,6}, fixed for the song",
        "registry_version": "1.0.0",
    },
    {
        "capability": "form_length",
        "target_schema": "cps.composition-generation-profile/2.0.0",
        "current_state": "3..8 sections, 2..16 bars each, 16..64 total",
        "registry_version": "1.0.0",
    },
    {
        "capability": "rhythm_groove",
        "target_schema": "cps.song-program/0.2",
        "current_state": "480 ticks/beat, rhythm steps and rotation",
        "registry_version": "1.0.0",
    },
    {
        "capability": "chord_vocabulary",
        "target_schema": "cps.song-program/0.2",
        "current_state": "chord reference 2..8 step EDO relations; 5D dictionary is 3/4-note axis index",
        "registry_version": "1.0.0",
    },
    {
        "capability": "tuning",
        "target_schema": "cps.song-program/0.2",
        "current_state": "exact equave/generator lattice; continuous pitch curve not expressible",
        "registry_version": "1.0.0",
    },
    {
        "capability": "timbre_automation",
        "target_schema": "cps.arrangement-project/1.3",
        "current_state": "production envelopes empty-only; gain/pan per-track constants",
        "registry_version": "1.0.0",
    },
    {
        "capability": "vocals",
        "target_schema": "cps.arrangement-project/1.3",
        "current_state": "tracks.role in {drums,bass,harmony,melody,texture}; catalog-limited render",
        "registry_version": "1.0.0",
    },
    {
        "capability": "role_entry_exit",
        "target_schema": "cps.composition-generation-profile/2.0.0",
        "current_state": "section/realization exist; current bridge places all roles in every section",
        "registry_version": "1.0.0",
    },
    {
        "capability": "motif_development",
        "target_schema": "cps.composition-generation-profile/2.0.0",
        "current_state": "motif events 2..16, 7-operation vocabulary, fixed transition constraints",
        "registry_version": "1.0.0",
    },
]


def _obs_by_type(analysis: dict[str, Any], obs_type: str) -> list[dict[str, Any]]:
    return [o for o in analysis["observations"] if o["type"] == obs_type]


def _fold_octave(value_milli: int, base_milli: int) -> int:
    """Fold a local tempo estimate into the base's octave class.

    Each window resolves its own octave ambiguity, so a 120 BPM song can
    yield local estimates of 60/120/240.  Folding keeps only genuine tempo
    change as a signal; octave flips are not variation.
    """

    value = value_milli
    while value * 2 <= base_milli:
        value *= 2
    while value >= base_milli * 2:
        value //= 2
    return value


def _item(
    item_id: str,
    capability: str,
    target_schema: str,
    observation_ids: list[str],
    span_samples: list[int],
    status: str,
    observed: Any,
    attempted: Any,
    error: Any,
    reason: str,
    severity: str,
    suggested_update: str,
    priority: int,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "capability": capability,
        "target_schema": target_schema,
        "observation_ids": observation_ids,
        "span_samples": span_samples,
        "status": status,
        "observed": observed,
        "attempted": attempted,
        "error": error,
        "reason": reason,
        "severity": severity,
        "suggested_update": suggested_update,
        "priority": priority,
    }


def build_capability_report(
    analysis: dict[str, Any], target: Target, validation_status: str
) -> dict[str, Any]:
    """Assign a capability status to each observed pattern for the target."""

    items: list[dict[str, Any]] = []
    total = analysis["input"]["time_reference"]["frame_count"]

    # Tempo: a stable in-song tempo within 30..300 is specifiable (exact);
    # windowed local estimates that vary beyond tolerance need a tempo_map the
    # fixed-clock schema cannot express (unsupported).  Octave candidates are
    # ambiguity, not variation, so they do not drive this verdict.
    tempo_obs = _obs_by_type(analysis, "tempo")
    if tempo_obs:
        obs = tempo_obs[0]
        value = obs["value"]
        base: int | None = value.get("tempo_milli_bpm") if isinstance(value, dict) else None
        local: list[int] = (
            [int(v) for v in value.get("local_tempo_milli_bpm", [])] if isinstance(value, dict) else []
        )
        lo: int | None
        hi: int | None
        deviation: int | None
        if base is None:
            status, reason, severity = "uncertain", "tempo_unresolved", "cosmetic"
            lo = hi = None
            deviation = None
        elif not (30_000 <= base <= 300_000):
            status, reason, severity = "unsupported", "tempo_out_of_fixed_clock_range", "structural"
            lo = hi = base
            deviation = None
        else:
            if local:
                folded = [_fold_octave(v, base) for v in local]
                lo, hi = min(folded), max(folded)
                deviation = max(abs(v - base) for v in folded)
            else:
                lo, hi = base, base
                deviation = 0
            if deviation <= 10_000:  # <= 10 BPM variation
                status, reason, severity = "exact", "fixed_clock_in_range", "none"
            else:
                status, reason, severity = "unsupported", "schema_fixed_clock", "structural"
        items.append(
            _item(
                "gap_tempo_map_001",
                "tempo_map",
                "cps.song-program/0.2",
                [obs["id"]],
                [obs["start_sample"], obs["end_sample"]],
                status,
                {"bpm_range": [lo // 1000, hi // 1000] if lo is not None and hi is not None else None},
                {"tempo_milli_bpm": base},
                {"maximum_bpm_deviation": deviation // 1000} if (status != "exact" and deviation is not None) else None,
                reason,
                severity,
                "versioned tempo map in Program/Project/renderer" if status != "exact" else "",
                1 if status != "exact" else 5,
            )
        )

    # Meter: beats_per_bar in {2,3,4,6} -> exact; else unsupported meter_map.
    meter_obs = _obs_by_type(analysis, "meter")
    if meter_obs:
        obs = meter_obs[0]
        bpbs = [c["beats_per_bar"] for c in obs.get("candidates", []) if "beats_per_bar" in c]
        supported = [b for b in bpbs if b in (2, 3, 4, 6)]
        if supported:
            status, reason, severity = "exact", "meter_in_supported_set", "none"
        elif bpbs:
            status, reason, severity = "unsupported", "meter_outside_supported_set", "structural"
        else:
            status, reason, severity = "uncertain", "meter_unresolved", "cosmetic"
        items.append(
            _item(
                "gap_meter_map_001",
                "meter_map",
                "cps.song-program/0.2",
                [obs["id"]],
                [obs["start_sample"], obs["end_sample"]],
                status,
                {"beats_per_bar_candidates": bpbs},
                {"beats_per_bar": supported[0] if supported else None},
                None if status == "exact" else {"unsupported_meters": [b for b in bpbs if b not in (2, 3, 4, 6)]},
                reason,
                severity,
                "versioned meter map in Program/Project/renderer" if status != "exact" else "",
                1 if status != "exact" else 5,
            )
        )

    # Form length: within profile bounds -> approximated; else unsupported.
    section_obs = _obs_by_type(analysis, "section")
    if section_obs:
        obs = section_obs[0]
        count = obs["value"]["count"] if obs["value"] else 0
        if 3 <= count <= 8:
            status, reason, severity = "approximated", "form_within_template_bounds", "cosmetic"
        else:
            status, reason, severity = "unsupported", "form_outside_template_bounds", "structural"
        items.append(
            _item(
                "gap_form_length_001",
                "form_length",
                "cps.composition-generation-profile/2.0.0",
                [obs["id"]],
                [obs["start_sample"], obs["end_sample"]],
                status,
                {"section_count": count},
                {"section_count": max(3, min(8, count))},
                None if status == "approximated" else {"section_count": count},
                reason,
                severity,
                "relax template section/bar bounds or shorten form" if status != "approximated" else "",
                2 if status != "approximated" else 4,
            )
        )

    # Chord vocabulary: report the richest observed quality.
    chord_obs = _obs_by_type(analysis, "chord")
    if chord_obs:
        qualities = {c["value"]["quality"] for c in chord_obs if c["value"] and c["value"].get("root") is not None}
        note_counts = {"major": 3, "minor": 3, "dominant7": 4, "major7": 4, "minor7": 4, "halfdim7": 4, "dim": 3, "sus2": 3, "sus4": 3}
        max_notes = max((note_counts.get(q, 3) for q in qualities), default=3)
        if max_notes <= 4:
            status, reason, severity = "uncertain", "chord_fit_unverified", "cosmetic"
        else:
            status, reason, severity = "unsupported", "chord_beyond_dictionary", "structural"
        items.append(
            _item(
                "gap_chord_vocabulary_001",
                "chord_vocabulary",
                "cps.song-program/0.2",
                [c["id"] for c in chord_obs[:8]],
                [chord_obs[0]["start_sample"], chord_obs[-1]["end_sample"]],
                status,
                {"qualities": sorted(qualities), "max_note_count": max_notes},
                None,
                None if status == "uncertain" else {"max_note_count": max_notes},
                reason,
                severity,
                "verify exact chord resolution against the 5D dictionary" if status != "exact" else "",
                3,
            )
        )

    # Timbre automation: envelopes are empty-only in the current renderer.
    if any(o["type"] == "energy" for o in analysis["observations"]):
        items.append(
            _item(
                "gap_timbre_automation_001",
                "timbre_automation",
                "cps.arrangement-project/1.3",
                [o["id"] for o in _obs_by_type(analysis, "energy")],
                [0, total],
                "unsupported",
                {"within_section_energy_ramp": True},
                None,
                {"envelopes": "empty-only"},
                "schema_envelopes_empty",
                "structural",
                "versioned automation envelopes in production/renderer",
                3,
            )
        )

    # Role entry/exit: current bridge places all roles in every section.
    if any(o["type"] == "section" for o in analysis["observations"]):
        items.append(
            _item(
                "gap_role_entry_exit_001",
                "role_entry_exit",
                "cps.composition-generation-profile/2.0.0",
                [o["id"] for o in _obs_by_type(analysis, "section")],
                [0, total],
                "unsupported",
                {"per_section_role_change": True},
                None,
                {"density_q": "not reflected in onset density"},
                "current_lowering_unsupported",
                "structural",
                "complete Realization 2.1 role masks and density reflection",
                3,
            )
        )

    if validation_status == "not_run":
        for item in items:
            if item["status"] in ("exact", "approximated"):
                item["status"] = "uncertain"
                item["reason"] = "validation_not_run"

    return {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "target_schema": f"cps.{ 'song-program' if target.dimensions == 3 else 'piano-solo' }/{ '0.2' if target.dimensions == 3 else 'v3' }",
        "target_generator": target.manifest_id,
        "registry_version": "1.0.0",
        "validation_status": validation_status,
        "items": items,
    }
