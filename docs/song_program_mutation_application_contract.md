# SongProgram Mutation Application Contract 1.1

Status: normative for `cps.mutation` `1.0.0` and SongProgram `0.1.0`.

This document defines the complete meaning of the eight typed mutations. The
JSON schemas constrain representation; this contract constrains resolution,
ordering, dependency roots, locks, application, invalidation, and failures.
An implementation MUST NOT infer another operation, repair an invalid result,
or fall back to model text, process state, or an unbound catalog.

## 1. Authoritative inputs and output

The machine form is `cps.mutation-application-request` `1.0.0`. It contains:

- `contract = cps-mutation-application/v1`;
- SHA-256 hashes of this contract's exact checked-in UTF-8 bytes and the raw
  Mutation, request, impact, and receipt schema bytes;
- one canonical, strictly valid SongProgram `0.1.0` and its hash;
- an ordered array of canonical Mutation `1.0.0` objects;
- a sorted unique array of locked scope roots;
- the complete active RunManifest and its hash;
- the exact MutationChoiceCatalog and digest named by that RunManifest;
- the exact InstrumentCatalog named by `SongProgram.production.catalog_digest`;
- the canonical action ID used for lineage derivation.

A scope root is `{kind,id}`. Kinds are `material`, `rhythm`, `chord_intent`,
`section`, `realization`, `track`, `production`, and `global_form`.
`global_form` has the sole valid ID `global_form`. Production profile mutations
use ID `production`; per-track production mutations use the track ID.

All payloads are inline; v1 performs no external lookup. Recompute and compare
the RunManifest (`cps.search-run-manifest/v1`), choice catalog
(`cps.mutation-choice-catalog/v1`), and instrument catalog
(`cps.instrument-catalog/v1`) digests. Request fields, RunManifest,
SongProgram, and recomputed values MUST agree. RunManifest binds the Mutation
schema hash. InstrumentCatalog binds to the request and SongProgram production
digest (RunManifest 1.2 has no instrument-catalog field). `action_id` is an
opaque schema-valid audit identifier in v1; action-coordinate verification is
the enclosing search runner's responsibility.

Success returns the canonical resulting SongProgram, MutationImpactReport, and
MutationApplicationReceipt. A batch is atomic: failure returns no resulting
program and no impact report. Private prefix hashes in a failure receipt are
audit-only and MUST NOT be published as candidates.

For any domain `D` and JSON value `V`, `artifact_hash(D,V)` is exactly
`"sha256:" + hexlower(SHA256(UTF8(D + "\0") || canonical_json_with_final_LF(V)))`.
Request, scope, closure, step impact, impact report, and receipt use domains
`cps.mutation-application-request/v1`,
`cps.mutation-scope/v1`, `cps.mutation-closure/v1`,
`cps.mutation-impact/v1`, `cps.mutation-impact-report/v1`, and
`cps.mutation-application-receipt/v1`. `scope_hash` hashes `actual_roots`;
`closure_hash` hashes `{closure_before,closure_after}`; `impact_hash` hashes the
complete impact entry; `mutation_hash` hashes the complete Mutation object.
Receipt identity hashes the complete receipt with `receipt_hash` omitted.
Mutation identity uses `cps.mutation/v1`. Raw file hashes have no domain prefix
and hash the exact checked-in bytes.

The applier never patches a compiled Project. The successful SongProgram is
compiled again through the bound compiler/resolver. Project impact in section
8 is the minimum invalidation set an incremental implementation MUST recompute;
a conforming implementation MAY recompile the whole Project.

## 2. Canonical sequential algorithm

For mutation ordinal `i`, operate on a fresh private copy of the result of
ordinal `i-1`:

1. validate the Mutation schema and canonical bytes (the request envelope
   intentionally treats mutation items as opaque objects so this produces an
   ordinal failure receipt);
2. require `operation == parameters.kind`;
3. hash the current private SongProgram and require exact equality with
   `base_program_hash`;
4. validate compatibility that requires no semantic ID lookup;
5. resolve semantic IDs in this operation order: scalar/choice `owner_id`;
   transpose/root-anchor `material_id`; rotate `rhythm_id`; chord reference
   `chord_intent_id`; edit `section_id` then non-null `insert_after_section_id`;
   swap `track_id` then `instrument_id`. Resolve catalog entries next,
   then validate dynamic bounds and dimensions;
6. compute the actual root set from the pre-mutation program;
7. canonicalize `declared_scope` by sorting `(kind UTF-8,id UTF-8)`, rejecting
   duplicates, and require exact canonical-byte equality with the actual set;
