# SongProgram Search Decision Contract

**Status:** normative for Search RunManifest 1.3  
**Scope:** archive admission, challenger comparison, duplicate suppression,
stopping, cancellation, and render-budget decisions

Search decisions are immutable content-addressed artifacts. Policies are bound
by hash in `SearchRunManifest 1.3`; a run never reads ambient defaults. Decision
records contain only canonical inputs and derived integer results. Wall-clock
time, worker identity, cache telemetry, and physical completion order are not
decision inputs.

## Hash preimages and component binding

Every artifact hash defined by this contract is lowercase `sha256:<64 hex>`;
digests of externally specified artifacts retain their producer contract. For
an artifact carrying its own hash, the preimage is
`UTF-8("cps-artifact-hash/v1\\0" + schema + "\\0" + schema_version + "\\0") ||
canonical_json(artifact with only its self-hash member removed)`. For an
artifact without a self-hash member, no member is removed. Nested hashes and
nullable members remain. Invalid artifacts are rejected before hashing.
`run_hash` is the artifact hash of the bound SearchRunManifest 1.3.

RunManifest 1.3 binds `fallback_manifest_hash` and
`broad_prior_production_manifest_hash`. Binding is one-way: those component
manifests do not contain the run hash; a request may cite both hashes without a
hash cycle. Every policy metric/order component binds `artifact_kind`, exact
producer `schema_hash`, and RFC 6901 `json_pointer`. The pointed value must be a
canonical integer. Missing/non-integer values, schema mismatch, duplicate IDs
or ordinals, and invalid pointers make the candidate ineligible.

## Canonical action coordinate

Actions are ordered by `(round, phase_ordinal, candidate_ordinal,
event_ordinal)` as unsigned integers. `event_ordinal` is u16 and assigned by
the fixed SearchLoop13 schedule; it is not derived from physical completion,
cache outcome, or a retry. Phases are fixed: `0 sample_or_plan`, `1 fallback`, `2 mutate`,
`3 compile`, `4 fingerprint`, `5 duplicate`, `6 render_reserve`,
`7 render_dispatch`, `8 evaluate`, `9 challenger`, `10 archive`, `11 round`,
`12 checkpoint`, `13 reserved`. Cancellation is a control-barrier event at any
ordinary phase, not a phase-13 action. An unused candidate coordinate is zero.
For RunManifest 1.3, `action_id` is `act_` plus the first 130 bits of
`SHA-256("cps-action-id/v2\\0" || run_hash_ascii || u64be(round) ||
u8(phase_ordinal) || u64be(candidate_ordinal) || u16be(event_ordinal))`,
base32-lower without padding. The tuple, not lexical ID order, is authoritative.
Duplicate tuples are invalid. RunManifest 1.2 retains its legacy action-ID
algorithm and cannot be resumed by SearchLoop13. The full event schedule and
resume rules are normative in `song_program_search_loop_1_3_contract.md`.

## Canonical processing order

For each canonical candidate ordinal: commit Program and compile artifacts,
commit FingerprintRecord, record near-duplicate decision, and only then consider
rendering. Distinct candidates are ordered for rendering by the bound selection
policy. A render charge is reserved before dispatch and is never refunded after
dispatch. Final evaluation precedes challenger acceptance and archive admission.
At the completed-round barrier, archive updates precede RoundDecision and
checkpoint. Cancellation is observed only at an action barrier.

## Archive admission

`ArchiveAdmissionPolicy` binds the QD manifest, required hard checks, duplicate
policy, quality tuple definition, and deterministic tie-break. Admission is not
a fixed quality threshold: an eligible candidate enters an empty cell or
replaces its champion only when the policy's total comparator prefers it.
`ArchiveAdmissionDecision` records the cell state before and after, comparator
result, and all evidence hashes.

## Challenger acceptance

