# Structural sampler and lowering 1.1

**Status:** normative. Version 1.0 artifacts remain valid only under their
original contracts and MUST NOT be interpreted using this document.

## 1. Authorities and pipeline boundary

`broad-prior-v1.1` produces `cps.structural-song-program` 1.0.0.  That payload
contains clock, lattice, form, timing-neutral materials, chord intents and
realizations, but no tracks, instrument IDs, drum maps, production profile,
gain or pan.  `broad-prior-production` is the sole owner of those omitted
fields and converts the structural payload to `cps.song-program` 0.1.0.

SearchLoop13 binds `BroadPriorProductionRequest 1.1`; legacy request 1.0 is
never used with a structural payload. The 1.1 request contains the complete
inline structural payload and binds its hash, both lowering manifests, the
run/context/source decision, catalog and active roles. Its `request_hash` uses
the Search Decision artifact preimage with only `request_hash` removed.

Production creates, in frozen role order, exactly one track for each active
role. Its ID is `trk_` plus the role token. It replaces every structural
realization's `role` member with `track_id` naming that track and otherwise
preserves the realization. Duplicate generated track IDs, an inactive role,
or a realization role absent from `active_roles` is
`SAMPLER_ACTIVE_ROLE_INVALID`. Final tracks use frozen role order and final
realizations retain structural order. Track shells never occur in a structural
payload.

The request binds a SamplerManifest 1.1, StructuralLoweringManifest 1.0 and the
raw schema hashes of both the structural payload and rejection evidence.  A
producer MUST reject a binding mismatch before drawing.

The structural payload CAS identity is exactly:

```text
structural_program_hash =
  SHA256("cps.structural-song-program/1.0\0" || canonical(structural_program)+LF)
```

It is not the raw hash of the canonical bytes and it is distinct from the
lowered SongProgram hash. `candidate_program_hash` in sampler traces/results
and `structural_program_hash` in production requests/results use this same
identity.

The execution boundary receives four resolved values: request, Production
Lowering Manifest, Instrument Catalog, and Structural Lowering Manifest. The
last three may be obtained from CAS, but resolution is exact: the requested
hash maps to one immutable canonical byte string, those bytes must parse and
validate against the bound schema, and recomputing the artifact hash must equal
the request binding. The Structural Lowering Manifest artifact hash is
`SHA256("cps.structural-lowering-manifest/v1\0" || canonical(manifest without
manifest_hash)+LF)`; its embedded `manifest_hash` must equal that value. The
production manifest uses its existing `cps.production-lowering-manifest/v1`
preimage. Missing, ambiguous, malformed, or mismatched manifest resolution is
`SAMPLER_PRODUCTION_MANIFEST_INVALID`; it precedes catalog validation and all
draws. Implementations may expose this as an explicit fourth argument or as a
content-addressed resolver, but fallback lookup and process-local defaults are
forbidden.

## 2. Attempt-addressed stream

The sampler algorithm is `broad-prior-v1.1`; its stream algorithm is
`path-addressed-sha256-attempt/v1.1`.  The attempt seed is the 32 raw digest
bytes specified by SearchLoop13 Group D.  For an expanded path, encode each
segment in order: integers as byte `0x00 || u64be(value)`, and strings as byte
`0x01 || u32be(length) || NFC UTF-8 bytes`.  Then:

```text
stream_key = SHA256(UTF8("cps.broad-prior/stream/v1.1\0") ||
                    raw32(attempt_seed_hash) || encoded_path)
draw = u64be(SHA256(stream_key || u64be(counter))[0:8])
```

All integers are checked u64. Every v1.1 decision uses counter zero. The
selected point is `draw mod checked_u64_sum(positive weights)`. Zero-weight
entries are ineligible. Empty eligible tables and addition overflow reject.

## 3. Decision expansion and table identity

Decision-program ordinals are consecutive from zero. Expansion is ordinal
order, then lexicographic integer tuple order. Placeholders are integer u64:
`{section}` and `{material}` use their zero-based array ordinal; `{role}` uses
`drums,bass,harmony,melody,texture` filtered by selected active roles;
`{recall}` uses the zero-based ordinal of `(section_ordinal,material_ordinal)`
in lexicographic order; `{transform}` uses `0..transform_count-1`. A placeholder
whose owner has not been selected is invalid. `per_recall` means every selected
recall pair, not every section. Transform type and amount paths MUST contain
both `{recall}` and `{transform}`.

`recall_decision` is the sole exception to the selected-owner rule: it expands
first over the complete Cartesian product of selected sections and selected
materials, in `(section_ordinal,material_ordinal)` order. A truthy selected
value includes that pair in the recall set and a false value excludes it. Only
after this pass may any other `per_recall` decision expand; it expands exactly
over the included pairs and uses their ordinal in the filtered ordered set.
Thus selection never depends on a decision whose expansion it controls.

Trace table `index` is the original manifest-array index; zero-weight entries
are omitted without renumbering. Define:

```text
value_hash = SHA256("cps.sampler-choice-value/v1.1\0" || canonical(value)+LF)
choice_id = "choice_" || lower-base32(raw32(value_hash))[0:26]
```

