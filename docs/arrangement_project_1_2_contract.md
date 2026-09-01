# ArrangementProject 1.2 Strict Contract

Status: normative for SP0. Models are immutable and strict: unknown fields and
primitive coercion reject; ratios are positive reduced strings.

## Root and canonical form

Required fields: `schema=cps.arrangement-project`, `schema_version=1.2.0`,
`source_program`, `compiler`, `lattice`, `clock`, `tracks` (1..8), `form`
(1..16), `material_instances` (<=512), `resolved_chords` (<=4096),
`harmony_occurrences`, `events` (1..8192), `mix`, `render_settings`. Metadata,
diagnostics, timestamps, runner-ups, near-class summaries, automation, and
artifact hash are forbidden; diagnostics are a separate artifact.

`source_program` carries hash/schema/version. `compiler` carries build ID,
NumericContract ID, `resolver_build_id`, resolver-profile hash,
budget-profile digest, and instrument
catalog digest. `lattice` carries domain hash, base frequency millihertz,
equave, 1..3 semantically ordered generators, one inclusive integer
`coordinate_bounds[min,max]` pair per generator, and inclusive
`register_bounds[min,max]`, plus `maximum_odd_limit` and
`maximum_reduced_complexity_bits`. These two filters are hard membership rules
and are revalidated for every stored pitch. Odd limit follows NumericContract;
reduced complexity is `bit_length(n)+bit_length(d)` for the same equave-reduced
`n/d`, compared inclusively. Its domain hash is
`SHA256("cps.lattice-domain/v1\0" + canonical_json(lattice_without_domain_hash))`.
Standalone validation therefore recomputes both membership and identity.

Tracks, material instances, and resolved chords are ID-byte ordered; form is
contiguous from bar zero; occurrences are gapless chord-index order; maps are
key-byte ordered. Events sort by `(start_tick, track_id, kind_order,
ratio_or_drum_note, semantic_address, id)`. Reject duplicate IDs before sorting.
Only canonical bytes are hashable.

## Occurrences and sources

`MaterialInstance` contains ID, material/realization/section/track IDs, repeat
ordinal 0..31, absolute tick, and SongProgram JSON Pointer. `EventSource`
contains material-instance ID, source-step ordinal 0..63,
`emitted_voice_ordinal` 0..7, and semantic address.

MaterialInstanceId v1 is derived from the realization ID and repeat ordinal.
Remove a leading `real_` when present, otherwise use the complete realization
ID as the stem. Repeat zero is `"mi_" + stem`; later repeats are
`"mi_" + stem + "_" + unsigned_decimal(repeat_ordinal)`. The result must
match the Project symbol-ID grammar and be unique; truncation, hashing, or
collision repair is forbidden and fails `MATERIAL_INSTANCE_ID_INVALID`.

SemanticAddressEncoding v1 is UTF-8 canonical JSON, with no whitespace and only
JSON-required escaping, of `["cps.semantic-address",1,section_id,
realization_id,repeat_ordinal,material_id,source_step_ordinal,
emitted_voice_ordinal]`. The stored value is
`"sa_"+base32lower_no_pad(SHA256(bytes))[0:26]`. Base32 is RFC 4648,
lowercased, without padding.

`emitted_voice_ordinal` is derived, never freely assigned: drum and
`direct_vector` are 0; `resolved_chord_voice` equals `shape_voice_ordinal`;
`resolved_melody/chord_member` is 0. Within one material instance/source step,
the pair `(kind,emitted_voice_ordinal)` must be unique.

`HarmonyOccurrence` contains gapless `chord_index`, section, start, duration,
and resolved-chord ID. This is the sole meaning of `chord_index`; array position
is never a reference.

## Event and provenance unions

`ProjectEvent` is discriminated by `kind`.

- `drum`: common ID/track/section/timing/velocity/articulation, drum note, source;
  ratio, chord index, and pitch provenance are null.
- `note`: common fields, exact ratio, nullable chord index, non-null pitch
  provenance; drum note is null.

Pitch provenance is discriminated by `kind`; fields from other branches reject:

- `direct_vector`: material vector, tonal center, register delta,
  register-shift equaves, placed-equave exponent, final vector/exponent/ratio.
  SP0 requires `final_vector=material+tonal_center` and
  `final_exponent=register_delta+register_shift+placed_exponent`.
- `resolved_chord_voice`: chord ID, target/shape ordinals, anchor, offset, final
  vector/exponent/ratio. It must exactly select one stored chord voice and
  `final_vector=anchor+offset`.
- `resolved_melody`: melody-intent ID, relation, active chord/target voice,
  nullable next chord, source vector, relation and tonal-center deltas, final
  vector/exponent/ratio. SP0 accepts only `chord_member`: zero deltas, null next
  chord, exact identity with its active chord voice. `neighbor`/`approach` are
  typed but rejected by SP0 capability validation.

