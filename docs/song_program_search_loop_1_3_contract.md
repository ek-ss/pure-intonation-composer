# SongProgram SearchLoop13 Coordinator Contract

**Status:** normative coordinator design; production implementation pending.

This contract introduces SearchLoop13 exclusively for `SearchRunManifest
1.3.0`. It does not reinterpret, upgrade, resume, or write a RunManifest 1.2
run, a RunRecord 1.0, or a SearchCheckpoint 1.0. Those legacy contracts remain
owned by `ProductionSearchLoop`.

## Factory and immutable RunContext

The only SearchLoop13 factory is conceptually:

```text
SearchLoop13.open(root, run_context, seams)
```

`run_context` is a closed `cps.search-loop-13-context/1.0.0` document. It
inlines the RunManifest 1.3 and every artifact used to rebuild a request: the
sampler, fallback, broad-prior production, compiler, evaluation and GenreIntent
artifacts; QD, planner (or null), catalog, fingerprint, all decision policies,
render manifest, CandidateSourcePolicy, instrument catalog, and executor
manifest. It also carries the raw mutation/connected/fallback/production
contract hashes and mutation/request/receipt/record/checkpoint/fallback schema
hashes. Each binding carries its producer schema hash, artifact hash, and
document. Factory validation recomputes every binding hash, checks that each
property name matches its binding kind, verifies every raw hash and manifest
binding, verifies `run_hash` from the inline manifest, and then
content-addresses the context. Later filesystem lookup, unbound defaults, and
substitution of similarly named artifacts are forbidden.
The RunManifest also binds the raw schema hashes for RunContext, EventPayload,
candidate source, sampler request/result, planner request/response, and
evaluation manifest/request/report. Context must exactly match those bindings;
an arbitrary same-shaped payload schema cannot be introduced for a run.

`context_hash` uses the Search Decision Contract artifact hash preimage with
only `context_hash` removed: `cps-artifact-hash/v1\0`, schema, schema version,
then canonical JSON. `run_hash` is calculated from the inline RunManifest by
the same rule with no self-hash member. A RunContext and every sealed request
are immutable CAS values.

For `planner_manifest_hash: null`, RunContext's `planner_manifest` is null and
its `FallbackManifest 1.1` / `FallbackRequest 1.1` `planner_manifest_hash` is
also null. A RunManifest 1.3 `fallback_manifest_hash` therefore always binds a
FallbackManifest 1.1, never legacy FallbackManifest 1.0. This path makes no
planner seam call and increments no planner budget. A planner failure
uses only contract-defined diagnostic codes, never provider text, timestamps,
or timeout wording.

The manifest binds `candidate_source_policy_hash`. CandidateSourcePolicy uses
`candidate-ordinal-mod-source-cycle/v1`. Its selected source is recorded before
any source result:

- `initial_sampler` records root seed, candidate-derived cohort index, sampler
  manifest hash, and canonical locked roots as an intent. The later sampler and
  production results supply the base Program; the source decision cannot cite a
  future result.
- `archive_parent` records the exact round-start champion program hash, source
  archive record hash, source decision hash, CandidateSourcePolicy hash, and
  canonical locked roots. Parent selection is sorted by cell then program hash;
  the source-occurrence ordinal (the count of prior archive-parent choices in
  that round) selects modulo that sorted list. An empty archive follows the
  policy's explicit initial-sampler behavior.

No candidate may infer its source from a mutable `current` program or from a
physically latest archive head. `cohort_index` is exactly
`round * candidates_per_round + candidate_ordinal`, evaluated as checked u64
with overflow rejecting the run. Only an initial-sampler source executes
production lowering. An archive-parent Program skips phase-0 production events
and is the immutable base Program for phase 1. Fallback receives the successful
production Program for initial-sampler sources or the selected parent Program
for archive-parent sources.

## Action coordinates and IDs

