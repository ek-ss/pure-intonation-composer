# GEN0-B Compiler Lowering Contract 1.0

Status: normative for SongProgram 0.1 to Project 1.2 under
`gen0-progression-exact-v1`.

## Authority

A GEN0-B CompilerManifest MUST bind a separate progression resolver record:
build ID, `gen0-progression-exact/v1`, profile hash, `exact`, top-K in 1..24,
maximum voice motion, and crossing policy. These values are copied into every
ProgressionQuery; no default applies. The compiler build identity binds the
complete CompilerManifest, including both GEN0-A and GEN0-B resolvers.

## Occurrence expansion

After section offset, repeat, rhythm rotation, mapping, and gate scaling,
expand each HarmonyIntentCell step to
`{section_id,track_id,realization_id,repeat_ordinal,material_id,
source_step_ordinal,start_tick,duration_ticks,intent_id,intent_hash,root_anchor}`.
Duration is `max(1,RHE(source_duration*gate_scale_q/10000))`; root anchor is
material anchor plus section tonal center.

```text
occurrence_id = "hoc_" + base32lower_no_pad(SHA256(
  UTF8("cps.harmony-query-occurrence/v1\0") || canonical_json_LF(
    [section_id,realization_id,repeat_ordinal,material_id,source_step_ordinal]
  )
))[0:26]
```

ID collision fails `HARMONY_OCCURRENCE_ID_COLLISION`. Sort expanded records by
`(track_id UTF-8,start_tick,section_id UTF-8,realization_id UTF-8,
repeat_ordinal,source_step_ordinal)`.

## Query partition

Partition by track. In time order, overlap fails
`PROGRESSION_QUERY_CONTEXT_INVALID`, equality continues the current run, and a
gap starts a new maximal run. A section boundary does not split a contiguous
run. Every run, including one occurrence, becomes one query. Query order is
`(first_start_tick,track_id UTF-8,first_occurrence_id UTF-8)`.

Global Project occurrence order is `(start_tick,track_id UTF-8,section_id
UTF-8,occurrence_id UTF-8)` and assigns consecutive chord indices. Project 1.2
is retained; event track/chord relations independently validate this ordering.

## GEN0-A adapter

Resolve each distinct `(domain_hash,intent_hash,root_anchor)` once in tuple
order with manifest K, and reuse its immutable ordered top-K. Zero candidates
fails `NO_JOINT_CHORD_SOLUTION`. Build the complete Project ResolvedChord,
injecting the bound GEN0-A resolver build ID before core hash/ID derivation.
ResolvedChord parallel arrays remain shape-voice order. Progression projection
voices are derived from those arrays and sorted only by the Progression
Contract voice key. Candidate order is `(local RMS,local max,local complexity,
core_hash)`. Independently revalidate every projection field and hash.

Queries contain the complete candidate payload. A selected hash resolves
exactly once inside that query; external lookup, retuning, or fallback fails.

## Project lowering

Byte-copy selected chords. Deduplicate equal full cores by ID; equal ID with
unequal core fails `RESOLVED_CHORD_ID_COLLISION`; store unique chords in ID-byte
order. Store occurrences in global order. Emit harmony events in shape-voice
ordinal order using existing semantic-address, velocity, duration, and event-ID
rules. Query/result/score/receipt never enter Project identity.

## Evidence and receipts

The closed `cps.gen0b-compiler-evidence` 1.0 sidecar binds Program and
CompilerManifest hashes, expanded occurrence records, ordered GEN0-A query
summaries, complete ordered ProgressionQueries and Results, selected
occurrence/core/chord-index mappings, Project hash, and root receipt digest.
Its artifact domain is `cps.gen0b-compiler-evidence/v1`, omitting
`evidence_hash`. Query/result domains are `cps.progression-query/v1` and
`cps.progression-result/v1`.

CompileReport accepts `progression_states` and `progression_edges` error
counters. Budget usage and child receipts follow the Budget Contract. Cache
telemetry and worker behavior are deferred to the connected-cache contract.

GEN0-B uses CompilerManifest, ChargeReceipt, and CompileReport `1.1.0`.
Receipt children are all GEN0-A `chord_query` children in tuple order, then all
`progression_query` children in query order. Chord child usage contains exactly
chord-search, pair-relation, numeric-eval, and total counters; progression child
usage contains exactly progression-state, progression-edge, and total counters.
Root usage contains every counter; child totals are views of root reservations.

Logical opcode records are `{ordinal,phase,counter,charge,child_id}`. Root
ordinals are consecutive execution order. A child stream projects matching
root records and renumbers from zero. Stream hash uses
`cps.logical-opcode-stream/v1` with `stream_hash` omitted. Failed reservations
emit no opcode. A completed no-path search has a complete receipt and failed
CompileReport.

## Failure order

