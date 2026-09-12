"""Generate PIL oracle suite *input* templates (Phases 1-4).

Outputs case-input JSON templates to ``docs/pil_oracle_case_templates/``.
These are NOT authoritative fixtures: every expected/golden field
(``expected.*``, ``case_hash``, suite-index hashes) is null and must be
filled only by the oracle maintainer through the documented
authoritative-update workflow.  Asset payloads and manifest hashes embedded
in the inputs are real, because the bound hashes are part of the case input,
not of the expected output.

Run from the backend directory:

    python tools/build_pil_oracle_case_templates.py
"""

from __future__ import annotations

import json
import math
import sys
from fractions import Fraction
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram import perceptual  # noqa: E402
from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.pil_fixture_suite import PIL_REQUIRED_COVERAGE  # noqa: E402

OUT = BACKEND.parent / "docs" / "pil_oracle_case_templates"

Q31 = perceptual.Q31_TOTAL


def _sha(byte: int) -> str:
    return "sha256:" + f"{byte:02x}" * 32


def _note(
    event_id: str, ratio: str, start: int, track: str = "harmony", duration: int = 480
) -> dict:
    return {
        "id": event_id,
        "kind": "note",
        "track_id": track,
        "start_tick": start,
        "duration_ticks": duration,
        "velocity": 100,
        "ratio": ratio,
    }


def _factor_exponents(value: Fraction) -> dict[int, int]:
    result: dict[int, int] = {}
    for number, sign in ((value.numerator, 1), (value.denominator, -1)):
        divisor = 2
        while divisor * divisor <= number:
            while number % divisor == 0:
                result[divisor] = result.get(divisor, 0) + sign
                number //= divisor
            divisor += 1
        if number > 1:
            result[number] = result.get(number, 0) + sign
    return {prime: exponent for prime, exponent in result.items() if exponent}


