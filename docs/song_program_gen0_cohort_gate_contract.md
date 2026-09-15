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
Because the denominator is fixed at 1,000, every valid rate is a multiple of
10 basis points; boundary fixtures use the nearest reachable value on each
side of a threshold.
The denominator is always 1,000, including sampler, production, compiler,
evaluation, and fingerprint failures.

## 3. Candidate ledger

There is exactly one `Gen0CohortCandidateRecord 1.0.0` for each ordinal. Records
are ordered by ascending ordinal and bind the stage artifacts that actually
exist. Nullable hashes are mandatory fields, not omitted fields.

Every record binds its StructuralSamplerRequest and, after sampler success,
its BroadPriorProductionRequest. The sampler request `root_seed` and
`cohort_index` must equal the record and cohort-manifest coordinate. Its
`request_hash` must equal both `artifact_hashes.sampler_request` and the
sampler result's `request_hash`. The production request has the identical
coordinate, its `request_hash` must equal both
`artifact_hashes.production_request` and the production result's
`request_hash`, and its manifest hashes must equal the cohort bindings. A
missing request before an existing result, a request/result cross-link
mismatch, or any coordinate mismatch is `COHORT_COORDINATE_MISMATCH`.

On sampler success, recompute the production request's embedded
`structural_program` hash as
`SHA256("cps.structural-song-program/1.0" || 0x00 || canonical(program) || LF)`.
It must equal both the production request `structural_program_hash` and the
sampler result `structural_program_hash`. On production success, recompute
`output.program_hash` from `output.program` using the bound SongProgram schema's
normative hash algorithm; the exact program object and hash must equal the CAS
program artifact and `CandidateRecord.artifact_hashes.program`. Any payload or
hash disagreement is `COHORT_ARTIFACT_BINDING_MISMATCH`.

For every later stage, the validator applies these exact cross-links (all
hashes refer to the already-verified CAS artifacts):

- CompileReport `source_program_hash` equals the record program hash,
  `compiler_manifest_hash` equals the cohort binding, `compiler_build_id`
  equals the bound CompilerManifest `build_id`, and on success `project_hash`
  equals the record Project hash.
- Project `source_program.hash` equals the record program hash and Project
  `compiler.build_id` equals the bound CompilerManifest `build_id`.
- EvaluationReport `evaluation_manifest_hash`, `program_hash`, and
  `project_hash` equal the cohort binding and record artifacts respectively.
- FingerprintRecord `fingerprint_spec_hash` and `project_hash` equal the cohort
  binding and record Project. Its six component entries have exactly the bound
  FingerprintSpec component IDs in spec order, and each component `hash`
  resolves to the same-ID fingerprint-component CAS payload.
- NearDuplicateDecision `candidate_ordinal`, `candidate_program_hash`,
  `candidate_fingerprint_hash`, and `fingerprint_spec_hash` equal the record
  ordinal, record program, FingerprintRecord `fingerprint_hash`, and cohort
  binding. Its `threshold_q` equals FingerprintSpec
  `near_duplicate_threshold_q`; its recomputed classification under the bound
  fingerprint algorithm equals both the decision and record
  `duplicate_classification`.

Any violation of these stage links is
`COHORT_ARTIFACT_BINDING_MISMATCH` (coordinate/request violations retain the
earlier `COHORT_COORDINATE_MISMATCH` precedence).

For cohort NearDuplicateDecision only, canonical action order is exactly
ascending `candidate_ordinal`; no external run/archive state participates. The
comparison universe contains all and only lower-ordinal cohort records that
are compile-valid, have a committed and fully validated FingerprintRecord, and
were themselves classified `distinct`. `comparison_program_hashes` is the
unique universe program hashes sorted by raw 32-byte SHA-256 digest. Its closed
comparison-set payload and hash are exactly those in
`song_program_search_decision_contract.md` (including the valid empty set).
The validator recomputes every component distance and weighted aggregate from
the bound FingerprintSpec and the candidate/comparison fingerprint-component
payloads. Exact program hash wins first. Otherwise nearest order is
`(aggregate_distance_q, component_distances_q tuple, program-hash raw digest)`;
distance equal to the threshold is `near_duplicate`. The representative is
the candidate program for `distinct`, the identical prior program for
`exact_duplicate`, and the nearest prior program for `near_duplicate`.
`nearest` is null only for an empty comparison set and otherwise contains the
recomputed prior hashes and distances. The decision's comparison list, set
hash, nearest, representative, and classification must all equal these
recomputed values.

