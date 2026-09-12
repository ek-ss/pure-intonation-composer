# Perceptual Interpretation Layer 1.0

**Status:** normative architecture and artifact boundary; numerical model
assets remain audit-only until independently calibrated.

## 1. Non-replacement rule

The Perceptual Interpretation Layer (PIL) is a new, parallel interpretation of
immutable native musical events. It MUST NOT replace, normalize, rewrite, or
round the Project's ratio, vector, equave exponent, lattice coordinate,
ResolvedChord, native voice-leading, comma-drift, harmonicity, roughness, or
Native JI evaluation evidence.

```text
                         immutable Project / rendered evidence
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
       Native JI Evaluation                    Perceptual Interpretation
       (existing authority)                    (new derived authority)
                 |                                         |
                 +--------------------+--------------------+
                                      |
                         separately bound evidence rows
```

Neither branch consumes the other branch's report. Failure, absence, cache
miss, or model-version change in PIL cannot change Native JI values or validity.
Failure in Native JI cannot be hidden by a PIL label or score. A combined UI may
display both reports, but it MUST label them `native_ji` and
`perceptual_interpretation`; merging them into an unlabeled score is forbidden.

PIL answers “how strongly could this be conventionally perceived as X?”, not
“what native object is this?”. A conventional chord/function label is never a
native identity, compiler input, pitch replacement, or provenance source.
`native_ji_report_hash` in a PIL report is nullable correlation metadata for a
combined display or later two-evidence decision. It is excluded from PIL
feature computation and does not make either report an input to the other.

## 2. Authority and promotion

`PerceptualInterpretationManifest 1.0` binds the Project schema, Numeric
Contract, segmentation, pitch kernel, vocabulary, trajectory and optional
genre model assets by content hash. `PerceptualInterpretationReport 1.0` binds
the Project hash, manifest hash, all derived records and its own hash. No
ambient corpus, locale, note spelling, A4 setting, model endpoint or default is
allowed.

Manifest and report self-hashes use the Search Decision artifact preimage with
only `manifest_hash` or `report_hash` removed:
`UTF8("cps-artifact-hash/v1\0" || schema || "\0" || schema_version || "\0")`
followed by canonical JSON with no trailing LF. The initial Phase 1 launch
profile binds the exact raw bytes whose SHA-256 values are:

- ArrangementProject 1.2 schema: `sha256:960891e2390acb2a3c14e35074de9a56bb0604c9098baff0aada3fbeeeeb167d`;
- Numeric Contract `cps-numeric/decimal-log2-rhe-v1`:
  `sha256:a24ed6cc9cd96f49792f553c52b6237afcad0c9a3172e6931bb65c3e30ed3abb`.
- SegmentationPolicy 1.0 schema:
  `sha256:77559f2ad4f563c761be20505eec8af4c4a04e63b51b9201df680e280bfa370d`.

An implementation embeds or content-addressedly resolves these identities; it
MUST NOT accept an arbitrary same-shaped hash. A later byte change creates a
new manifest/build profile rather than silently updating these bindings.

PIL 1.0 is audit-only by default. It may affect QD axes, rejection, archive
quality, challenger acceptance or stopping only when a versioned
CalibrationDecision explicitly promotes the exact PIL manifest hash, metric
IDs, directions, thresholds and missing-value behavior. Promotion adds PIL
evidence; it never removes or aliases a Native JI criterion. Native and PIL
metric IDs occupy disjoint namespaces: `native_ji.*` and `pil.*`.

## 3. Pitch projection

The source of truth is each event's exact reduced ratio, vector, equave
exponent and source provenance. PIL derives frequency and cents using the bound
Numeric Contract. It stores integer `frequency_millihz` and
`absolute_millicents`; binary float is forbidden in canonical artifacts.

Native equave phase and conventional pitch-class projection are distinct:

- `native_phase_millicents` wraps by the Project lattice equave;
- `interpretation_phase_millicents` wraps by the manifest's explicit
  `interpretation_period`, which is `2/1` for the initial 12-TET vocabulary;
- `absolute_millicents` is never wrapped and preserves register.

A 3/1 lattice therefore remains 3/1-native even when PIL also asks how it may
be heard through an octave-periodic vocabulary.

Hard nearest-note quantization is forbidden. For each pitch, the report retains
an ordered sparse probability row over vocabulary pitch classes. PIL 1.0 uses
`triangular-millicent-q31/v1`: for circular distance `d` and bound radius `R`,
raw weight is `max(0,R-d)`; normalize eligible raw weights to sum exactly
`2^31-1` using floor division, then distribute remaining units by descending
fractional remainder and pitch-class ordinal. Ties use ordinal. Empty support
is `PIL_PITCH_SUPPORT_EMPTY`. Gaussian is reserved until a versioned integer
lookup-table asset, construction oracle and golden boundaries are bound.

## 4. Harmonic segmentation

Segmentation operates on Project event timing without modifying events.
Candidate boundaries are the sorted union of bound beat/sub-beat grid points,
bass changes, sustained-set changes and pitch-distribution changes. Every rule,
threshold and weight is an integer in the bound SegmentationPolicy. Event
salience is a checked integer function of overlap duration, metrical weight,
velocity, role gain, persistence and bass salience. Zero-weight events are
omitted.

The segmentation algorithm and all half-open interval rules are manifest-bound.
Each `HarmonicSegment` records start/end tick, ordered source event IDs,
weighted pitch distribution, bass event ID or null, and confidence Q0.10000.
Passing-tone robustness is evaluated as a separate regression metric; an
implementation may not silently delete a passing tone from provenance.

### 4.1 SegmentationPolicy 1.0

The initial algorithm is `pil-harmonic-segmentation-grid-events/v1`. Its
closed policy binds: Project and policy schema hashes; `grid_divisions_per_beat`
in `{1,2,4,8}`; `minimum_segment_ticks`; sustained-note threshold; normalized
pitch-distribution L1 threshold; metrical, persistence and bass coefficients;
all-five-role gain table; ordered bass roles; boundary priority; and its self hash. The Project's
`ticks_per_beat` MUST divide evenly by the grid divisor. There are no ambient
defaults.

First form elementary half-open spans from the sorted unique set containing
`0`, Project `total_ticks`, and every pitched note onset/end clipped to that
range. For each nonempty elementary span, its active set contains exactly notes
with `start_tick < span_end` and `start_tick + duration_ticks > span_start`.
The span bass is the active event whose `track.role` occurs earliest in the
policy's `bass_role_order`, then has lowest `absolute_millicents`, then lowest
UTF-8 event ID. If no eligible event is active, bass is null.

Boundary candidates are the union below. Reasons at one tick are retained as
one ordered reason set.

1. `endpoint`: ticks `0` and `total_ticks`;
2. `bass_change`: an elementary boundary whose left/right bass IDs differ;
3. `sustained_change`: an onset/end of an event whose duration is at least
   `sustained_minimum_ticks` and whose left/right membership differs;
4. `pitch_distribution_change`: an elementary boundary where half the L1
   distance of the left/right normalized 12-bin distributions is at least
   `pitch_distribution_change_q`;
5. `metrical`: multiples of `ticks_per_beat/grid_divisions_per_beat` strictly
   inside the Project.

For the change test, each active event contributes `velocity * role_gain_q`
to the bin containing its `interpretation_phase_millicents` by half-open
100,000-millicent bins. Normalize each nonempty vector to Q0.10000 by floor and
largest remainder, bin ordinal tie-break; an empty vector is twelve zeros.
The distance is `RHE(sum(abs(left_i-right_i))/2)` and is therefore 0..10000.