8. reject if any actual root exactly equals a locked root;
9. detect a derived-ID collision;
10. apply exactly one operation to the fresh copy;
11. canonicalize and strictly validate the complete SongProgram; and
12. compute before/after closure and impact, append its receipt step, and make
    it the current private program.

Thus mutation `i+1` binds the canonical program hash produced by mutation `i`.
All ID resolution and scopes are recomputed after every mutation. There is no
parallel interpretation, stale-base rebasing, automatic scope widening,
clamping, wrapping except where explicitly stated, or best-effort application.

Locks are root-exact, not transitive. For example, locking a material does not
implicitly lock its rhythm; a planner that needs both protected declares both
locks. Dependency closure controls invalidation, not lock expansion.

Mutation application v1 consumes no OperationBudgetLedger counter. Schema
bounds make it finite; operational limits cannot change semantic output. Any
future charging requires versioned contract, schema, and budget-profile changes.

## 3. Actual roots and compatibility table

The following table is exhaustive. The listed roots, sorted canonically, are
the required `declared_scope`.

| Operation and target | Actual roots |
|---|---|
| scalar `section.bars` | `section/<owner_id>`, `global_form/global_form` |
| scalar `realization.velocity_scale_q` or `gate_scale_q` | `realization/<owner_id>` |
| scalar `production.gain_q` or `pan_q` | `production/<owner_id>` where owner ID is a track ID |
| choice `section.role` or `development_stage` | `section/<owner_id>` |
| choice `material.mapping` | `material/<owner_id>` |
| choice `track.role` | `track/<owner_id>` |
| choice `production.profile_id` | `production/production` and owner ID MUST be `production` |
| `transpose_material_vector` | `material/<material_id>` |
| `rotate_rhythm` | `rhythm/<rhythm_id>` |
| `replace_chord_intent_reference` | `chord_intent/<chord_intent_id>` |
| `replace_root_anchor_item` | `material/<material_id>` |
| `edit_section` | `section/<section_id>`, `global_form/global_form` |
| `swap_track_catalog_entry` | `track/<track_id>` |

Scalar parameter bounds MUST equal, not merely lie within, these field bounds:
`bars [1,32]`, `velocity_scale_q [0,10000]`, `gate_scale_q [1,10000]`,
`gain_q [0,10000]`, and `pan_q [-10000,10000]`. `value` must be within the
matching interval. Any other owner/field pairing is invalid.

## 4. Operation semantics

### 4.1 `replace_bounded_scalar`

Replace only the named scalar. Production track lookup is
`production.tracks[owner_id]`; absence rejects. No numeric coercion or clamp is
performed.

### 4.2 `replace_distribution_choice`

Resolve exactly as specified by `song_program_search_artifacts_contract.md`
section 6 and replace only the named field. `material.mapping` requires a
`direct_vector_cell`, `melody_intent`, or `harmony_intent_cell`; a RhythmCell
rejects. The resolved value must satisfy the target SongProgram field schema.
Changing a role does not repair track/material relationships; strict final
validation decides validity.

### 4.3 `transpose_material_vector`

The target MUST be `direct_vector_cell` or `harmony_intent_cell`. Add
`vector_delta[j]` to every component `j` of every `vectors` item or every
`root_anchors` item respectively. Delta dimension MUST equal the lattice
generator count and every target vector dimension. MelodyIntent and RhythmCell
reject. Do not equave-wrap, normalize, or clamp; an out-of-schema result rejects.

### 4.4 `rotate_rhythm`

Use the rhythm-derived invariant quantum and ordering defined in
`song_program_search_artifacts_contract.md` section 6. This operation changes
only `steps[].at_tick` and their canonical array order; duration, accent, and
lane remain attached to their source step.

### 4.5 `replace_chord_intent_reference`

Reduce `reference_equave` to lowest positive terms. Require
`0 <= step < divisions` for every supplied step; negative or out-of-range steps
reject rather than wrap. Sort steps numerically ascending and reject duplicates.
Replace `reference` with `{temperament:"edo",equave,divisions,steps}` and leave
voicing, recognition, and complexity budget unchanged. If
`bass_policy == "preserve_target"`, `bass_target_ordinal` MUST be non-null and
less than `steps.length`; otherwise final validation rejects.

### 4.6 `replace_root_anchor_item`

The target MUST be `harmony_intent_cell`; `index` MUST exist and `vector`
dimension MUST equal the lattice generator count. Replace that one array item.
Do not normalize, reorder, or modify another anchor.

### 4.7 `edit_section`

For `delete`, `insert_after_section_id` MUST be null. Remove the named section
and every realization whose `section_id` names it. Deleting the sole section
rejects. Materials, rhythms, chord intents, and tracks are not garbage-collected.

