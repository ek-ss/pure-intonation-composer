# SearchLoop13 payload envelopes

**Status:** normative for Groups A--D. Group C defines compile-only/cache and
cancellation-inbox payloads. They are SearchLoop13-only and never alter the
legacy connected executor or legacy cancellation schemas.

All envelopes are closed objects and self-hash by
`cps-artifact-hash/v1\0 || schema || \0 || schema_version || \0 || canonical_json`
with only their named self-hash omitted. Producer payload bytes are not copied:
their hash and producer schema hash are causal inputs. A mismatched context,
producer schema, or self hash is terminal `CONTEXT_BINDING_MISMATCH`.
The Group-A/B/C machine envelopes use `1.0.0`, except the explicitly versioned
SearchLoop13 cancellation inbox and decision envelopes, which use `1.1.0` to
remain distinct from the untouched legacy cancellation schemas.

`CandidateSourceDecision` binds run/context/policy hashes, coordinate, locked
roots, and exactly one source: initial `(root_seed, cohort_index)` or archive
`(round_start_archive_heads_hash, selected_archive_update_record_hash,
archive_admission_decision_hash, parent_program_hash, inline parent_program,
source_occurrence_ordinal)`. Cohort is
checked u64 `round*candidates_per_round+candidate`.

`StructuralSamplerRequest/Result` bind source decision and sampler manifest;
result is success `(structural_program_hash)` or a frozen sampler failure code.
`PlannerRequest/Response` bind source program, context and planner manifest;
response is success `(inline mutation_proposal, proposal_hash)` or a frozen
diagnostic code. Phase-1 later binds the response and proposal hashes.
Planner null creates neither envelope.

## Group A: source, structural sampling, and planning

The machine schemas are `candidate_source_decision.schema.json`,
`structural_sampler_request.schema.json`,
`structural_sampler_result.schema.json`, `planner_request.schema.json`, and
`planner_response.schema.json`. Their self-hash members are respectively
`decision_hash`, `request_hash`, `result_hash`, `request_hash`, and
`response_hash`. Array order below is semantic and implementations MUST reject
an array that is not in the prescribed order even if JSON Schema cannot express
that predicate.

Every Group-A envelope repeats `run_hash` and `context_hash`. The context MUST
be schema-valid and self-valid; `run_hash` MUST equal its bound run. For each
envelope, the RunManifest raw schema-hash field and the identically named
`RunContext.schema_hashes` member MUST both equal the raw SHA-256 of the schema
used to parse that envelope. A repeated manifest or policy hash MUST equal both
the RunManifest member and the corresponding context artifact binding. These
checks precede self-hash validation. The first mismatch is terminal
`CONTEXT_BINDING_MISMATCH`; no result envelope is produced from an invalid
request.

### CandidateSourceDecision

`round` and `candidate_ordinal` identify the phase-0 candidate coordinate.
`cohort_index` is the checked-u64 result
`round * run_manifest.candidates_per_round + candidate_ordinal`; the candidate
ordinal MUST be below `candidates_per_round`. `locked_roots` is unique and
sorted `(kind UTF-8,id UTF-8)`.

The policy cycle first selects `source_cycle[candidate_ordinal mod
source_cycle.length]`. `initial_sampler` records exactly the run root seed,
derived cohort, and sampler-manifest hash. `archive_parent` additionally
records the source-occurrence ordinal, round-start archive-heads hash, selected
archive-update-record hash, archive admission-decision hash, and both the
parent Program hash and complete inline parent Program. The inline Program MUST
canonicalize to `parent_program_hash`. The source-occurrence
ordinal is counted from zero among earlier archive selections in the same round.
If the round-start archive is empty, the selected archive branch is replaced by
the policy-declared initial branch; the decision records only the resulting
initial branch. Archive candidates sort `(cell integer lexicographic,
program_hash raw digest bytes)` and selection is occurrence ordinal modulo
candidate count. No unselected-branch field is permitted.

### StructuralSamplerRequest and Result

A sampler request is legal only for an `initial_sampler` source. Its root seed,
cohort, source-decision hash, and sampler-manifest hash are copied exactly from
that decision/context. `structural_program_schema_hash` identifies the sealed
producer payload schema; producer bytes live at `structural_program_hash` in
CAS and are never duplicated in the envelope.

