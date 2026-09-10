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

### Closed event artifact binding table

For every scheduled event, `kind` selects exactly one artifact schema. The
EventPayload `artifact_schema_hash`, the named RunManifest field, and the
`hash` in the named `RunContext.schema_hashes` raw-bytes binding MUST all equal
the raw SHA-256 of that exact checked-in schema file. No compatible substitute
schema is allowed.

| EventPayload `kind` | exact artifact schema | RunManifest field | RunContext raw-bytes field |
|---|---|---|---|
| `candidate_source_decision` | `candidate_source_decision.schema.json` | `candidate_source_decision_schema_hash` | `candidate_source_decision` |
| `sampler_request` | `structural_sampler_request.schema.json` | `sampler_request_schema_hash` | `sampler_request` |
| `sampler_result` | `structural_sampler_result.schema.json` | `sampler_result_schema_hash` | `sampler_result` |
| `production_request` | `broad_prior_production_request.schema.json` | `production_request_schema_hash` | `production_request` |
| `production_result` | `broad_prior_production_result.schema.json` | `production_result_schema_hash` | `production_result` |
| `planner_request` | `planner_request.schema.json` | `planner_request_schema_hash` | `planner_request` |
| `planner_response` | `planner_response.schema.json` | `planner_response_schema_hash` | `planner_response` |
| `fallback_request` | `fallback_request_1_1.schema.json` | `fallback_request_schema_hash` | `fallback_request` |
| `mutation_request` | `mutation_application_request_1_2.schema.json` | `mutation_request_schema_hash` | `mutation_request` |
| `mutation_result` | `mutation_application_receipt.schema.json` | `mutation_receipt_schema_hash` | `mutation_receipt` |
| `fallback_result` | `fallback_result_1_1.schema.json` | `fallback_result_schema_hash` | `fallback_result` |
| `compile_request` | `compile_only_request.schema.json` | `compile_only_request_schema_hash` | `compile_only_request` |
| `compile_result` | `compile_only_result.schema.json` | `compile_only_result_schema_hash` | `compile_only_result` |
| `fingerprint_result` | `fingerprint_record.schema.json` | `fingerprint_record_schema_hash` | `fingerprint_record` |
| `near_duplicate_decision` | `near_duplicate_decision.schema.json` | `near_duplicate_decision_schema_hash` | `near_duplicate_decision` |
| `render_request` | `render_request.schema.json` | `render_request_schema_hash` | `render_request` |
| `render_reservation` | `render_charge.schema.json` | `render_charge_schema_hash` | `render_charge` |
| `render_dispatch` | `render_dispatch_authorization.schema.json` | `render_dispatch_authorization_schema_hash` | `render_dispatch_authorization` |
| `render_result` | `render_result.schema.json` | `render_result_schema_hash` | `render_result` |
| `evaluation_request` | `evaluation_request.schema.json` | `evaluation_request_schema_hash` | `evaluation_request` |
| `metric_report` | `evaluation_report.schema.json` | `evaluation_report_schema_hash` | `evaluation_report` |
| `challenger_acceptance_decision` | `challenger_acceptance_decision.schema.json` | `challenger_acceptance_decision_schema_hash` | `challenger_acceptance_decision` |
| `archive_admission_decision` | `archive_admission_decision.schema.json` | `archive_admission_decision_schema_hash` | `archive_admission_decision` |
| `archive_update` | `qd_archive_record.schema.json` | `qd_archive_record_schema_hash` | `qd_archive_record` |
| `round_decision` | `round_decision.schema.json` | `round_decision_schema_hash` | `round_decision` |
| `checkpoint` | `search_checkpoint_1_1.schema.json` | `checkpoint_schema_hash` | `checkpoint` |
| `cancellation_request` | `cancellation_inbox_record_1_1.schema.json` | `cancellation_inbox_record_schema_hash` | `cancellation_inbox_record` |
| `cancellation_decision` | `cancellation_decision_1_1.schema.json` | `cancellation_decision_schema_hash` | `cancellation_decision` |

`payload_hash` is the EventPayload's own artifact hash. Its exact preimage is
`UTF-8("cps-artifact-hash/v1\0" + "cps.search-loop-13-event-payload" +
"\0" + "1.0.0" + "\0") || canonical_json(payload with only payload_hash
removed)`, with no trailing LF. `RunRecord.payload_hash` MUST equal this value;
it MUST NOT equal the inner `artifact_hash` unless an accidental digest
collision occurs. CAS stores the complete canonical EventPayload bytes,
including `payload_hash`, with no LF. The `u64be-length-canonical-json/v1`
framing is `u64be(byte_length) || canonical_bytes` for record transport and
append validation only and is not part of either artifact-hash preimage.

