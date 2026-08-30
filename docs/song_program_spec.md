# SongProgram Specification

**Schema:** `cps.song-program`
**Version:** `0.1.0`
**Status:** normative for the closure scope declared in
[song_program_review_2026-08-30.md](song_program_review_2026-08-30.md)

## 1. Purpose and Boundary

`SongProgram` is the searchable, mutable genotype of a composition.
`ArrangementProject` is the compiled, immutable, playable phenotype. They are
separate artifacts.

```text
SongProgram 0.1
  -> strict validation and canonicalization
  -> deterministic SongProgram compiler
  -> ArrangementProject 1.2 (lossless provenance)
  -> ArrangementProject 1.1 compatibility projection
  -> existing MIDI/WAV exporters
```

`SongProgram` describes reusable musical material and how it develops. It is
not a note-grid dump, a genre template selector, an arbitrary programming
language, or a synthesizer graph.

The full v0.1 objective is to prove:

- total and bounded compilation;
- exact lattice-pitch provenance;
- useful sampling priors;
- local, measurable mutations;
- substantially more structural diversity than the current fixed Kawaii
  generator.

## 2. Deliberate v0.1 Limits

Implementation is staged. SP0 freezes only exact pitch arithmetic, strict core
schemas, a small-domain exact joint-chord resolver, and one deterministic
8-bar `2/1` Project. The same arithmetic/reduction/oracle path must have `2/1`
and `3/1` fixtures, but full `3/1` composition/export is the next capability
milestone. GEN0 then adds optimized/progression search, sampling, diversity,
rendering, and calibrated perception metrics.

The first version uses:

- one tempo and meter per song;
- an ordered, finite section sequence rather than a general form graph;
- 1–3 non-equave lattice generators plus a variable explicit equave, including
  at least `2/1` octave and `3/1` tritave spaces;
- three material types: rhythm cell, pitch/melody intent, and harmony-intent
  cell;
- explicit section/part realizations that reference materials;
- two draft interaction constraints, deferred beyond SP0;
- track assignments and draft section-level production envelopes, with static
  track settings only in SP0;
- a closed, non-nesting transform vocabulary;
- rejection only; bounded repair is deferred to v0.2.

Branches, recursion, arbitrary conditions, modulation of tempo/meter, general
constraint solving, synthesizer topology, audio effects graphs,
reharmonization search, and interpolation enter later schema versions only
after v0.1 locality and viability are demonstrated.

## 3. Design Invariants

1. Integer lattice vectors are the pitch source of truth. Ratio strings are
   derived and verified during compilation.
2. All time is integer ticks. No compilation pass uses floating-point time.
3. Every output event retains its material, realization, transform, and
   semantic-address provenance.
4. Every random decision uses a named, path-addressed random stream. Adding an
   unrelated node cannot change an existing decision.
5. Unknown fields, dangling references, cycles, implicit clipping, and silent
   fallback are errors.
6. Role labels are descriptive outputs in the GEN0 sampler. They do not
   condition form, material, or realization generation in v0.1.
7. A transform changes only its declared dependency closure.
8. Compilation is a pure function of canonical program bytes and compiler
   build identity.

## 4. Top-Level Model

```yaml
schema: cps.song-program
schema_version: 0.1.0
program_id: sp_example
seed: 42
clock: Clock
lattice: LatticeDomain
chord_intents: [ChordIntent]
form: [Section]
tracks: [Track]
materials: [Material]
realizations: [Realization]
interactions: [Interaction]
production: ProductionPlan
compile_policy: CompilePolicy
limits: Limits
```

All symbol IDs match `^[a-z][a-z0-9_-]{0,39}$` and are unique globally in v0.1
to make diagnostics and semantic addresses unambiguous. References use symbol
IDs, never array indices. `program_id` is non-referenceable metadata and is not
part of the symbol table.

`program_id` is metadata and is excluded from `program_hash`. `seed` is an
unsigned 64-bit integer and is included.

## 5. Clock

```yaml
clock:
  tempo_milli_bpm: 150000
  beats_per_bar: 4
  ticks_per_beat: 480
```

- `tempo_milli_bpm`: `30000..300000`;
- `beats_per_bar`: `2 | 3 | 4 | 6`;
- `ticks_per_beat`: v0.1 requires `480`;
- total duration is `sum(section.bars) * beats_per_bar * ticks_per_beat`;
- all offsets and durations must be integral ticks.

## 6. LatticeDomain

