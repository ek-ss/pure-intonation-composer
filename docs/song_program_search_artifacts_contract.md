# GEN0-D / LLM Search Artifacts Contract v1

**Status:** normative and implementation-ready baseline

## 1. Identity and canonical bytes

SamplerManifest, DescriptorSpec, FingerprintSpec, QDManifest, PlannerManifest,
MutationChoiceCatalog, LineageIndex, Mutation, RunRecord, and Checkpoint use
their checked-in closed schemas. Manifest objects do not contain their own digest. Their canonical
bytes are UTF-8 canonical JSON with NFC strings, UTF-8-byte-sorted object keys,
preserved array order, shortest decimal integers, no whitespace, and one final
LF. A manifest digest is:

```text
"sha256:" + hexlower(SHA256(UTF8(type_domain + "\0") + canonical_bytes))
```

Domains are respectively `cps.sampler-manifest/v1`,
`cps.descriptor-spec/v1`, `cps.fingerprint-spec/v1`, `cps.qd-manifest/v1`,
`cps.planner-manifest/v1`, `cps.mutation-choice-catalog/v1`, and
`cps.lineage-index/v1`. Array order is normative
unless a field explicitly requires sorting. No runtime default fills an absent
field.

## 2. SamplerManifest and streams

The baseline is `broad_prior_v1` in `fixtures/search/sampler_manifest.json`.
It names all compiler/schema/catalog digests, rejection ceiling, generation
limits, and these required tables: section count/role/bars, total bars, material
count/kind, active roles, equave domain, rhythm grid/density, chord reference,
recall decision, transform count/type/rotate amount, track instrument by role,
gain, and pan. Every table is an ordered list of `{value,weight}`; values are
closed JSON scalars or objects appropriate to that table. Weights are u64 and
their checked sum must be `1..2^64-1`. A non-forced table has at least two
positive entries. Integer distributions are explicit weighted value tables,
never implicit ranges.

For root seed `S`, cohort index `I`, and path segments `P`, encode:

```text
stream_key = SHA256(
  UTF8("cps.broad-prior/stream/v1\0") || u64be(S) || u64be(I) ||
  concat(u32be(len(UTF8(NFC(segment)))) || UTF8(NFC(segment)) for segment in P)
)
draw(counter) = uint64_be(SHA256(stream_key || u64be(counter))[0:8])
```

Counter starts at zero independently for each path. Selection uses
`draw % sum(weights)` and the first strictly greater cumulative upper bound.
Paths are the exact decision addresses listed in the fixture's
`decision_program`; repeat variables are substituted as unsigned decimal
segments. Rejection attempt appends segments `reject`, then its decimal
ordinal, so a rejected candidate cannot shift another seed. Decisions execute
in listed order. The baseline table values are normative data, not suggested
defaults; changing one produces a different manifest/cohort.

## 3. DescriptorSpec and LineageIndex

Descriptor input is `(canonical Project 1.2, canonical LineageIndex)`. The
index binds the Project hash and maps every material-instance ID exactly once to
a `lineage_hash` and `lineage_root_hash`. The compiler derives a lineage hash
from the source SongProgram material core with ID and placement removed; a
mutation preserves it, while creation of genuinely new material derives a new
hash from the creating action ID. Descendants retain the same root hash.
Missing, extra, duplicate, or wrong-Project mappings reject evaluation.
Persistent outputs use `descriptor_result.schema.json` and
`fingerprint_record.schema.json`; both bind Project, LineageIndex, and owning
spec hashes. Descriptor nulls remain explicit and fingerprint component hashes
remain in spec order.

For compiler-origin material, `material_core` is the complete canonical
SongProgram material object with only its top-level `id` omitted. Placement is
not part of a material object and therefore requires no additional exclusion.
Both the initial `lineage_hash` and `lineage_root_hash` are:

```text
SHA256("cps.material-lineage/v1\0" + canonical_json(material_core))
```

`program_lineage_root_hash` hashes the sorted unique lineage-root hash array
under `cps.program-lineage-root/v1`. `project_hash` is the Project 1.2 artifact
hash defined by the Project contract, including compiler build identity.

For each lineage, compiler-origin instances sort by `(at_tick,id UTF-8)` and
each instance after the first records one edge from its predecessor. With no
rhythm transform the operation is `identity` and `identity=true`. The SP0
rotate list is combined left-to-right by integer addition and stored as
`rotate_ticks:<signed-decimal-total>` with `identity=false`, except a zero
total, which canonicalizes to `identity`. No edge is fabricated for the first
instance of a lineage. Mutation-created edges use their separately defined
typed operation identity.