The result repeats request/source/context/sampler bindings. `rejections_consumed`
is the number of rejected attempts before termination and
`decision_trace_hash` binds the complete producer trace artifact. Success has a
non-null structural Program hash and null error. Failure has a null Program
hash and exactly one error. This list is also the mandatory first-failure-wins
validation precedence: `SAMPLER_REQUEST_INVALID`,
`SAMPLER_CONTEXT_MISMATCH`, `SAMPLER_MANIFEST_MISMATCH`,
`SAMPLER_SOURCE_MISMATCH`, `SAMPLER_REJECTIONS_EXHAUSTED`,
`SAMPLER_RESULT_INVALID`. A successful attempt
after `r` rejected attempts stores `r`; exhaustion stores exactly
`sampler_manifest.maximum_rejections_per_seed`.

### PlannerRequest and Response

A PlannerRequest exists only when `planner_manifest_hash` is non-null. It binds
the immutable source Program, source decision, GenreIntent, latest available
evaluation/fingerprint/render evidence hashes, locks, failed constraints,
remaining budgets, and lineage summary. Evidence hash fields are nullable; a
missing artifact is null, not an all-zero digest. `metrics` sort by metric ID;
each metric has either integer `value` and integer `delta`, or both null and a
non-null frozen missing-reason code. `failed_constraints` sort by UTF-8 and are
unique. Lineage-root hashes sort by raw digest bytes and are unique.

The response repeats request/source/context/planner bindings. A success has a
closed ordered `mutation_proposal` of one through four complete Mutation
objects, its `proposal_hash`, and null diagnostic. `proposal_hash` uses the
exact Group-D closed preimage object and domain prefix below. A later phase-1
MutationApplicationRequest binds `response_hash` and
`proposal_hash`; PlannerResponse MUST NOT name that future request. Failure has
null proposal and proposal hash and one frozen diagnostic. This list is also
the mandatory first-failure-wins validation precedence:
`PLANNER_REQUEST_INVALID`, `PLANNER_CONTEXT_MISMATCH`,
`PLANNER_MANIFEST_MISMATCH`, `PLANNER_SOURCE_MISMATCH`,
`PLANNER_REQUEST_TOO_LARGE`, `PLANNER_PROVIDER_UNAVAILABLE`,
`PLANNER_TIMEOUT`, `PLANNER_RESPONSE_TOO_LARGE`,
`PLANNER_RESPONSE_SCHEMA_INVALID`, `PLANNER_OPERATION_NOT_ALLOWED`,
`PLANNER_MUTATION_COUNT_INVALID`, `PLANNER_RESULT_INVALID`. Rationale and raw
provider output are forbidden. Provider
text, exception text, latency, timestamps, and retry counts are forbidden.
Planner-null creates neither request nor response. Committing PlannerRequest
consumes one planner call; producing or replaying PlannerResponse consumes none.

## Group B: evaluation

The machine schemas are `evaluation_manifest.schema.json`,
`evaluation_request.schema.json`, and `evaluation_report.schema.json`; their
self-hash members are `manifest_hash`, `request_hash`, and `report_hash`.
RunManifest fields `evaluation_manifest_schema_hash`,
`evaluation_request_schema_hash`, and `evaluation_report_schema_hash`, and the
same three raw-schema bindings in `RunContext.schema_hashes`, MUST equal the raw
SHA-256 of the parsing schemas. `evaluation_manifest_hash` MUST equal the
RunManifest and RunContext artifact binding. SearchLoop event kind
`evaluation_request` maps to EvaluationRequest; legacy-stable event kind
`metric_report` maps to EvaluationReport and MUST carry its report and schema
hashes. It does not denote a second report format.

### EvaluationManifest

The manifest binds the evaluator ID, version, build hash, and GenreIntent hash.
`hard_checks` and `metrics` are unique and sorted by ID UTF-8. Each declaration
has exactly one source resolver `(artifact_kind, schema_hash, json_pointer)` and
states whether render evidence is required. A metric also fixes its direction;
all metric values are integers. Source pointers are RFC 6901 pointers evaluated
against the canonical producer document after its schema and artifact hashes
have been verified. Missing pointers, wrong types, and schema/hash mismatches
are errors, never implicit zeroes.

### EvaluationRequest