The records file is `cps.gen0-cohort-candidate-ledger` 1.0.0: it binds the
cohort manifest, contains exactly 1,000 records in ordinal order, and carries
the `ledger_hash` defined in section 6. Its raw schema hash is bound by the
cohort manifest and the fixture suite schema registry.

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

Artifact presence is closed by this matrix; `R` means non-null and successfully
validated, `F` means non-null with `status=failure`, and `-` means null. Columns
are in pipeline order.

| `terminal_stage` | sampler req | sampler result | production req | production result | program | compile report | project | evaluation report | fingerprint | duplicate decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `sampler` | R | F | - | - | - | - | - | - | - | - |
| `production` | R | R | R | F | - | - | - | - | - | - |
| `compiler` | R | R | R | R | R | F | - | - | - | - |
| `evaluation` | R | R | R | R | R | R | R | F | - | - |
| `fingerprint` | R | R | R | R | R | R | R | R | - | - |
| `duplicate` | R | R | R | R | R | R | R | R | R | - |
| `complete` | R | R | R | R | R | R | R | R | R | R |

For every `R` result/report that has a status field, status is `success`.
`terminal_code` is exactly sampler-result `error`, production-result `error`,
CompileReport `error.code`, or EvaluationReport `failure_code` for the first
four failure rows. The fingerprint row uses the sole fixed code
`FINGERPRINT_COMPUTATION_FAILED`; the duplicate row uses the sole fixed code
`NEAR_DUPLICATE_DECISION_FAILED`; the complete row requires null. No other
code is accepted. Any presence, status, or terminal-code disagreement is
`COHORT_STAGE_PRECEDENCE_INVALID`, checked after coordinate/request linkage and
before derived counts.

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
cas_index_hash = SHA256("cps.gen0-cohort-gate-cas-index/v1" || 0x00 ||
                        canonical(CAS index without index_hash) || LF)
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
12. `COHORT_LEDGER_HASH_MISMATCH`;
13. `COHORT_AGGREGATE_MISMATCH`;
14. `COHORT_GATE_RESULT_MISMATCH`;
15. `COHORT_REPORT_HASH_MISMATCH`.

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
separation. A suite-level `Gen0CohortGateCasIndex` maps every record artifact
hash to immutable canonical bytes; no case may use an ambient resolver. Case
IDs and coverage labels are unique and UTF-8 byte ordered. Every failure case
also binds the untrusted input report bytes being validated; failures before
report inspection use the otherwise-valid golden report as that input.

Every candidate-record `artifact_hashes` value, cohort-manifest binding, and
CAS `artifact_hash` is the artifact's normative lookup identity: its specified
domain-separated self hash, the SongProgram hash, or the ArrangementProject
artifact hash as appropriate. `raw_sha256` is separately the plain SHA-256 of
the exact stored canonical bytes. The two values need not be equal. The CAS
entry also binds the raw schema-file SHA-256. Resolution verifies path
confinement, raw bytes, schema, recomputed normative lookup identity, and only
then semantic cross-links.
CAS entries are unique and ordered by `(artifact_hash bytes, artifact_kind,
path UTF-8 bytes)`.

The same CAS must resolve every manifest payload named by the cohort manifest:
SamplerManifest, StructuralLoweringManifest, production-lowering manifest,
CompilerManifest, EvaluationManifest, DescriptorSpec, FingerprintSpec, and
QDManifest. When
near-duplicate policy is `enforced`, it must also resolve the bound
NearDuplicateCalibrationDecision. The validator uses only those resolved payloads to obtain
required hard-check IDs, the `transformed_recall_count` metric source,
fingerprint component rules, QD bins, and near-duplicate authority.