`foreground` is exact: every drum event and every pitched event whose track
role is `melody`; bass, harmony, and texture are not foreground. For rhythmic
syncopation an eligible event is foreground, quantizable, positive-duration,
and crosses its next 120-tick boundary. Its maximum possible contribution is
5, the frozen maximum metrical-strength increase, so the denominator is
`5 * eligible_event_count`. Contributions use only that next boundary.

Material recurrence groups instances by `lineage_hash`, never material ID.
`distinct_sounding_material_lineage_count` counts lineage hashes with at least
one non-drum positive-duration event. A lineage is transformed recall when it
sounds in two sections and at least one later instance has a non-identity
transform edge recorded in LineageIndex. Descriptor result storage is the
closed integer/null record identified by DescriptorSpec digest.

## 4. FingerprintSpec

FingerprintSpec names ordered components and integer weights. The baseline
components are `section_bars`, `role_time_grid`, `root_anchor_deltas`,
`chord_steps`, `lineage_edges`, and `sounding_intervals`. Component payloads
are canonical arrays defined in the search-loop contract; each component hash
uses domain `cps.fingerprint-component/v1\0` plus component ID and payload.
The full fingerprint hashes the ordered component hash array.

Near distance is half-even `10000 * weighted_difference / weight_sum`.
`section_bars` and `chord_steps` use position-wise Hamming after padding with a
single null sentinel; `role_time_grid`, `lineage_edges`, and
`sounding_intervals` use multiset Jaccard; `root_anchor_deltas` uses ordinary
set Jaccard. For Jaccard, two empty sets have zero difference. The baseline
threshold and every weight are digest-covered.

## 5. QDManifest and archive

QDManifest binds DescriptorSpec, FingerprintSpec, evaluation and acceptance
policy digests, axis bin edges, cell capacity, and comparison field order. A
cell key is the ordered zero-based bin-index array. `maximum possible
contribution` is not inferred by QD; it comes from the descriptor rule above.

The champion is the best candidate under the frozen quality tuple. Runners-up
are scanned in the same total order and retained only if their
`lineage_root_hash` differs from the champion and every already retained
runner. At most `cell_capacity-1` are kept. This is the complete meaning of
`lineage-diverse runners-up`; no distance threshold or random choice applies.
`QDArchiveRecord` stores manifest digest, cell, revision, champion, runners,
and previous record hash.

## 6. Mutation and dependency scope

Mutation schema `1.0.0` has exactly eight operations:

1. `replace_bounded_scalar`;
2. `replace_distribution_choice`;
3. `transpose_material_vector`;
4. `rotate_rhythm`;
5. `replace_chord_intent_reference`;
6. `replace_root_anchor_item`;
7. `duplicate_section` or `delete_section` through the `edit_section` union;
8. `swap_track_catalog_entry`.

All integers and arrays are bounded by the schema. Parameters contain semantic
IDs, never JSON pointers. The applier resolves IDs against the base program and
computes the actual dependency closure with typed edges:

The top-level `operation` must equal `parameters.kind`. Scalar bounds satisfy
`minimum <= value <= maximum` and must also equal the owning SongProgram field
bounds. Rotation `steps` is nonzero. Section duplicate requires a non-null
insertion predecessor; delete requires it null. Chord steps are canonicalized
and revalidated against divisions/equave. Violations are
`MUTATION_PARAMETER_INVALID` before dependency traversal.

`rotate_rhythm.steps` is a rhythm-derived-grid displacement, not an ordinal
array rotation and not a globally fixed tick grid. For the targeted
RhythmCell, sort distinct onsets and form their positive cyclic gaps, including
the wrap from the last onset to `length_ticks + first_onset`. The immutable
rotation quantum is `gcd(length_ticks, every duration_ticks, every positive
cyclic onset gap)`, with zero gaps omitted. Shift every source step by
`steps * quantum` ticks modulo `length_ticks`; duration, accent, and lane remain
attached to the step. Sort by `(new_at_tick, original_source_ordinal)` and then
discard the temporary ordinal. The quantum is invariant under rotation, so
applying `n` and then `-n` restores canonical bytes.

`replace_distribution_choice` resolves only through the
`MutationChoiceCatalog` whose digest is mandatory in Search RunManifest 1.2.
The closed supported `(owner_kind,field)` pairs are `(section,role)`,
`(section,development_stage)`, `(material,mapping)`, `(track,role)`, and
`(production,profile_id)`. A catalog entry core is exactly
`{owner_kind,field,value}` and its ID is:

```text
"choice_" + base32lower_no_pad(SHA256(
  UTF8("cps.mutation-choice/v1\0") + canonical_json(entry_core)
))[0:20]
```