Boundary merge is exact. Coalesce equal ticks and union reasons in frozen
priority `endpoint,bass_change,sustained_change,pitch_distribution_change,
metrical`. Accept both endpoints first. Visit remaining candidates by
`(best_reason_priority,tick)` and accept a tick only when its distance from
every already accepted tick is at least `minimum_segment_ticks`; otherwise
discard it entirely. Finally sort accepted ticks ascending. This global rule,
including endpoint priority, prevents a late candidate from creating a short
terminal segment. Every adjacent accepted pair creates exactly one segment.

The requested/completed execution phase is either `pitch_projection` or
`harmonic_segmentation`. It is a required report member and a cache-key member;
an implementation MUST NOT satisfy one phase from an entry produced for the
other. `harmonic_segmentation` requires the complete policy payload whose
`policy_hash` equals the manifest binding. A segment ID is
`seg_ || lowercase_hex(SHA-256(preimage))[0:32]`, where `preimage` is
`UTF8("cps.pil-segment-id/v1\\0") || canonical_json({"end_tick":b,
"policy_hash":policy_hash,"project_hash":project_hash,"start_tick":a})`.
Thus the ID is independent of traversal order and contains no ambient state.
The segment `bass_event_id` is the bass of its earliest nonempty elementary
span; it is null only when every elementary span in the segment is empty.
This rule still applies when minimum-length merging discards an internal
`bass_change` candidate.

### 4.2 Integer event weight

Within segment `[a,b)`, event overlap is
`max(0,min(event_end,b)-max(event_start,a))`. Define:

```text
metrical_q = 10000 if event.start_tick mod ticks_per_beat == 0
              5000 if event.start_tick mod (ticks_per_beat/2) == 0
                 0 otherwise
persistence_q = RHE(10000 * overlap_ticks / event.duration_ticks)
bass_q = 10000 iff event.id == segment bass_event_id, else 0
factor_q = duration_coefficient_q
         + RHE(metrical_coefficient_q * metrical_q / 10000)
         + RHE(persistence_coefficient_q * persistence_q / 10000)
         + RHE(bass_coefficient_q * bass_q / 10000)
event_weight = RHE(overlap_ticks * velocity * role_gain_q * factor_q / 10000)
```

`role_gain_q` is the policy's required Q0.10000 value indexed by the source
event track's Project `role`. ArrangementProject 1.2 has no per-track gain;
the Project-wide render `mix.gain_q` is deliberately not reused as a salience
prior. An absent/duplicate track ID or unknown role is
`PIL_SEGMENTATION_POLICY_INVALID`.

All products/additions use checked u64 before division. Non-note events and
zero weights are excluded. Segment pitch distribution sums `event_weight` by
the same 12 bins and normalizes to Q31 total `2147483647` using floor/largest
remainder with bin ordinal tie-break. `source_event_ids` sort by UTF-8 ID and
include every positive-weight event. The policy binds one Q0.10000 confidence
for each boundary reason. Segment confidence is the maximum bound confidence
among the retained starting boundary's reasons; the initial endpoint
confidence MUST be 10000.

### 4.3 Failure precedence

First failure wins in this order, with event traversal by
`(start_tick,event_id UTF-8)` and boundary traversal by tick:

1. `PIL_BINDING_MISMATCH`
2. `PIL_SCHEMA_INVALID`
3. `PIL_NUMERIC_OVERFLOW`
4. `PIL_PITCH_SUPPORT_EMPTY`
5. `PIL_SEGMENTATION_POLICY_INVALID`
6. `PIL_SEGMENT_BOUNDARY_INVALID`
7. `PIL_SEGMENT_EMPTY`
8. `PIL_FEATURE_EXTRACTION_FAILED`
9. `PIL_VOCABULARY_FAILED`
10. `PIL_VOICE_MATCHING_FAILED`
11. `PIL_TRAJECTORY_FAILED`
12. `PIL_GENRE_FAILED`
13. `PIL_RESULT_VALIDATION`

Binding/schema failures create no report. Once Project and manifest bindings
are valid, later failures create a normal failed PIL report. None of these
codes changes or suppresses the parallel Native JI report.