`candidate_artifact_schema_hashes` binds the raw checked-in schema-file hash
for each of the ten candidate stage artifact kinds plus the fingerprint
component sidecar. Every CAS entry's `schema_hash` must equal the value selected
by its `artifact_kind`; a CAS entry cannot self-declare an alternate schema.

Every successful FingerprintRecord component hash resolves through the same
CAS to a `cps.gen0-cohort-fingerprint-component` payload. Its
`component_hash` recomputes as
`SHA256("cps.fingerprint-component/v1" || 0x00 ||
canonical({"id":id,"payload":payload}) || LF)` and must equal both the
FingerprintRecord entry and CAS lookup identity. Mode keys are computed only
from these validated payloads.

An `enforced` near-duplicate policy binds
`cps.near-duplicate-calibration-decision` 1.0.0 with status `promoted`, the
identical FingerprintSpec hash, and a `threshold_q` identical to the
FingerprintSpec's `near_duplicate_threshold_q`. The decision self hash is
`SHA256("cps.near-duplicate-calibration-decision/v1" || 0x00 ||
canonical(decision without decision_hash) || LF)`. Generic SearchLoop or PIL
CalibrationDecision artifacts cannot authorize this gate.

`schemas.cas_index` binds the CAS index schema file; the top-level `cas_index`
binds the suite's CAS index payload. These are intentionally distinct and must
not resolve to the same bytes.

`schema_registry` is the portable schema-byte authority. It contains every
schema directly named by the cohort manifest or CAS entries and the complete
transitive closure of their non-HTTP `$ref` targets. Entries are unique and
ordered by `(raw_sha256 bytes, schema_id UTF-8, path UTF-8)`. Each entry binds
the schema `$id`, suite-relative file path, and plain raw-file SHA-256;
`artifact_kinds` names the CAS kinds for which that exact schema is valid and
is empty only for reference-only dependency schemas. Every CAS `schema_hash`
must resolve to exactly one registry `raw_sha256`, and its artifact kind must
occur in that entry. Missing, duplicate, cyclic-unresolvable, escaping, or
hash-mismatched `$ref` closure is `COHORT_ARTIFACT_BINDING_MISMATCH`.

Registry `identity_rules` are fixed by artifact kind:

| Kind | Required schema file | Rule |
| --- | --- | --- |
| `sampler_manifest` | `sampler_manifest_1_1.schema.json` | `sampler-manifest-v1.1`: `cps.sampler-manifest/v1.1`, omit `manifest_hash`, canonical+LF |
| `structural_lowering_manifest` | `structural_lowering_manifest.schema.json` | `structural-lowering-manifest-v1`: `cps.structural-lowering-manifest/v1`, omit `manifest_hash`, canonical+LF |
| `production_lowering_manifest` | `broad_prior_production_manifest.schema.json` | `production-lowering-manifest-v1`: `cps.production-lowering-manifest/v1`, whole artifact, canonical+LF |
| `compiler_manifest` | `compiler_manifest_1_1.schema.json` | `compiler-manifest-v1.1`: `cps.compiler-manifest/v1.1`, whole artifact, canonical+LF |
| `evaluation_manifest` | `evaluation_manifest_1_1.schema.json` | `evaluation-manifest-v1.1`: generic rule below, omit `manifest_hash` |
| `descriptor_spec` | `descriptor_spec.schema.json` | `descriptor-spec-v1`: `cps.descriptor-spec/v1`, whole artifact, canonical+LF |
| `fingerprint_spec` | `fingerprint_spec.schema.json` | `fingerprint-spec-v1`: `cps.fingerprint-spec/v1`, whole artifact, canonical+LF |
| `qd_manifest` | `qd_manifest.schema.json` | `qd-manifest-v1`: `cps.qd-manifest/v1`, whole artifact, canonical+LF |
| `near_duplicate_calibration_decision` | `near_duplicate_calibration_decision.schema.json` | `near-duplicate-calibration-decision-v1`, omit `decision_hash` |
| `sampler_request` | `structural_sampler_request_1_1.schema.json` | `generic-cps-artifact-v1`, omit `request_hash` |
| `sampler_result` | `structural_sampler_result_1_1.schema.json` | `structural-sampler-result-v1.1`: `cps.structural-sampler-result/v1.1`, omit `result_hash`, canonical+LF |
| `production_request` | `broad_prior_production_request_1_1.schema.json` | `generic-cps-artifact-v1`, omit `request_hash` |
| `production_result` | `broad_prior_production_result_1_1.schema.json` | `broad-prior-production-result-v1.1`: `cps.broad-prior-production-result/v1.1`, omit `result_hash`, canonical+LF |
| `program` | `song_program_0_1.schema.json` | `song-program-v0.1`: existing SongProgram hash, omit `program_id`, no LF |
| `compile_report` | `compile_report_1_1.schema.json` | `generic-cps-artifact-v1`, whole artifact |
| `project` | `arrangement_project_1_2.schema.json` | `arrangement-project-v1.2`: compiler-build-bound Project hash, no LF |
| `evaluation_report` | `evaluation_report_1_1.schema.json` | `generic-cps-artifact-v1`, omit `report_hash` |
| `fingerprint_record` | `fingerprint_record.schema.json` | `generic-cps-artifact-v1`, whole artifact |
| `fingerprint_component` | `gen0_cohort_fingerprint_component.schema.json` | `fingerprint-component-v1`, defined above |
| `near_duplicate_decision` | `near_duplicate_decision.schema.json` | `generic-cps-artifact-v1`, omit `decision_hash` |