For `duplicate`, source and insertion predecessor MUST exist and
`insert_after_section_id` MUST be non-null. Copy the section, insert the copy
immediately after the named predecessor, and copy every realization of the
source section. Rebuild `realizations` in existing array order: emit each
original and then its derived copy when it belongs to the source section.
Arrays are not subsequently sorted. Derive IDs as follows:

```text
section_id = "sec_" + base32lower_no_pad(SHA256(
  UTF8("cps.mutation-section-id/v1\0") || UTF8(mutation_id) || NUL ||
  UTF8(source_section_id)
))[0:20]

realization_id = "real_" + base32lower_no_pad(SHA256(
  UTF8("cps.mutation-realization-id/v1\0") || UTF8(mutation_id) || NUL ||
  UTF8(source_realization_id)
))[0:20]
```

Set each copied realization's `section_id` to the derived section ID; all other
fields stay byte-equivalent except its derived `id`. Any derived-ID collision
rejects. Duplication does not copy materials or create a new lineage root.

### 4.8 `swap_track_catalog_entry`

Require the bound catalog digest to equal `production.catalog_digest`, resolve
the instrument ID exactly, and replace only `track.instrument_id`. A `drums`
track requires a `drum_kit` entry and every note selected by its non-null
`drum_map` MUST exist in that entry's note map. Every other role requires a
`pitched` entry. No catalog fallback or role rewrite is allowed.

## 5. Dependency closure

Mutation closure contains SongProgram entities only. Compute
`closure_before` from the pre-mutation program and `closure_after` from the
post-mutation program. Both include every actual root even when an
operation-owned entity is absent on that side, then take the least fixed point:

- rhythm -> materials whose `rhythm_id` names it;
- chord intent -> harmony materials whose `chord_intent_ids` contain it;
- material -> realizations whose `material_id` names it;
- section -> realizations whose `section_id` names it;
- track -> realizations whose `track_id` names it and its production mix entry;
- global form -> every section at or after the first structurally changed
  section and all their realization descendants;
- production -> no further SongProgram entity.

Closure output is the unique visited set sorted by `(kind UTF-8,id UTF-8)`;
traversal order is unobservable. Duplicate post-closure contains derived
section/realizations through `global_form`; delete retains removed entities
only in pre-closure. Closure does not alter the root-exact lock rule.

The track edge emits `{kind:"production",id:track_id}`. The global-form start
index is the target section index for bars/delete. For duplicate it is the
insertion boundary immediately after the predecessor: in the pre-form it is
`predecessor_index+1`, and in the post-form it is the derived section index.
All sections from that boundary onward are adjacent to global form.

## 6. Lineage effects

Existing material lineage and root hashes survive all eight operations.
LineageIndex edge creation/removal is compiler responsibility and is not part
of pure Mutation output. Impact marks `lineage_index` when recompilation must
reproduce changed mappings or edges.

No current v1 operation creates a material. The mutation-created lineage-root
preimage in the search artifacts contract is reserved for a future versioned
operation and MUST NOT be invoked by `edit_section`.

## 7. Failure codes and priority

Return the first applicable code in this order:

1. `MUTATION_SCHEMA_INVALID` — schema or canonical representation invalid;
2. `MUTATION_OPERATION_MISMATCH` — operation differs from parameter kind;
3. `MUTATION_BASE_HASH_MISMATCH` — current private program hash differs;
4. `MUTATION_PARAMETER_INVALID` — statically invalid pairing or parameter;
5. `MUTATION_REFERENCE_NOT_FOUND` — semantic target/predecessor/entry missing;
6. `MUTATION_CHOICE_UNRESOLVED` — a correctly bound choice catalog has no
   exact compatible choice;
7. `MUTATION_PARAMETER_INVALID` — dynamically invalid bound, dimension,
   index, role, note map, or value;
8. `MUTATION_SCOPE_MISMATCH` — declared and actual root arrays differ;
9. `MUTATION_LOCKED` — an actual root is locked;
10. `MUTATION_ID_COLLISION` — a derived section/realization ID exists;
11. `MUTATION_RESULT_INVALID` — canonicalized complete SongProgram is invalid.

