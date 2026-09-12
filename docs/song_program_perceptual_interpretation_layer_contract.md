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
threshold and weight is an integer in the manifest. Event salience is a checked
integer function of overlap duration, metrical weight, velocity, track gain,
persistence and bass salience. Zero-weight events are omitted.

The segmentation algorithm and all half-open interval rules are manifest-bound.
Each `HarmonicSegment` records start/end tick, ordered source event IDs,
weighted pitch distribution, bass event ID or null, and confidence Q0.10000.
Passing-tone robustness is evaluated as a separate regression metric; an
implementation may not silently delete a passing tone from provenance.

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
Numeric Contract hash and implementation build ID. Cold, hit, corrupt,
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
