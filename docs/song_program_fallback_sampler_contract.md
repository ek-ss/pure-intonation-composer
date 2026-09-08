# Deterministic Fallback and Broad-Prior Production Contract v1

**Status:** normative for the first deterministic search runner.

This contract closes the two remaining generation boundaries: producing typed
mutations when the model planner is unavailable, and lowering broad-prior role
choices to tracks and static production. Neither process may invent notes,
repair invalid music, read model prose, or use process-global randomness.

## 1. Independent random domains

Fallback and initial sampling never share a stream or rejection counter.

```text
fallback domain: cps.mutation-fallback/v1
fallback counter: fallback_attempt_ordinal, local to one action coordinate

production domain: cps.broad-prior-production/v1
production counter: production_rejection_ordinal, local to one sampler seed
```

A choice digest is the first unsigned big-endian 64 bits of:

```text
SHA256(UTF8(domain + "\0") || u64be(root_seed) || canonical_json(path))
```

Fallback paths are `[run_manifest_hash,round,candidate,fallback_attempt_ordinal,
mutation_ordinal,decision_kind,...selected_prefix]`; the selected prefix is
empty for the operation draw and then contains, in order, operation,
owner-kind, owner-ID, and field-or-index as those values become available.
Production paths are
`[sampler_manifest_hash,production_rejection_ordinal,"production",role,field]`.
Tables sort entries by canonical value bytes. Selection is `u64 mod
sum(positive weights)` over the cumulative weights of eligible entries. Zero
weights and duplicate values reject the manifest. Filtering rebuilds the
cumulative table from original weights; it does not renormalize stored values.

## 2. Fallback manifest

The closed machine form is
`backend/songprogram_conformance/schemas/fallback_manifest.schema.json`.
It binds the PlannerManifest, Mutation schema, MutationChoiceCatalog, and
Mutation Application Contract. It MUST NOT bind the RunManifest: RunManifest
binds this manifest, so the reverse edge would make content addressing cyclic.
The request binds both hashes. The eight operations and initial weights are:

| operation | weight |
|---|---:|
| replace_bounded_scalar | 24 |
| replace_distribution_choice | 10 |
| transpose_material_vector | 12 |
| rotate_rhythm | 22 |
| replace_chord_intent_reference | 8 |
| replace_root_anchor_item | 10 |
| edit_section | 6 |
| swap_track_catalog_entry | 8 |

Parameter tables are complete and hash-covered. Scalar tables contain exact
field/value choices; choice values use catalog choice IDs; transposition and
root-anchor deltas are signed unit vectors; chord references are complete EDO
references; edit actions are `duplicate` or `delete`; instruments are catalog
entry IDs.

Every manifest, request, result, eligible table, selected value, profile, drum
map, and trace artifact uses the Search Artifacts canonical JSON. Its digest is
`sha256:` plus SHA-256 over `UTF8(type_domain + "\0") ||
canonical_json(object_without_its_hash_field)`. Domains are
`cps.fallback-manifest/v1`, `cps.fallback-request/v1`,
`cps.fallback-result/v1`, `cps.fallback-eligible-table/v1`,
`cps.fallback-selected-value/v1`, `cps.production-profile/v1`,
`cps.drum-map-profile/v1`, `cps.production-lowering-manifest/v1`,
`cps.production-lowering-request/v1`, and
`cps.production-lowering-result/v1`. Every referenced hash is recomputed.
Every fallback or production trace `path_hash` is
`artifact_hash("cps.choice-path/v1", {"path": path})`; hashing the bare path
array, its displayed text, or the random-choice preimage is non-conforming.

Weighted tables sort by canonical value bytes, contain no duplicate value, and
have each weight and their checked sum in `1..2^64-1`. Eligible mutation tuples
sort by `(operation_ordinal, owner_kind UTF-8, owner_id UTF-8,
field_or_index_canonical_bytes, parameter_canonical_bytes)`. Scalar values must
satisfy table and owning-field bounds. Vectors have the target dimension and
exactly one `-1` or `1` component, all others zero. Chord steps are strictly
increasing and less than divisions. A violation rejects before any draw.

`rotate_rhythm` never stores or samples a tick delta. Its only parameter is
`ordinal_steps` from `[-4,-3,-2,-1,1,2,3,4]`. Resolve the target rhythm's
invariant quantum `q` using the Mutation Application Contract, then compute
`ticks_delta = ordinal_steps * q`. The candidate is ineligible if
`ticks_delta mod length_ticks == 0`. The emitted Mutation stores ordinal steps;
the applier derives ticks from the same bound rhythm and quantum.