`ChallengerAcceptancePolicy` binds a GenreIntent and an ordered set of named
metrics. Each metric declares maximize/minimize direction and a non-negative
integer Pareto margin. Challenger `c` dominates champion `p` when it is no worse
than `p` after every margin and strictly better beyond margin on at least one
metric. If neither dominates, the declared tie rule applies to the canonical
margin-adjusted metric tuple, then program hash. There is no fixed minimum score
and no required-consecutive-round rule. A missing or differently versioned
metric makes the decision ineligible rather than silently neutral.

## Near duplicates

Near-duplicate classification occurs after symbolic compilation/fingerprinting
and before render selection. Comparison input is the hash-sorted set of earlier
eligible fingerprints. Exact program hash wins first; otherwise the weighted
integer fingerprint distance is compared inclusively to the bound threshold.
Nearest ties use component-distance tuple and then program hash. Duplicate
candidates consume no render frames and cannot enter archive or challenger
comparison.

The comparison set contains all and only earlier candidates in canonical action
order that are compile-valid, have a committed fingerprint, and were classified
distinct. Its closed value is `{"schema":"cps.near-duplicate-comparison-set",
"schema_version":"1.0.0","program_hashes":[...]}`, with unique hashes sorted
by raw digest bytes. `comparison_program_hashes` must equal that array and
`comparison_set_hash` is its artifact hash. Empty sets are valid. A nearest or
representative member must belong to this exact set.

## Patience and stopping

`StoppingPolicy` uses integer rounds and material archive improvement. A round
improves when it opens a cell or replaces a champion by at least the declared
first-differing quality-component delta. Improvement resets patience to zero;
otherwise it increments once per completed round. Stop precedence is
`cancelled`, `logical_budget_exhausted`, `accepted`, `maximum_rounds`, then
`patience`. Here `accepted` means a policy-approved challenger selected as the
run champion; it is not a consecutive-threshold gate.

## Cancellation

A cancellation request is external immutable input. At the next canonical
barrier the coordinator records a cutoff action ID. Already reserved lower
action coordinates drain and commit in coordinate order; the cutoff and later actions never
start or commit. The decision preserves the best fully evaluated candidate at
the cutoff. Operational timestamps belong to telemetry and are excluded.

The cancellation barrier runs immediately before reserve and before dispatch.
Reservation is a committed phase-6 action; dispatch is a distinct phase-7
action. If cutoff is at or before dispatch, a prior reservation remains charged
and the result is `cancelled_before_dispatch`. A dispatch committed before
cutoff drains to a terminal result and is never refunded. A reservation at or
after cutoff is neither created nor charged.

## Render budget

Render selection considers only distinct compile-valid candidates and orders
them by the policy's symbolic tuple, then program hash. Budget is counted in
output frames, independent of channel count. Charge equals content frames plus
the renderer-manifest tail. Reservation uses inclusive `used + requested <=
ceiling`; cache hits replay the same charge and failed dispatched renders are
not refunded. Final full-song export uses another manifest and does not borrow
the preview budget.

`RenderRequest` is hashed first; `RenderCharge` cites it and records the atomic
reservation transition. A reserved charge is immutable. `RenderResult` cites
both artifacts and records exactly one of pre-dispatch cancellation, cache hit,
rendered audio, or render failure. Cache lookup occurs after reservation and
dispatch authorization, so hits and dispatched failures keep the same charge.
Cache keys bind project hash and render-manifest digest; cache telemetry is not
a decision input.

## Run records and checkpoints

`RunRecord 1.1` adds explicit decision kinds and `event_ordinal` while
preserving the v1 hash chain. `SearchCheckpoint 1.1` stores the complete next
coordinate, acceptance/champion state, and a typed termination reference.
Checkpoints summarize committed records and never become an alternative source
of truth. Version 1.2 run manifests and 1.0 records remain valid legacy
contracts but cannot be mixed into a 1.3 run.

## Required conformance cases

Conformance must cover empty/occupied archive cells, comparator ties, every
Pareto direction and exact margin, missing GenreIntent metrics, exact and
threshold-adjacent duplicates, render selection ties, exact/+1 frame budget,
cache and render-failure charge parity, patience reset/exhaustion, simultaneous
stop reasons, cancellation before and during render, completion-order shuffle,
and checkpoint/resume byte identity.