An action coordinate is `(round, phase_ordinal, candidate_ordinal,
event_ordinal)`, ordered lexicographically as unsigned integers. `round` and
`candidate_ordinal` are u64, `phase_ordinal` is u8 in `0..13`, and
`event_ordinal` is u16. Candidate ordinal is zero for round/checkpoint actions.
Event ordinals are constants in the schedule below; they are never
allocated from worker identity, physical completion order, cache outcome, or
retry timing.

For RunManifest 1.3 only, `action_id` is `act_` plus the first 130 bits,
base32-lowercase without padding, of:

```text
SHA-256(
  "cps-action-id/v2\0" || UTF-8(run_hash) || u64be(round) ||
  u8(phase_ordinal) || u64be(candidate_ordinal) || u16be(event_ordinal)
)
```

The event ordinal is an audit/record coordinate only. It must not enter sampler,
broad-production, fallback, mutation, or cache selection preimages. Existing
`cps.search-action/v1` IDs are legacy-only.

## Canonical record schedule

Each listed event has exactly one RunRecord 1.1. Events marked conditional are
omitted when their condition is false; no placeholder record is emitted. A
payload is a closed `SearchLoop13 Event Payload Binding` that binds its inline
RunContext, source decision, concrete payload schema hash, and sealed CAS
artifact hash. Its request is committed before its calculation/output. `failure` is allowed only as the listed result event's
payload status, not as an extra duplicate-coordinate record.

| Phase | Event | RunRecord kind | Payload / condition |
|---:|---:|---|---|
| any 0..12 | 0 | `cancellation_request` | Conditional control-inbox winner at this barrier. |
| any 0..12 | 1 | `cancellation_decision` | Conditional cutoff decision for event 0. |
| 0 | 2 | `candidate_source_decision` | Source intent; archive parent evidence is present only for archive source. |
| 0 | 3 | `sampler_request` | Initial-sampler source only. |
| 0 | 4 | `sampler_result` | Result for event 3, including rejection evidence. |
| 0 | 5 | `production_request` | Initial-sampler source only, after successful structural sampling. |
| 0 | 6 | `production_result` | Result for event 5. |
| 1 | 2 | `planner_request` | Non-null planner manifest only. |
| 1 | 3 | `planner_response` | Result for event 2; schema-valid proposal or contract-defined failure. |
| 1 | 4 | `fallback_request` | Planner-null or the sealed failure at event 3 only. |
| 1 | 5 | `mutation_request` | The sealed MutationApplicationRequest 1.1, planner- or fallback-derived. |
| 2 | 2 | `mutation_result` | The sole application receipt/result for phase-1 event-5 request. |
| 2 | 3 | `fallback_result` | Fallback path only; binds the phase-2 receipt. |
| 3 | 2/3 | `compile_request` / `compile_result` | Sealed compile-only request and its result; no mutation application. |
| 4 | 2 | `fingerprint_result` | FingerprintRecord, following a compile-valid Project only. |
| 5 | 2 | `near_duplicate_decision` | Exact comparison set and classification. |
| 6 | 2/3 | `render_request` / `render_reservation` | Selected distinct candidate only. |
| 7 | 2/3 | `render_dispatch` / `render_result` | Authorized dispatch and terminal outcome. |
| 8 | 2/3 | `evaluation_request` / `metric_report` | Bound evaluation request/report. |
| 9 | 2 | `challenger_acceptance_decision` | Policy-bound challenger comparison. |
| 10 | 2/3 | `archive_admission_decision` / `archive_update` | Admission then admitted-candidate CAS update. |
| 11 | 2 | `round_decision` | Completed-round archive/patience/stop result. |
| 12 | 2 | `checkpoint` | Summary after phase 11. |

The fallback path is intentionally two-stage. With a planner manifest, phase 1
first commits PlannerRequest and PlannerResponse. Planner-null omits events 0
and 1. Planner-null or a sealed planner failure commits FallbackRequest at
event 2. Every successful path commits its proposed MutationApplicationRequest
at event 3. Phase 2 applies that exact request once, commits its receipt, then
commits a FallbackResult only for the fallback path. On resume, a committed
phase-2 receipt is replayed; it is never reapplied.
Planner-null omits phase-1 events 2 and 3, then uses event 4 and event 5.