The non-event render cache artifacts are also closed and run-bound by raw
schema bytes: `render_cache_entry.schema.json` via
`render_cache_entry_schema_hash` / `render_cache_entry`, and
`render_cache_corruption_receipt.schema.json` via
`render_cache_corruption_receipt_schema_hash` /
`render_cache_corruption_receipt`. `audio_artifact.schema.json` is bound by
`audio_artifact_schema_hash` / `audio_artifact`; it describes exactly little-
endian PCM32, stereo LR interleaved, at 48000 Hz. Semantic validation requires
`pcm_byte_length == frame_count * 2 * 4`; `pcm_sha256` is `sha256:` plus
lowercase SHA-256 of the exact unframed PCM bytes, and
`reference_render_report_hash` binds their producer report.

For render caching, `RenderDispatchAuthorization.cache_key_hash` and
`RenderCacheEntry.request_hash` MUST both equal the sealed
`RenderRequest.request_hash`. A corrupt lookup creates a
RenderCacheCorruptionReceipt before cold recomputation. Its
`observed_entry_bytes_hash` is `sha256:` plus lowercase SHA-256 of every exact
raw byte returned by the cache read before parsing or canonicalization. If the
cache API returns length-framed bytes, the framing bytes are part of that raw
input and therefore part of the digest; if it returns an unframed object, no
framing is synthesized. The successful recomputation has outcome `rendered`
and MUST place the receipt's self hash in `corruption_receipt_hash`. An ordinary
cold `rendered` result uses null. `cache_hit`, `render_failed`, and
`cancelled_before_dispatch` always use null. Thus the receipt remains
telemetry, but its existence is committed into the semantic RenderResult root.

| Auxiliary artifact | exact schema | RunManifest field | RunContext raw-bytes field |
|---|---|---|---|
| render cache entry | `render_cache_entry.schema.json` | `render_cache_entry_schema_hash` | `render_cache_entry` |
| render corruption receipt | `render_cache_corruption_receipt.schema.json` | `render_cache_corruption_receipt_schema_hash` | `render_cache_corruption_receipt` |
| rendered PCM audio | `audio_artifact.schema.json` | `audio_artifact_schema_hash` | `audio_artifact` |

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

For every attempt, `attempt_seed_hash` is exactly:

```text
sha256:hex(SHA-256(
  UTF-8("cps.structural-sampler-attempt-seed/v1\0") ||
  u64be(root_seed) || u64be(cohort_index) || u64be(attempt_ordinal) ||
  raw_32_bytes(sampler_manifest_hash)
))
```

The seed inputs are unsigned integers in `0..2^64-1`; conversion outside that
range fails before hashing and is never truncated or reduced modulo `2^64`.
Attempt ordinals are consecutive from zero and strictly less than
`sampler_manifest.maximum_rejections_per_seed`, whose maximum is 256. The
attempt seed is a stream root only; per-decision path/counter derivation remains
the manifest's `path-addressed-sha256/v1` contract.

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
cutoff may exist except the single drain result below. Once all lower
coordinates and that required drain are sealed, the coordinator emits
the unique terminal checkpoint at `(round, phase=13, candidate=0, event=2)`.
It is legal only when the matching committed decision has `cancelled=true` and
no terminal checkpoint already exists. Its cursor is `(round,13,0,3)`, its
`next_action_id` is the corresponding terminal-sentinel action ID, and its
termination is exactly `status=terminated`, `reason=cancelled`, with
`decision_hash` equal to that CancellationDecision hash. Phase 0..12 event 2
always retains its ordinary scheduled meaning.

The sole cutoff exception applies when phase-6 event-3 RenderCharge is already
committed as `reserved` and phase-7 event-2 dispatch has not started. Phase-7
event-3 RenderResult MUST then commit as
`not_dispatched/cancelled_before_dispatch`, with null cache-entry,
corruption-receipt, audio, and failure hashes. It performs no cache lookup or
renderer call, remains charged, and the phase-13 checkpoint MUST wait for it.
No other at-or-above-cutoff record is permitted.

## Authoritative fixture closure

An authoritative case is a closed `search_loop_13_fixture_case.schema.json`
document. Its `inputs` list is unique by role and sorted by role UTF-8 bytes;
each row binds a repository-relative path, exact raw file SHA-256, parsed
artifact hash, and raw schema hash. Its root seed, policy hashes, planner
branch, budgets, and expected stop branch MUST equal the bound RunManifest and
RunContext. The case self-hashes by the standard artifact rule with only
`case_hash` omitted. Expected outputs bind the final RunRecord hash as
`transcript_root_hash`, the closed CAS inventory root, final checkpoint artifact
hash, cache-publication index hash, and every PCM asset's file/PCM/artifact
hashes. Files not reachable from these roots are not fixture authority.