```yaml
lattice:
  base_frequency_millihz: 220000
  equave: 2/1
  generators: [3/1, 5/1, 7/1]
  coordinate_bounds: [[-12, 12], [-8, 8], [-6, 6]]
  register_bounds: [-4, 6]
  maximum_odd_limit: 63
  pitch_exploration:
    maximum_domain_points: 100000
    near_class_merge_millicents: 8000
    maximum_reduced_complexity_bits: 48
    reference_divisions: 12
    audible_offset_band_millicents: [12000, 48000]
    target_audible_event_share_q: [1200, 3500]
    minimum_exposed_sections: 2
    minimum_recurrent_color_relations: 1
    maximum_melodic_jump_millicents: 700000
```

The ratio of vector `v` is:

```text
raw(v) = product(generators[i] ** v[i])
pitch(v, register) = raw(v) * equave ** register
```

Requirements:

- `base_frequency_millihz` is `20000..2000000`, participates in the program
  hash, and lowers to the Project base frequency;
- `equave` and generators are positive reduced fractions and `equave > 1/1`;
- v0.1 conforming implementations must support `2/1` and `3/1`; other equaves
  are accepted only when declared by the compiler capability manifest;
- generator count is `1..3`, and every vector has exactly that dimension;
- coordinate bounds are within `[-32, 32]`, contain zero on every axis, and
  pair positionally with the ordered generators;
- `register_bounds` are equave exponents and remain finite;
- `coordinate_cardinality` is the product of inclusive coordinate-axis widths;
  `placed_pitch_cardinality` is that value multiplied by the inclusive register
  width; `maximum_domain_points` constrains `placed_pitch_cardinality` using
  checked 128-bit integer arithmetic before enumeration;
- no scale or `allowed_points` list is materialized in SongProgram and no scale
  cardinality is an input, target, or quality value;
- points are enumerated lazily only for a concrete harmony or melody query;
- points that reduce to the same exact ratio are deduplicated for search while
  alternate vector spellings may be retained as bounded provenance;
- generation outside bounds is rejected, not reflected or wrapped;
- register placement changes only the explicit equave exponent;
- compiler output records `material_vector`, `post_transform_vector`,
  `equave_exponent`, `final_ratio`, and
  octave/equave-reduced pitch class.

The v0.1 DSL does not treat coordinate L1 distance as musical distance by
itself. Priors may combine coordinate distance, cents distance, odd-limit,
voice-leading cost, and active-harmony relation.

### 6.1 PitchExplorationPolicy

`pitch_exploration` separates coordinate-domain breadth from audible breadth.

- `maximum_domain_points` bounds the implicit domain and is never a diversity
  target;
- exact sound classes are exact ratios reduced into `[1, equave)`; vectors
  related by an equave
  shift or generator-kernel relation occupy one exact class;
- near sound classes cluster exact classes on the circular equave pitch space;
  a deterministic bounded-diameter algorithm uses
  `near_class_merge_millicents`, not single-link chaining;
- `maximum_reduced_complexity_bits` bounds the sum of numerator and denominator
  bit lengths after exact equave reduction;
- `reference_divisions` is an evaluation grid only. Presets default to 12 for
  `2/1` and 13 for `3/1`; it never quantizes generated pitches;
- the audible offset band measures distance from the nearest reference-grid
  pitch. It is a target band rather than a “farther is better” objective;
- audible event share is weighted by duration, accent/velocity, track gain,
  and foreground occupancy, preventing short duplicated ornaments from
  satisfying the target;
- color exposure must occur in multiple sections and at least one non-unison
  color interval relation must recur in another phrase or section;
- the melodic-jump ceiling is measured in absolute sounding millicents, not
  lattice L1 distance.

All cent-like serialized values use integer millicents. For cross-equave
algorithms, the evaluator additionally stores an integer equave phase in
`0..999999999`, computed with versioned high-precision logarithm and
round-half-even rules. Exact pitch-class identity never uses logarithms.

An intentional coordinate-only move that remains in the same near sound class
is a neutral mutation for perceptual diversity. The domain can therefore be
large without pretending to be a large audible scale.

## 7. Form

```yaml
form:
  - id: sec_intro
    role: intro
    bars: 4
    energy_q: [1800, 3200]
    density_q: [2200, 3400]
    tonal_center: [0, 0, 0]
    development_stage: introduce
  - id: sec_drop_a
    role: drop
    bars: 8
    energy_q: [8200, 9400]
    density_q: [7600, 9000]
    tonal_center: [1, 0, 0]
    development_stage: develop
```

Sections are ordered and contiguous. `start_bar` is derived, never stored.

- sections: `1..16`;
- total bars: `1..128`; the GEN0 prior initially samples `16..64`;
- bars per section: `1..32`; the GEN0 prior initially samples `2..16`;
- `energy_q` and `density_q` are integer endpoints in `0..10000`;
- `development_stage`: `introduce | repeat | develop | contrast | recall | close`;
- `role` is a descriptive open string, not a generator dispatch key;
- later sections express A/A' by referencing the same material through new
  realizations rather than copying prior event arrays.

