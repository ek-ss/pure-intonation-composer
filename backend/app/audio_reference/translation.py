"""Translate analysis observations into a typed profile patch.

Implements spec section 3.5.  Sections are tentatively mapped onto the
profile's ``opening/statement/preparation/arrival/contrast/return/closure``
functions via a position-based skeleton (never asserted as T/D/S), bar counts
are derived from beat counts and clamped to the profile's 2..16 range, and
energy/density come from the in-song relative acoustics.  Tempo is patched
into the generation manifest's lowering choices.  Every setting carries its
source observation ids and a translation-rule id so the patch is traceable,
and the mapping policy (literal / probabilistic / unresolved) is recorded.
"""

from __future__ import annotations

from typing import Any

from .targets import Target

PATCH_SCHEMA = "cps.audio-derived-profile-patch"
PATCH_SCHEMA_VERSION = "0.1.0-proposal"

MIN_SECTIONS = 3
MAX_SECTIONS = 8
MIN_BARS = 2
MAX_BARS = 16
MIN_TOTAL_BARS = 16
MAX_TOTAL_BARS = 64

TRANSITIONS = {
    "opening": {"statement", "arrival"},
    "statement": {"preparation", "arrival"},
    "preparation": {"arrival", "return"},
    "arrival": {"statement", "contrast", "return", "closure"},
    "contrast": {"preparation", "return"},
    "return": {"preparation", "closure"},
    "closure": set(),
}

FOREGROUND_BY_FUNCTION = {
    "opening": "introduce",
    "statement": "present",
    "preparation": "develop",
    "arrival": "present",
    "contrast": "develop",
    "return": "recall",
    "closure": "release",
}