`generic-cps-artifact-v1` is
`SHA256(UTF8("cps-artifact-hash/v1\0" || schema || "\0" || schema_version ||
"\0") || canonical(artifact with the table's named self-field omitted, no
LF))`. Reference-only schema entries have empty `artifact_kinds` and
`identity_rules`. Otherwise the two arrays correspond by ordinal and must
match this table exactly.

The QDManifest `descriptor_spec_hash` must equal the cohort manifest binding.
Each DescriptorSpec axis `id` must occur exactly once in the bound
EvaluationManifest `metrics`. For a successful candidate, that manifest metric
must in turn have exactly one EvaluationReport metric with the same `id` and
`ordinal`; its `value` is the authoritative axis value. Descriptor axis order
comes only from DescriptorSpec (not EvaluationManifest ordinal or report array
order). Each non-null `qd_cell` is recomputed from those values using that axis
order and the corresponding half-open `bin_edges`; it is null if either value
is null or outside every bin. A duplicate/missing axis metric, an `id`/`ordinal`
mismatch, or an alternate bin definition is
`COHORT_ARTIFACT_BINDING_MISMATCH`.

The suite also binds one `cps.gen0-cohort-gate-matrix-receipt` 1.0.0. Its 16
coordinates are seed-major then worker-minor over
`PYTHONHASHSEED=[0,1,7,42]` and `workers=[1,2,4,8]`. Each fresh-process row binds
both the plain report-byte SHA-256 and the normative report hash; all equal the
serial `(0,1)` baseline. The receipt hash is
`SHA256("cps.gen0-cohort-gate-matrix-receipt/v1" || 0x00 ||
canonical(receipt without receipt_hash) || LF)`. Completion order, PID,
duration, cache state, and filesystem paths are excluded.

The suite must cover every label below exactly once unless a single case lists
multiple labels:

```text
golden.success
policy.near_audit_only
policy.near_enforced
boundary.compile.9490_fail
boundary.compile.9500_pass
boundary.initial_viability.6990_fail
boundary.initial_viability.7000_pass
boundary.planner_viability.7990_fail
boundary.planner_viability.8000_pass
boundary.exact_duplicate.90_pass
boundary.exact_duplicate.100_fail
boundary.near_duplicate.990_pass
boundary.near_duplicate.1000_fail
boundary.transformed_recall.7990_fail
boundary.transformed_recall.8000_pass
boundary.mode.3500_pass
boundary.mode.3510_fail
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