Duplicate `choice_id` or `value_hash` within a table is invalid. The selected
value hash equals the selected eligible row. Tables retain original index
order.

## 4. Structural lowering

StructuralLoweringManifest is closed and owns every field not selected by a
decision: Program and object ID format; clock; lattice scalar and exploration
policy; section energy/density/tonal-center/development templates; rhythm step
builder; direct-vector, melody and harmony builders; chord voicing,
recognition and complexity; realization placement/scales; compile policy and
limits. No implementation default exists outside it.

The builder substitutions are integer-only. Rhythm length is
`beats_per_bar*ticks_per_beat`; onsets are ascending grid multiples below the
length, and exactly `max(1, half_even(grid_count*density_q/10000))` positions
are selected by the manifest's declared `rhythm_position_policy`. Direct
vectors, melody members and harmony roots are copied/cycled from the matching
closed templates. References are resolved by ordinal and dangling references
reject. Selected section bars are never normalized: their checked sum MUST
equal selected `total_bars`, otherwise reject.

For each selected material, lowering first creates its rhythm helper using the
selected grid and density. It then emits one realization for every compatible
active role for every selected recall pair, including the pair's first
occurrence. Compatibility is frozen: rhythm material maps only to `drums`;
direct-vector material maps to `bass` and `texture`; harmony-intent material
maps to `harmony` and `texture`; melody-intent material maps to `melody` and
`texture`. A material with no compatible active role emits no realization.
Within a pair, compatible roles use frozen role order. Placement, transpose,
scale and transform fields come only from the bound lowering manifest and the
pair-addressed decisions; an implementation MUST NOT invent defaults.

IDs are exactly the manifest prefixes plus zero-padded decimal ordinals:
section/material/rhythm/chord/realization use widths declared by the manifest;
tracks do not exist at this stage. `program_id` is its prefix plus the first 26
lower-base32 characters of `SHA256("cps.structural-program-id/v1\0" ||
raw32(attempt_seed_hash))`. Any collision rejects. Arrays sort: form by section
ordinal; rhythm helpers then musical materials by owning material ordinal;
chords by chord ordinal; realizations by
`(section,material,role,recall)` ordinal tuple. Canonical JSON uses NFC, sorted
object keys, minimal integers, no insignificant whitespace and one final LF.

## 5. Rejection and candidate hashes

`StructuralRejectionEvidence` has the closed ordered codes below. First failure
wins in this exact order:

1. `SAMPLER_LOWERING_BINDING_INVALID`
2. `SAMPLER_DECISION_PROGRAM_INVALID`
3. `SAMPLER_WEIGHT_SUM_OVERFLOW`
4. `SAMPLER_TABLE_EMPTY`
5. `SAMPLER_PATH_EXPANSION_INVALID`
6. `SAMPLER_TOTAL_BARS_MISMATCH`
7. `SAMPLER_ID_COLLISION`
8. `SAMPLER_SECTION_UNCOVERED`
9. `SAMPLER_SOUNDING_ROLE_UNDERSHOOT`
10. `SAMPLER_RECALL_MISSING`
11. `SAMPLER_NON_IDENTITY_RECALL_MISSING`
12. `SAMPLER_STRUCTURAL_SCHEMA_INVALID`
13. `SAMPLER_STRUCTURAL_SEMANTIC_INVALID`

Validation traversal is binding; decision-program ordinal/path/table/repeat;
checked table arithmetic; path expansion; draws; lowering in form/material/
chord/realization order; the constraints above. Evidence pointers are unique
RFC 6901 pointers sorted by UTF-8 bytes. Evidence hash is SHA-256 of
`"cps.structural-rejection-evidence/v1\0" || canonical(evidence without
evidence_hash)+LF`.

A failure before a complete schema-valid structural payload has null
`candidate_program_hash`. A complete payload rejected by a hard invariant has
its canonical payload hash. Accepted attempts always have the payload hash.
Only the terminal attempt may be accepted.

The 1,000-seed 35% fingerprint-mode rule is not an individual rejection. It is
evaluated only by the preregistered cohort gate report and cannot alter draws,
retry counts or candidate acceptance.

The four structural coverage predicates are exact:

- `SAMPLER_SECTION_UNCOVERED`: a selected section has zero realizations.
- `SAMPLER_SOUNDING_ROLE_UNDERSHOOT`: the structural payload realizes fewer
  than the manifest's `minimum_sounding_roles` distinct active roles.
- `SAMPLER_RECALL_MISSING`: no material is realized in two or more distinct
  selected sections.
- `SAMPLER_NON_IDENTITY_RECALL_MISSING`: no material realized in two or more
  sections has a later occurrence whose selected rotation is nonzero modulo
  that material's rhythm-helper step count. A zero step count is structurally
  invalid before this predicate is evaluated.

Predicate traversal is section ordinal for uncovered, frozen role order for
undershoot, then material ordinal followed by occurrence order for both recall
checks. Evidence pointers name every violating owner considered by that
predicate and retain the global UTF-8 sorting rule above.