## 3. Fallback algorithm

Validate the closed request, all raw hashes and bindings, base program hash,
canonical sorted locks, action coordinate, and `requested_mutation_count` in
`1..manifest.maximum_mutations`. For each mutation ordinal:

1. Build every operation's eligible target/parameter tuples in the operation
   order above. Apply static schema compatibility, dynamic bounds, vector
   dimensions, catalog compatibility, non-identity, and derived-ID collision
   checks.
2. Compute actual roots exactly as Mutation Application Contract 1.1. Remove a
   tuple if any actual root exactly equals a lock. Dependency closure never
   expands a lock.
3. Choose operation, owner kind, owner ID, field/index, then value from their
   separate path-addressed choices.
4. Emit canonical `declared_scope` equal to the sorted actual roots and bind
   `base_program_hash` to the current private program.
5. Apply through the normative mutation applier. On success, canonicalize the
   program and rebuild eligibility for the next ordinal.

The batch is atomic and sequential. One attempt selects one complete eligible
tuple for the current mutation ordinal. Identity or a mutation core already
emitted by this request consumes one attempt and increments the single
candidate-wide `fallback_attempt_ordinal`; success also consumes one attempt.
All draws for an attempt use that ordinal and path-local counter zero. The
ordinal starts at zero and must be below `maximum_attempts_per_candidate`
before a draw; reaching the ceiling permits no next draw. Other failures do not
retry. Success requires exactly `requested_mutation_count` mutations. An
applier rejection after eligibility is contract drift and terminates.

At every stage first filter complete eligible rows by the already selected
prefix, then rebuild the cumulative table. Operation choices retain their
manifest operation weights, but operations with no remaining row are omitted.
Distinct `owner_kind`, `owner_id`, and `field_or_index` tokens each have weight
one and sort by canonical token bytes. Parameter choices use the weight of their
raw manifest row. Their paths append the selected operation and the complete
selected prefix, so no two stages or prefixes share a draw. Vector parameter
rows are eligible only when their length equals `D =
len(current_program.lattice.generators)`.

`mutation_id` is `mut_` plus the first 20 base32lower-no-pad characters of
`SHA256(UTF8("cps.fallback-mutation-id/v1\0") ||
UTF8(fallback_request_hash) || u64be(round) || u64be(candidate) ||
u64be(fallback_attempt_ordinal) || u32be(mutation_ordinal) ||
canonical_json_with_final_LF(mutation_core))`. The core is the complete Mutation
object with only `mutation_id` omitted and therefore includes
`base_program_hash`. Retry duplicate detection
instead compares canonical Mutation core with both `mutation_id` and
`base_program_hash` removed.

The completed batch is submitted once in one
`MutationApplicationRequest 1.1`; the fallback result binds one corresponding
`MutationApplicationReceipt`. No per-mutation application request or receipt is
published. The applier still validates and applies its ordered mutations
sequentially and atomically.

Failure precedence is:

```text
FALLBACK_REQUEST_INVALID
FALLBACK_RUN_MANIFEST_MISMATCH
FALLBACK_PLANNER_MANIFEST_MISMATCH
FALLBACK_MANIFEST_MISMATCH
FALLBACK_CHOICE_CATALOG_MISMATCH
FALLBACK_PROGRAM_HASH_MISMATCH
FALLBACK_LOCKS_INVALID
FALLBACK_ACTION_COORDINATE_INVALID
FALLBACK_NO_ELIGIBLE_OPERATION
FALLBACK_ATTEMPTS_EXHAUSTED
FALLBACK_MUTATION_APPLICATION_FAILED
```

Failure publishes no candidate or partial batch. Every result binds request,
fallback manifest, base Program, action coordinate, requested mutation count,
attempts consumed, and its own recomputable result hash. Success returns exactly
the requested mutations, application receipt, final Program hash, and trace;
failure returns a trace prefix and null partial candidate.

## 4. Broad-prior production lowering

The machine form is `broad_prior_production_manifest.schema.json`. The old
`track_instrument_by_role` completed-map table is non-conforming. Lower one
track at a time in canonical role order:

```text
drums, bass, harmony, melody, texture
```

For active roles only, choose in this order:

```text
production profile (once)
instrument entry (per role)
register preset (per pitched role)
maximum polyphony (per role)
drum-map profile (drums only)
gain_q (per role)
pan_q (per role)
```