## 8. Tracks

```yaml
tracks:
  - id: lead
    role: melody
    instrument_id: pi17
    register_cents: [1200, 3600]
    maximum_polyphony: 1
  - id: harmony
    role: harmony
    instrument_id: pi18
    register_cents: [0, 3600]
    maximum_polyphony: 6
  - id: drums
    role: drums
    instrument_id: gm_kit
    drum_map: {kick: 36, snare: 38, closed_hat: 42}
```

- tracks: `1..8`;
- role: `drums | bass | harmony | melody | texture`;
- register endpoints are integer cents relative to base frequency and may only
  be satisfied through equave placement, never pitch-class substitution;
- `instrument_id` resolves against a versioned instrument catalog whose digest
  is part of the compiler build identity.
- a drums track declares a non-empty `drum_map` from symbolic lane IDs to MIDI
  notes `0..127`; non-drum tracks must not declare it.

## 9. Materials

Materials form an ID-addressed collection of event-independent source objects.
A song initially
samples `2..5` seed materials; later appearances normally reference and
transform them.

### 9.1 RhythmCell

```yaml
- id: rhythm_hook
  kind: rhythm_cell
  length_ticks: 1920
  steps:
    - {at_tick: 0, duration_ticks: 210, accent_q: 8800}
    - {at_tick: 360, duration_ticks: 180, accent_q: 7200, lane_id: kick}
```

Step input order is semantic and must be nondecreasing by `at_tick`; same-onset
order remains meaningful. Rests are the absence of steps. Overlap is valid
at the material level and checked against the target track at realization.
For a drums realization every step must carry `lane_id`, which resolves through
the target track's `drum_map`. For a pitched realization no step may carry
`lane_id`. Missing lanes fail with `UNKNOWN_DRUM_LANE`; no catalog fallback
occurs.

### 9.2 MelodyIntent

```yaml
- id: contour_hook
  kind: melody_intent
  rhythm_id: rhythm_hook
  points:
    - {relation: chord_member, member: 2, contour: hold}
    - {relation: neighbor, of_member: 2, direction: up,
       target_edo_steps: 2}
    - {relation: approach, to_member: 0, direction: down}
  mapping: cycle
```

`mapping` is `zip | cycle`. `zip` requires equal intent-point and rhythm counts.
`cycle` maps rhythm-step ordinal modulo point count.

`chord_member` shares the exact vector of the selected chord realization.
`neighbor` and `approach` are resolved over a short phrase window against the
active/next chords, target 12-EDO frequency relation, sounding contour,
complexity, and resolution direction. They are not independently snapped to
the nearest lattice point. If no phrase solution exists, the compiler returns
to another harmony-path candidate or fails with `MELODY_HARMONY_CONFLICT`.
Implicit retuning of a sustained common tone is forbidden; any comma movement
requires explicit event provenance.

Only `chord_member` is part of SP0. `neighbor` and `approach` are draft GEN0
extensions; when enabled they inherit the active ChordIntent reference rather
than a global reference grid. Mixed-reference phrases and melody-to-harmony
backtracking are unsupported in SP0. A melody failure returns the stable
`MELODY_HARMONY_CONFLICT` error without trying another harmony path.

### 9.3 ChordIntent and HarmonyIntentCell

```yaml
chord_intents:
  - id: ci_major7
    reference:
      temperament: edo
      equave: 2/1
      divisions: 12
      steps: [0, 4, 7, 11]
    voicing:
      bass_policy: preserve_target
      bass_target_ordinal: 0
      minimum_spacing_millicents: 70000
      maximum_span_millicents: 4800000
    recognition:
      maximum_pair_error_millicents: 38000
      maximum_pair_rms_millicents: 22000
    complexity_budget: 30

materials:
  - id: harmony_drop
    kind: harmony_intent_cell
    rhythm_id: rhythm_chords
    root_anchors: [[0, 0, 0], [1, 0, 0]]
    chord_intent_ids: [ci_major7]
    mapping: cycle
```

`reference.steps` describes the target frequency relationships, not a fixed
scale. For 12-EDO, target voice `i` has ratio `2 ** (steps[i] / 12)` relative
to the first voice, independent of the SongProgram domain equave. Thus a
`3/1` lattice domain may still search for a chord whose target relationships
come from ordinary 12-TET; it must fail explicitly if its generators/bounds
cannot realize the requested tolerance.

Canonical step is `s mod divisions`. Targets sort by `(edo_phase_mc,
canonical_step)` and receive canonical ordinals after sorting. `bass_policy` is
`any` or `preserve_target`; the latter requires `bass_target_ordinal` in
`0..voice_count-1`, while `any` requires it null. No implicit conversion from
input-array ordinal is permitted.

