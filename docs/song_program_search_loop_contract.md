# GEN0-D / LLM1-4 Search, QD, and Planner Contract

**Status:** normative orchestration contract

## 1. Separation of authority

`SongProgram` is genotype; CompilerManifest defines interpretation;
SamplerManifest proposes initial genotypes; Mutation proposes bounded changes;
EvaluationManifest defines measurements; QDManifest defines archive placement;
PlannerManifest defines model interaction; RunManifest binds their hashes and
budgets. None may silently supply defaults owned by another artifact.

An LLM is never compiler, renderer, evaluator, or acceptance authority. It may
only return a schema-valid ordered list of Mutation objects. Invalid output is
recorded and replaced by the deterministic fallback proposer.

## 2. broad_prior_v1 sampler

SamplerManifest contains every categorical weight, integer distribution, named
choice algorithm, path-addressed seed derivation, catalog/compiler/schema
digests, and rejection ceiling. Weights are non-negative u64, at least two
permitted choices have positive weight in every non-forced table, and selection
uses `r = uint64_be(SHA256(stream_key || counter)) mod sum(weights)`, choosing
the first cumulative interval containing r. Modulo bias is accepted and frozen
for v1; changing it changes manifest identity.

Generation order is form, timing-neutral materials, realizations/transforms,
track/instrument assignment, then static production. Role labels are derived
after structural generation. Hard generated invariants:

- 3..8 sections and 16..64 total bars;
- 2..5 seed materials and at least three sounding roles;
- every section has a realization;
- one material lineage appears in at least two sections with a non-identity
  temporal transform;
- lattice/domain/ChordIntent choices come from manifest tables, not genre text;
- no fixed harmony/rhythm fingerprint mode exceeds 35% in the 1,000-seed
  preregistered cohort.

Rejected programs remain cohort records with decision trace and exact error.
After `maximum_rejections_per_seed`, sampling fails; it never switches preset.

## 3. Symbolic descriptors

DescriptorSpec v1 consumes canonical Project 1.2 and is invariant to IDs,
velocity, instrument, mix, event array order, and exact duplicate events.

### Rhythmic syncopation

Quantize onset/end to the nearest 120-tick sixteenth using half-even; distance
over 30 ticks is `DESCRIPTOR_UNQUANTIZABLE`. In each beat, metrical strengths
for sixteenth positions are `[3,0,1,0]`; the first beat of a bar adds 2 and each
other beat adds 1. A pitched foreground or drum event contributes
`max(0, strength(next grid boundary before its end)-strength(onset))` when it
sounds across that stronger boundary. Sum contributions and divide half-even
by the maximum possible contribution for the same number of eligible events,
mapping to `0..10000`; no eligible event yields null.

### Material recurrence distance

For every pair of instances with the same material lineage in different
sections, discard events shorter than 60 ticks, translate onset so the instance
starts at zero, quantize onset/duration to 120 ticks, equave-reduce pitch, and
form a multiset of `(kind,onset_slot,duration_slots,ratio_n,ratio_d,
source_step_ordinal)`. Distance is `10000 * (1-weighted_Jaccard)` half-even.
The descriptor is the median pair distance, with an even count averaged
half-even. Fewer than two eligible instances yields null.

Initial bins for both axes are `[0,2000)`, `[2000,4000)`, `[4000,6000)`,
`[6000,8000)`, `[8000,10001)`. Null candidates are reported but not archived.

## 4. Fingerprint and duplicate policy

The canonical musical fingerprint excludes IDs, velocity, catalog/production,
and absolute transposition. It contains section bar lengths; per-role onset and
duration slots; root-anchor differences; ChordIntent canonical steps; material
lineage/reuse/transform edges; and exact sounding interval multiset. Normalize
the first tonal center to zero. Hash identical fingerprints are exact musical
duplicates.

Fingerprint component payloads are fixed as follows. `section_bars` is the
form-order bar-count array. `role_time_grid` is the sorted multiset of
`[track_role,onset_slot,duration_slots]` for events quantized by FingerprintSpec.
`root_anchor_deltas` lists each harmony occurrence anchor minus the first
occurrence anchor, beginning with the all-zero vector; no occurrence yields an
empty array. `chord_steps` is the occurrence-order array of each referenced
ResolvedChord `canonical_steps`. `lineage_edges` is the sorted multiset of
`[from_lineage_hash,to_lineage_hash,operation]` resolved through LineageIndex.
`sounding_intervals` contains one equave-reduced larger/smaller exact ratio for
every unordered pair of pitched events whose half-open sounding intervals
overlap, sorted as reduced ratio strings. Each event pair contributes once,
independent of overlap duration. Exact duplicate Project events are removed
before all event-derived components. These rules make velocity, IDs, event
array order, instrumentation, and global lattice transposition irrelevant.

Near-duplicate distance is weighted Hamming/Jaccard over the explicitly named
components in FingerprintSpec. Weights, quantization, and threshold are digest-
covered. The baseline FingerprintSpec is checked in with the Search Artifacts
fixtures. Its threshold drives reproducible audit/cohort counts; near-duplicate
rejection still requires a CalibrationDecision promotion. Exact duplicates are
always rejected from archive insertion after being counted in cohort statistics.

