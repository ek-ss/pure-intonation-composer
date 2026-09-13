# PIL Metric ID Registry — Draft Candidate List

**Status:** non-normative design draft prepared by the implementation side,
accompanying `song_program_pil_calibration_promotion_draft.md` (blockers
C1–C6). This is **not** a contract and promotes nothing. It enumerates the
candidate PIL metric IDs derivable from the Phase 1–4 report fields so the
owner can rule on spelling (C1), directions/thresholds (C6) and aggregation.
All PIL metrics remain audit-only.

## 1. Spelling convention assumed by this draft

C1 is open: the CalibrationDecision 1.0 `metric_id` pattern
(`^[a-z][a-z0-9_]{0,63}$`) cannot spell dots. This draft therefore writes
candidate IDs with underscores (`pil_...`). If the owner instead extends the
schema for dotted `pil.*` IDs, every row below maps mechanically
(`pil_chord_confidence_q` → `pil.chord.confidence_q` or similar; the exact
dotted forms remain an owner choice).

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

## 3. Open decisions per row (owner)

1. **Aggregation**: report fields are per segment/transition/window; a
   promotable metric needs one declared aggregation each (C3/C6).
2. **Direction**: cost-like metrics are lower-is-better; the decision schema
   has no direction member, so the convention must be fixed with C6.
3. **Missing-value behavior**: nullable components (`bass`) and empty
   trajectory results need the C4 channel before their rows can be promoted.
4. **Namespace collision check**: any final ID must not collide with the
   `native_ji.*` namespace after respelling.

## 4. Non-goals

Nothing here authorizes connecting any listed metric to QD axes, rejection,
archive quality, challenger acceptance or stopping. Promotion requires the
full CalibrationDecision path of the companion draft.