Instrument choices are role-specific entries, never full maps. Eligibility
requires exact catalog digest, drum/pitched kind, declared-equave pitch
capability, full containment of the selected register preset in instrument
range, catalog maximum polyphony, and required drum lanes. Registers are never
intersected or clamped. Drum maps copy immutable named catalog mappings into
SongProgram. No compatible choice rejects the seed; it does not remove the
role, change equave, or substitute an unlisted instrument.

The structural Program already contains exactly one track shell for every
active role and no track for an inactive role. Lowering preserves canonical
track order, every track ID, and all realization bindings. It replaces only
the selected instrument, register, maximum polyphony, drum map, and the static
production fields named by this contract. A missing, duplicate, or extra role
track is `SAMPLER_RESULT_INVALID`; lowering never invents a track ID or repairs
a realization reference.

For a pitched catalog endpoint frequency `F` and Program base frequency `B`,
derive its base-relative endpoint as `ratio_mc(F/B)` using NumericContract
round-half-even. The selected register `[lo,hi]` is compatible exactly when
`catalog_lo_mc <= lo <= hi <= catalog_hi_mc`; endpoints are inclusive and the
equave is irrelevant. Invalid/non-positive frequencies, overflow, or numeric
conversion failure is `SAMPLER_PRODUCTION_VALUE_INVALID`. The compiler later
revalidates every exact event frequency against the catalog range.

The manifest stores profile choices as `(profile_id, profile_payload_hash)` and
drum-map choices as `(drum_map_id, drum_map, drum_map_payload_hash)`. Hashes are
recomputed over the canonical profile core and lane-to-MIDI-note map; an ID by
itself is never authoritative.

`BroadPriorProductionRequest` binds its hash, sampler/lowering manifests, root
seed, cohort index, production rejection ordinal, active roles, lattice equave,
catalog digest, and structural Program hash. `BroadPriorProductionResult` binds
the request, status, rejection count, ordered role decisions and trace, output
Program hash, or typed failure with null output. Each trace row stores rejection
ordinal, role, field, counter, path hash, eligible-table hash, and selected-value
hash in the role/field order above.

The profile supplies static synthesis/mix defaults only. Broad prior v1 writes
`production.catalog_digest`, one track per active role, gain/pan records, and
an empty envelope array. It may not produce form, rhythm, note, chord, sidechain
onset, or automation events. Pan duplication and instrument reuse are valid.

Failure precedence is:

```text
SAMPLER_PRODUCTION_MANIFEST_INVALID
SAMPLER_CATALOG_MISMATCH
SAMPLER_ACTIVE_ROLE_INVALID
SAMPLER_PRODUCTION_PROFILE_UNAVAILABLE
SAMPLER_NO_COMPATIBLE_INSTRUMENT
SAMPLER_NO_COMPATIBLE_REGISTER
SAMPLER_NO_COMPATIBLE_POLYPHONY
SAMPLER_DRUM_MAP_INVALID
SAMPLER_PRODUCTION_VALUE_INVALID
SAMPLER_RESULT_INVALID
```

Every trace row records only a completed draw. A failure result stores the
attempt's first typed error in its top-level `error` and preserves the exact
prefix of draw rows completed before that error; it never invents a selected
value for a failed draw. If a complete assignment is rejected and another
attempt is permitted, all of that assignment's completed rows remain in the
trace under its rejection ordinal. Advancing an attempt changes only
`production_rejection_ordinal`; form and material streams are unchanged.

The ordinal starts at zero and must be below
`maximum_production_rejections` before a draw. Each field path uses counter zero.
`rejections_consumed` counts rejected complete assignments; on success its value
equals the successful production rejection ordinal. It never reads or advances
the fallback attempt ordinal.

## 5. Conformance

- model timeout, schema error, and unavailable provider yield the same fallback
  batch for the same authoritative request;
- shuffled inputs and diagnostics do not change output;
- all lock kinds remove exactly their actual-root mutations;
- every sequential mutation binds the previous result hash;
- ordinal rotation is non-identity and recomputes ticks from the target quantum;
- fallback and production counters can change independently without changing
  the other's choices;
- catalog order and unrelated entries do not change a bound role table;
- 1,000 eligible production samples yield at least three instrument-role maps
  and no one map exceeds 50 percent;
- generated production creates no musical events or automation;
- every failure case returns the first code above and no partial candidate.
