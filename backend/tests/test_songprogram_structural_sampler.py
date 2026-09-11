from __future__ import annotations

from app.songprogram.structural_sampler import (
    _hash,
    execute_structural_sampler,
    structural_lowering_manifest_hash,
    structural_program_hash,
)


SHA = "sha256:" + "a" * 64


def _table(*values):
    return [{"value": value, "weight": 1} for value in values]


def _authorities():
    lowering = {
        "schema": "cps.structural-lowering-manifest", "schema_version": "1.0.0",
        "algorithm": "structural-song-program-lowering/v1",
        "structural_program_schema_hash": SHA,
        "id_policy": {"program_prefix": "sp_", "section_prefix": "sec_", "material_prefix": "mat_", "rhythm_prefix": "rhy_", "chord_prefix": "cho_", "realization_prefix": "rea_", "ordinal_width": 3},
        "clock": {"tempo_milli_bpm": 150000, "beats_per_bar": 4, "ticks_per_beat": 480},
        "lattice_constants": {"base_frequency_millihz": 440000, "maximum_odd_limit": 31, "pitch_exploration": {"maximum_domain_points": 4096, "near_class_merge_millicents": 10, "maximum_reduced_complexity_bits": 64, "reference_divisions": 12, "audible_offset_band_millicents": [10, 100], "target_audible_event_share_q": [1000, 9000], "minimum_exposed_sections": 2, "minimum_recurrent_color_relations": 1, "maximum_melodic_jump_millicents": 1200000}},
        "section_templates": {"energy_q": [5000, 5000], "density_q": [5000, 5000], "tonal_center": [0, 0], "development_stage_by_role": {role: "statement" for role in ("intro", "verse", "build", "drop", "break", "final", "outro")}},
        "material_builders": {"rhythm_accent_q": 8000, "rhythm_duration_ticks": 120, "direct_vectors": [[0, 0], [1, 0]], "melody_members": [0, 1], "harmony_root_anchors": [[0, 0]], "mapping": "cycle", "register_delta": 0},
        "chord_constants": {"voicing": {"bass_policy": "any", "bass_target_ordinal": None, "minimum_spacing_millicents": 0, "maximum_span_millicents": 2400000}, "recognition": {"maximum_pair_error_millicents": 50000, "maximum_pair_rms_millicents": 50000}, "complexity_budget": 32},
        "realization_constants": {"at_tick": 0, "repeat": 1, "every_ticks": 1920, "velocity_scale_q": 10000, "gate_scale_q": 9000},
        "rhythm_position_policy": "ascending-even-grid-prefix/v1", "compile_policy": {"repair": "reject"},
        "limits": {"max_sections": 8, "max_bars": 64, "max_tracks": 8, "max_materials": 64, "max_realizations": 512, "max_transforms_per_realization": 8, "max_events": 8192},
        "manifest_hash": "",
    }
    lowering["manifest_hash"] = structural_lowering_manifest_hash(lowering)
    tables = {
        "section_count": _table(3), "total_bars": _table(24),
        "section_role": _table("intro", "drop", "final"), "section_bars": _table(8),
        "material_count": _table(3),
        "material_kind": _table("rhythm", "direct_vector", "harmony_intent", "melody_intent"),
        "active_roles": _table(["drums", "bass", "harmony", "melody", "texture"]),
        "equave_domain": _table({"equave": "2/1", "generators": ["3/1", "5/1"], "coordinate_bounds": [[-6, 6], [-5, 5]], "register_bounds": [-3, 3]}),
        "rhythm_grid": _table(240), "rhythm_density": _table(5000),
        "chord_reference": _table({"divisions": 12, "equave": "2/1", "steps": [0, 4, 7]}),
        "recall_decision": _table(True), "transform_count": _table(1),
        "transform_type": _table("rotate"), "rotate_amount": _table(1),
    }
    specs = [
        ("section_count", "once", ["form", "section_count"]),
        ("total_bars", "once", ["form", "total_bars"]),
        ("section_role", "per_section", ["form", "{section}", "role"]),
        ("section_bars", "per_section", ["form", "{section}", "bars"]),
        ("material_count", "once", ["materials", "count"]),
        ("material_kind", "per_material", ["materials", "{material}", "kind"]),
        ("active_roles", "once", ["roles"]), ("equave_domain", "once", ["lattice"]),
        ("rhythm_grid", "per_material", ["materials", "{material}", "grid"]),
        ("rhythm_density", "per_material", ["materials", "{material}", "density"]),
        ("chord_reference", "per_material", ["materials", "{material}", "chord"]),
        ("recall_decision", "per_recall", ["recall", "{section}", "{material}"]),
        ("transform_count", "per_recall", ["recall", "{recall}", "count"]),
        ("transform_type", "per_transform", ["recall", "{recall}", "{transform}", "type"]),
        ("rotate_amount", "per_transform", ["recall", "{recall}", "{transform}", "amount"]),
    ]
    sampler = {"schema": "cps.sampler-manifest", "schema_version": "1.1.0", "algorithm": "broad-prior-v1.1", "choice_algorithm": "sha256-u64-mod-cumulative/v1.1", "stream_algorithm": "path-addressed-sha256-attempt/v1.1", "structural_program_schema_hash": SHA, "structural_lowering_manifest_hash": lowering["manifest_hash"], "structural_rejection_evidence_schema_hash": SHA, "compiler_manifest_hash": SHA, "maximum_rejections_per_seed": 32, "limits": {"minimum_sections": 3, "maximum_sections": 8, "minimum_bars": 16, "maximum_bars": 64, "minimum_materials": 2, "maximum_materials": 5, "minimum_sounding_roles": 3, "maximum_transforms_per_recall": 3}, "tables": tables, "decision_program": [{"ordinal": n, "stage": "realizations" if n >= 11 else "materials" if n >= 4 else "form", "path": path, "table": table, "repeat": repeat} for n, (table, repeat, path) in enumerate(specs)], "manifest_hash": SHA}
    request = {"schema": "cps.structural-sampler-request", "schema_version": "1.1.0", "run_hash": SHA, "context_hash": SHA, "source_decision_hash": SHA, "sampler_manifest_hash": SHA, "structural_lowering_manifest_hash": lowering["manifest_hash"], "structural_program_schema_hash": SHA, "structural_rejection_evidence_schema_hash": SHA, "root_seed": 7, "cohort_index": 0, "request_hash": ""}
    request["request_hash"] = _hash("cps.structural-sampler-request/v1.1", request, omit="request_hash")
    return request, sampler, lowering


def test_structural_sampler_is_deterministic_and_production_free():
    request, sampler, lowering = _authorities()
    first = execute_structural_sampler(request, sampler, lowering)
    second = execute_structural_sampler(request, sampler, lowering)
    assert first == second
    assert first["result"]["status"] == "success"
    program = first["structural_program"]
    assert structural_program_hash(program) == first["result"]["structural_program_hash"]
    assert "tracks" not in program and "production" not in program
    assert program["materials"][:3][0]["id"].startswith("rhy_")


def test_structural_sampler_rejects_request_hash_before_attempts():
    request, sampler, lowering = _authorities()
    request["request_hash"] = SHA
    envelope = execute_structural_sampler(request, sampler, lowering)
    assert envelope["result"]["error"] == "SAMPLER_REQUEST_INVALID"
    assert envelope["trace"] is None