def _project(events: list[dict], *, equave: str = "2/1", total_ticks: int = 480) -> dict:
    """Compile compact case notes into a standalone-valid Project 1.2 input."""
    template_path = (
        BACKEND / "songprogram_conformance/fixtures/pack/minimal_direct_song_program.json"
    )
    program = json.loads(template_path.read_text(encoding="utf-8"))
    equave_value = Fraction(equave)
    equave_prime = equave_value.numerator
    factorizations = [_factor_exponents(Fraction(event["ratio"])) for event in events]
    generator_primes = sorted(
        {prime for factors in factorizations for prime in factors if prime != equave_prime}
    )
    if not generator_primes:
        generator_primes = [3 if equave_prime == 2 else 2]
    if len(generator_primes) > 3:
        raise ValueError("PIL template exceeds Project 1.2 generator capability")

    vectors = [[factors.get(prime, 0) for prime in generator_primes] for factors in factorizations]
    equave_exponents = [factors.get(equave_prime, 0) for factors in factorizations]
    coordinate_bounds = [
        [
            min(0, *(vector[index] for vector in vectors)),
            max(0, *(vector[index] for vector in vectors)),
        ]
        for index in range(len(generator_primes))
    ]
    program["program_id"] = "pil_oracle_template"
    program["clock"] = {
        "tempo_milli_bpm": 120_000,
        "beats_per_bar": 1,
        "ticks_per_beat": 480,
    }
    program["lattice"]["equave"] = equave
    program["lattice"]["generators"] = [f"{prime}/1" for prime in generator_primes]
    program["lattice"]["coordinate_bounds"] = coordinate_bounds
    program["lattice"]["register_bounds"] = [min(equave_exponents), max(equave_exponents)]
    program["lattice"]["maximum_odd_limit"] = max(generator_primes)
    program["lattice"]["pitch_exploration"]["maximum_domain_points"] = max(
        1,
        (max(equave_exponents) - min(equave_exponents) + 1)
        * math.prod(high - low + 1 for low, high in coordinate_bounds),
    )
    program["form"] = [
        {
            **program["form"][0],
            "id": "section",
            "bars": total_ticks // 480,
            "tonal_center": [0] * len(generator_primes),
        }
    ]
    roles = sorted({event.get("track_id", "harmony") for event in events})
    program["tracks"] = [
        {
            "id": role,
            "role": role,
            "instrument_id": "pi17",
            "register_millicents": [-12_000_000, 12_000_000],
            "maximum_polyphony": 16,
            "drum_map": None,
        }
        for role in roles
    ]
    program["production"]["tracks"] = {role: {"gain_q": 8_000, "pan_q": 0} for role in roles}
    program["materials"] = []
    program["realizations"] = []
    for index, (event, vector, exponent) in enumerate(
        zip(events, vectors, equave_exponents, strict=True)
    ):
        rhythm_id, pitch_id = f"rhythm_{index}", f"pitch_{index}"
        program["materials"].extend(
            [
                {
                    "id": rhythm_id,
                    "kind": "rhythm_cell",
                    "length_ticks": total_ticks,
                    "steps": [
                        {
                            "at_tick": 0,
                            "duration_ticks": event["duration_ticks"],
                            "accent_q": 8_000,
                            "lane_id": None,
                        }
                    ],
                },
                {
                    "id": pitch_id,
                    "kind": "direct_vector_cell",
                    "rhythm_id": rhythm_id,
                    "vectors": [vector],
                    "mapping": "cycle",
                    "register_delta": exponent,
                },
            ]
        )
        realization = {
            "repeat": 1,
            "rhythm_transforms": [],
            "pitch_transforms": [],
            "velocity_scale_q": 10_000,
            "gate_scale_q": 10_000,
        }
        realization.update(
            {
                "id": f"real_{index}",
                "section_id": "section",
                "track_id": event.get("track_id", "harmony"),
                "material_id": pitch_id,
                "at_tick": event["start_tick"],
                "every_ticks": total_ticks,
            }
        )
        program["realizations"].append(realization)
    identity = CompilerIdentity(
        build_id="pil.oracle.template.compiler/v1",
        resolver_build_id="gen0-a-bnb-exact-v1",
        resolver_profile_hash=_sha(0x11),
        budget_profile_digest=_sha(0x12),
        instrument_catalog_digest=_sha(0x13),
    )
    return compile_sp0(program, identity)


def _manifest(radius: int = 100_000) -> dict:
    manifest = {
        "schema": "cps.perceptual-interpretation-manifest",
        "schema_version": "1.0.0",
        "algorithm": "pil-parallel-interpretation/v1",
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "numeric_contract_hash": perceptual.NUMERIC_CONTRACT_HASH,
        "implementation_build_id": perceptual.PIL_IMPLEMENTATION_BUILD_ID,
        "interpretation_period": "2/1",
        "pitch_kernel": {
            "algorithm": "triangular-millicent-q31/v1",
            "radius_millicents": radius,
            "normalization_total": Q31,
        },
        "segmentation_policy_schema_hash": perceptual.SEGMENTATION_POLICY_SCHEMA_HASH,
        "segmentation_policy_hash": _sha(0x03),
        "feature_spec_hash": _sha(0x04),
        "vocabulary_hash": _sha(0x05),
        "voice_matching_policy_hash": _sha(0x06),
        "trajectory_template_set_hash": _sha(0x07),
        "genre_model_hash": None,
    }
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return manifest