The resolver compares the full signed pairwise interval matrix of the target
with the full matrix of every lattice-chord candidate. It must not independently
snap target voices to their nearest lattice pitches. Hard maximum pair and RMS
errors cannot be traded away by complexity, roughness, or voice-leading gains.

At rhythm-step ordinal `i`, `cycle` selects
`root_anchors[i mod root_count]` and
`chord_intent_ids[i mod intent_count]`; `zip` requires counts equal to the
rhythm-step count. `root_anchors` guide progression placement but do not form a
finite vocabulary of permitted notes.

### 9.4 ResolverProfile (compiler/cohort artifact)

Resolver controls are not SongProgram fields and cannot be mutated by the
planner. They belong to the versioned compiler/cohort manifest; changing them
changes compiler/cohort identity, not musical genotype.

```yaml
resolver_profile:
  algorithm: sp0-joint-bnb/v1
  candidates_per_intent: 24
  optimized_report_schema: 1.0.0
  progression_algorithm: gen0-progression-exact/v1
  operation_budget_profile: gen0-progression-exact-v1
```

The profile contains a typed budget ledger rather than an unaccounted global
loop: structural operations, placed pitches examined, exact reductions,
joint nodes, progression edges, and melody nodes. Every loop charges exactly
one counter. SP0 uses an `sp0-small-exact-v1` profile with a 4,096
placed-pitch compiler ceiling. GEN0-A/B algorithm and budget identities are governed by
the optimized-resolver and progression contracts; benchmark changes may alter
profile ceilings but never candidate/result semantics.

Chord shape search fixes the first relative vector to zero, removing common
lattice-translation symmetry. It lazily indexes root-relative difference
vectors near each target interval, then performs deterministic joint
branch-and-bound. Adding a voice evaluates all pairwise relationships to the
voices already chosen. Exact/near-collision spellings cannot multiply candidate
weight.

SP0 ignores the progression fields and uses exhaustive small-domain exact
search ranked only by hard pair limits, pair RMS/max error, exact-ratio
complexity, and canonical tie-break. No roughness, openness, character, recall,
or genre cost participates in SP0 ranking.

GEN0-A optimized chord resolution is governed by
[song_program_optimized_resolver_contract.md](song_program_optimized_resolver_contract.md).
GEN0-B retains exact top-K chord states and uses the exact lexicographic Viterbi
and voice-correspondence rules in
[song_program_progression_contract.md](song_program_progression_contract.md).
Weighted musical costs and native beam results are non-conforming.

Search uses fixed integer millicent/numeric contracts and stable lexicographic
tie-breaking. In SP0, budget exhaustion returns a typed failure and only
`exact` results may enter Project 1.2. Experimental `beam_bounded` results are
diagnostic artifacts outside native Project/QD/viability inputs until a later
ADR promotes them. No mode invokes a per-note nearest-snap fallback.

## 10. Realizations

```yaml
realizations:
  - id: real_drop_lead
    section_id: sec_drop_a
    track_id: lead
    material_id: contour_hook
    at_tick: 0
    repeat: 4
    every_ticks: 1920
    rhythm_transforms:
      - {op: rotate, ticks: 240}
    pitch_transforms: []
    velocity_scale_q: 9500
    gate_scale_q: 8200
```

Offsets are section-relative. `repeat` is `1..32`; `every_ticks` must be
positive. Expanded events must remain inside the section unless a future
explicit transition realization type permits a boundary crossing.

A realization has zero to eight transforms total across `rhythm_transforms`
and `pitch_transforms`. Each list applies left to right and does not nest. The
rhythm list targets the material's referenced `RhythmCell`; the pitch list
targets compatible `MelodyIntent` or `HarmonyIntentCell` relations. A direct `RhythmCell` realization
may declare only `rhythm_transforms`.

SP0 through LLM4 permits only the temporal `rotate` rhythm transform and rejects
a non-empty `pitch_transforms` list with `UNSUPPORTED_SP0_TRANSFORM`. The
remaining entries below are reserved v0.2 vocabulary and are not residual
requirements of the frozen 0.1/GEN0/LLM1-4 scope.

## 11. Reserved v0.2 Transform DSL

The initial closed vocabulary is:

| Operator | Input | Parameters | Declared scope |
| --- | --- | --- | --- |
| `rotate` | rhythm cell | `ticks` | onset time |
| `reverse` | rhythm cell | none | onset time |
| `slice` | rhythm cell | `from_tick`, `to_tick` | length/events |
| `stretch` | rhythm cell | `factor: n/d`, bounded | time |
| `thin` | rhythm cell | `keep_q`, `choice_key` | event presence |
| `lattice_transpose` | pitched | `vector` | pitch |
| `invert` | melody intent | `axis_vector` | pitch relation |
| `register_shift` | pitched | `equaves` | register |