The request binds run, context, source decision, manifest, GenreIntent, source
Program, compiled Project and CompileReport, FingerprintRecord, optional
NearDuplicateDecision, and render evidence by artifact and producer-schema
hashes. A null near-duplicate hash means that decision was not produced.
Render evidence has exactly one state: `available` supplies RenderResult and
audio hashes with null reason; `not_selected` supplies neither and reason
`not_selected`; `failed` supplies the failed RenderResult hash, no audio hash,
and reason `render_failed`. These states are distinct from an all-zero digest.

### EvaluationReport and policy resolution

On success, `hard_checks` and `metrics` have the same lengths, IDs, and order as
their manifest declarations. Every hard check contains a boolean `passed` and
non-empty causal evidence. Every metric contains either an integer `value`,
null reason, and its evidence; or null value, an explicit reason
(`source_unavailable`, `render_not_selected`, `render_failed`, or
`not_applicable`), and only the available evidence. A declaration with
`required_render=true` cannot produce a value when render state is not
`available`. Failure reports contain empty result arrays.

The following EvaluationReport failure list is the mandatory
first-failure-wins validation precedence:
`EVALUATION_REQUEST_INVALID`, `EVALUATION_CONTEXT_MISMATCH`,
`EVALUATION_MANIFEST_MISMATCH`, `EVALUATION_GENRE_INTENT_MISMATCH`,
`EVALUATION_SOURCE_MISMATCH`, `EVALUATION_PROJECT_MISMATCH`,
`EVALUATION_FINGERPRINT_MISMATCH`,
`EVALUATION_RENDER_EVIDENCE_MISMATCH`, `EVALUATION_RESULT_INVALID`.

Decision-policy IDs resolve without search. Each
`required_hard_checks[i]` MUST name exactly one manifest hard check and its
report row. An archive/challenger source selecting an evaluation metric MUST use
`artifact_kind=evaluation_report`, the bound EvaluationReport raw schema hash,
and pointer `/metrics/N/value`, where `N` is the sole manifest/report row whose
ID equals the policy component ID. A hard-check pointer analogously is
`/hard_checks/N/passed`. Any other pointer for those policy components is
invalid. A required policy metric with a missing value makes that decision
ineligible; it is never coerced to zero.

## Group C: compile-only/cache and cancellation control inbox

The machine schemas are `compile_only_request.schema.json`,
`compile_only_result.schema.json`, `compile_only_cache_entry.schema.json`,
`cancellation_inbox_record_1_1.schema.json`, and
`cancellation_decision_1_1.schema.json`. Their self-hash members are,
respectively, `request_hash`, `result_hash`, `entry_hash`, `inbox_hash`, and
`decision_hash`. A Group-C payload is wrapped by the closed
`search_loop_13_event_payload.schema.json` binding, which repeats the run,
context, action ID, and four-part coordinate. The binding coordinate must equal
the RunRecord coordinate and its action ID must be recomputed by the v2 action
ID formula.

### CompileOnlyRequest, Result, and CacheEntry

`CompileOnlyRequest` is phase-3 input only. It binds its source decision, the
exact phase-2 `mutation_result_event_payload_hash`, successful
`mutation_application_receipt_hash`, and both the complete published result
Program and its hash, as well as compiler manifest and context. These are the
three phase-2 causal values; all are required. It has no mutation member and
calling `execute_connected` or otherwise applying a mutation while satisfying
it is invalid.

The cache key is exactly the sealed `CompileOnlyRequest.request_hash`.
`CompileOnlyResult.cache_key_hash` MUST equal that request hash. The result is
therefore sealed before a CAS entry that binds its result hash, avoiding a
self-hash cycle. `CompileOnlyCacheEntry.request_hash` is that same cache key;
it binds the result and receipt hashes and records exactly the semantic
Project/report hashes and logical charge. A cache entry is valid only if those
repeated values equal its result and request.

The error list is ordered first-failure-wins:
`COMPILE_REQUEST_INVALID`, `COMPILE_CONTEXT_MISMATCH`,
`COMPILE_MANIFEST_MISMATCH`, `COMPILE_SOURCE_MISMATCH`,
`COMPILE_PROGRAM_MISMATCH`, `COMPILE_BUDGET_EXHAUSTED`, `COMPILE_FAILED`, and
`COMPILE_RESULT_INVALID`. A sealed request without a result recomputes that
same request. A committed result replays and never recompiles. Cold and valid
hit paths must publish the same semantic result and consume the same logical
charge. A corrupt cache entry is telemetry-only: quarantine it, then cold
recompute; it is never a semantic result/error/cache outcome. The compile
budget is checked before the seam; a successful committed result (including a
hit) increments the logical counter exactly once. A budget failure has zero
charge and no cache entry.

