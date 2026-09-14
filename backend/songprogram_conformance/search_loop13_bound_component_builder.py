"""Build SearchLoop13 components whose identities depend on other run artifacts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .search_decision_oracle import artifact_hash
from .search_loop13_component_authority_builder import component_hashes, producer_digest
from .search_loop13_genre_evaluation_builder import build_genre_evaluation_authority


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "songprogram_conformance" / "fixtures"
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
SHARED = FIXTURES / "search_loop_13" / "shared_authority" / "artifacts"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _raw(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _structural_lowering() -> dict[str, Any]:
    value = {
        "schema": "cps.structural-lowering-manifest",
        "schema_version": "1.0.0",
        "algorithm": "structural-song-program-lowering/v1",
        "structural_program_schema_hash": _raw(SCHEMAS / "structural_song_program_1_0.schema.json"),
        "id_policy": {
            "program_prefix": "sp_",
            "section_prefix": "sec_",
            "material_prefix": "mat_",
            "rhythm_prefix": "rhy_",
            "chord_prefix": "cho_",
            "realization_prefix": "rea_",
            "ordinal_width": 3,
        },
        "clock": {"tempo_milli_bpm": 120_000, "beats_per_bar": 4, "ticks_per_beat": 480},
        "lattice_constants": {
            "base_frequency_millihz": 440_000,
            "maximum_odd_limit": 31,
            "pitch_exploration": {
                "maximum_domain_points": 4096,
                "near_class_merge_millicents": 0,
                "maximum_reduced_complexity_bits": 4096,
                "reference_divisions": 12,
                "audible_offset_band_millicents": [0, 200_000],
                "target_audible_event_share_q": [0, 10_000],
                "minimum_exposed_sections": 0,
                "minimum_recurrent_color_relations": 0,
                "maximum_melodic_jump_millicents": 2_000_000,
            },
        },
        "section_templates": {
            "energy_q": [0, 10_000],
            "density_q": [0, 10_000],
            "tonal_center": [0, 0],
            "development_stage_by_role": {
                "intro": "introduce",
                "verse": "repeat",
                "build": "develop",
                "drop": "contrast",
                "break": "contrast",
                "final": "recall",
                "outro": "close",
            },
        },
        "material_builders": {
            "rhythm_accent_q": 10_000,
            "rhythm_duration_ticks": 120,
            "direct_vectors": [[0, 0], [1, 0]],
            "melody_members": [0, 1],
            "harmony_root_anchors": [[0, 0]],
            "mapping": "cycle",
            "register_delta": 0,
        },
        "chord_constants": {
            "voicing": {
                "bass_policy": "any",
                "bass_target_ordinal": None,
                "minimum_spacing_millicents": 0,
                "maximum_span_millicents": 4_000_000,
            },
            "recognition": {
                "maximum_pair_error_millicents": 200_000,
                "maximum_pair_rms_millicents": 200_000,
            },
            "complexity_budget": 65535,
        },
        "realization_constants": {
            "at_tick": 0,
            "repeat": 1,
            "every_ticks": 1920,
            "velocity_scale_q": 10_000,
            "gate_scale_q": 10_000,
        },
        "rhythm_position_policy": "ascending-even-grid-prefix/v1",
        "compile_policy": {"repair": "reject"},
        "limits": {
            "max_sections": 8,
            "max_bars": 64,
            "max_tracks": 8,
            "max_materials": 64,
            "max_realizations": 512,
            "max_transforms_per_realization": 8,
            "max_events": 8192,
        },
        "manifest_hash": "",
    }
    value["manifest_hash"] = producer_digest(
        "cps.structural-lowering-manifest/v1",
        {k: v for k, v in value.items() if k != "manifest_hash"},
    )
    return value


def build_bound_components() -> dict[str, dict[str, Any]]:
    reusable = {
        name: _load(SHARED / f"{name}.json")
        for name in (
            "compiler_manifest",
            "mutation_choice_catalog",
            "fingerprint_spec",
            "instrument_catalog",
            "render_manifest",
            "executor_manifest",
        )
    }
    hashes = component_hashes(reusable)
    genre = build_genre_evaluation_authority()
    lowering = _structural_lowering()

    old_sampler = _load(FIXTURES / "search" / "sampler_manifest.json")
    decisions = deepcopy(old_sampler["decision_program"][:15])
    decisions[-1].update(stage="realizations", path=["realizations", "active_roles"])
    sampler = {
        "schema": "cps.sampler-manifest",
        "schema_version": "1.1.0",
        "algorithm": "broad-prior-v1.1",
        "choice_algorithm": "sha256-u64-mod-cumulative/v1.1",
        "stream_algorithm": "path-addressed-sha256-attempt/v1.1",
        "structural_program_schema_hash": _raw(SCHEMAS / "structural_song_program_1_0.schema.json"),
        "structural_lowering_manifest_hash": lowering["manifest_hash"],
        "structural_rejection_evidence_schema_hash": _raw(
            SCHEMAS / "structural_rejection_evidence_1_1.schema.json"
        ),
        "compiler_manifest_hash": hashes["compiler_manifest"],
        "maximum_rejections_per_seed": old_sampler["maximum_rejections_per_seed"],
        "limits": old_sampler["limits"],
        "tables": {
            key: deepcopy(old_sampler["tables"][key])
            for key in (
                "section_count",
                "section_role",
                "section_bars",
                "total_bars",
                "material_count",
                "material_kind",
                "active_roles",
                "equave_domain",
                "rhythm_grid",
                "rhythm_density",
                "chord_reference",
                "recall_decision",
                "transform_count",
                "transform_type",
                "rotate_amount",
            )
        },
        "decision_program": decisions,
        "manifest_hash": "",
    }
    sampler["manifest_hash"] = artifact_hash(sampler, "manifest_hash")

    choice_id = reusable["mutation_choice_catalog"]["entries"][0]["choice_id"]
    fallback_semantic = _load(FIXTURES / "fallback_sampler" / "fallback_manifest_semantic.json")
    fallback_semantic["parameter_tables"]["distribution_choice_ids"] = [
        {"value": choice_id, "weight": 1}
    ]
    fallback_semantic["parameter_tables"]["instrument_entry_ids"] = [
        {"value": "pitched_fixture_harmony", "weight": 1}
    ]
    fallback = {
        "schema": "cps.fallback-manifest",
        "schema_version": "1.1.0",
        "algorithm": "typed-weighted-fallback/v1",
        "choice_algorithm": "sha256-u64-mod-cumulative/v1",
        "planner_manifest_hash": None,
        "mutation_schema_hash": _raw(SCHEMAS / "mutation.schema.json"),
        "mutation_choice_catalog_hash": hashes["mutation_choice_catalog"],
        "mutation_application_contract_hash": _raw(
            ROOT.parent / "docs" / "song_program_mutation_application_contract.md"
        ),
        **fallback_semantic,
    }

    base_production = _load(FIXTURES / "fallback_sampler" / "production_manifest.json")
    for row in base_production["profile_ids"]:
        row["value"]["profile_payload_hash"] = producer_digest(
            "cps.production-profile/v1", row["value"]["profile_payload"]
        )
    for row in base_production["drum_map_profiles"]:
        row["value"]["drum_map_payload_hash"] = producer_digest(
            "cps.drum-map-profile/v1", row["value"]["drum_map"]
        )
    role_ids = {
        "drums": "drum_fixture_kit",
        "bass": "pitched_fixture_bass",
        "harmony": "pitched_fixture_2_1",
        "melody": "pitched_fixture_melody",
        "texture": "pitched_fixture_texture",
    }
    base_production["instrument_entries_by_role"] = {
        role: [{"value": value, "weight": 1}] for role, value in role_ids.items()
    }
    production = {
        "schema": "cps.broad-prior-production-manifest",
        "schema_version": "1.0.0",
        "algorithm": "broad-prior-production-lowering/v1",
        "choice_algorithm": "sha256-u64-mod-cumulative/v1",
        "maximum_production_rejections": 16,
        "role_order": ["drums", "bass", "harmony", "melody", "texture"],
        **base_production,
        "sampler_manifest_hash": sampler["manifest_hash"],
        "instrument_catalog_digest": hashes["instrument_catalog"],
    }

    descriptor = _load(FIXTURES / "search" / "descriptor_spec.json")
    descriptor_hash = producer_digest("cps.descriptor-spec/v1", descriptor)
    qd = deepcopy(_load(FIXTURES / "search" / "qd_manifest.json"))
    qd.update(
        descriptor_spec_hash=descriptor_hash,
        fingerprint_spec_hash=hashes["fingerprint_spec"],
        evaluation_manifest_hash=genre["evaluation_manifest"]["manifest_hash"],
        acceptance_policy_hash=genre["challenger_acceptance_policy"]["policy_hash"],
    )
    qd_hash = producer_digest("cps.qd-manifest/v1", qd)
    report_schema = _raw(SCHEMAS / "evaluation_report_1_1.schema.json")
    metric_index = {row["id"]: row["ordinal"] for row in genre["evaluation_manifest"]["metrics"]}
    quality_ids = qd["quality_fields"][:-1]
    archive = {
        "schema": "cps.archive-admission-policy",
        "schema_version": "1.0.0",
        "qd_manifest_hash": qd_hash,
        "required_hard_checks": ["compile_activity_valid"],
        "duplicate_rule": "distinct-only/v1",
        "quality_components": [
            {
                "id": metric_id,
                "direction": "minimize"
                if metric_id == "negative_program_structural_item_count"
                else "maximize",
                "source": {
                    "artifact_kind": "evaluation_report",
                    "schema_hash": report_schema,
                    "json_pointer": f"/metrics/{metric_index[metric_id]}/value",
                },
            }
            for metric_id in quality_ids
        ],
        "tie_break": "quality-lexicographic-then-program-hash/v1",
    }
    archive_hash = artifact_hash(archive)
    stopping = {
        "schema": "cps.stopping-policy",
        "schema_version": "1.0.0",
        "maximum_rounds": 1,
        "patience_rounds": 1,
        "material_improvement": {
            "comparator": "qd-quality-lexicographic/v1",
            "first_differing_component_min_delta": 1,
            "new_cell_is_improvement": True,
        },
        "stop_precedence": [
            "cancelled",
            "logical_budget_exhausted",
            "accepted",
            "maximum_rounds",
            "patience",
        ],
    }
    render_selection = {
        "schema": "cps.render-selection-policy",
        "schema_version": "1.0.0",
        "render_manifest_digest": hashes["render_manifest"],
        "maximum_renders_per_round": 1,
        "preview_content_frames": 1,
        "tail_rule": "render-manifest-trailing-zero-frames/v1",
        "candidate_filter": "compile-valid-distinct-only/v1",
        "order_components": [
            {
                "id": "chord_eligible_candidates",
                "direction": "maximize",
                "source": {
                    "artifact_kind": "compile_report",
                    "schema_hash": _raw(SCHEMAS / "compile_report_1_1.schema.json"),
                    "json_pointer": "/search_statistics/chord_eligible_candidates",
                },
            }
        ],
        "tie_break": "program-hash-ascending/v1",
        "charge_unit": "output_frame",
    }
    candidate = {
        "schema": "cps.candidate-source-policy",
        "schema_version": "1.0.0",
        "selection_algorithm": "candidate-ordinal-mod-source-cycle/v1",
        "source_cycle": ["initial_sampler"],
        "initial_sampler": {
            "sampler_manifest_hash": sampler["manifest_hash"],
            "cohort_index_rule": "candidate-ordinal/v1",
            "production_required": True,
        },
        "archive_parent": {
            "qd_manifest_hash": qd_hash,
            "selection": "round-start-champions-cell-then-program-hash/v1",
            "parent_index_rule": "source-occurrence-ordinal-mod-sorted-round-start-champions/v1",
            "empty_archive_behavior": "initial_sampler/v1",
        },
        "locked_roots_rule": "candidate-source-decision-bound/v1",
    }
    return {
        "structural_lowering_manifest": lowering,
        "descriptor_spec": descriptor,
        "sampler_manifest": sampler,
        "fallback_manifest": fallback,
        "broad_prior_production_manifest": production,
        "qd_manifest": qd,
        "archive_admission_policy": archive,
        "stopping_policy": stopping,
        "render_selection_policy": render_selection,
        "candidate_source_policy": candidate,
        "component_hashes": {
            "sampler_manifest": sampler["manifest_hash"],
            "fallback_manifest": producer_digest("cps.fallback-manifest/v1", fallback),
            "broad_prior_production_manifest": producer_digest(
                "cps.production-lowering-manifest/v1", production
            ),
            "qd_manifest": qd_hash,
            "archive_admission_policy": archive_hash,
            "stopping_policy": artifact_hash(stopping),
            "render_selection_policy": artifact_hash(render_selection),
            "candidate_source_policy": artifact_hash(candidate),
        },
    }


def write_bound_components(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lf_terminated = {
        "structural_lowering_manifest",
        "descriptor_spec",
        "fallback_manifest",
        "broad_prior_production_manifest",
        "qd_manifest",
        "component_hashes",
    }
    for name, value in build_bound_components().items():
        suffix = b"\n" if name in lf_terminated else b""
        (root / f"{name}.json").write_bytes(canonical_bytes(value) + suffix)