Transform semantics must be total for supported input kinds or return a typed
compile error. Identity transforms canonicalize away. Structural/time
transforms run before pitch transforms; within each group, source order is
preserved. A program that places them in a different group order is
canonicalized to the specified phase order and receives a diagnostic. A later
version may reject noncanonical order after tooling supports it.

`thin` is the only stochastic transform. Its decision for each source step is
derived from a keyed hash of `(program seed, choice_key, realization id,
repeat ordinal, source step semantic address)`. It cannot consume a global RNG
sequence.

Normative temporal semantics are:

- `rotate(ticks)`: `at_tick = (at_tick + ticks) mod length_ticks`; duration is
  unchanged and steps are sorted by `(at_tick, source_ordinal)`;
- `reverse`: `at_tick = length_ticks - (at_tick + duration_ticks)`; a negative
  result is invalid;
- `slice(a,b)`: retain only steps fully contained in `[a,b)`, subtract `a`
  from their onsets, set length to `b-a`, and reject an empty result;
- `stretch(n/d)`: multiply onset, duration, and length by `n/d`; every result
  must be integral or compilation fails—rounding is forbidden.

Temporal transforms apply only to `RhythmCell`. Melody and harmony materials
inherit timing from their referenced, transformed rhythm. Applying a temporal
transform directly to either pitched material kind is a type error.

## 12. Interactions

### 12.1 OnsetAvoid

```yaml
- id: int_lead_kick
  kind: onset_avoid
  section_id: sec_drop_a
  subject_track_id: lead
  object_track_id: drums
  window_ticks: 30
  strength: soft
```

The object is immutable. A `hard` violation rejects the program. For `soft`,
violations are retained and scored.

### 12.2 CallResponse

```yaml
- id: int_call_answer
  kind: call_response
  section_id: sec_drop_a
  call_track_id: lead
  response_track_id: harmony
  split_ticks: [1920, 3840]
  maximum_overlap_ticks: 120
  strength: soft
```

This is an evaluable scheduling constraint, not an event generator. Material
ancestry must create the musical relationship explicitly.

Interaction ordering is by `id`. Conflicting hard interactions do not choose a
winner; any hard violation fails compilation.

## 13. ProductionPlan

```yaml
production:
  profile_id: kawaii_future_bass_v1
  catalog_digest: sha256:...
  tracks:
    lead: {gain_q: 7600, pan_q: 800}
  envelopes:
    - id: env_drop_pump
      section_id: sec_drop_a
      target_track_id: harmony
      parameter: sidechain_send
      points: [{tick: 0, value_q: 9000}, {tick: 240, value_q: 1200}]
      repeat_every_ticks: 480
```

v0.1 parameters are `gain`, `pan`, `filter_cutoff`, `stereo_width`, and
`sidechain_send`. Production may not alter note timing or pitch. A profile
provides instrument/mix priors, not completed event patterns.

## 14. CompilePolicy and Limits

```yaml
compile_policy:
  repair: reject
limits:
  max_sections: 16
  max_bars: 128
  max_tracks: 8
  max_materials: 64
  max_realizations: 512
  max_transforms_per_realization: 8
  max_events: 8192
```

Program limits are structural schema limits only. Operation ceilings belong
exclusively to CompilerManifest and are frozen in
[song_program_budget_contract.md](song_program_budget_contract.md). Expansion
is checked before realization; failure returns no partial output.

## 15. Compiler Semantics

Compilation passes are normative and ordered:

1. strict parse and range validation;
2. canonicalize source representation;
3. build symbol table and resolve every reference;
4. derive the contiguous section timeline;
5. estimate expansion and enforce budgets;
6. instantiate finite realization repeats and semantic addresses;
7. apply SP0 temporal rhythm transforms;
8. construct finite chord queries from rhythm steps, root anchors, and
   ChordIntents;
9. exhaustively resolve each small-domain joint chord and create canonical
   exact `ResolvedChord` entries;
10. bind chord-member melody points to selected resolved-chord voices;
11. resolve non-harmony direct vectors and their registers;
12. evaluate enabled post-SP0 interactions, if the compiler capability permits
    them;
13. validate invariants and hard constraints; any violation rejects the
    program;
14. lower to ArrangementProject 1.2 without changing harmony registers;
15. sort events, assign stable IDs, and validate the project;
16. compute artifact hash and return Project plus a separate CompileReport.

No pass may feed production automation back into note generation.

