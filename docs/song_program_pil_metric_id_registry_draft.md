# PIL Metric ID Registry — Promotion Record

**Status:** the Phase 1–4 IDs and extraction semantics are authoritative in
`backend/songprogram_conformance/fixtures/pil_calibration/metric_registry.json`
under `song_program_pil_calibration_promotion_contract.md`. The registry
promotes nothing by itself. All PIL metrics remain audit-only until an
evidence-backed decision is promoted.

## 1. Spelling convention

C1 is closed with dotted IDs in a PIL-specific schema. The existing Genre
CalibrationDecision 1.0 schema is not changed or reinterpreted.

## 2. Candidate metrics from the Phase 1–4 report

| candidate metric_id | source report field | proposed direction | aggregation question (open) |
| --- | --- | --- | --- |
| `pil_segment_confidence_q` | `segments[].confidence_q` | higher | min vs weighted mean across segments |
| `pil_chord_confidence_q` | `segment_interpretations[].confidence_q` | higher | min vs mean across segments |
| `pil_chord_margin_q` | derived: `candidates[0].similarity_q - candidates[1].similarity_q` per interpretation (runner-up is not a stored field) | higher | min vs mean; single-candidate and unlabeled (`best_label` null) handling |
| `pil_voice_matching_cost_q` | `voice_matching_records[].total_cost_q` | **lower** | max vs mean across transitions |
| `pil_common_tone_q` | `voice_matching_records[].common_tone_q` | higher | min vs mean |
| `pil_contrary_motion_q` | `voice_matching_records[].contrary_motion_q` | higher | mean; all-zero treatment |
| `pil_tension_change_abs_q` | `transition_feature_records[].directed_tension_change_q` | lower (absolute) | max vs mean; sign handling |
| `pil_trajectory_similarity_q` | `trajectory_interpretations[].similarity_q` | higher | best window only vs mean of retained windows |
| `pil_trajectory_chord_q` | `component_scores_q.chord` | higher | same window question |
| `pil_trajectory_bass_q` | `component_scores_q.bass` (nullable) | higher | missing-bass behavior ties to C4 |
| `pil_trajectory_common_tone_q` | `component_scores_q.common_tone` | higher | same |
| `pil_trajectory_contrary_q` | `component_scores_q.contrary_motion` | higher | same |
| `pil_trajectory_resolution_q` | `component_scores_q.resolution` | higher | same |
| `pil_trajectory_tension_q` | `component_scores_q.tension` | higher | same |
| `pil_trajectory_metrical_q` | `component_scores_q.metrical` | higher | same |

Genre/style Q values (`typicality_q` etc.) are excluded: Phase 5 remains
blocked on G1–G7 and would add its own registry rows later.

## 3. Closed common semantics

Aggregation, direction, selector and missing behavior are fixed per registry
row. Thresholds are evidence-derived and appear in a decision, not fabricated
in the registry. Cost and absolute tension-change metrics minimize; all other
1.0 metrics maximize. Missing values are unavailable and never zero. Dotted
`pil.*` IDs cannot collide with `native_ji.*`.

## 4. Non-goals

Nothing here authorizes connecting any listed metric to QD axes, rejection,
archive quality, challenger acceptance or stopping. Promotion requires the
full CalibrationDecision path of the companion draft.