If the committed planner-call count equals `planner_call_budget`, phase 1 does
not call planner and does not invoke fallback. It records the completed-round
logical-budget-exhausted outcome at the next round barrier. Planner budget
exhaustion is therefore `logical_budget_exhausted`, never a fallback diagnostic.

## Records, checkpoints, and mid-phase resume

RunRecord 1.1 carries `event_ordinal`; checkpoints carry it in `cursor` and
derive `next_action_id` using v2. A coordinator verifies the whole append-only
record chain and every CAS payload before using a checkpoint. It reconstructs
candidate stages, source decisions, comparison population, reservations,
render results, evaluation/challenger/archive state, budget counters, patience,
and termination from records; a checkpoint is only a verified acceleration.
RunRecord 1.1 uses the existing v1 record-hash chain preimage exactly: omit only
`record_hash`, canonicalize the remaining closed record, and hash with the
declared `cps.search-run-record/v1` domain. CAS payload bytes use the declared
`u64be-length-canonical-json/v1` framing. The v2 action ID changes coordinate
identity only; it does not change the record-hash or CAS framing algorithm.

If a sealed request exists without its result, the same request is rerun:

- sampler/production rerun with the same cohort/rejection coordinate;
- phase-1 event 2/3 (planner request/response), event 4 (fallback request),
  and event 5 (mutation request) are sealed independently; an absent result
  reruns only its sealed request;
- phase-2 event 2 applies the event-5 request once. If its receipt exists,
  phase-2 event 3 merely seals/replays FallbackResult and reapplication is
  forbidden;
- a committed compile output, render result, or evaluation report is replayed
  rather than recomputed through an external seam.

Checkpoint counters change only after their charging result commits. A real
planner attempt increments `planner_calls` once when its sealed request is
committed; planner-null increments it zero. Production rejection counts are
result evidence, not budget consumption.

## Cache, parallel execution, and cancellation

Phase 3 calls a compile-only seam with the Program already published by phase
2; it must not invoke `execute_connected` or apply a mutation again. Connected
compile cache keys derive from that fully sealed compile-only request, including
the already-published Program hash and phase-2 receipt hash. Cold, valid hit,
and corrupt-recompute paths must yield the same semantic output and compile
charge; cache telemetry is non-decision metadata.

Render cache keys derive from the sealed RenderRequest (therefore project,
render manifest, excerpt, and tail). Lookup follows reservation and dispatch
authorization. Cache hits and dispatched failures retain the same frame charge
as a render; reservations are never refunded.

Workers may calculate independent sealed requests in parallel, but commit only
the schedule order above. Candidate source state is fixed at the round barrier,
so physical completion cannot choose a parent. A coordinator must buffer later
completion until every earlier applicable coordinate is committed or has its
sealed terminal result.

An external cancellation request is accepted into a control-inbox CAS at any
time. At each next unstarted ordinary coordinate, the coordinator selects the
lowest raw request-hash digest among accepted requests, commits events 0 and 1,
and sets the cutoff to that ordinary coordinate. If no request is present both
events are omitted and ordinary events start at 2. A cutoff forbids all ordinary
events at or above its coordinate; lower coordinates drain in order. This lets a
phase-6 reservation drain while cancelling its phase-7 dispatch. The decision
records the cutoff champion and archive-head hash; at that same barrier only,
event 2 is a terminal `checkpoint` and all ordinary event-2-or-later work is
omitted. Thus the terminal checkpoint never requires progressing to phase 12.

## Required implementation tests

Before implementation, add fixtures for every schedule edge, mid-phase resume
at each request/result boundary, cold/hit/corrupt compile and render cache
parity, 1/2/4/8 worker completion shuffles, planner-null/fallback, cancellation
before reserve/between reserve and dispatch/after dispatch, and byte-identical
resume. The same suite must prove that all legacy 1.2 fixtures remain unchanged.