For non-harmony direct-vector events, register resolution is deterministic
placement, not repair. Apply material
`register_delta` and all `register_shift` operations first. Enumerate equave
exponents whose exact pitch lies inside the target track range. Choose the
candidate minimizing `(absolute distance from requested exponent, exponent)`;
if none exists, reject.

Harmony anchor vectors, registers, equave exponents, voice ordering, and voice
paths are authoritative outputs of `ResolvedChord`/progression selection.
Lowering validates and copies them and must never invoke independent register
placement. Any range or crossing violation rejects the selected state.

`onset_avoid` with `strength: hard` is validation in v0.1 and does not move or
delete events. Soft constraints emit diagnostics and scores. Bounded repair
and its priority system require a separate v0.2 ADR.

All counter names, charges, ceilings, atomic reservation semantics, and failure
codes are defined only by
[OperationBudgetLedger v1](song_program_budget_contract.md). Earlier single
operation-counter rules are non-conforming.

## 16. Deterministic Ordering and IDs

Event order, SemanticAddressEncoding v1, and EventId v1 are defined only by
[ArrangementProject 1.2](arrangement_project_1_2_contract.md). IDs are computed
before the final event sort. Earlier order or unhashed-concatenation formulas
are non-conforming.

## 17. Canonical Serialization and Hashes

- unknown fields are rejected;
- default values are materialized;
- ratios use reduced `n/d`, including integers as `n/1`;
- floating-point numbers, exponent notation, NaN, infinity, and negative zero
  are prohibited;
- quantized controls use integers `0..10000`;
- object keys use deterministic ordering;
- `tracks`, `materials`, `chord_intents`, `realizations`, `interactions`, and
  `production.envelopes` sort by `id`;
- `form`, rhythm steps, melody-intent points, harmony root anchors/intent IDs,
  `rhythm_transforms`, `pitch_transforms`, and envelope points preserve
  semantic order; the two transform lists already define the temporal and
  pitch phases;
- serialization is UTF-8 JSON with sorted keys and no insignificant whitespace.

```text
program_hash = SHA256("cps.song-program/0.1\0" + canonical_program_bytes)
artifact_hash = SHA256(compiler_build_id + "\0project/1.2.0\0" +
                       canonical_project_bytes)
```

Program-hash exclusion is exactly `/program_id`. UI annotations live in a
separate artifact; an `/annotations` SongProgram field is rejected.
Project 1.2 forbids `artifact_hash`, `generated_at`, and `diagnostics`, so no
hash exclusions exist. Compile reports and audit reports are separate artifacts.
`compiler_build_id` includes schema/pass versions,
dependency lock digest, PRNG/choice algorithm version, and instrument-catalog
digest.

## 18. ArrangementProject 1.2 Requirements

The normative, directly implementable schema, provenance equations, canonical
orders, ResolvedChord hash preimage, reference validation, capability boundary,
and fixtures are frozen in
[arrangement_project_1_2_contract.md](arrangement_project_1_2_contract.md).
It supersedes all earlier Project 1.2 sketches.

Project 1.2 stores the lattice-domain digest and the actually visited exact
sound-class table. Near-class clustering and perceptual exposure remain outside
the SP0 Project/hash in a versioned `PitchAuditReport`; their deterministic
computation and calibration boundary are governed by the renderer/evaluation
contract. An illustrative report is:

```yaml
pitch_space_summary:
  coordinate_point_count: 180
  coordinate_axis_span: [12, 8, 6]
  exact_sound_class_count: 83
  near_sound_class_count: 67
  coordinate_inflation_bps: 12500
  used_sound_class_count: 18
  audible_color_event_share_q: 2480
  exposed_section_count: 3
  recurrent_color_relation_count: 4
  sounding_interval_entropy_q: 6320
  coordinate_collision_count: 14
```

`coordinate_inflation_bps` is `10000 * coordinate spellings / near sound
classes`; `10000` means no inflation. It is a diagnostic/penalty, never a
novelty reward.
Class counts, entropy, and event share deduplicate identical simultaneous events
before duration/accent/foreground weighting.

`PitchAuditReport` records the source Project artifact hash and complete metric
protocol hash. It cannot change Project validity, artifact identity, SP0
viability, or chord selection.

Project 1.2 contains canonical `resolved_chords[]` and gapless
`harmony_occurrences[]`. `chord_index` names an occurrence, never an array
position. Candidate archives, runner-ups, search statistics, operation budgets,
and telemetry remain separate artifacts.

One `ResolvedChord` entry is:

