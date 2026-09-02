# SongProgram Mutation Application Contract 1.0

Status: normative for `cps.mutation` `1.0.0` and SongProgram `0.1.0`.

This document defines the complete meaning of the eight typed mutations. The
JSON schemas constrain representation; this contract constrains resolution,
ordering, dependency roots, locks, application, invalidation, and failures.
An implementation MUST NOT infer another operation, repair an invalid result,
or fall back to model text, process state, or an unbound catalog.

## 1. Authoritative inputs and output

An application request contains:

- one canonical, strictly valid SongProgram `0.1.0`;
- an ordered array of canonical Mutation `1.0.0` objects;
- a sorted unique array of locked scope roots;
- the exact MutationChoiceCatalog named by the active RunManifest;
- the exact InstrumentCatalog named by `SongProgram.production.catalog_digest`;
- the canonical action ID used for lineage derivation.

A scope root is `{kind,id}`. Kinds are `material`, `rhythm`, `chord_intent`,
`section`, `realization`, `track`, `production`, and `global_form`.
`global_form` has the sole valid ID `global_form`. Production profile mutations
use ID `production`; per-track production mutations use the track ID.

Success returns the canonical resulting SongProgram and an ordered impact
report. A batch is atomic: any failed mutation returns no resulting program and
no partially applied candidate. Diagnostics MAY include the failing zero-based
mutation ordinal and the last valid private-copy hash.

The applier never patches a compiled Project. The successful SongProgram is
compiled again through the bound compiler/resolver. Project impact in section
8 is the minimum invalidation set an incremental implementation MUST recompute;
a conforming implementation MAY recompile the whole Project.

## 2. Canonical sequential algorithm

For mutation ordinal `i`, operate on a fresh private copy of the result of
ordinal `i-1`:

1. validate the Mutation schema and canonical bytes;
2. require `operation == parameters.kind`;
3. hash the current private SongProgram and require exact equality with
   `base_program_hash`;
4. resolve every semantic ID and bound catalog by exact ID/digest;
5. validate the operation/owner/field compatibility and all normative bounds;
6. compute the actual root set from the pre-mutation program;
7. canonicalize `declared_scope` by sorting `(kind UTF-8,id UTF-8)`, rejecting
   duplicates, and require exact canonical-byte equality with the actual set;
8. reject if any actual root exactly equals a locked root;
9. reserve the mutation/application budget, when a bound budget profile has
   such a counter;
10. apply exactly one operation to the fresh copy;
11. canonicalize and strictly validate the complete SongProgram; and
12. compute its impact report and make it the current private program.

Thus mutation `i+1` binds the canonical program hash produced by mutation `i`.
All ID resolution and scopes are recomputed after every mutation. There is no
parallel interpretation, stale-base rebasing, automatic scope widening,
clamping, wrapping except where explicitly stated, or best-effort application.

Locks are root-exact, not transitive. For example, locking a material does not
implicitly lock its rhythm; a planner that needs both protected declares both
locks. Dependency closure controls invalidation, not lock expansion.

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
source section. Preserve their relative canonical order. Derive IDs as follows:

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

After root computation, closure is the least fixed point of these typed edges:

- rhythm -> materials whose `rhythm_id` names it;
- chord intent -> harmony materials whose `chord_intent_ids` contain it;
- material -> realizations whose `material_id` names it;
- section -> realizations whose `section_id` names it;
- track -> realizations whose `track_id` names it and its production mix entry;
- realization -> compiled material instances, chord occurrences, and events;
- global form -> every section at or after the first structurally changed
  section and all their realization descendants;
- production -> the named mix contribution, or all render contributions for
  `production/production`.

Traversal order is canonical root order followed by edge-target UTF-8 order.
Visited typed IDs are unique. Closure bytes and hashes, if persisted, are the
canonical array of `{kind,id}` in that traversal order; they do not alter the
root-exact lock rule.

## 6. Lineage effects

Existing material lineage and root hashes survive all eight operations. A
changed or duplicated compiled instance gets an edge whose operation is
`mutation/<operation>/<mutation_id>` as specified in the search artifacts
contract. Duplicate-section instances derive from the corresponding source
instance. Their `identity` is true because the musical core excludes semantic
ID and placement and is otherwise byte-identical. Delete removes the compiled
instances and their incident edges from the new LineageIndex.

No current v1 operation creates a material. The mutation-created lineage-root
preimage in the search artifacts contract is reserved for a future versioned
operation and MUST NOT be invoked by `edit_section`.

## 7. Failure codes and priority

Return the first applicable code in this order:

1. `MUTATION_SCHEMA_INVALID` — schema or canonical representation invalid;
2. `MUTATION_OPERATION_MISMATCH` — operation differs from parameter kind;
3. `MUTATION_BASE_HASH_MISMATCH` — current private program hash differs;
4. `MUTATION_REFERENCE_NOT_FOUND` — semantic target/predecessor missing;
5. `MUTATION_CATALOG_MISMATCH` — required catalog bytes/digest unavailable;
6. `MUTATION_CHOICE_UNRESOLVED` — choice lookup fails or is incompatible;
7. `MUTATION_PARAMETER_INVALID` — pairing, bound, dimension, index, or value invalid;
8. `MUTATION_SCOPE_MISMATCH` — declared and actual root arrays differ;
9. `MUTATION_LOCKED` — an actual root is locked;
10. `MUTATION_BUDGET_EXHAUSTED` — atomic reservation fails;
11. `MUTATION_ID_COLLISION` — a derived section/realization ID exists;
12. `MUTATION_RESULT_INVALID` — canonicalized complete SongProgram is invalid.

A failing operation consumes no semantic budget except where the governing
Budget Contract explicitly defines attempt charging. It never emits a candidate.

## 8. Project impact report

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

If a field is not represented in Project 1.2 (currently development stage and
production profile), only `source_program.hash` plus downstream consumers of
that SongProgram field change. An incremental compiler MUST NOT fabricate a
Project field to expose it.

## 9. Required conformance coverage

The conformance pack MUST contain, for every operation: one golden success,
one negative parameter case, one exact-scope and one scope-mismatch case, one
lock case, and one boundary case. It MUST additionally cover sequential base
hash rebinding, atomic batch rollback, duplicate/delete lineage, derived-ID
collision, catalog mismatch, cache parity, and cross-process canonical-byte
equality against an independent oracle.