Catalog canonical bytes and digest use the artifact rules with domain
`cps.mutation-choice-catalog/v1`. Entries sort by
`(owner_kind UTF-8,field UTF-8,choice_id UTF-8)` and duplicate cores, IDs, or
triples reject. Resolution requires one exact catalog match for owner kind,
field, and choice ID. Missing, ambiguous, digest-mismatched, or incompatible
choices fail `MUTATION_CHOICE_UNRESOLVED`; no sampler-table, model-text,
environment, or current-value fallback is permitted. `owner_id` selects the
target object and is absent from choice identity, allowing reuse across owners.

- material -> realizations using it -> emitted instances/events;
- rhythm -> materials referring to it -> their realization closure;
- ChordIntent -> harmony materials referring to it -> their closure;
- section -> realizations/instances/events in it; duplicate additionally owns
  newly derived IDs, delete owns removed descendants and shifted form timing;
- track -> its realizations/instances/events and mix entry;
- production scalar -> named track mix or envelope consumers.

`declared_scope` is the sorted unique list of `{kind,id}` roots plus
`global_form`. The actual root set must equal it byte-for-byte; subset and
superset declarations reject `MUTATION_SCOPE_MISMATCH`. Locks match these roots
before application. Sequential proposal application recomputes closure after
each mutation. SongProgram §19 is superseded by this vocabulary for 0.1.

For lineage-preserving mutations, both lineage hashes remain unchanged and
each derived-instance edge uses the exact operation string
`mutation/<operation>/<mutation_id>`. `identity` is true exactly when the
canonical material/instance musical core is byte-identical before and after
application; a nonzero request may therefore be a canonical identity.

A genuinely new material has no parent lineage. In its creating action's
canonical mutation order, assign `creation_ordinal` from zero and derive both
its initial lineage and root hash as:

```text
SHA256(
  UTF8("cps.mutation-lineage-root/v1\0") || UTF8(action_id) || NUL ||
  UTF8(mutation_id) || NUL || u32be(creation_ordinal) ||
  canonical_json(new_material_without_id)
)
```

The same tuple reproduces the same root; any changed component creates a new
root. Transform edges sort by `(to_instance_id UTF-8,from_instance_id UTF-8,
operation UTF-8)`. The first instance of a new root has no fabricated parent
edge.

## 7. PlannerManifest

PlannerManifest binds provider/model/snapshot, reasoning effort, prompt bytes
hash, input/output schema hashes, allowed operations, maximum mutations,
request/output byte limits, timeout as operational metadata, fallback stream
domain, and lock/scope policy IDs. Model text cannot expand any bound. The raw
response is stored by CAS hash; only a schema-valid parsed Mutation list is
actionable.

## 8. Append-only run state and CAS

The run hash is the digest of RunManifest canonical bytes under
`cps.search-run-manifest/v1`. Logical action identity is:

```text
action_id = "act_" + base32lower_no_pad(SHA256(
  UTF8("cps.search-action/v1\0") || run_hash_bytes ||
  u64be(round) || u32be(phase_ordinal) || u64be(candidate_ordinal)
))[0:26]
```

Phase ordinals are `0 sample`, `1 propose`, `2 apply`, `3 compile`, `4 render`,
`5 evaluate`, `6 archive`, `7 checkpoint`. Each RunRecord is canonical JSON
with sequence, action ID, kind, payload hash, previous record hash, and record
hash. `record_hash` uses domain `cps.search-run-record/v1\0` and the record with
that field omitted. Sequence starts zero; previous hash is null only there.

CAS keys are `sha256:<hex>` and local paths are
`cas/sha256/<first-two-hex>/<remaining-hex>`. Write bytes to a same-directory
unique temporary file, fsync file, atomically create-if-absent at the final
path, verify an existing winner byte-for-byte, fsync directory, then append the
record. A record is appended as `u64be(byte_length) || canonical_record_bytes`
to `runs/<run_hash_hex>/records.log` under one exclusive run lock, followed by
file fsync. The atomicity boundary is one CAS object plus one record append;
records never reference a missing CAS object.

A checkpoint payload contains run hash, last sequence/hash, next action ID,
round/candidate/phase cursor, exact logical budget usage, planner calls,
patience, cancellation state, QD archive head hashes, and all live champion
program/project/report hashes. Resume verifies the entire hash chain and every
referenced CAS object, selects the greatest valid checkpoint, then executes the
smallest unfinished action ID. Stored planner response replay never calls the
model.

## 9. Required parity

The checked-in search fixture set freezes all manifests, one sampler trace,
mutation positive/negative/boundary cases, descriptor/fingerprint inputs and
outputs, archive updates, a run log, checkpoint, and CAS blobs. An independent
oracle recomputes every digest, stream draw, action ID, record chain, and replay
cursor. Cold/hit cache and 1/2/4/8-process sidecars must produce identical
canonical bytes.