```yaml
resolved_chord:
  id: rc_...
  domain_hash: sha256:...
  intent_hash: sha256:...
  resolver_build_id: ...
  numeric_contract: cps-numeric/decimal-log2-rhe-v1
  search_completeness: exact
  reference_equave: 2/1
  reference_divisions: 12
  canonical_steps: [0, 4, 7]
  eligibility_contract:
    bass_policy: preserve_target
    bass_target_ordinal: 0
    minimum_spacing_millicents: 70000
    maximum_span_millicents: 4800000
    maximum_pair_error_millicents: 15641
    maximum_pair_rms_millicents: 12052
    complexity_budget: 10
  anchor_vector: [0, 0, 0]
  voice_offsets: [[0, 0, 0], [0, 1, 0], [1, 0, 0]]
  equave_exponents: [0, -2, -1]
  exact_ratios: [1/1, 5/4, 3/2]
  target_voice_ordinals: [0, 1, 2]
  pair_errors_millicents: [-13686, 1955, 15641]
  maximum_pair_error_millicents: 15641
  pair_rms_error_millicents: 12052
  complexity_score: 10
```

Harmony events store resolved-chord ID, target/shape voice ordinals, voice-path
ID, anchor/offset/final vectors, equave exponent, and exact ratio. The Project
validator requires `final_vector = anchor_vector + voice_offset` and recomputes
every ratio, the full pair-error matrix,
and the progression predecessor/voice-assignment chain. Exact numeric rules are
frozen in [song_program_numeric_contract.md](song_program_numeric_contract.md),
and deterministic stopping rules in
[song_program_budget_contract.md](song_program_budget_contract.md).

## 19. Mutation Contract

Mutations are typed operations, not unrestricted JSON Patch:

```yaml
patch_schema_version: 0.1.0
base_program_hash: sha256:...
mutation_id: mut_001
op: transpose_material
target_id: contour_hook
vector: [0, 1, 0]
declared_scope: material/contour_hook
```

Initial mutation operations are:

- replace one bounded scalar;
- replace one compatible reference;
- insert/delete one realization;
- append/remove one compatible transform;
- transpose one pitched material;
- replace one material step;
- replace one production envelope point.

Each compiled event carries a dependency set. After mutation, canonical event
cores and automation outside the dependency closure must be identical or the
compiler reports `NON_LOCAL_MUTATION`. Form-length edits are explicitly
`global` mutations and are not evaluated as local.

## 20. Generation Prior Contract

The sampler is separately versioned from the schema. It produces distributions,
not role-specific complete templates.

Initial prior requirements:

- `3..8` sections totaling `16..64` bars;
- `2..5` seed materials;
- at least three active part roles across the song;
- at least one transformed material recall;
- each later section chooses new material or a prior material plus `1..3`
  transforms;
- probability of recall increases in the latter half;
- limits on consecutive identical roles and exact material copies;
- local pitch prior combines cents, lattice distance, harmonic complexity, and
  current chord relation;
- pitch selection is two-stage: select a collision-corrected sound class, then
  choose a vector spelling from that class using tonal-center distance,
  voice-leading, and complexity priors;
- the initial class mixture reserves non-zero mass for anchor, audible-color,
  and contrast classes, and gives unused sound classes a bounded novelty bonus;
- pitch-diversity audits use near sound classes, audible color share, interval
  entropy, section exposure, and recurrent color relations—not coordinate count
  or raw L1 excursion; these remain audit-only until listening calibration;
- global prior covers introduction, development, contrast, recall, and closure
  without mapping those stages to fixed section patterns;
- the sampler assigns descriptive `role` labels only after form, material, and
  realization decisions; replacing every role label and recompiling with the
  same seed must not alter those decisions;
- genre profiles may initially condition BPM, production macros, and bounded
  operator probability ranges, but every enabled operator retains a declared
  non-zero exploration probability.

Sampler output must include a decision trace and named random-choice addresses.

## 21. Acceptance Tests for the v0.1 Freeze

### Compiler correctness

- property-based compilation of 10,000 valid programs terminates within the
  operation budget;
- same canonical program and build compile byte-identically across 100 runs;
- canonical parse/serialize round-trip preserves `program_hash`;
- every event is within its section and clock, has valid references and a
  unique stable ID;
- every pitched event's vector recomputes exactly to its ratio;
- exact/equave-shift-equivalent vectors map to one exact sound class independent
  of lazy-enumeration order;
- a later `PitchAuditReport` protocol must prove near-class membership/ID order
  invariance and that extra coordinate spellings cannot increase audible class
  count, share, or interval entropy before those metrics affect selection;
- `2/1` and `3/1` golden fixtures validate reduction, circular distance,
  reference-grid offset, and boundary rounding;
- cycles, dangling references, 8,193 events, invalid ratios, and boundary
  overflow fail before lowering with a JSON pointer and stable error code;
- input map ordering and constraint ordering do not change output;
- adding an unrelated realization does not change existing keyed choices;
- known 12-TET major, minor, and dominant-seventh intents find joint lattice
  chords within their declared pairwise tolerances in reference domains;