Every vector dimension equals generator count, and
`final_ratio=product(generator_i^vector_i)*equave^exponent` exactly. Event ratio
equals provenance ratio. Direct events have null chord index; resolved harmony
and chord-member melody require an occurrence and fall inside it with matching
resolved-chord ID.

EventId v1 first serializes canonical JSON of this ordered mapping, excluding
only `id` and `source.semantic_address`:
`kind,track_id,section_id,start_tick,duration_ticks,velocity,articulation,
drum_note,ratio,chord_index,pitch_provenance,source{material_instance_id,
source_step_ordinal,emitted_voice_ordinal}`. Every nullable key is present with
JSON null; ratios are reduced strings and vectors are integer arrays. Then:

```text
preimage = UTF8("cps.event-id/v1\0") + UTF8(semantic_address) + NUL + core_json
id = "ev_" + base32lower_no_pad(SHA256(preimage))[0:20]
```

The compiler computes semantic address, then event ID, then final event order.

Event velocity is derived before EventId computation. For a rhythm step with
`accent_q=A` and realization `velocity_scale_q=S`, compute
`v=RHE(125*A*S/100000000)`, then clamp to `1..127`. This deliberately reserves
two MIDI velocity codes at unity gain and makes a zero accent a minimally
audible event rather than deleting it. Duration is
`max(1,RHE(source_duration_ticks*gate_scale_q/10000))`.

## ResolvedChord

Required fields: ID, domain hash, intent hash, resolver build ID,
NumericContract ID, `search_completeness=exact`, anchor, 2..8 voice offsets,
equave exponents, exact ratios, target-voice ordinals, signed pair errors,
maximum, RMS, and complexity. Parallel voice arrays have equal length; target
ordinals are a permutation; pair errors use `(0,1),(0,2),...` target order. All
equations and metrics are recomputed with NumericContract.

Each chord also stores hash-covered recognition target fields
`reference_equave`, `reference_divisions`, and `canonical_steps` in canonical
target order. Steps are in `0..divisions-1`, unique by computed phase, and their
count equals voice count. `intent_hash` is provenance identity; these inline
fields are the standalone authority for pair-error recomputation.

Each chord also stores hash-covered `eligibility_contract` with exactly
`bass_policy`, nullable `bass_target_ordinal`,
`minimum_spacing_millicents`, `maximum_span_millicents`,
`maximum_pair_error_millicents`, `maximum_pair_rms_millicents`, and
`complexity_budget`. The standalone validator replays NumericContract hard
checks in their normative order. Threshold equality passes. ResolvedChord
`resolver_build_id` must exactly equal `project.compiler.resolver_build_id`.

```text
id = "rc_" + base32lower_no_pad(
  SHA256(UTF8("cps.resolved-chord/v1\0") + canonical_resolved_core_json)
)[0:26]
```

`canonical_resolved_core_v1` is the canonical ordered mapping of exactly:
`domain_hash,intent_hash,resolver_build_id,numeric_contract,
search_completeness,reference_equave,reference_divisions,canonical_steps,
eligibility_contract,
anchor_vector,voice_offsets,equave_exponents,exact_ratios,
target_voice_ordinals,pair_errors_millicents,maximum_pair_error_millicents,
pair_rms_error_millicents,complexity_score`. The ID preimage is
`UTF8("cps.resolved-chord/v1\0") + canonical_json(core)`; ID itself is excluded.
Search stats, cache state, and diagnostics are forbidden. Domain/numeric/compiler
identities agree with Project. IDs are unique and the stored-ID set equals the
set referenced by occurrences; unused entries reject.

## Validation and capability

Validate in order: ID uniqueness; form/clock; material refs; occurrence refs and
timing; event refs/roles/timing; union/chord-index rules; provenance equations
and register; chord equations/metrics/ID; exact referenced-set equality;
event-ID recomputation/uniqueness; canonical order.

SP0 output permits drums, direct vectors without pitch transforms, resolved
chord voices, chord-member melody, exact search, and native 8-bar 2/1 Projects.
The schema validates generic 3/1 arithmetic fixtures, while export returns
`UNSUPPORTED_EQUAVE_CAPABILITY` unless declared supported. Beam/truncated
results, fabricated legacy provenance, pitch-transform traces, automation
provenance, and interaction-repair provenance reject.

Required positives: minimal direct 2/1, resolved triad, chord-member melody,
drum lane, canonical permutation/hash, 3/1 schema, and 100-cycle/cross-process
roundtrip. Required negatives cover unknown/coerced fields, non-reduced ratio,
dimension mismatch, duplicate/dangling refs, role/source mismatch, cross-union
fields, altered equations/metrics/hash, ordinal bounds, illegal melody relation,
chord-index gap/interval mismatch, unused chord, event-ID mismatch, section
overflow, and register violation.
