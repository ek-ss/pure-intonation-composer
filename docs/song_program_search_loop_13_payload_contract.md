# SearchLoop13 payload envelopes

**Status:** normative for Group A only. Evaluation, compile-only/cache, and
cancellation-inbox payloads remain SPEC-BLOCKER until later groups define their
closed schemas and failure precedence.

All envelopes are `1.0.0`, closed objects, and self-hash by
`cps-artifact-hash/v1\0 || schema || \0 || schema_version || \0 || canonical_json`
with only their named self-hash omitted. Producer payload bytes are not copied:
their hash and producer schema hash are causal inputs. A mismatched context,
producer schema, or self hash is terminal `CONTEXT_BINDING_MISMATCH`.

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
objects, its `proposal_hash`, and null diagnostic. `proposal_hash` hashes the
canonical proposal array in domain `cps.planner-mutation-proposal` version
`1.0.0`. A later phase-1 MutationApplicationRequest binds `response_hash` and
`proposal_hash`; PlannerResponse MUST NOT name that future request. Failure has
null proposal and proposal hash and one frozen diagnostic. This list is also
the mandatory first-failure-wins validation precedence: `REQUEST_INVALID`,
`CONTEXT_MISMATCH`, `MANIFEST_MISMATCH`, `SOURCE_MISMATCH`,
`REQUEST_TOO_LARGE`, `PROVIDER_UNAVAILABLE`, `TIMEOUT`, `RESPONSE_TOO_LARGE`,
`RESPONSE_SCHEMA_INVALID`, `OPERATION_NOT_ALLOWED`, `MUTATION_COUNT_INVALID`,
`RESULT_INVALID`. Rationale and raw provider output are forbidden. Provider
text, exception text, latency, timestamps, and retry counts are forbidden.
Planner-null creates neither request nor response. Committing PlannerRequest
consumes one planner call; producing or replaying PlannerResponse consumes none.