## 5. Continuous features and conventional interpretations

Before labels, every segment produces a continuous integer feature record:
pitch and interval distributions, bass relation, harmonicity, roughness,
register profile, common-tone profile and native lattice compactness. Native
components are copied by hash/reference from Native JI evidence, never
recomputed with a perceptual approximation.

Vocabulary comparison returns an ordered list of candidates with similarity
Q0.10000. It does not require a winner. `best_label` is nullable and, when
present, is only the first candidate after sorting
`(-similarity_q, vocabulary_ordinal)` and meeting the bound confidence floor.
It MUST be exposed under `perceptual_interpretation`, never written into
ResolvedChord or Project events.

## 6. Function, trajectory and voice leading

Functional interpretation consumes segment features plus bass trajectory,
perceptual voice assignment, common tones, directed tension change, metrical
position and surrounding segments. It MUST NOT perform string matching on a
hard chord-label sequence.

Perceptual voice assignment is a separately versioned exact matching operator.
Its output retains source event IDs, signed absolute/circular millicent motion,
common-tone likelihood, contrary motion and resolution features. Native GEN0-B
matching remains unchanged and continues to own native voice-leading metrics.

Trajectory templates such as `ii-V-I`, `V-I`, `IV-V-I` and `I-vi-IV-V` are
content-addressed assets. Results are likelihood-like Q0.10000 similarities,
not assertions that the native progression “is” that template. Bass intervals
remain exact acoustic intervals with separate fifth/fourth/step likeness.

## 7. Genre/style interpretation

Genre evaluation may combine harmonic trajectory, melody, rhythm/groove,
form, instrumentation and production only when each feature source is bound.
Unavailable symbolic/audio feature groups are reported in `missing_groups` and
are not replaced by zero. It reports at least separate `typicality_q`,
`idiomaticity_q`, `cliche_dependence_q` and `novelty_q`; no normative overall
score exists in 1.0. Harmonic detail retains chord-vocabulary, progression,
function, voice-leading and harmonic-rhythm similarities separately.

An LLM may act only as a semantic/style judge over a sealed structured PIL
context. It may not calculate frequency, cents, matching, segmentation or
numeric similarity. Provider text and hidden model state are non-normative;
any promoted LLM judgment requires the existing planner/model identity,
tokenizer, prompt, response and calibration authorities.

## 8. Determinism, cache and failures

Canonical JSON follows the existing NFC/sorted-key/integer/no-float rule.
Cache keys bind Project hash, PIL manifest hash, every referenced asset hash,
Numeric Contract hash, implementation build ID and requested execution phase.
Cold, hit, corrupt,
cross-process and 1/2/4/8-worker executions MUST produce identical report bytes.

Failures use the ordered namespace: binding; schema; numeric overflow; pitch
support; segmentation; feature extraction; vocabulary; voice matching;
trajectory; genre; result validation. A failed PIL report remains independent
of the successful Native JI report and cannot trigger a Native JI fallback.

## 9. Required authoritative cases

The independent oracle suite must include:

1. `1/1,5/4,3/2` with high soft major similarity while retaining exact ratios;
2. a 7-limit chord whose pitch rows retain multiple nonzero candidates;
3. a short passing-tone perturbation bounded by a declared similarity delta;
4. a conventional 12-TET ii-V-I with high trajectory similarity;
5. an exact-ratio JI analogue with high trajectory similarity;
6. a lattice-smooth nonfunctional progression with high Native JI coherence
   and low ii-V-I similarity in two separate reports;
7. a 3/1-equave case proving native phase and 2/1 interpretation phase differ;
8. kernel edge/tie/empty-support, segment boundary, matching tie, cache corrupt
   and cross-process/worker parity cases.

Until these assets and a CalibrationDecision exist, all PIL metrics remain
audit-only. This restriction does not delay or weaken existing Native JI
evaluation.