def _segmentation_policy(**updates: object) -> dict:
    policy = {
        "schema": "cps.perceptual-segmentation-policy",
        "schema_version": "1.0.0",
        "algorithm": "pil-harmonic-segmentation-grid-events/v1",
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "policy_schema_hash": perceptual.SEGMENTATION_POLICY_SCHEMA_HASH,
        "grid_divisions_per_beat": 1,
        "minimum_segment_ticks": 480,
        "sustained_minimum_ticks": 480,
        "pitch_distribution_change_q": 1_000,
        "duration_coefficient_q": 10_000,
        "metrical_coefficient_q": 0,
        "persistence_coefficient_q": 0,
        "bass_coefficient_q": 0,
        "role_gain_q": {
            "drums": 0,
            "bass": 10_000,
            "harmony": 10_000,
            "melody": 10_000,
            "texture": 10_000,
        },
        "bass_role_order": ["bass", "harmony", "melody", "texture", "drums"],
        "boundary_priority": list(perceptual.BOUNDARY_PRIORITY),
        "boundary_confidence_q": {
            "endpoint": 10_000,
            "bass_change": 9_000,
            "sustained_change": 8_000,
            "pitch_distribution_change": 7_000,
            "metrical": 6_000,
        },
    }
    policy.update(updates)
    policy["policy_hash"] = perceptual.segmentation_policy_hash(policy)
    return policy


def _distribution(ordinals: list[int]) -> list[dict[str, int]]:
    raw = [1 if index in ordinals else 0 for index in range(12)]
    values = perceptual._normalize(raw, Q31)
    return [
        {"pitch_class_ordinal": index, "weight_q31": value}
        for index, value in enumerate(values)
        if value
    ]


def _interval(pitch_rows: list[dict[str, int]]) -> list[dict[str, int]]:
    pitch = perceptual._expand_distribution(pitch_rows)
    raw = [
        sum(pitch[index] * pitch[(index + offset) % 12] for index in range(12))
        for offset in range(12)
    ]
    values = perceptual._normalize(raw, Q31)
    return [
        {"pitch_class_ordinal": index, "weight_q31": value}
        for index, value in enumerate(values)
        if value
    ]


def _feature_spec(policy: dict) -> dict:
    spec = {
        "schema": "cps.perceptual-chord-feature-spec",
        "schema_version": "1.0.0",
        "algorithm": "pil-chord-features-12pc/v1",
        "feature_spec_schema_hash": perceptual.CHORD_FEATURE_SPEC_SCHEMA_HASH,
        "feature_record_schema_hash": perceptual.CHORD_FEATURE_RECORD_SCHEMA_HASH,
        "project_schema_hash": perceptual.PROJECT_SCHEMA_HASH,
        "segmentation_policy_hash": policy["policy_hash"],
        "pitch_distribution_algorithm": "soft-event-mapping-weighted-q31/v1",
        "interval_distribution_algorithm": "circular-ordered-autocorrelation-q31/v1",
        "bass_relative_algorithm": "soft-bass-circular-correlation-q31/v1",
        "register_profile_algorithm": "segment-event-weighted-absolute-millicents/v1",
        "common_tone_algorithm": "histogram-intersection-q10000/v1",
        "similarity": {
            "algorithm": "weighted-normalized-l1-q10000/v1",
            "pitch_weight": 5_000,
            "interval_weight": 3_000,
            "bass_relative_weight": 2_000,
            "confidence_floor_q": 0,
            "winner_margin_floor_q": 0,
            "maximum_candidates": 8,
        },
    }
    spec["spec_hash"] = perceptual.chord_feature_spec_hash(spec)
    return spec


def _vocabulary(spec: dict) -> dict:
    entries = []
    for ordinal, (entry_id, members) in enumerate((("major", [0, 4, 7]), ("minor", [0, 3, 7]))):
        pitch = _distribution(members)
        entries.append(
            {
                "id": entry_id,
                "ordinal": ordinal,
                "functional_tension_q": 2_000 + ordinal * 1_000,
                "pitch_distribution_q31": pitch,
                "interval_distribution_q31": _interval(pitch),
                "bass_relative_distribution_q31": pitch,
            }
        )
    vocabulary = {
        "schema": "cps.perceptual-chord-vocabulary",
        "schema_version": "1.0.0",
        "algorithm": "pil-chord-vocabulary-q31/v1",
        "vocabulary_schema_hash": perceptual.CHORD_VOCABULARY_SCHEMA_HASH,
        "interpretation_period": "2/1",
        "feature_spec_hash": spec["spec_hash"],
        "entries": entries,
    }
    vocabulary["vocabulary_hash"] = perceptual.chord_vocabulary_hash(vocabulary)
    return vocabulary