## 5. QD archive

The initial archive is a 5x5 map keyed by the two descriptor bins. Only compile-
successful, automatically viable, native Project candidates enter. Each cell
stores one champion and up to four lineage-diverse runners-up.

Champion comparison is lexicographic descending on:

```text
(
  transformed_recall_count,
  distinct_sounding_material_lineage_count,
  sounding_role_count,
  section_coverage_q,
  negative_program_structural_item_count
)
```

Negative fields mean smaller is better; complete equality selects the bytewise
smaller program hash deterministically. Genre score, audio embedding, LLM
opinion, and lattice-coordinate inflation do not choose GEN0 champions.
Archive update is an atomic compare-and-swap on `(manifest_hash,cell,revision)`.

The 1,000-seed GEN0 gate is fixed: >=95% compile success, >=70% automatic
viability initially and >=80% before planner use, <1% exact duplicate, <10%
near duplicate once calibrated, no fingerprint mode >35%, and at least 80%
with transformed recall. Failed and duplicate candidates remain denominators.

## 6. Evaluation and Pareto policy

EvaluationReport separates:

- hard validity/viability;
- symbolic descriptors and audit metrics;
- deterministic render technical metrics;
- calibrated perceptual/genre metrics with dataset/decision hashes;
- uncertainty and missing reasons.

Uncalibrated or missing metrics cannot be treated as zero. After calibration,
challenger acceptance uses Pareto dominance over the GenreIntent-declared
metric set: no metric worse beyond its integer non-inferiority margin and at
least one strictly better beyond improvement margin. Ties use lower render
cost, then smaller program hash. Weighted scalar reward may guide proposals but
cannot replace the acceptance rule.

## 7. Planner protocol and mutations

Planner input is a compact immutable object containing GenreIntent, champion
program hash, locks, allowed mutation schema/version, latest metric values and
deltas, failed constraints, remaining budgets, and lineage summary. Audio is
referenced by artifact hash, never inlined. Planner output is
`{rationale_tags, mutations}`; free prose is diagnostic only.

Every Mutation carries base program hash, operation, target semantic ID,
declared dependency scope, bounded parameters, and mutation schema version.
Allowed v1 operations are replace bounded scalar, replace distribution choice,
transpose material vector, rotate rhythm, replace ChordIntent reference,
replace root-anchor item, duplicate/delete a section within limits, and swap a
track catalog entry. Arbitrary JSON Patch, code, recursion, production graph,
compiler/resolver/profile change, and edits intersecting a lock reject.

Apply mutations sequentially to a private copy, validating declared versus
actual dependency closure after each. Any failure rejects the entire proposal;
partial candidates are not compiled. Deterministic fallback enumerates the same
allowed mutations by `(operation,target_id,canonical_parameters)` using a named
path-addressed stream.

## 8. Run state, termination, and recovery

RunManifest fixes population size, maximum rounds, candidates/round, compilation
and render budgets, planner-call budget, wall-clock operational deadline,
acceptance policy, artifact store, and every referenced manifest hash.
Semantic outcomes never depend on wall time: deadline interruption checkpoints
and resumes the same next logical action.

The loop terminates on first of maximum rounds, logical budget exhaustion,
planner-call budget, explicit cancellation, or `patience_rounds` without an
accepted/archived improvement. Cancellation atomically retains the last
playable champion. A failed model call records raw response hash/error and runs
fallback; a failed compile/render/evaluation records the candidate and advances.
Three failures do not alter policy or broaden mutation scope.

Persistence is append-only: Run, Candidate, lineage edge, artifact reference,
metric report, planner request/response, acceptance decision, and checkpoint.
Resume validates all hashes and continues from the smallest unfinished logical
action ID. Replaying stored planner responses reproduces lineage exactly;
calling a remote model again is a new run identity.

All machine forms, canonical bytes, stream/action/record hashes, CAS layout,
atomicity, checkpoint fields, baseline manifests, and replay rules are frozen
in [song_program_search_artifacts_contract.md](song_program_search_artifacts_contract.md).
Where this overview is less specific, that artifact contract is authoritative.

## 9. GenreIntent and references

GenreIntent names requested descriptors, calibrated metric IDs, non-inferiority
and improvement margins, optional licensed/internal reference-set digest, and
plain-language tags. A label such as `kawaii future bass` never selects a hidden
song template. Reference audio licensing/provenance and split membership are
mandatory; test references cannot appear in calibration/training partitions.

## 10. Phase gates

- LLM1: fallback-only loop improves at least one frozen benchmark metric without
  reducing archive coverage;
- LLM2: schema-valid planner with 100% lock/scope enforcement and deterministic
  fallback after malformed/timeout responses;
- LLM3: embedding/listening metrics only after CalibrationDecision promotion;
- LLM4: UI cancellation/resume and weak-section regeneration preserve locks,
  join validation, lineage, and champion playability.

No phase may weaken exact lattice provenance, native Project validation,
duplicate accounting, or manifest identity to improve apparent success.