### CancellationInboxRecord and CancellationDecision 1.1

An inbox record preserves the immutable canonical cancellation-request bytes,
their raw SHA-256 digest, the request's self hash, request-schema hash, run
hash, and an acceptance sequence. Validation is ordered: canonical bytes and
raw digest, request schema/self hash, request run hash, then idempotent inbox
CAS acceptance. An invalid input produces no inbox record and no cancellation
event. For a duplicate raw digest, the first accepted record is replayed; a
new `acceptance_sequence` is allocated only for a distinct accepted digest.
The sequence is audit-only and never selects the winner.

At each barrier the eligible inbox record with lexicographically lowest raw
digest wins. `CancellationDecision 1.1` binds that inbox record/digest/request,
run/context, the next unstarted ordinary four-part cutoff coordinate, recomputed
cutoff action ID, current champion, and archive heads. It is committed after
the `cancellation_request` event and before ordinary work at the cutoff.
Cancellation has no cache or budget charge. A cutoff event ordinal is at least
2; control events 0 and 1 are reserved for the inbox winner and decision.

## Group D: archive/sampler evidence and terminal cancellation checkpoint

The machine schemas are `archive_heads_snapshot.schema.json`,
`structural_sampler_trace.schema.json`, and
`planner_proposal_preimage.schema.json`. Their raw schema bytes are bound by
the matching `RunManifest 1.3` fields and `RunContext.schema_hashes` entries.

An ArchiveHeadsSnapshot binds run, context, and round. Its entries are unique
and sorted by `(cell integer lexicographic, program_hash raw digest bytes)`.
Each entry binds the archive update record, archive admission decision, inline
parent Program and its canonical hash, compiled Project, and EvaluationReport.
For an `archive_parent` CandidateSourceDecision, `round_start_archive_heads_hash`
MUST equal this snapshot hash. The selected entry is
`source_occurrence_ordinal mod entries.length`; all selected hashes and the
inline parent Program MUST equal that entry exactly. Selection from an empty
snapshot is forbidden and uses the policy's recorded initial-sampler branch.

A StructuralSamplerTrace binds the run, context, source decision, sealed
sampler request, and sampler manifest. Attempts are ordered by consecutive
zero-based attempt ordinal. Within an attempt, decision rows follow the
manifest decision-program ordinal and expanded path order. Each row records
the exact manifest path, counter, complete index-ordered weighted `table`,
`table_hash`, selected index, selected-value hash, and `row_hash`;
these values MUST reproduce the path-addressed draw. A rejected attempt has a
non-null rejection code; an accepted attempt has null rejection and its Program
hash. Only the terminal attempt may be accepted. `terminal_attempt_ordinal`
equals the final array index. A successful SamplerResult's
`rejections_consumed` equals that ordinal. An exhausted result has exactly
`maximum_rejections_per_seed` rejected attempts and no accepted attempt.
`decision_trace_hash` MUST equal the trace's `trace_hash`.
`table_hash` is SHA-256 of
`"cps.structural-sampler-table/v1\0" || canonical_json(table) || LF`, and
`row_hash` is SHA-256 of
`"cps.structural-sampler-decision/v1\0" ||
canonical_json(row_without_row_hash) || LF`.

Planner proposal hashing never hashes a bare array and never adds an implicit
wrapper field. The exact preimage is:

```text
SHA-256(
  UTF-8("cps.planner-mutation-proposal/v1\0") ||
  canonical_json_with_final_LF({"mutations": ordered_mutation_array})
)
```

The closed preimage object contains only `mutations`. Its schema identity is a
RunManifest/RunContext binding and is not inserted into the hashed object.

When a CancellationDecision is committed, no ordinary event at or above its
cutoff may exist. Once all lower coordinates are sealed, the coordinator emits
the unique terminal checkpoint at `(round, phase=13, candidate=0, event=2)`.
It is legal only when the matching committed decision has `cancelled=true` and
no terminal checkpoint already exists. Its cursor is `(round,13,0,3)`, its
`next_action_id` is the corresponding terminal-sentinel action ID, and its
termination is exactly `status=terminated`, `reason=cancelled`, with
`decision_hash` equal to that CancellationDecision hash. Phase 0..12 event 2
always retains its ordinary scheduled meaning.