- a counterexample where independently nearest voices violate a pairwise limit
  must yield another joint chord or `NO_JOINT_CHORD_SOLUTION`, never the snapped
  collection;
- stored chord errors, anchor/offset vectors, exact ratios, voice paths, and
  predecessor chains recompute exactly;
- small-domain optimized search matches an exhaustive oracle; expanding a
  domain or search budget cannot worsen the best objective under the same
  algorithm version;
- progression search beats or equals greedy per-chord choice on fixed
  voice-leading counterexamples;
- capability-supported Project 1.2 projects produce valid 1.1 compatibility
  views and pass existing MIDI/WAV exporters; unsupported equaves return a
  stable capability error and are never silently converted.

### Mutation locality

- dependency-closure scope violations are zero;
- inverse metamorphic tests hold where defined: reverse twice is identity,
  rotate `n` then `-n` is identity, stretch `1/1` is identity;
- at least 95% of declared small mutations fall inside preregistered symbolic
  and perceptual distance bands;
- neutral mutations remain below a preregistered ceiling.

### Search viability and diversity

- a `musical_fingerprint` excludes IDs, velocities, instruments, production,
  and provenance; it transposition-normalizes sounding pitch and contains the
  section-length sequence, part-entry mask, quantized onset/duration tuples,
  reduced sounding pitches, and material-recall edges;
- fingerprint quantization, component weights, and the near-duplicate threshold
  must be preregistered in an ADR before measuring the generator;
- at least 95% of 1,000 prior samples compile under `repair: reject`;
- initial automatic viability is at least 70% and must reach 80% before an LLM
  planner is introduced;
- canonical exact duplicates are below 1%;
- canonical-event near duplicates, excluding velocity-only differences, are
  below 10%;
- at least 80% of songs contain a transformed recall;
- internal median pairwise distance significantly exceeds the current Kawaii
  generator's seed-to-seed baseline;
- root-anchor n-grams, ChordIntent n-grams, and harmony-rhythm fingerprints are
  reported separately; no single n-gram/fingerprint mode may exceed `35%` of
  the preregistered broad-prior cohort;
- lattice-vector diversity is reported separately from reduced sounding-pitch
  diversity.
- audible-share, exposed-section, recurrent-relation, and interval-entropy
  values are audit-only until the matched listening protocol calibrates a
  later gate;
- coordinate inflation has a cohort median no greater than `1.5` and 95th
  percentile no greater than `2.0`;
- widening coordinate bounds is accepted only when sounding-class count and
  sounding-interval entropy both improve over the previous cohort; increased
  out-of-old-bound usage alone is not improvement.

The GEN0 viability gate requires `16..64` bars, `3..8` sections, at least one
realization in every section, actual emitted events on at least three of the
drums/bass/harmony/melody roles, preregistered bounds on silent-bar ratio and
maximum polyphony, and a non-identity transformed recall of the same material
in at least two sections. Compile success and viability success are reported
separately. Lineage concentration becomes an acceptance criterion only after a
quality-diversity archive exists.

The numerical thresholds are preregistered GEN0 starting points. They may be
changed only through an Architecture Decision Record backed by baseline data.

## 22. Architecture Decisions and Calibration Work

The former P0 decisions are resolved in
[adr_song_program.md](adr_song_program.md): variable equave, mutation-band
calibration, renderer/catalog identity, Project 1.2 authority and legacy
isolation, the versioned broad sampler, and the initial quality-diversity axes.

Implementation still requires preregistering the concrete calibration
artifacts: anchor mutations, listener cohort, instrument assets, renderer
ceiling fixtures, sampler probability tables, fingerprint thresholds, and QD
bin edges, plus `PitchExplorationPolicy` thresholds and matched-snap listening
fixtures. These values may be selected from baseline measurements but may not
silently alter the accepted architecture or overwrite an earlier cohort.

## 23. First Implementation Slice

Build SP0 in three bounded slices before implementing a sampler:

1. strict Pydantic models with `extra="forbid"`;
2. canonical serializer, NumericContract, and program hash;
3. generic exact vector/equave/reduction fixtures for `2/1` and `3/1`;
4. a small-domain exhaustive joint-chord oracle and exact resolver;
5. Project 1.2 provenance union plus canonical inline `resolved_chords[]`;
6. one 8-bar `2/1` linear form with one rhythm cell, one chord intent, and
   chord-member-only melody;
7. temporal `rotate` only; pitch transforms, `thin`, interactions, and
   production envelopes are deferred;
8. determinism, bounds, provenance, numeric, and oracle-equality tests.

This slice answers whether the representation and compiler contract work. It
does not attempt to prove genre quality.