def _voice_matching_policy(spec: dict) -> dict:
    policy = {
        "schema": "cps.perceptual-voice-matching-policy",
        "schema_version": "1.0.0",
        "algorithm": "pil-injective-voice-matching-dp/v1",
        "policy_schema_hash": perceptual.VOICE_MATCHING_POLICY_SCHEMA_HASH,
        "matching_record_schema_hash": perceptual.VOICE_MATCHING_RECORD_SCHEMA_HASH,
        "feature_spec_hash": spec["spec_hash"],
        "maximum_voices_per_segment": 4,
        "selection_algorithm": "event-weight-desc-absolute-mc-id/v1",
        "identity_constraint": "same-event-id-must-match/v1",
        "interpretation_period_millicents": 1_200_000,
        "half_period_tie": "negative",
        "absolute_motion_cap_millicents": 4_800_000,
        "cost_weights": {
            "absolute_motion": 4_000,
            "circular_motion": 3_000,
            "pitch_mapping_l1": 2_000,
            "role_mismatch": 1_000,
        },
        "bass_likeness_kernels": {
            "fifth_center_millicents": 700_000,
            "fourth_center_millicents": 500_000,
            "step_up_center_millicents": 100_000,
            "step_down_center_millicents": -100_000,
            "radius_millicents": 100_000,
        },
    }
    policy["policy_hash"] = perceptual.voice_matching_policy_hash(policy)
    return policy


def _template_set(spec: dict, vocabulary: dict, vm_policy: dict, templates: list[dict]) -> dict:
    template_set = {
        "schema": "cps.perceptual-trajectory-template-set",
        "schema_version": "1.0.0",
        "algorithm": "pil-consecutive-trajectory-l1/v1",
        "template_set_schema_hash": perceptual.TRAJECTORY_TEMPLATE_SET_SCHEMA_HASH,
        "transition_record_schema_hash": perceptual.TRANSITION_FEATURE_RECORD_SCHEMA_HASH,
        "trajectory_result_schema_hash": perceptual.TRAJECTORY_RESULT_SCHEMA_HASH,
        "feature_spec_hash": spec["spec_hash"],
        "vocabulary_hash": vocabulary["vocabulary_hash"],
        "voice_matching_policy_hash": vm_policy["policy_hash"],
        "alignment": {
            "algorithm": "all-consecutive-windows/v1",
            "missing_component_policy": "omit-and-renormalize/v1",
            "maximum_results": 16,
        },
        "score_weights": {
            "chord": 4_000,
            "bass": 2_000,
            "common_tone": 1_000,
            "contrary_motion": 500,
            "resolution": 1_000,
            "tension": 500,
            "metrical": 1_000,
        },
        "templates": templates,
    }
    template_set["template_set_hash"] = perceptual.trajectory_template_set_hash(template_set)
    return template_set


def _step(vocabulary_id: str) -> dict:
    return {"chord_targets": [{"vocabulary_id": vocabulary_id, "weight_q31": Q31}]}


def _transition(center: int) -> dict:
    return {
        "bass_motion_center_millicents": center,
        "bass_motion_radius_millicents": 100_000,
        "common_tone_target_q": 5_000,
        "contrary_motion_target_q": 0,
        "resolution_kind": "step_up",
        "resolution_target_q": 0,
        "directed_tension_change_target_q": 0,
        "metrical_target_q": 7_500,
    }


