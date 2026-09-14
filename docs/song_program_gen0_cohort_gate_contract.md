# GEN0 1,000-Seed Cohort Gate Contract

**Status:** normative for the first GEN0 broad-prior cohort  
**Contract:** `cps-gen0-cohort-gate/v1`

## 1. Purpose and authority boundary

This contract closes the offline acceptance measurement required by
`song_program_search_loop_contract.md` and ADR-SP-005/006. It does not change
sampling, compilation, evaluation, archive admission, or PIL authority. A
cohort report observes already-produced artifacts and cannot repair, retry,
discard, or reorder a candidate.

The gate is independent of PIL genre calibration. Missing external PIL
authority therefore never prevents this symbolic GEN0 cohort from being
measured, and a GEN0 report cannot promote any `pil.*` metric.

## 2. Bound manifest and cohort coordinates

`Gen0CohortGateManifest 1.0.0` binds the exact SamplerManifest,
StructuralLoweringManifest, production-lowering manifest, CompilerManifest,
EvaluationManifest, FingerprintSpec, QDManifest, their schema hashes, and the
near-duplicate policy. The first cohort has exactly 1,000 coordinates:

```text
root_seed = manifest.root_seed
cohort_index = 0, 1, ..., 999
candidate_ordinal = cohort_index
```

No failed coordinate is replaced. Changing any bound artifact, root seed,
threshold, mode algorithm, or near-duplicate authority creates a different
manifest and cohort.

The manifest thresholds are frozen as integer basis points (`0..10000`):

- compile success: `>= 9500`;
- initial automatic viability: `>= 7000`;
- planner eligibility viability: `>= 8000`;
- exact duplicate rate: `< 100`;
- near-duplicate rate: `< 1000`, only when promoted;
- transformed recall: `>= 8000`;
- maximum mode prevalence: `<= 3500`.

All rates use `RHE(10000 * numerator / 1000)`, where `RHE` is round-half-even.
The denominator is always 1,000, including sampler, production, compiler,
evaluation, and fingerprint failures.

## 3. Candidate ledger

There is exactly one `Gen0CohortCandidateRecord 1.0.0` for each ordinal. Records
are ordered by ascending ordinal and bind the stage artifacts that actually
exist. Nullable hashes are mandatory fields, not omitted fields.

`terminal_stage` is the first non-success stage in this precedence:

1. `sampler`;
2. `production`;
3. `compiler`;
4. `evaluation`;
5. `fingerprint`;
6. `duplicate`;
7. `complete`.

After the terminal stage, all later artifact hashes and derived facts are null.
`compile_success` is true exactly when compilation produced a valid Project and
CompileReport, even if a later stage fails. `automatic_viable` is true exactly
when every required hard check in the bound EvaluationManifest is present and
passes. A failed or unavailable evaluation makes it false, never null.

`has_transformed_recall` is read from the bound evaluation metric named
`transformed_recall_count` and is true iff its integer value is at least one.
It is false when its authoritative source is unavailable. Descriptor/QD nulls
do not change viability and result in a null `qd_cell`.

Duplicate classification comes from the candidate's bound
`NearDuplicateDecision`. The three classes are disjoint. A missing or invalid
decision terminates at `duplicate`; it is not interpreted as `distinct`.

## 4. Mode keys and the 35% rule

Mode extraction uses canonical fingerprint component payloads before hashing;
IDs, velocity, instruments, production, and absolute transposition remain
excluded exactly as in FingerprintSpec v1.

Each complete candidate contributes a set (not a multiset) of keys in each
family. Failed candidates contribute an empty set but remain in the denominator.

- `root_anchor_ngram`: adjacent order-2 windows in `root_anchor_deltas`.
- `chord_intent_ngram`: adjacent order-2 windows in `chord_steps`.
- `harmony_rhythm_fingerprint`: one tuple containing the complete
  `role_time_grid`, `root_anchor_deltas`, `chord_steps`, and
  `sounding_intervals` component payloads.

A sequence of length zero contributes the canonical sentinel `[]`; a sequence
of length one contributes its single item as a one-item window. This prevents
short songs from disappearing from prevalence measurement.

Each public key is:

```text
SHA256("cps.gen0-cohort-mode-key/v1" || 0x00 ||
       canonical([family, payload]) || LF)
```

For a key, prevalence numerator is the number of candidate ordinals whose set
contains it, at most once per candidate. The family maximum selects descending
count, then bytewise-smallest key. The gate maximum selects the greatest family
count, ties by family order `root_anchor_ngram`, `chord_intent_ngram`,
`harmony_rhythm_fingerprint`, then key bytes. `<= 3500` passes.

## 5. Aggregate counts and gates

The report records these mutually checkable counts:

- terminal-stage histogram, whose values sum to 1,000;
- compile successes;
- automatically viable candidates;
- exact duplicates;
- near duplicates excluding exact duplicates;
- distinct candidates;
- candidates with transformed recall;
- QD occupied-cell histogram for viable, distinct candidates with non-null
  cells;
- per-family maximum mode key, count, and basis-point prevalence.

Initial GEN0 passes when compile, initial viability, exact duplicate,
transformed recall, and mode gates pass. The near-duplicate gate has status
`not_enforced` when the manifest policy is `audit_only`; its measured rate is
still reported. It has status `passed` or `failed` only when the manifest binds
a promoted CalibrationDecision authorizing that FingerprintSpec threshold.