Before ordinal processing validate, in order: request schema/canonical form;
RunManifest hash/schema; base Program hash/validity; choice catalog
digest/binding; instrument catalog digest/binding; locked-root canonicality.
Failures are `MUTATION_REQUEST_INVALID`, `MUTATION_RUN_MANIFEST_MISMATCH`,
`MUTATION_BASE_HASH_MISMATCH`, `MUTATION_CHOICE_CATALOG_MISMATCH`,
`MUTATION_INSTRUMENT_CATALOG_MISMATCH`, and `MUTATION_LOCKS_INVALID`.
Within an ordinal use the numbered order; resolve semantic IDs in schema field
order. Missing swap instrument is `MUTATION_REFERENCE_NOT_FOUND`; role or note
map mismatch is `MUTATION_PARAMETER_INVALID`. Failure emits no candidate.

## 8. Project impact report

An entry is identity exactly when before and after Program hashes are equal.
Identity succeeds with ordinary roots/closures but empty component arrays.
Batch identity is the AND of entry identities even when non-identity steps
eventually restore the base hash.

Non-identity entries list exactly those top-level SongProgram components whose
canonical values differ before/after, tested in this order:
`form,tracks,materials,chord_intents,realizations,production`, Project
components from `source_program_hash,form_clock,form_metadata,track_records,
mix,material_instances,resolved_chords,harmony_occurrences,events`, and
downstream components from `lineage_index,render_stems,render_mix,
audio_evaluation,descriptors`. Arrays use this declared order. Components are
listed even when this input would compile zero members of that collection.

Every non-identity successful mutation changes `Project.source_program.hash`
and therefore the Project artifact hash. The impact report additionally lists
these minimum semantic paths:

| Mutation | Minimum Project recomputation |
|---|---|
| section bars, edit section | form/clock; changed and following timing; descendant instances, occurrences, events |
| realization velocity/gate | that realization's occurrences/events and render contribution |
| production gain/pan | named mix entry, stem/mix render hashes, audio evaluation |
| production profile | production-bound render/evaluation configuration |
| section role/development stage | form metadata and form-derived descriptors |
| material mapping, transpose, root anchor | descendant instances/events; harmony also occurrences/resolved chords |
| rhythm rotation | referring material descendants, instances, occurrences, events |
| chord reference | referring harmony occurrences, resolved chords, events |
| track role | track record, descendant compilation constraints and descriptors |
| catalog swap | track instrument, stem/mix render hashes and audio evaluation |

The table is encoded as follows: section bars/edit add `form_clock`; section
role/development and edit add `form_metadata`; track role/swap add
`track_records`; gain/pan add `mix`. Section bars/edit, material
mapping/transpose/root, rhythm, chord-reference, and track-role changes add
`material_instances,resolved_chords,harmony_occurrences,events,lineage_index`.
Realization velocity/gate adds `harmony_occurrences,events,lineage_index`.
Every operation except section role/development adds render stems/mix and audio
evaluation. Every operation except production gain/pan, production profile,
and catalog swap adds descriptors. Every non-identity entry includes
`source_program_hash`; production profile adds only render/downstream items.

If a field is not represented in Project 1.2 (currently development stage and
production profile), only `source_program.hash` plus downstream consumers of
that SongProgram field change. An incremental compiler MUST NOT fabricate a
Project field to expose it.

## 9. Receipt

Impact entries are mutation-ordinal order. MutationApplicationReceipt is a
cache-neutral semantic audit artifact, not a ChargeReceipt. It binds request,
each attempted mutation, input/output Program hashes, scope/closure/impact
hashes, final result/impact hashes on success, and only the first failure on
failure. It contains no cache source, worker count, telemetry, or budget usage.
An identity step is explicit. On batch failure, `result_program_hash` and
`impact_report_hash` are null; successful prefix step hashes are audit-only.

For a complete receipt, steps are consecutive `0..mutations.length-1`, every
step is complete, top-level error is null, result/impact hashes are non-null,
step hashes chain from base to result, impact entry count equals step count,
and report identity is the AND of step identity. For failure during request
preflight, steps is empty and top-level error has null ordinal. For ordinal
failure, steps contains all successful prefixes plus exactly one failed step;
its error equals the top-level error byte-for-byte. Fields become non-null only
after their phase succeeds: mutation hash after item canonicalization; actual
roots/scope hash after root construction; both closures only after successful
application/validation; output hash, identity, and impact hash only for a
complete step. Failure receipts have null result/impact hashes. Arrays marked
ordered by this contract reject duplicates or any other ordering even where
JSON Schema can express only uniqueness.

## 10. Required conformance coverage

The conformance pack MUST contain, for every operation: one golden success,
one negative parameter case, one exact-scope and one scope-mismatch case, one
lock case, and one boundary case. It MUST additionally cover sequential base
hash rebinding, atomic batch rollback, duplicate/delete lineage, derived-ID
collision, catalog mismatch, cache parity, and cross-process canonical-byte
equality against an independent oracle.