def _bind(manifest: dict, **assets: dict | None) -> dict:
    mapping = {
        "segmentation_policy": ("segmentation_policy_hash", "policy_hash"),
        "feature_spec": ("feature_spec_hash", "spec_hash"),
        "chord_vocabulary": ("vocabulary_hash", "vocabulary_hash"),
        "voice_matching_policy": ("voice_matching_policy_hash", "policy_hash"),
        "trajectory_template_set": ("trajectory_template_set_hash", "template_set_hash"),
    }
    for name, asset in assets.items():
        if asset is not None:
            manifest_field, asset_field = mapping[name]
            manifest[manifest_field] = asset[asset_field]
    manifest["manifest_hash"] = perceptual.manifest_hash(manifest)
    return manifest


def _case(
    case_id: str,
    coverage: list[str],
    project: dict,
    manifest: dict,
    assets: dict[str, dict | None],
    note: str,
) -> dict:
    return {
        "schema": "cps.pil-oracle-case",
        "schema_version": "1.0.0",
        "case_id": case_id,
        "description": note,
        "coverage": coverage,
        "manifest": manifest,
        "project": project,
        "project_hash": perceptual.project_hash(project),
        "segmentation_policy": assets["segmentation_policy"],
        "feature_spec": assets["feature_spec"],
        "vocabulary": assets["chord_vocabulary"],
        "voice_matching_policy": assets["voice_matching_policy"],
        "trajectory_template_set": assets["trajectory_template_set"],
        "native_ji_report_hash": None,
        "expected": {
            "status": None,
            "error": None,
            "report_hash": None,
            "canonical_report_sha256": None,
        },
        "execution": {
            "worker_counts": [1, 2, 4, 8],
            "pythonhashseeds": ["0", "1", "424242"],
        },
        "case_hash": None,
    }


def _phase1(case_id, coverage, events, *, equave="2/1", radius=100_000, note=""):
    manifest = _manifest(radius)
    return _case(
        case_id,
        coverage,
        _project(events, equave=equave),
        manifest,
        {
            "segmentation_policy": None,
            "feature_spec": None,
            "chord_vocabulary": None,
            "voice_matching_policy": None,
            "trajectory_template_set": None,
        },
        note,
    )


def _phase3_assets():
    policy = _segmentation_policy()
    spec = _feature_spec(policy)
    vocabulary = _vocabulary(spec)
    return policy, spec, vocabulary


def _phase4_assets(templates: list[dict]):
    policy = _segmentation_policy()
    spec = _feature_spec(policy)
    vocabulary = _vocabulary(spec)
    vm_policy = _voice_matching_policy(spec)
    template_set = _template_set(spec, vocabulary, vm_policy, templates)
    return policy, spec, vocabulary, vm_policy, template_set


