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
chord-search, pair-relation, numeric-eval, exact-arithmetic, ordering, and total
counters; progression child
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

## Receipt traversal closure

The following rules override any more general wording in the Budget Contract
for GEN0-B compilation. Query-dependent GEN0-A exact-arithmetic actions,
including `PAIR_RATIO`, mirror into the active chord child. Domain
pre-enumeration arithmetic that is independent of a chord query remains a
root action with null child ID. Consequently chord-child usage contains
exactly `chord_search_nodes`, `pair_relations`, `numeric_eval_units`,
`exact_arithmetic_units`, `ordering_units`, and their checked sum
`total_logical_units`; its exact-arithmetic and ordering ceilings are each
500000. Candidate voice-projection sorts and top-K insertion ordering remain
mirrored into the active chord child.

A GEN0-A branch-and-bound node is charged once immediately after it is popped
from the canonical frontier and before any proof or hard-constraint check.
The root is the first such node. Enqueue and child generation are free. A
failed reservation emits no opcode and the popped node is not examined.
The root identity has `assigned_target_count=1` and its prefix contains the
query's fixed anchor pitch. It is the anchor partial node; no count-zero or
separate anchor node exists. Its children assign target ordinal 1 from the
canonical non-anchor placed pitches.

At enqueue time the implementation derives the frontier `lower_prefix` as an
uncharged, pure canonical-integer priority preview. This preview is not a
Budget Contract semantic numeric-function call, MUST NOT populate a logical
query value table, emits no opcode, and cannot eliminate or alter any
post-pop materialization or charge. Physical memoization is permitted only
when the observable logical stream remains exactly as if every prescribed
post-pop operation had executed. The preview key MUST equal the key obtained
from the subsequently materialized values; a mismatch is the operational
failure `DETERMINISM_VIOLATION`, and no authoritative artifact is published.

For progression, charge one state immediately before each candidate hard
check in occurrence then frozen-candidate order. Charge one edge for every
adjacent-layer Cartesian pair in canonical predecessor-outer,
current-candidate-inner order, before endpoint validity or reachability is
examined. Matching enumeration, matching metrics, and path-score integer
arithmetic are included in that edge action and emit no additional opcode.
Child/root execution order is the distinct GEN0-A tuple order followed by
progression-query order.

The complete charged-sort inventory, in execution order, is:

1. expanded harmony-occurrence records by the lowering tuple;
2. distinct GEN0-A keys by `(domain_hash,intent_hash,root_anchor)`;
3. each candidate's progression voices by the Progression voice key, in
   candidate/query order;
4. contiguous progression runs by
   `(first_start_tick,track_id,first_occurrence_id)`;
5. unique Project ResolvedChords by ID UTF-8 bytes;
6. Project HarmonyOccurrences by the global occurrence order;
7. raw chord-member records by the Melody Contract order; and
8. final Project events by the Project canonical event key.

For each item, `n<=1` emits no record and `n>1` charges
`n*ceil(log2(n))`. No other sort is charged. Already-canonical arrays, domain
lexicographic enumeration, permutations, matchings, dynamic-programming
ordering, and adjacency checks are uncharged. Item 3 and top-K insertion alone
carry the chord child ID; the other seven have null child ID. Top-K charges
`ceil(log2(K+1))` once per eligible complete candidate and has no final-sort
charge.

Standalone Project validation emits opcodes in these stages and orders:

A. `VALIDATE_COLLECTION_MEMBER`: collections `tracks`, `form`,
   `material_instances`, `resolved_chords`, `harmony_occurrences`, `events`,
   `mix`; arrays use stored order, mix uses track-ID UTF-8 key order, one per
   member.
B. `VALIDATE_REFERENCE`: material instances use `section_id,track_id` only;
   occurrences use `section_id,resolved_chord_id`; events use
   `track_id,section_id,source.material_instance_id`, non-null `chord_index`,
   then provenance `resolved_chord_id`, `active_resolved_chord_id`, and non-null
   `next_resolved_chord_id` in that schema-field order; mix keys reference
   tracks in UTF-8 order. Stop at the first missing reference. `material_id`
   and `realization_id` are deliberately excluded from standalone Project
   reference charging.
C. For events in stored order emit bounds, role, provenance-equation, and
   register opcodes; drums omit the last two.
D. For ResolvedChords in ID order emit one voice opcode per voice ordinal, one
   pair opcode per target `i<j`, then one hash-core opcode for each of the fixed
   19 ResolvedChord core fields in contract order.
E. Emit canonical-adjacency opcodes for `tracks`, `form`,
   `material_instances`, `resolved_chords`, `harmony_occurrences`, `events`,
   and `mix`, in that order, one per adjacent pair; `n<=1` emits none.

### Logical query value tables

Charges follow semantic materialization, not physical function calls. For each
distinct domain, visit pitches in canonical enumeration order, construct the
ratio with the prescribed exact opcodes, equave-reduce exactly once, share that
reduced value between complexity-bit and odd-limit tests, and call `ratio_mc`
exactly once. Later queries share this immutable domain table without charge.

For a chord query, materialize each target phase exactly once in target-ordinal
order and share it throughout that query. After charging a popped node, apply
the pre-pair checks in exact order: range; duplicate vector/voice identity;
spacing; span; bass. The bass proof reuses the domain table's absolute
`ratio_mc` and exact-height tie key and emits no additional numeric or exact
arithmetic charge. `BASS_VIOLATION` stops at this position without pair
materialization. Stop at the first failure. A node passing all five checks then
materializes relations from its new voice to assigned voices, in
existing-voice ordinal order. Each relation performs `PAIR_RATIO` once,
`EQUAVE_REDUCE` once, and `ratio_mc` once for the oriented error/crossing
value. At the start of the same relation materialization, compare the two
exact absolute ratios with exactly one charged `FRAC_COMPARE` (an exact tie is
broken by target ordinal), then perform exactly one separate `FRAC_DIV` of
`max_exact_absolute_ratio/min_exact_absolute_ratio` and `EQUAVE_REDUCE` it.
Complexity bits and odd limit share this stored unordered reduced ratio.
Later node checks and scoring reuse both stored values without another exact
or numeric operation. Spacing and span share the domain-table absolute value.
Then apply post-pair checks in exact
order: complexity; maximum error; RMS; ranking proof, again stopping at the
first failure.

The ranking proof applies only to a partial node. A complete node that passes
all hard checks and RMS is eligible: it always emits exactly one top-K
insertion ordering charge, is canonically inserted, and, when the resulting
list exceeds K, the final member is dropped. A complete candidate is never
rejected in advance as `WORSE_THAN_TOP_K`.

At every popped partial BnB node, compute lower-bound RMS exactly once from
stored pair errors. A complete node reuses that value when it is already the
final RMS; only a complete RMS containing previously absent pairs is evaluated
once. Complete scoring reuses stored target phases, pair values, complexity,
RMS, and maximum and performs no additional numeric evaluation. A hard
rejection materializes no later table entry. Logical table lookup, reuse,
memoization, and cache replay are uncharged; a physical implementation MUST
replay this same stream regardless of its caching strategy.

When a popped partial node has zero known pairs, its lower-bound RMS is the
constant integer zero and emits no numeric call, opcode, or charge. This
includes the root and any pair-free partial node. Only a positive known-pair
count invokes the once-per-node RMS operation described above.