Program/schema; symbols/references; structural budget; temporal expansion;
occurrence collision/overlap; GEN0-A query; GEN0-A budget/no-solution;
candidate adapter; progression context; state/edge budget; score
overflow/no-path; selected-payload integrity; harmony lowering; remaining
material passes; final Project validation. Failure returns null Project, null
evidence, and the logical receipt accumulated before the failure.

## Canonical hashes, receipts, and context

Evidence is success-only. Every CompileReport failure has `project_hash:null`
and `evidence_hash:null`; reached queries and charges remain only in its
receipt. Artifact hash means SHA-256 of `UTF8(domain + "\0")` followed by
canonical JSON with final LF. CompilerManifest uses
`cps.compiler-manifest/v1.1`; ChargeReceipt uses
`cps.charge-receipt/v1.1`; evidence uses its domain above, each omitting its
own hash field only when that field exists. `root_receipt_digest` hashes the
complete root receipt. A child digest is the artifact hash under
`cps.charge-receipt-child/v1.1` of the exact embedded child record. GEN0-A
query hash is bare SHA-256 of canonical JSON with no final LF, matching the
existing chord-cache contract. Progression query/result hashes use their domains above; result hash
includes `path_hash`.

Root receipt `input_hash` is the artifact hash under `cps.compile-request/v1`
of `{song_program,compiler_manifest,instrument_catalog_digest}`. Child
`input_hash` is its query hash. Child ID is `chord_` or `progression_` followed
by the first 16 lowercase hex digits of that query hash. Child ordering is the
GEN0-A distinct tuple order followed by progression-run order; this overrides
generic query-ID sorting for GEN0-B compilation.

Child `total_logical_units` is the checked sum of that child's leaf counters.
Root total is the checked sum of all root leaf charges; child views are not
added again. A failed reservation creates a `status:failed` child containing
usage/stream through the last successful reservation. No-solution/no-path has
a complete child. Root receipt status is `failed` exactly when an atomic budget
reservation fails or arithmetic complexity prevents the next prescribed
opcode. Schema, semantic, no-solution, no-path, selected-integrity, lowering,
and final-validation failures have `complete` receipt status after executing
the prescribed stream through their first failure. Receipt status therefore
does not mirror CompileReport status.

Opcode phase mapping is exhaustive: canonical parse/symbol insertion is
`parse`/`symbols`; domain enumeration and its arithmetic is `domain`; GEN0-A
search and its numeric work is `chord`; progression states/edges are
`progression`; event creation is `events`; Project validation is `validation`;
every sort charge is `ordering` regardless of caller phase. Charges outside a
query have null child ID; query charges carry its child ID. Records with equal
counter/charge remain distinct by ordinal.

JSON-node structural charges are `parse`. Symbol inserts, scalar ID references,
form items, and material-instance records are `symbols`. Realized repeats,
source steps, transform/source-step and interaction/event products, temporal
calculations, anchor, anchor additions, direct lowering, and event emission are
`events`. Domain enumeration, VECTOR_RATIO, and its fraction/log operations are
`domain`; target assignment, PAIR_RATIO, pair evaluation, and GEN0-A nodes are
`chord`; matching and progression-score arithmetic are `progression`;
validation opcodes are `validation`; sort charges alone are `ordering`.
Only GEN0-A actions carry a chord child ID and only progression actions carry a
progression child ID; every other record has null child ID.

Harmony tracks require non-null ordered register bounds and
`maximum_polyphony <= 8`; otherwise fail `PROGRESSION_QUERY_CONTEXT_INVALID`
without repair. Query occurrence register/polyphony copy the track fields.
`overlapping_nonprogression_pitched_events` counts already expanded direct
pitched intervals on the same track intersecting the run half-open interval;
boundary contact is not overlap. Nonzero fails before progression search.
Temporal shadow expansion validates direct material/rhythm/realization
references, rotations, mapping, repeats, section containment, onset, and
duration before partitioning. Its failures occur at temporal expansion. Pitch
placement, register, IDs, and event emission remain later and do not affect it.

Manifest GEN0 budget profiles semantically require both progression counters
in root/child ceilings and progression occurrence/candidate shape limits;
absence is `COMPILER_MANIFEST_INVALID`. Tuple comparison is field order shown,
with vectors integer-lexicographic. Evidence resolved chord IDs use Project
ID-byte order; event IDs use Project event canonical order. Search statistics
are: distinct GEN0-A query count; complete assignments examined; eligible
complete assignments; progression run count; and successful state/edge
reservations, the last two equal receipt root counters.

Project `compiler.build_id` is the CompilerManifest `build_id`, which MUST be
`"cb_" + base32lower_no_pad(SHA256(UTF8("cps.compiler-build/v1\0") ||
canonical_json_no_LF(manifest with build_id omitted)))[0:26]`. Project hashing
then follows Arrangement Project 1.2. An arbitrary build ID is non-conforming.