`planner_eligible` additionally requires the 8000 viability gate and an
enforced, passing near-duplicate gate. PIL/genre calibration is a separate later
planner condition and is not asserted by this boolean.

Comparators are exact: `ge`, `lt`, or `le`; no epsilon or floating-point value
is permitted. Counters use checked unsigned 64-bit arithmetic. Histogram keys
are UTF-8 byte ordered; mode rows are family order then key bytes; QD cells are
lexicographically ordered integer arrays.

## 6. Canonical identities

Canonical JSON is the repository canonical encoder plus one LF.

```text
manifest_hash = SHA256("cps.gen0-cohort-gate-manifest/v1" || 0x00 ||
                       canonical(manifest without manifest_hash) || LF)
record_hash   = SHA256("cps.gen0-cohort-candidate-record/v1" || 0x00 ||
                       canonical(record without record_hash) || LF)
ledger_hash   = SHA256("cps.gen0-cohort-ledger/v1" || 0x00 ||
                       canonical(ordered record_hash array) || LF)
report_hash   = SHA256("cps.gen0-cohort-gate-report/v1" || 0x00 ||
                       canonical(report without report_hash) || LF)
```

The report contains `ledger_hash`, not embedded mutable candidate records.
Independent validation receives the ordered records and recomputes all counts,
rates, maxima, gate states, and identities. It also receives a content-addressed
resolver; every non-null artifact hash in a record must resolve to canonical
bytes of the type fixed by the corresponding manifest schema binding. Ambient
filesystem lookup and a missing-object fallback are forbidden.

## 7. Validation failure precedence

Validation stops at the first applicable code:

1. `COHORT_REPORT_SCHEMA_INVALID`;
2. `COHORT_MANIFEST_INVALID`;
3. `COHORT_MANIFEST_HASH_MISMATCH`;
4. `COHORT_RECORD_COUNT_MISMATCH`;
5. `COHORT_RECORD_ORDER_INVALID`;
6. `COHORT_RECORD_HASH_MISMATCH`;
7. `COHORT_COORDINATE_MISMATCH`;
8. `COHORT_ARTIFACT_BINDING_MISMATCH`;
9. `COHORT_STAGE_PRECEDENCE_INVALID`;
10. `COHORT_DUPLICATE_CLASSIFICATION_INVALID`;
11. `COHORT_MODE_KEY_INVALID`;
12. `COHORT_COUNTER_OVERFLOW`;
13. `COHORT_LEDGER_HASH_MISMATCH`;
14. `COHORT_AGGREGATE_MISMATCH`;
15. `COHORT_GATE_RESULT_MISMATCH`;
16. `COHORT_REPORT_HASH_MISMATCH`.

Within records, ascending candidate ordinal is authoritative. Within one
record, fields are checked in schema property order. Histograms precede rates,
rates precede modes, and modes precede gate results.

A validation failure returns the stable code out of band and produces no
`Gen0CohortGateReport`. A report is therefore always `status: success` with
`failure_code: null`; partially trusted aggregate fields are never published as
a failure report.

## 8. Conformance and authority

Implementation acceptance requires positive, negative, boundary, cache-free
replay, cross-process, and 1/2/4/8-worker fixtures from an independent oracle.
Production code may implement the schemas and validator before promotion but
must not create or update authoritative expected hashes. The actual 1,000-seed
result is evidence, not a golden, and must be stored under its manifest and
ledger hashes.

The oracle owner publishes `Gen0CohortGateFixtureSuiteIndex 1.0.0`. Every case
binds immutable input bytes and either immutable expected report bytes or one
expected validation failure. Paths are relative POSIX paths, contain neither
an empty segment nor `.`/`..`, and resolve beneath the suite directory after
symlink-free component traversal. `raw_sha256` hashes file bytes without domain
separation. Case IDs and coverage labels are unique and UTF-8 byte ordered.

The suite must cover every label below exactly once unless a single case lists
multiple labels:

```text
golden.success
policy.near_audit_only
policy.near_enforced
boundary.compile.9499_fail
boundary.compile.9500_pass
boundary.initial_viability.6999_fail
boundary.initial_viability.7000_pass
boundary.planner_viability.7999_fail
boundary.planner_viability.8000_pass
boundary.exact_duplicate.99_pass
boundary.exact_duplicate.100_fail
boundary.near_duplicate.999_pass
boundary.near_duplicate.1000_fail
boundary.transformed_recall.7999_fail
boundary.transformed_recall.8000_pass
boundary.mode.3500_pass
boundary.mode.3501_fail
failure.report_schema
failure.manifest_schema
failure.manifest_hash
failure.record_count
failure.record_order
failure.record_hash
failure.coordinate
failure.artifact_binding
failure.stage_precedence
failure.duplicate_classification
failure.mode_key
failure.counter_overflow
failure.ledger_hash
failure.aggregate
failure.gate_result
failure.report_hash
process.pythonhashseed_0_1_7_42
parallel.workers_1_2_4_8
```

The suite hash is
`SHA256("cps.gen0-cohort-gate-fixture-suite-index/v1" || 0x00 ||
canonical(index without suite_hash) || LF)`. Expected report files and failure
codes are oracle-owner authority. Builders used by production tests are
read-only consumers and must fail if a golden differs.
