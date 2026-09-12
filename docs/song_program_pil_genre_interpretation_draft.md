# PIL Genre/Style Interpretation (Phase 5) — Draft Prerequisite Specification

**Status:** non-normative design draft prepared by the implementation side.
This document is **not** a contract. It enumerates what contract section 7
leaves undefined, proposes artifact shapes and algorithms for owner review,
and lists the decisions required before any Phase 5 implementation may
start. Until the owner closes these points in
`song_program_perceptual_interpretation_layer_contract.md`, genre evaluation
remains a SPEC-BLOCKER and all PIL metrics remain audit-only.

## 1. What section 7 already fixes

- Genre evaluation combines harmonic trajectory, melody, rhythm/groove,
  form, instrumentation and production **only when each feature source is
  bound**; unavailable groups are reported in `missing_groups`, never
  replaced by zero.
- At least `typicality_q`, `idiomaticity_q`, `cliche_dependence_q` and
  `novelty_q` are reported separately; no normative overall score in 1.0.
- Harmonic detail retains chord-vocabulary, progression, function,
  voice-leading and harmonic-rhythm similarities separately.
- An LLM may act only as a semantic/style judge over a sealed structured
  PIL context and never computes numbers; promotion needs the existing
  planner/model identity, tokenizer, prompt, response and calibration
  authorities.
- Failure namespace includes `genre` (section 8); the report schema already
  carries `genre_interpretations[]` (GenreInterpretation shape: `genre_id`
  plus the four Q0.10000 values) and `missing_groups`.

## 2. Undefined points that block implementation (SPEC-BLOCKER detail)

| # | Undefined item | Why it blocks |
| --- | --- | --- |
| G1 | GenreModel 1.0 asset type: payload fields, frozen raw-schema hash, content-addressed identity | `genre_model_hash` is nullable in the manifest, but no payload shape exists to bind |
| G2 | Per-group feature source definitions: which prior artifacts (PIL Phase 1-4 records, Project, render evidence) feed harmony/melody/rhythm/form/instrumentation/production, and their hash bindings | section 7 says "only when each feature source is bound" without naming the sources |
| G3 | Integer algorithms for `typicality_q`, `idiomaticity_q`, `cliche_dependence_q`, `novelty_q` (formulas, weights, rounding) | no normative computation exists; guessing would create unreviewable canonical bytes |
| G4 | Harmonic-detail sub-scores (chord-vocabulary, progression, function, voice-leading, harmonic-rhythm) — inputs from Phase 3/4 records and their aggregation | the report schema has no field for them yet |
| G5 | `missing_groups` semantics for a harmony-only model: whether evaluation proceeds with `missing_groups` listing the other five groups, or fails | affects failure vs success precedence |
| G6 | `completed_phase` enum extension (e.g. `genre_interpretation`) and Phase 5 build identity | report schema enum currently ends at `functional_trajectory` |
| G7 | LLM judge sealing format, if any LLM path is ever enabled | explicitly requires separate authorities; out of scope for a numeric-only Phase 5 |

## 3. Proposed artifact shapes (for owner review)

### 3.1 GenreModel 1.0 (content-addressed asset)

```yaml
schema: cps.perceptual-genre-model
schema_version: 1.0.0
algorithm: pil-genre-prototype-l1/v1        # proposed; see G3
model_schema_hash: sha256:...               # frozen raw schema bytes
feature_spec_hash: sha256:...               # binds Phase 3 FeatureSpec
vocabulary_hash: sha256:...                 # binds Phase 3 Vocabulary
trajectory_template_set_hash: sha256:...    # binds Phase 4 template set
required_groups: [harmony]                  # minimum executable closure
entries:                                    # 1..64 genre prototypes
  - genre_id: ^[a-z][a-z0-9_.-]{0,127}$
    ordinal: 0..63                          # unique, contiguous, stored order
    chord_vocabulary_targets:               # sparse Q31 over vocabulary ordinals
      - {vocabulary_ordinal: 0, weight_q31: ...}
    progression_targets:                    # sparse Q31 over template ordinals
      - {template_ordinal: 0, weight_q31: ...}
    function_profile_q: [0..10000 x N]      # closed integer profiles
    voice_leading_profile_q: [...]
    harmonic_rhythm_profile_q: [...]
model_hash: <generic artifact self hash>
```

### 3.2 GenreFeatureRecord 1.0 (per report, harmony group)

Derived only from already-bound Phase 3/4 records (never recomputed with new
approximations): segment-interpretation candidate distributions aggregated
into a vocabulary-ordinal Q31 histogram, trajectory-result Q31 histogram over
template ordinals, function/voice-leading/harmonic-rhythm integer profiles
from transition feature records and segment ticks. Native JI evidence enters
only by hash/reference, exactly as in Phase 3.

### 3.3 GenreInterpretation 1.0 (report rows)

Existing report-schema `genre` definition is reused unchanged
(`genre_id`, four Q0.10000 values). Proposed computations (G3):

- `typicality_q`: weighted normalized L1 similarity between the feature
  record histograms and the prototype targets (same
  `weighted-normalized-l1-q10000/v1` family as Phase 3);
- `idiomaticity_q`: similarity restricted to function/voice-leading/
  harmonic-rhythm profiles;
- `cliche_dependence_q`: concentration of the trajectory histogram on the
  prototype's top templates (declared integer formula);
- `novelty_q`: `10000 - typicality_q` is forbidden as a silent alias; a
  separate declared formula is required (open decision G3).

Rows sort by `(-typicality_q, genre ordinal)`; no overall score, no winner
requirement. With a harmony-only model, evaluation proceeds and
`missing_groups` lists `["melody", "rhythm", "form", "instrumentation",
"production"]` (proposal for G5).

## 4. Proposed integration points

- New manifest profile field set: `genre_model_hash` becomes non-null when
  Phase 5 is requested; cache key and report identity already carry it.
- `completed_phase` gains `genre_interpretation`; Phase 5 requires a
  successful Phase 4 report and fails with `PIL_GENRE_FAILED` after Phase 4
  validation (section 8 namespace order).
- New build identity `pil.phase5.1.0.0`; earlier builds are not silently
  upgraded (same rule as Phases 3/4).
- Genre evaluation never reads Native JI values, never writes into Resolved
  Chords or Project events, and cannot affect QD/archive/challenger/stopping
  without a CalibrationDecision.

## 5. Required owner decisions before implementation

1. G1-G7 above, especially the four score formulas (G3) and the
   harmony-detail fields (G4, possibly a report-schema extension).
2. Whether the harmony-only minimum closure (G5) is acceptable for 1.0.
3. Genre prototype corpus provenance: prototypes are content-addressed
   calibration-adjacent assets; their source corpus and licensing must be
   recorded like other calibration artifacts.
4. Oracle coverage labels for genre cases (extend the suite's
   `required_coverage` set) and new golden cases.
