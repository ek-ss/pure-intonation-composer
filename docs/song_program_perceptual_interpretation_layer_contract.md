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
- ChordFeatureSpec 1.0 schema:
  `sha256:6744d7e50ce53046d497552d72d7bc2c747dd08650ebb75b00fba52978fec293`;
- ChordFeatureRecord 1.0 schema:
  `sha256:0e039841d18d1496161ba2283fdbd1dca743fd719288ca465823f03be0add1a6`;
- ChordVocabulary 1.0 schema:
  `sha256:dde975cb786368d66df8a79ea0457dd0f722fd40958c52efca448f5515edd3df`;
- PerceptualInterpretationReport 1.0 Phase 4 schema:
  `sha256:7b3e813f5fff25791738ba4f1b9e7d262f20bce912a24ad57ca231fd870f024c`;
- VoiceMatchingPolicy 1.0 schema:
  `sha256:288ae738994562e8ca67465c28cf102ce163ebfe35884c901860ee6f32e15690`;
- VoiceMatchingRecord 1.0 schema:
  `sha256:ae74975c01dedf1bf1cceea9d90e4a3a25fbb9c8e904aeae9e4313a49a28de29`;
- TransitionFeatureRecord 1.0 schema:
  `sha256:ff3e0c7e125f57347be40d31f77671572d7bde4450f52e65a0292f70e3cecff5`;
- TrajectoryTemplateSet 1.0 schema:
  `sha256:119fe9a73b47a11859c3d840d2541181d302c27c0a55fa5ff35215dfe42b1b45`;
- TrajectoryInterpretation 1.0 schema:
  `sha256:86ad76be91b2c2e2c33fac2630c7b3daa4fcaca4016740b0d930d3f0ab5d7dd1`.

The Phase 3 reference implementation build identity is
`pil.phase3.1.0.0`; manifests naming an earlier Phase 1/2 build are not
silently upgraded. The Phase 4 reference implementation build identity is
`pil.phase4.1.0.0`; it covers Phases 1-4 and binds the Phase 4 schema
profile above. Manifests naming `pil.phase3.1.0.0` remain valid for
`chord_similarity` and earlier phases but are not silently upgraded to
`functional_trajectory`.

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

Phase 3 uses `ChordFeatureSpec 1.0`, algorithm
`pil-chord-features-12pc/v1`, and `ChordVocabulary 1.0`, algorithm
`pil-chord-vocabulary-q31/v1`. Both are closed canonical artifacts using the
generic artifact self-hash rule. The complete payloads are required; hashes
alone are not executable inputs. Their self hashes MUST equal respectively the
manifest `feature_spec_hash` and `vocabulary_hash`; the vocabulary also binds
the feature-spec hash and `2/1` interpretation period. There are no defaults.
FeatureSpec embeds the exact FeatureSpec and FeatureRecord raw schema hashes;
Vocabulary embeds its exact raw schema hash. Schema hash mismatch is the owning
stage failure, not a permissive version negotiation.

### 5.1 ChordFeatureRecord

Every segment emits one `ChordFeatureRecord 1.0`, ordered by segment start,
with its complete canonical payload embedded in report `feature_records`.
`feature_record_hash` in the corresponding interpretation MUST equal its
generic artifact hash. Distributions are sparse, strictly increasing by pitch
class ordinal, contain positive weights only, and sum to `2147483647`.

- For every positive-weight source event, multiply each pitch-kernel
  `mapping_q31` bin by that exact Phase 2 event weight, sum by ordinal using
  checked u128, then normalize to Q31. This is `pitch_distribution_q31`.
  Phase 3 MUST NOT copy the Phase 2 coarse half-open-bin distribution: doing so
  would classify 5/4 (386314 millicents) as pitch class 3 instead of retaining
  its soft class-3/class-4 evidence.
- Expand pitch distribution to twelve bins `P`. For interval class `k`, raw
  value `I[k] = sum(P[i] * P[(i+k) mod 12])` for `i=0..11`. Normalize the
  twelve raw values to Q31 by floor/largest remainder, ordinal tie-break.
- If bass is non-null, expand that pitch record's soft mapping to twelve bins
  `B`. Bass-relative raw bin `R[k] = sum(B[i] * P[(i+k) mod 12])`, then use the
  same Q31 normalization. If bass is null, the field is null.
- The register set is the segment's positive-weight source events. Minimum and
  maximum are their `absolute_millicents`; mean is
  `RHE(sum(event_weight * absolute_millicents) / sum(event_weight))`.
- The first segment has null common-tone value. Later segments use
  `RHE(10000 * sum(min(previous_P[i], P[i])) / 2147483647)`.

