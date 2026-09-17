# PIL Synthetic Provisional Authority Contract 1.0

## 1. Purpose and authority boundary

This contract defines a synthetic LLM cohort used to produce reproducible,
provisional PIL calibration evidence. It is an audit aid, not listener
research. Every artifact declares `authority_kind: synthetic_llm`; cohort,
set, summary, and decision artifacts declare `authority_effect: audit_only`.
Every artifact fixes `human_authority_compatible: false`.
No artifact in this family is human-listener evidence or a PIL promotion
authority.

The final artifact is `cps.pil-synthetic-provisional-decision` 1.0. Its status
is always `synthetic_provisional`, `promotion_eligible` is always false, and it
cannot appear in a run context slot that requires `cps.pil-calibration-decision`.
It does not change Native JI, search acceptance, rejection, archive admission,
or QD axes.

## 2. Closed artifact chain

The dependency order is:

1. `cps.pil-synthetic-protocol-manifest` binds provider, exact model snapshot,
   reasoning effort, prompt, input/output schemas, and evaluation policy.
2. Each `cps.pil-synthetic-agent-manifest` binds that protocol, an independent
   seed, and the execution environment.
3. `cps.pil-synthetic-cohort-manifest` binds the unique agent manifests.
4. `cps.pil-synthetic-blind-assignment-set` deterministically binds every
   agent/context pair to an opaque item ID and presentation ordinal.
5. Each `cps.pil-synthetic-raw-response-record` binds exactly one assignment,
   a sealed PIL context,
   request bytes, provider response bytes, and closed ordinal judgments.
6. `cps.pil-synthetic-judgment-set` binds the cohort, assignment set, response records,
   partition membership, and zero partition leakage.
7. `cps.pil-synthetic-evidence-summary` binds the judgment set, existing PIL
   metric registry, evaluation policy, deterministic aggregation, and evidence.
8. `cps.pil-synthetic-provisional-decision` binds the complete chain and records
   only provisional metric results.

The eight evidence-chain schemas and the separate audit-binding schema are the
`pil_synthetic_*.schema.json` files in the conformance
schema directory. All are closed Draft 2020-12 schemas. Artifact self hashes
use the existing `cps-artifact-hash/v1` rule with only the named self-hash
member removed. Decision hashing uses the domain
`cps.pil-synthetic-provisional-decision/v1`.

## 3. Permitted model task

An agent may judge semantic or stylistic evidence in an already sealed PIL
context. It must not calculate or replace frequency, cents, segmentation,
pitch support, chord matching, voice matching, trajectory, or Phase 5 numeric
similarity. Provider prose and hidden model state are non-normative. The raw
provider response is bound by hash, while authority contains only the closed
ordinal labels in the response record.

The protocol requires `input_modality: audio_pcm` and `audio_capable: true`.
Feature-only or text-only judgments are not listener-equivalent evidence and
must not enter this chain. Generator and judge model-family hashes must differ.
The protocol also fixes the minimum agent quorum.

The runner and validator use the fixed mapping `strongly_below=0`,
`below=2500`, `borderline=5000`, `above=7500`, and `strongly_above=10000`,
then apply `ordinal-label-median-q/v1`. An even median uses round-half-to-even.
Missing or
unavailable evidence remains unavailable; it is never replaced by zero.
Quorum is evaluated independently for every metric using distinct agent
manifest hashes; retries and multiple contexts from one agent never increase
that metric's agent quorum.

## 4. Separation from external authority

The synthetic chain must never use `ListenerCohortManifest`, an `*_external`
scope, `status: promoted`, or a human calibration decision schema. Conversely,
the external PIL authority intake must reject every synthetic schema even when
metric rows and hashes otherwise resemble a human authority bundle.

Synthetic bundles are stored under a separate content-addressed namespace and
selected only through an explicitly synthetic audit interface. There is no
implicit conversion from a provisional decision to an external decision.

## 5. Determinism and intake

Canonical JSON is NFC, sorted-key, compact UTF-8 with integers only and no
trailing LF. Agent hashes sort ascending in a cohort; response-record hashes
sort ascending in a judgment set; metric rows and IDs sort by UTF-8 metric ID.
Counts must equal their bound arrays and all scope, protocol, cohort, registry,
policy, context, evidence, and self-hash links are recomputed at intake.

For each agent, context order is the ascending digest order defined by
`cps.pil-synthetic-order/v1`. Opaque IDs use
`cps.pil-synthetic-opaque-item/v1`; assignment IDs use
`cps.pil-synthetic-assignment/v1`. Neither worker count nor dispatch order is
an input. Replay regenerates the complete Cartesian agent/context assignment
and requires byte-equivalent canonical content. A response whose assignment,
agent, or sealed context does not match is rejected.

The runner creates artifacts; intake only validates and atomically copies
complete bundles. Intake must not call a model, synthesize missing evidence,
repair hashes, or relabel synthetic evidence as human evidence.

Stored-response intake is rooted at `cps.pil-synthetic-bundle-index`. The
index lists every agent and response identity in sorted order and binds all
single chain artifacts. Intake resolves only hash-derived member paths,
replays the complete validator, receives expected bindings from outside the
untrusted bundle, and writes atomically beneath the distinct
`synthetic-audit/sha256` namespace. Re-intake of identical content is
idempotent; a receipt mismatch at the same address is a collision failure.

Fresh calls cross only the provider-neutral judge boundary. The adapter
receives the sealed PCM bytes, an opaque item ID, and a closed request without
genre labels, filenames, reference IDs, scores, SongProgram data, or planner
commentary. It may return only canonical `cps.pil-synthetic-judge-response`
JSON. Free text, extra fields, duplicate or unordered metrics, invalid
availability semantics, and noncanonical bytes fail the trial. There is no
automatic retry: a later call is a new response artifact and never an extra
vote for the failed trial. Remote fresh-call bytes are not a conformance target;
stored-response replay is.

## 6. SearchLoop binding

`cps.pil-synthetic-audit-binding` is an out-of-band sidecar over an immutable
SearchLoop13 `context_hash`; it is deliberately not one of the 32 authoritative
RunContext slots. It binds the provisional decision and blind assignment set.
The only permitted uses, in canonical order, are `human_review_selection`,
`planner_diagnostics`, `shadow_archive`, and `soft_reranking`. GEN0 gates, hard
validity, production archive admission, production stopping, and every
`native_ji.*` result reject this binding.

Soft reranking is separately bound by
`cps.pil-synthetic-soft-reranking-policy`. Its ordered metric list is compared
lexicographically; unavailable values sort after available values, direction
is explicit per metric, and the sealed context hash is the final tie-break.
The output is a `cps.pil-synthetic-soft-reranking-result` with
`authority_effect: audit_only` and a `shadow_order`. It cannot replace the
production candidate order or an archive-admission decision.