The CAS inventory root is a closed `SearchLoop13 CAS Index 1.0`. Its
`cas_index_schema_hash` is bound in RunManifest/RunContext and copied into the
fixture expected object; all three raw schema hashes MUST agree. Every entry
has exactly one locator: repository-relative `path` or logical
`artifact_role`, plus `content_kind`, artifact hash, schema hash, and exact byte
length. `schema_hash` is non-null exactly for `json_artifact` and null exactly
for `raw_pcm`. Entries sort by `(locator.kind UTF-8, locator value UTF-8,
artifact_hash raw digest bytes)` and that tuple, locator values, and artifact
hashes are each unique. `index_hash` is the standard artifact hash with only
`index_hash` omitted, using canonical JSON with no LF. Fixture
`cas_index_hash` MUST equal it. The index contains every and only object
reachable from the transcript, final checkpoint, cache-publication index, and
declared audio assets.

The fixture schema intentionally does not enumerate a universal set of input
roles. The oracle derives the selected planner/source/render/stop branches,
walks every hash edge from the case roots, and MUST reject a missing input,
unreachable extra input, duplicate role, or incorrectly sorted input array.
This reachable closure, not JSON Schema alone, defines “all inputs.”

ArchiveHeadsSnapshot is the sole canonical archive-head collection object.
Exactly one `stage=round_before` snapshot is sealed before phase 0 and one
`stage=round_after` snapshot after all admitted phase-10 archive updates.
RoundDecision `archive_heads_before_hash` and `archive_heads_after_hash` MUST
equal those two snapshot artifact hashes. The phase-12 checkpoint
`archive_heads` entries MUST equal the after snapshot's cells and corresponding
phase-10 `archive_update` RunRecord hashes. Phase 11 cannot start until the
after snapshot is sealed.

Every successful cold CompileOnly or render publication is appended to one
`CachePublicationIndex 1.0`, ordered strictly by action coordinate and then
kind UTF-8 bytes. Compile rows use the phase-3 event-3 coordinate and
CompileOnlyCacheEntry; render rows use phase-7 event-3 and RenderCacheEntry.
Each row binds the sealed request and entry self hashes. Duplicate coordinates,
request hashes, or entry hashes are invalid. `index_hash` uses the standard
artifact rule with only itself omitted. The fixture's expected
`cache_publication_index_hash` makes cold cache bytes authoritative without
adding a scheduled RunRecord.

## Group E: planner/fallback causal handoff

SearchLoop13 uses `fallback_request_1_1.schema.json`,
`mutation_application_request_1_2.schema.json`, and
`fallback_result_1_1.schema.json`; legacy versions remain unchanged. Matching
RunManifest raw schema fields and RunContext bindings MUST name these versions.

FallbackRequest 1.1 binds run, context, source decision, and its phase-1 event-4
v2 coordinate. Its source is exactly `planner_null`, with no fabricated planner
hash, or `planner_failure`, with the sealed PlannerResponse hash and matching
ordered `PLANNER_*` diagnostic. Planner success never creates FallbackRequest.

MutationApplicationRequest 1.2 adds context, source decision, and exactly one
origin: planner `(response_hash,proposal_hash)` or fallback
`(fallback_request_hash,proposal_hash)`. The Group-D hash of its ordered
`mutations` MUST equal the origin proposal hash. Its self-hash omits only
`request_hash`.

FallbackResult 1.1 binds the fallback request and preserves result-specific
`attempts_consumed` and ordered `decision_trace`. Manifest, base Program,
event-4 v2 coordinate, requested count, and locks are not duplicated: they are
resolved from the mandatory sealed FallbackRequest CAS object and MUST validate
before the Result. Success repeats the ordered mutations/proposal hash, one
application request, its complete receipt, and final Program hash.
`pre_application_failure` has no application request or receipt;
`application_failed` binds the application request, its failed receipt, and the
attempted mutations/proposal hash, but has no final Program. A committed receipt
is replayed and the mutation batch never executes twice.
For success the receipt status is `complete`; for `application_failed` it is
`failed`. In both cases its `request_hash` MUST equal
`mutation_application_request_hash`, and the request's fallback origin,
proposal hash, and ordered mutations MUST equal the Result values.

FallbackResult diagnostics use this first-failure-wins order:
`FALLBACK_REQUEST_INVALID`, `FALLBACK_CONTEXT_MISMATCH`,
`FALLBACK_SOURCE_MISMATCH`, `FALLBACK_MANIFEST_MISMATCH`,
`FALLBACK_CHOICE_CATALOG_MISMATCH`, `FALLBACK_PROGRAM_HASH_MISMATCH`,
`FALLBACK_LOCKS_INVALID`, `FALLBACK_ACTION_COORDINATE_INVALID`,
`FALLBACK_NO_ELIGIBLE_OPERATION`, `FALLBACK_ATTEMPTS_EXHAUSTED`,
`FALLBACK_MUTATION_APPLICATION_FAILED`, `FALLBACK_RESULT_INVALID`.

CancellationDecision 1.1 has `status=accepted` and `cancelled=true`; both
constants participate in its self hash.