def function_skeleton(count: int) -> list[str]:
    if count == 3:
        return ["opening", "arrival", "closure"]
    if count == 4:
        return ["opening", "statement", "arrival", "closure"]
    if count == 5:
        return ["opening", "statement", "preparation", "arrival", "closure"]
    if count == 6:
        return ["opening", "statement", "preparation", "arrival", "return", "closure"]
    if count == 7:
        return ["opening", "statement", "preparation", "arrival", "contrast", "return", "closure"]
    if count == 8:
        return ["opening", "statement", "preparation", "arrival", "contrast", "preparation", "return", "closure"]
    raise ValueError(f"section count {count} outside {MIN_SECTIONS}..{MAX_SECTIONS}")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def map_sections_to_template(
    section_beat_counts: list[int],
    beats_per_bar: int,
    energy_q14: list[int],
    density_q14: list[int],
) -> dict[str, Any] | None:
    """Build a profile form_template from the observed section structure.

    Returns ``None`` when the structure cannot be reconciled with the
    profile's 3..8 section / 2..16 bar / 16..64 total constraints; the
    caller then records an unresolved mapping instead of forcing values.
    """

    if not section_beat_counts:
        return None
    count = len(section_beat_counts)
    if count > MAX_SECTIONS:
        # Merge trailing sections until within the template bound.
        merged = list(section_beat_counts[: MAX_SECTIONS - 1])
        merged.append(sum(section_beat_counts[MAX_SECTIONS - 1:]))
        section_beat_counts = merged
        count = len(section_beat_counts)
    if count < MIN_SECTIONS:
        # Split the longest section until within the bound.
        while count < MIN_SECTIONS:
            longest = max(range(len(section_beat_counts)), key=lambda i: section_beat_counts[i])
            value = section_beat_counts[longest]
            if value < 2 * MIN_BARS:
                return None
            half = value // 2
            section_beat_counts[longest:longest + 1] = [half, value - half]
            count += 1
    if beats_per_bar < 1:
        return None
    bars = [_clamp(round(beats / beats_per_bar), MIN_BARS, MAX_BARS) for beats in section_beat_counts]
    total = sum(bars)
    if not (MIN_TOTAL_BARS <= total <= MAX_TOTAL_BARS):
        # Scale bar counts proportionally into the allowed total range.
        target_total = _clamp(total, MIN_TOTAL_BARS, MAX_TOTAL_BARS)
        scale = target_total / total
        bars = [_clamp(round(b * scale), MIN_BARS, MAX_BARS) for b in bars]
        total = sum(bars)
        if not (MIN_TOTAL_BARS <= total <= MAX_TOTAL_BARS):
            return None
    functions = function_skeleton(len(bars))
    sections = []
    for i, (bars_count, function) in enumerate(zip(bars, functions)):
        energy = _clamp((energy_q14[i] if i < len(energy_q14) else 5000) * 10000 // 16384, 0, 10_000)
        density = _clamp((density_q14[i] if i < len(density_q14) else 5000) * 10000 // 16384, 0, 10_000)
        cadence = "home" if function == "closure" else ("arrival" if function == "arrival" else "continuation")
        sections.append(
            {
                "section_key": f"sec_{i:03d}",
                "function": function,
                "bars": bars_count,
                "energy_q": energy,
                "density_q": density,
                "cadence_target": cadence,
                "foreground_state": FOREGROUND_BY_FUNCTION[function],
            }
        )
    return {
        "template_id": "audio-derived",
        "weight": 1,
        "sections": sections,
    }


def _obs_by_type(analysis: dict[str, Any], obs_type: str) -> list[dict[str, Any]]:
    return [o for o in analysis["observations"] if o["type"] == obs_type]


def build_profile_patch(
    analysis: dict[str, Any],
    target: Target,
    reference_profile: dict[str, Any],
    generation_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Produce the ``profile_patch.json`` document."""

    settings: list[dict[str, Any]] = []
    proposed_only: list[str] = []

    section_obs = _obs_by_type(analysis, "section")
    meter_obs = _obs_by_type(analysis, "meter")
    energy_obs = _obs_by_type(analysis, "energy")
    density_obs = _obs_by_type(analysis, "onset_density")
    tempo_obs = _obs_by_type(analysis, "tempo")

    beats_per_bar = 4
    if meter_obs and meter_obs[0]["value"]:
        beats_per_bar = meter_obs[0]["value"].get("beats_per_bar", 4)

    tempo_milli_bpm = 120_000
    if tempo_obs and tempo_obs[0]["value"]:
        tempo_milli_bpm = tempo_obs[0]["value"]["tempo_milli_bpm"]
    sample_rate = analysis["input"]["time_reference"]["sample_rate_hz"]
    samples_per_beat = max(1, (sample_rate * 60_000) // tempo_milli_bpm)

    section_beat_counts: list[int] = []
    section_ids: list[str] = []
    if section_obs and section_obs[0]["candidates"]:
        for cand in section_obs[0]["candidates"]:
            span_beats = (cand["end_sample"] - cand["start_sample"]) // samples_per_beat
            section_beat_counts.append(max(1, span_beats))
            section_ids.append(section_obs[0]["id"])

    per_beat_energy: list[int] = []
    if energy_obs and energy_obs[0]["candidates"]:
        per_beat_energy = [c["energy_q14"] for c in energy_obs[0]["candidates"]]
    per_beat_density: list[int] = []
    if density_obs and density_obs[0]["candidates"]:
        per_beat_density = [c["density_q14"] for c in density_obs[0]["candidates"]]

    # Average the per-beat levels over each section's beat span so the profile
    # sees one energy/density per section, not the first few beats.
    energy_q14: list[int] = []
    density_q14: list[int] = []
    if section_obs and section_obs[0]["candidates"]:
        for cand in section_obs[0]["candidates"]:
            lo = cand.get("start_beat", 0)
            hi = cand.get("end_beat", lo + 1)
            e = per_beat_energy[lo:hi] if per_beat_energy else []
            d = per_beat_density[lo:hi] if per_beat_density else []
            energy_q14.append(int(sum(e) / len(e)) if e else 5000)
            density_q14.append(int(sum(d) / len(d)) if d else 5000)

    template = map_sections_to_template(section_beat_counts, beats_per_bar, energy_q14, density_q14)
    if template is not None:
        settings.append(
            {
                "document": "composition_profile",
                "target_path": "/form_templates",
                "value": [template],
                "source_observation_ids": sorted(set(section_ids)) or [section_obs[0]["id"]] if section_obs else [],
                "translation": "section-form-skeleton/v1",
                "mapping_policy": "probabilistic_style",
                "status": "candidate",
            }
        )
    elif section_obs:
        proposed_only.append("form_template_unresolved")

    if tempo_obs and tempo_obs[0]["value"] and generation_manifest is not None:
        tempo = tempo_obs[0]["value"]["tempo_milli_bpm"]
        settings.append(
            {
                "document": "generation_manifest",
                "target_path": "/lowering_choices/tempo_milli_bpm",
                "value": [tempo],
                "source_observation_ids": [tempo_obs[0]["id"]],
                "translation": "tempo-literal/v1",
                "mapping_policy": "literal_constraints",
                "status": "candidate",
            }
        )

    target_block = {
        "composition_profile_schema": "cps.composition-generation-profile/2.0.0",
        "composition_profile_hash": reference_profile.get("profile_hash"),
        "target_generator": target.manifest_id,
        "generation_manifest_hash": generation_manifest.get("manifest_hash") if generation_manifest else None,
    }
    return {
        "schema": PATCH_SCHEMA,
        "schema_version": PATCH_SCHEMA_VERSION,
        "target": target_block,
        "settings": settings,
        "proposed_only": proposed_only,
        "validation": {"status": "not_run", "target_hash": None},
    }


def _apply_pointer(doc: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [p for p in pointer.split("/") if p]
    node: Any = doc
    for part in parts[:-1]:
        node = node[part] if isinstance(node, dict) else node[int(part)]
    last = parts[-1]
    if isinstance(node, dict):
        node[last] = value
    else:
        node[int(last)] = value


def merge_profile_patch(
    reference_profile: dict[str, Any],
    generation_manifest: dict[str, Any] | None,
    patch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply the patch's settings to copies of the target documents.

    Returns ``(merged_profile, merged_manifest)``.  The ``profile_hash`` is
    stripped so the caller can recompute and validate the merged profile.
    """

    import copy

    merged_profile = copy.deepcopy(reference_profile)
    merged_manifest = copy.deepcopy(generation_manifest) if generation_manifest else None
    for setting in patch["settings"]:
        doc = merged_profile if setting["document"] == "composition_profile" else merged_manifest
        if doc is None:
            continue
        _apply_pointer(doc, setting["target_path"], copy.deepcopy(setting["value"]))
    merged_profile.pop("profile_hash", None)
    if merged_manifest is not None:
        merged_manifest.pop("manifest_hash", None)
    return merged_profile, merged_manifest