def build_cases() -> list[dict]:
    cases = []

    # --- Phase 1 (contract section 9 items 2, 7, 8) ---
    cases.append(
        _phase1(
            "pil_seven_limit_multi_candidate",
            ["success", "equave_2_1"],
            [
                _note("ev_a", "1/1", 0),
                _note("ev_b", "5/4", 0),
                _note("ev_c", "3/2", 0),
                _note("ev_d", "7/4", 0),
            ],
            note="7-limit chord; every pitch row must retain multiple nonzero candidates.",
        )
    )
    cases.append(
        _phase1(
            "pil_tritave_phase_split",
            ["success", "equave_3_1", "phase_independence"],
            [_note("ev_a", "3/1", 0)],
            equave="3/1",
            note="3/1 equave: native phase wraps by 3/1 while the 2/1 interpretation phase differs.",
        )
    )
    cases.append(
        _phase1(
            "pil_kernel_boundaries",
            ["success", "kernel_edge", "kernel_tie"],
            [
                _note("ev_a", "1/1", 0),
                _note("ev_b", "45/32", 0),
                _note("ev_c", "25/24", 0),
            ],
            note="Kernel edge/tie geometry; owner declares exact boundary expectations.",
        )
    )
    cases.append(
        _phase1(
            "pil_kernel_empty_support",
            ["failure", "kernel_empty_support"],
            [_note("ev_a", "16/15", 0)],
            radius=10_000,
            note="Radius 10000 leaves 16/15 without support: PIL_PITCH_SUPPORT_EMPTY.",
        )
    )
    cases.append(
        _phase1(
            "pil_cache_parity",
            ["success", "cache_cold", "cache_hit", "cache_corrupt"],
            [_note("ev_a", "5/4", 0), _note("ev_b", "3/2", 0)],
            note="Cold, hit and corrupt cache executions must be byte-identical.",
        )
    )
    cases.append(
        _phase1(
            "pil_cross_process_workers",
            ["success", "cross_process", "parallel_1", "parallel_2", "parallel_4", "parallel_8"],
            [_note("ev_a", "1/1", 0), _note("ev_b", "7/4", 0), _note("ev_c", "11/8", 0)],
            note="PYTHONHASHSEED and 1/2/4/8-worker parity matrix.",
        )
    )

    # --- Phase 2 (contract section 9 item 8, segment boundary) ---
    policy = _segmentation_policy()
    manifest = _bind(_manifest(), segmentation_policy=policy)
    cases.append(
        _case(
            "pil_segment_boundary",
            ["success"],
            _project(
                [
                    _note("ev_a", "1/1", 0),
                    _note("ev_b", "3/2", 480, track="bass"),
                ],
                total_ticks=960,
            ),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": None,
                "chord_vocabulary": None,
                "voice_matching_policy": None,
                "trajectory_template_set": None,
            },
            "Grid/bass/sustained/pitch-distribution boundary rules and half-open intervals.",
        )
    )

    # --- Phase 3 (contract section 9 items 1, 3) ---
    policy = _segmentation_policy(bass_role_order=["bass"])
    spec = _feature_spec(policy)
    vocabulary = _vocabulary(spec)
    manifest = _bind(
        _manifest(), segmentation_policy=policy, feature_spec=spec, chord_vocabulary=vocabulary
    )
    cases.append(
        _case(
            "pil_soft_major_1_1_5_4_3_2",
            ["success", "chord_similarity", "missing_bass"],
            _project([_note("ev_a", "1/1", 0), _note("ev_b", "5/4", 0), _note("ev_c", "3/2", 0)]),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": None,
                "trajectory_template_set": None,
            },
            "High soft major similarity while exact ratios are retained.",
        )
    )
    policy, spec, vocabulary = _phase3_assets()
    manifest = _bind(
        _manifest(), segmentation_policy=policy, feature_spec=spec, chord_vocabulary=vocabulary
    )
    cases.append(
        _case(
            "pil_passing_tone_delta",
            ["success"],
            _project(
                [
                    _note("ev_a", "1/1", 0),
                    _note("ev_b", "5/4", 0),
                    _note("ev_c", "3/2", 0),
                    _note("ev_pass", "9/8", 240, duration=120),
                    _note("ev_d", "1/1", 480),
                    _note("ev_e", "5/4", 480),
                    _note("ev_f", "3/2", 480),
                ],
                total_ticks=960,
            ),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": None,
                "trajectory_template_set": None,
            },
            "Short passing-tone perturbation; owner declares the similarity delta bound.",
        )
    )
    policy = _segmentation_policy()
    spec = _feature_spec(policy)
    spec["similarity"]["winner_margin_floor_q"] = 10_000
    spec["spec_hash"] = perceptual.chord_feature_spec_hash(spec)
    vocabulary = _vocabulary(spec)
    manifest = _bind(
        _manifest(), segmentation_policy=policy, feature_spec=spec, chord_vocabulary=vocabulary
    )
    cases.append(
        _case(
            "pil_ambiguous_chord_margin",
            ["success", "chord_similarity", "ambiguous_winner"],
            _project([_note("ev_a", "1/1", 0)]),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": None,
                "trajectory_template_set": None,
            },
            "Maximum winner margin retains candidates while suppressing the best label.",
        )
    )

    # --- Phase 4 (contract section 9 items 4, 5, 6, 8) ---
    ii_v_i_templates = [
        {
            "id": "ii_v_i",
            "ordinal": 0,
            "steps": [_step("minor"), _step("major"), _step("major")],
            "transitions": [_transition(500_000), _transition(-500_000)],
        }
    ]

    def _progression(events, case_id, note):
        policy, spec, vocabulary, vm_policy, template_set = _phase4_assets(ii_v_i_templates)
        manifest = _bind(
            _manifest(),
            segmentation_policy=policy,
            feature_spec=spec,
            chord_vocabulary=vocabulary,
            voice_matching_policy=vm_policy,
            trajectory_template_set=template_set,
        )
        return _case(
            case_id,
            ["success", "voice_matching", "trajectory_similarity"],
            _project(events, total_ticks=1_440),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": vm_policy,
                "trajectory_template_set": template_set,
            },
            note,
        )

    def _chord(prefix, start, root, third, fifth, bass):
        return [
            _note(f"{prefix}_r", root, start),
            _note(f"{prefix}_t", third, start),
            _note(f"{prefix}_f", fifth, start),
            _note(f"{prefix}_b", bass, start, track="bass"),
        ]

    cases.append(
        _progression(
            [
                # ii (minor on 9/8) -> V (major on 3/2) -> I (major on 1/1),
                # voiced near 12-TET target relationships.
                *_chord("s1", 0, "9/8", "27/20", "27/16", "9/8"),
                *_chord("s2", 480, "3/2", "15/8", "9/4", "3/2"),
                *_chord("s3", 960, "1/1", "5/4", "3/2", "1/1"),
            ],
            "pil_12et_ii_v_i",
            "Conventional 12-TET-target ii-V-I; owner declares the trajectory similarity floor.",
        )
    )
    cases.append(
        _progression(
            [
                # Exact-ratio JI analogue of the same functional shape.
                *_chord("s1", 0, "9/8", "27/20", "27/16", "9/8"),
                *_chord("s2", 480, "3/2", "15/8", "9/4", "3/2"),
                *_chord("s3", 960, "1/1", "5/4", "3/2", "1/1"),
            ],
            "pil_exact_ratio_ii_v_i",
            "Exact-ratio JI analogue; owner declares the trajectory similarity floor.",
        )
    )
    cases.append(
        _progression(
            [
                # Lattice-smooth nonfunctional colour movement (7/6 -> 6/5 -> 9/8).
                *_chord("s1", 0, "7/6", "7/5", "7/4", "7/6"),
                *_chord("s2", 480, "6/5", "4/3", "3/2", "6/5"),
                *_chord("s3", 960, "9/8", "45/32", "27/16", "9/8"),
            ],
            "pil_nonfunctional_two_reports",
            "High Native JI coherence with low ii-V-I similarity, reported separately; "
            "the Native JI report hash is correlation metadata filled by the owner.",
        )
    )

    # Matching tie (contract section 9 item 8): symmetric 386314 mc moves.
    # Only absolute-motion cost is weighted, so the two injections tie exactly
    # and the lexicographically smallest canonical_matching_key must win.
    policy, spec, vocabulary, vm_policy, template_set = _phase4_assets(
        [
            {
                "id": "tie_probe",
                "ordinal": 0,
                "steps": [_step("major"), _step("major")],
                "transitions": [_transition(400_000)],
            }
        ]
    )
    vm_policy["cost_weights"] = {
        "absolute_motion": 10_000,
        "circular_motion": 0,
        "pitch_mapping_l1": 0,
        "role_mismatch": 0,
    }
    vm_policy["policy_hash"] = perceptual.voice_matching_policy_hash(vm_policy)
    template_set["voice_matching_policy_hash"] = vm_policy["policy_hash"]
    template_set["template_set_hash"] = perceptual.trajectory_template_set_hash(template_set)
    manifest = _bind(
        _manifest(),
        segmentation_policy=policy,
        feature_spec=spec,
        chord_vocabulary=vocabulary,
        voice_matching_policy=vm_policy,
        trajectory_template_set=template_set,
    )
    cases.append(
        _case(
            "pil_matching_tie",
            ["success", "voice_matching", "matching_tie"],
            _project(
                [
                    _note("ev_a", "1/1", 0),
                    _note("ev_b", "5/4", 0),
                    _note("ev_c", "5/4", 480),
                    _note("ev_d", "25/16", 480),
                ],
                total_ticks=960,
            ),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": vm_policy,
                "trajectory_template_set": template_set,
            },
            "Symmetric +386314 mc motions produce an exact cost tie; the "
            "lexicographically smallest canonical_matching_key must win.",
        )
    )

    def _phase4_pair(case_id: str, coverage: list[str], events: list[dict], note: str) -> dict:
        templates = [
            {
                "id": "pair_probe",
                "ordinal": 0,
                "steps": [_step("major"), _step("major")],
                "transitions": [_transition(0)],
            }
        ]
        if "trajectory_missing_bass" in coverage:
            policy = _segmentation_policy(bass_role_order=["drums"])
            spec = _feature_spec(policy)
            vocabulary = _vocabulary(spec)
            vm_policy = _voice_matching_policy(spec)
            template_set = _template_set(spec, vocabulary, vm_policy, templates)
        else:
            policy, spec, vocabulary, vm_policy, template_set = _phase4_assets(templates)
        manifest = _bind(
            _manifest(),
            segmentation_policy=policy,
            feature_spec=spec,
            chord_vocabulary=vocabulary,
            voice_matching_policy=vm_policy,
            trajectory_template_set=template_set,
        )
        return _case(
            case_id,
            coverage,
            _project(events, total_ticks=960),
            manifest,
            {
                "segmentation_policy": policy,
                "feature_spec": spec,
                "chord_vocabulary": vocabulary,
                "voice_matching_policy": vm_policy,
                "trajectory_template_set": template_set,
            },
            note,
        )

    cases.append(
        _phase4_pair(
            "pil_matching_unequal",
            ["success", "voice_matching", "unequal_voice_count"],
            [
                _note("a", "1/1", 0),
                _note("b", "5/4", 0),
                _note("c", "3/2", 0),
                _note("d", "1/1", 480),
                _note("e", "3/2", 480),
            ],
            "Three-to-two voice transition fixes reverse injection and unmatched encoding.",
        )
    )
    cases.append(
        _phase4_pair(
            "pil_matching_identity",
            ["success", "voice_matching", "identity_constraint"],
            [
                _note("sustain", "1/1", 0, duration=960),
                _note("a", "5/4", 0),
                _note("b", "3/2", 480),
            ],
            "A note sustained across the boundary must match its own event identity.",
        )
    )
    cases.append(
        _phase4_pair(
            "pil_trajectory_missing_bass",
            ["success", "trajectory_similarity", "trajectory_missing_bass"],
            [
                _note("a", "1/1", 0),
                _note("b", "5/4", 0),
                _note("c", "1/1", 480),
                _note("d", "3/2", 480),
            ],
            "No bass-role event: bass component is omitted and weights renormalize.",
        )
    )
    return cases


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    for case in cases:
        path = OUT / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    index = {
        "schema": "cps.pil-oracle-suite-index",
        "schema_version": "1.0.0",
        "suite_version": None,
        "required_coverage": PIL_REQUIRED_COVERAGE,
        "cases": [
            {
                "case_id": case["case_id"],
                "path": f"{case['case_id']}.json",
                "raw_file_sha256": None,
                "case_hash": None,
                "case_schema_hash": None,
                "coverage": case["coverage"],
            }
            for case in sorted(cases, key=lambda row: row["case_id"].encode())
        ],
        "suite_hash": None,
        "template_note": "Index template; all hash fields are owner-filled goldens.",
    }
    (OUT / "suite_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(cases)} case templates plus suite_index.json to {OUT}")


if __name__ == "__main__":
    main()