Distribution multiplication/accumulation uses checked u128; signed register
accumulation uses checked i128. Overflow is `PIL_NUMERIC_OVERFLOW`. Phase 3
reuses the exact Phase 2 event-weight operator; it may not reconstruct weights
from the already-normalized pitch histogram.

Harmonicity, roughness and native lattice compactness remain Native JI-owned.
The feature record carries the nullable `native_ji_report_hash` for correlation
but never copies or recomputes those values. A later joint decision may join
the two immutable reports by hash. This explicitly preserves the parallel,
non-replacing evaluation architecture.

### 5.2 Vocabulary and similarity

Vocabulary entry ordinals MUST be unique and contiguous `0..N-1`; IDs are
unique and entries are stored in ordinal order. Every template distribution
obeys the same sparse-Q31 invariant as feature records. A null template
bass-relative distribution means that component is unavailable, not zero.
Every entry also binds `functional_tension_q` in Q0.10000. It is vocabulary
metadata for Phase 4 perceptual interpretation, never a Native JI tension value.

For two Q31 distributions `A,B` define:

```text
l1 = sum(abs(A[i] - B[i]))
component_similarity_q = 10000 - RHE(10000 * l1 / (2 * 2147483647))
```

Compute pitch and interval components always. Compute bass-relative only when
both record and template values are non-null. The FeatureSpec binds three
unsigned weights. Pitch and interval weights MUST be positive and the sum of
all three MUST be positive. Missing bass removes its weight from numerator and
denominator; it is never replaced by zero. Final similarity is
`RHE(sum(component_similarity_q * available_weight) / sum(available_weight))`.
All operations are checked u64.

Compare every vocabulary entry, sort by
`(-similarity_q, vocabulary_ordinal, id UTF-8)`, then retain the first
`maximum_candidates`. `confidence_q` is the first similarity, or zero only for
an empty vocabulary (which schema validation already forbids). Let runner-up
similarity be zero when only one candidate exists. `best_label` is the first
ID iff confidence is at least `confidence_floor_q` and
`confidence_q-runner_up_q` is at least `winner_margin_floor_q`; otherwise it
is null. A soft candidate list is always retained and never changes native
identity, ratios, events or ResolvedChords.

### 5.3 Phase and failure behavior

Successful Phase 3 reports use `completed_phase: chord_similarity`. Their
cache key includes this phase and therefore cannot alias Phase 1 or Phase 2.
Feature extraction traverses segments by start tick, vocabulary entries by
ordinal and bins by ordinal. Feature failure precedes vocabulary failure as
already fixed in section 4.3. Invalid FeatureSpec or feature result is
`PIL_FEATURE_EXTRACTION_FAILED`; invalid vocabulary or similarity result is
`PIL_VOCABULARY_FAILED`. Both are computation-stage failed reports and cannot
alter or suppress Native JI evidence.

## 6. Function, trajectory and voice leading

Phase 4 uses complete, content-addressed `VoiceMatchingPolicy 1.0` and
`TrajectoryTemplateSet 1.0` payloads. A hash without its canonical payload is
not executable. Each asset embeds its frozen raw-schema hashes and binds the
Phase 3 FeatureSpec/Vocabulary hashes. Self hashes use the generic artifact
rule. Native GEN0-B matching is neither an input nor fallback and remains the
sole owner of native voice-leading metrics.

### 6.1 Selected perceptual voices

For each segment recompute the exact Phase 2 event weights. Sort positive-weight
source events by `(-event_weight, absolute_millicents, event_id UTF-8)`, retain
the first `maximum_voices_per_segment`, then canonicalize the retained set by
`(absolute_millicents,event_id UTF-8)`. These zero-based positions are the
`from` and `to` voice ordinals. No onset clustering, track preference or ambient
foreground detector is allowed.

For adjacent segments A/B, enumerate every injection from the smaller retained
set into the larger. Equal sizes orient A→B. If B is smaller, enumeration is
B→A but output pairs always contain A's event as `from_event_id` and B's as
`to_event_id`. An event ID present in both sets MUST pair with itself; candidates
violating this identity constraint are infeasible.

For a candidate pair define signed absolute motion `d = B.absolute_mc -
A.absolute_mc` and circular motion `c = ((d + 600000) mod 1200000)-600000`.
Thus the exact half-period tie is `-600000`. Expand both soft pitch mappings and
define `pitch_l1_cost_q = RHE(10000*L1/(2*2147483647))`. Other component costs:

```text
absolute_cost_q = min(10000,RHE(10000*abs(d)/absolute_motion_cap_mc))
circular_cost_q = RHE(10000*abs(c)/600000)
role_mismatch_cost_q = 0 if Project track roles match, else 10000
pair_cost_q = RHE(sum(component_cost_q * bound_weight) / sum(bound_weight))
```

The four weights are Q0.10000 and at least one MUST be positive. Sum pair costs
and choose the minimum. Exact ties choose lexicographically smallest
`canonical_matching_key`:

```text
[from_count,to_count,pair_count,
 from_ordinal_0,to_ordinal_0,...,
 unmatched_from_count,unmatched_from_ordinals...,
 unmatched_to_count,unmatched_to_ordinals...]
```

Pairs and unmatched ordinals are ascending. `total_cost_q` is RHE(mean pair
cost). Pair common-tone Q is `10000-pitch_l1_cost_q`. Pair step-up/down likeness
is `max(0,10000-RHE(10000*abs(c-center)/radius))` using the policy-bound centers
and radius. Record common-tone Q is the pair mean. Contrary-motion Q is 10000
iff nonzero absolute motions contain both signs, otherwise 0. All arithmetic is
checked u64/i64. Matching traversal is candidate key order after cost.

`transition_id` is `trn_` plus the first 32 lowercase hex digits of SHA-256 over
`UTF8("cps.pil-transition-id/v1\0") || canonical_json({from_segment_id,
to_segment_id,policy_hash})`. VoiceMatchingRecord uses the generic self hash.

### 6.2 TransitionFeatureRecord

For every adjacent segment pair emit one transition record. It binds the
VoiceMatchingRecord hash. If either bass is null, all bass fields are null.
Otherwise bass absolute/circular motion uses the same formulas above. A kernel
likeness is `max(0,10000-RHE(10000*wrapped_distance/radius))`; fifth and fourth
use their bound centers, while `bass_step_likeness_q` is the maximum of the
bound up/down kernels. Step-up/down resolution values are the corresponding
means across matched pairs. Common-tone and contrary-motion copy the matching
record values.

Destination metrical strength is 10000 at a bar boundary, 7500 at another beat
boundary, 5000 at a half-beat boundary and 0 otherwise. Earlier cases win.
`ticks_per_beat` and `beats_per_bar` come only from the Project. The record uses
the generic artifact self hash.

Observed segment tension is
`RHE(sum(candidate_similarity_q * entry.functional_tension_q) /
sum(candidate_similarity_q))` across retained candidates; a zero denominator is
`PIL_TRAJECTORY_FAILED`. Directed tension change is destination minus source
and is therefore -10000..10000.

### 6.3 Trajectory templates and alignment

Template IDs and ordinals are unique; ordinals are contiguous `0..N-1` and
stored in that order. Each template has 2..16 steps and exactly `steps-1`
transitions. Each step's unique vocabulary IDs are stored in vocabulary ordinal
order and positive weights sum exactly Q31. Unknown IDs reject the template set.
Template transition values are closed integers: signed bass center/radius,
common-tone target, contrary-motion target, resolution kind/target and metrical
target, plus signed directed-tension-change target.

Alignment is only every consecutive segment window of exactly template length;
no skips, padding, time warping or hard-label string matching occurs. At each
step, absent vocabulary candidates have similarity zero and
`step_chord_q = RHE(sum(candidate_similarity_q * target_weight_q31) /
2147483647)`. Chord component is the mean step score.

For each transition, bass score uses the template triangular circular-motion
kernel; a missing observed bass omits that transition's bass component.
Common-tone, contrary, resolution and metrical scores are each
`10000-abs(observed_q-target_q)`. Resolution selects the observed up/down value
named by the template. Tension score is
`10000-RHE(abs(observed_change-target_change)/2)`. Each component is the mean of its available step or
transition values. If all bass observations are missing, bass component is null.

The set binds seven Q0.10000 weights: chord, bass, common-tone, contrary-motion,
resolution, tension and metrical. Chord weight MUST be positive and total weight MUST be
positive. Final similarity is the RHE weighted mean over available components;
null bass removes its weight rather than contributing zero.

Every template/window result is retained, sorted by
`(-similarity_q,template_ordinal,start_segment_ordinal)`, then truncated to
`maximum_results`. `canonical_alignment_key` is
`[template_ordinal,start_segment_ordinal]`. `match_id` is `tjm_` plus the first
32 lowercase hex digits of SHA-256 over
`UTF8("cps.pil-trajectory-match-id/v1\0") || canonical_json({segment_ids,
template_id,template_set_hash})`. The result embeds component scores, segment IDs and
transition record hashes, so no hard chord-label sequence is authoritative.

### 6.4 Phase, cache and failures

Successful Phase 4 reports use `completed_phase: functional_trajectory` and
embed ordered `voice_matching_records`, `transition_feature_records` and full
trajectory results. The cache key includes this phase. After successful Phase 3
validation, invalid matching policy/result is `PIL_VOICE_MATCHING_FAILED`;
invalid template/alignment/result is `PIL_TRAJECTORY_FAILED`. Voice matching
precedes trajectory validation. Neither failure changes Native JI evidence.

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
