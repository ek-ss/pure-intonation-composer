# Composition Generation Profile 2.0

Status: implemented, non-authoritative composition planning contract.

## Scope

`cps.composition-generation-profile` version `2.0.0` is a new contract. It does not
extend or replace `cps.song-preview-exploration-profile`. Version 2.0 initially owns
four stages:

1. selection of an ordered form template;
2. exact partition of every section into ordered phrases.
3. a phrase-aligned, function-constrained harmonic trajectory.
4. a normalized foreground motif lineage with explicit transformations.

Groove, coordinated parts and SongProgram lowering are later stages.
Consumers must not infer those stages from a CompositionPlan.

The machine-readable schemas are:

- `backend/songprogram_conformance/schemas/composition_generation_profile_2_0.schema.json`
- `backend/songprogram_conformance/schemas/composition_plan_2_0.schema.json`

The initial checked-in profile is:

- `backend/songprogram_conformance/profiles/composition_generation_v2.json`

The executable entry point is:

```bash
backend/.venv/bin/python backend/tools/generate_composition_plan.py \
  --profile backend/songprogram_conformance/profiles/composition_generation_v2.json \
  --seed 0 \
  --output /tmp/composition-plan.json
```

Omitting `--output` writes the canonical JSON bytes plus one LF to stdout. File output
uses a same-directory temporary file and atomic replacement.

## Ordered form

Each template contains three to eight sections in playback order. Every section owns
its function, bar count, energy target, density target, cadence target and foreground
state. These values are not derived from a section label.

The first function must be `opening`, the last must be `closure`, and every adjacent
function pair must be present in this transition table:

```text
opening     -> statement | arrival
statement   -> preparation | arrival
preparation -> arrival | return
arrival     -> statement | contrast | return | closure
contrast    -> preparation | return
return      -> preparation | closure
closure     -> (none)
```

Section keys are unique within one template. Total form length is 16–64 bars.

## Phrase generation

Phrase length choices are declared independently for every section function. The
generator partitions a section without gaps or overlap. At each phrase boundary it
removes choices that would leave an unpartitionable remainder, then makes one weighted
choice from the remaining rows.

`slots_by_length_bars` contains exactly one slot sequence for every declared phrase
length. A sequence has one slot per bar and its last slot is always `cadence`.
Non-final phrases receive cadence target `continuation`; the final phrase inherits the
section cadence target.

## Deterministic choice

The profile seals `seed-domain-sha256-weighted/v1`. For each decision:

```text
digest = SHA-256(
  UTF8("cps.composition-choice/2.0") || 0x00 ||
  U64BE(seed) || UTF8(domain)
)
point = U64BE(digest[0:8]) mod sum(weights)
```

Rows retain profile order. The selected row is the first cumulative interval containing
`point`. Domains are:

```text
form-template
phrase-length/<template_id>/<section_ordinal>/<phrase_ordinal>
```

Filtering ineligible phrase lengths does not reorder the remaining rows.

## Harmonic trajectory

The profile declares harmonic states independently from a concrete lattice. Each state
has a functional identity and a signed `root_degree_ordinal`; conversion of that ordinal
to a JI lattice vector belongs to a later lowering contract.

Every phrase receives exactly one state. The first phrase uses `home_state_id`. Later
states are selected only from transitions whose destination is allowed by both the
section function and the phrase cadence target. Transition rows retain profile order.
The decision domain is:

```text
harmonic-state/<phrase_id>
```

The checked-in profile distinguishes `home`, `departure`, `preparation`, `arrival` and
`return`. This prevents the earlier generator's single harmony state from being copied
unchanged through the entire form without prematurely choosing an equave or generator
basis.

## Motif lineage

Motif templates use normalized phrase coordinates. `position_q` and `duration_q` are
integer fractions of a phrase on `[0, 10000]`; `degree_delta` is an abstract melodic
ordinal. Concrete ticks and lattice vectors belong to later lowering.

The first non-absent foreground phrase creates `motif_000`. Every derived event records
the corresponding root `source_event_id`, and every derived occurrence records the root
`source_phrase_id`. Supported operations are:

```text
statement
recall
answer
rhythmic_displacement
fragmentation
cadential_release
rest
```

`answer` negates degree deltas. Displacement chooses only signed offsets that keep all
events within the phrase. Fragmentation retains the first half of the root events.
Cadential release keeps the final source event, moves it to the phrase end and resolves
its abstract degree to zero. Foreground state `recall` cannot select an unchanged
`recall`, so a declared return always contains a non-identity development operation.

Decision domains are:

```text
motif-template
motif-operation/<phrase_id>
motif-displacement/<phrase_id>
```

## Canonical hashes

Canonical bytes use the repository canonical JSON encoding.

```text
profile_hash = SHA-256(
  UTF8("cps.composition-generation-profile/2.0") || 0x00 ||
  canonical(profile without profile_hash)
)

plan_hash = SHA-256(
  UTF8("cps.composition-plan/2.0") || 0x00 ||
  canonical(plan without plan_hash)
)
```

Hashes are lowercase and represented as `sha256:<64 hex>`.

## Failure precedence

Generation validates in this order:

1. complete profile payload, semantic form constraints and `profile_hash`;
2. unsigned 64-bit seed;
3. exact phrase partition while traversing sections in ordinal order;
4. harmonic path while traversing phrases in ordinal order.

Stable errors are:

```text
COMPOSITION_PROFILE_INVALID
COMPOSITION_SEED_INVALID
COMPOSITION_PHRASE_PARTITION_UNAVAILABLE
COMPOSITION_HARMONIC_PATH_UNAVAILABLE
COMPOSITION_MOTIF_TRANSFORM_UNAVAILABLE
```

No fallback, profile repair, ambient randomness or fixture lookup is permitted.

## Song generation bridge

The initial non-authoritative bridge lowers a CompositionPlan onto the lattice and
production authority supplied by the existing structural sampler, then uses the existing
compiler and reference renderer:

```bash
backend/.venv/bin/python backend/tools/generate_composition_song.py \
  --seed 0 \
  --output local_authority/composition_generation_v2_seed0
```

It creates:

```text
composition_plan.json
structural_program.json
program.json
project.json
preview.wav
receipt.json
song_validity.json
```

The bridge requires drums, bass and harmony material authority from the structural
sampler. A candidate without that exact core set is rejected; the bridge tries at most 64
consecutive structural authority seeds while keeping the requested composition seed and
CompositionPlan unchanged. The selected structural seed and rejection ordinal are stored
in the receipt. It creates phrase-specific melody intent and rhythm materials directly from the
motif lineage. Melody durations are bounded by both phrase and harmony-occurrence bar
boundaries, preserving exact chord-member binding.

This bridge proves end-to-end generation; it is not yet the final Stage D coordinated
part generator.

## Stage D initial coordination

The checked-in `part_coordination_policy` now owns normalized kick, bass and boundary
gesture positions. Bass onsets must be a subset of drum onsets. Lowering creates section-
specific drum and bass materials, follows the section harmonic root vector, and adds one
shared boundary gesture material on the last bar of every section. Return sections apply a
non-identity transformation to that shared gesture, preserving audible and metadata recall.

Motif `degree_delta` selects among the resolved chord's target voice ordinals `0`, `1`
and `2`; it no longer collapses every melody event to the chord root. Concrete chromatic
or JI interval displacement beyond chord membership remains a later lattice-degree policy.

## Implemented section semantics

The section name is descriptive only. Audible behavior is determined by the section's
`function`, `energy_q`, `density_q`, `cadence_target`, `foreground_state` and the lowering
rules below. This section documents the current implementation, including its known gaps;
it must not be read as the intended final arrangement contract.

### Common behavior in every section

The current lowering emits all four roles in every section. It does not yet use a
section-specific role mask.

| Role | Current realization |
| --- | --- |
| drums | Four identical note-36 hits per bar at normalized positions 0, 2500, 5000 and 7500, plus one shared boundary hit in the final bar at 8750 |
| bass | Two root-vector notes per bar at positions 0 and 5000, fixed one-equave-down register and fixed gate policy |
| harmony | The same source harmony material once per bar; the section tonal center can transpose it but rhythm, voicing policy and gate do not change by section |
| melody | One phrase-specific chord-member melody realization for every non-rest motif occurrence |

`energy_q` is copied to the section and used as the realization velocity scale. It is
constant within a section, so a change at a boundary is a step rather than a ramp.
`density_q` is copied to the section but does **not** currently alter drum subdivision,
bass onsets, harmony onsets, role presence or event thinning. Therefore two sections with
different density targets can have identical drum, bass and harmony event counts.

All sections use the same boundary-gesture material. A `return` section rotates that
gesture by one quarter note; other functions do not select distinct transition gestures.

### Function-to-lowering mapping

| Function | SongProgram role | Development stage | Tonal-center prototype | Foreground policy | What is currently audible |
| --- | --- | --- | --- | --- | --- |
| `opening` | `intro` | `introduce` | `[0, 0]` (`home`) | statement or recall | Lower velocity and the selected introductory motif operation; all four roles still play |
| `statement` | `verse` | `statement` | `[0, 0]` or `[1, 0]` | recall or answer | Medium velocity, possible departure-center transposition and motif answer; rhythm section remains unchanged |
| `preparation` | `build` | `develop` | `[1, 0]` or `[0, 1]` | answer, displacement or fragmentation | Higher velocity, preparation/departure center and motif transformation; no implemented density ramp or drum build-up |
| `arrival` | `drop` | `contrast` | `[0, 0]` | recall or answer | Highest velocity and return to a home/arrival center; no added role, layer, kick pattern or wider voicing |
| `contrast` | `break` | `contrast` | `[1, 0]` or `[0, 1]` | answer, displacement or fragmentation | Reduced velocity and possible non-home center; drums, bass and harmony are not removed |
| `return` | `verse`, or `final` when `section_key=final` | `recall` | `[0, 0]` or `[1, 0]` | non-identity answer, displacement or fragmentation | Recalled/transformed motif and rotated boundary hit; `final` otherwise differs mainly through its profile energy and cadence target |
| `closure` | `outro` | `release` | `[0, 0]` | cadential release | Low velocity, final motif source event moved to phrase end and resolved to chord member zero; other roles continue with their normal patterns |

The tonal-center prototype is the concrete lattice vector used by the current bridge:

```text
home / arrival / return -> [0, 0]
departure              -> [1, 0]
preparation            -> [0, 1]
```

It is bounded by the selected lattice domain. `cadence_target` restricts the final
harmonic state eligible for the section's final phrase, but it does not currently select
a dedicated bass cadence, drum cadence, voicing cadence or automation envelope.

### Checked-in form template A

`intro-verse-build-drop-return-final-outro` has weight 3 and always contains 32 bars:

| Section | Function | Bars | Energy | Density | Cadence | Foreground | Effective current change |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| intro | opening | 4 | 3000 | 3000 | continuation | introduce | Quiet home-centered full arrangement; introductory motif operation |
| verse_a | statement | 4 | 5000 | 5000 | continuation | present | Medium velocity; home or departure path; motif recall/answer |
| build_a | preparation | 4 | 7500 | 7000 | arrival | develop | Louder preparation center and transformed motif; fixed backing rhythm |
| drop_a | arrival | 4 | 10000 | 9000 | home | present | Maximum velocity and home/arrival center; event density remains essentially fixed |
| verse_b | return | 4 | 6000 | 5500 | continuation | recall | Reduced velocity, non-identity motif return and rotated boundary gesture |
| build_b | preparation | 4 | 8500 | 8000 | arrival | develop | Louder repetition of the same preparation mechanism |
| final | return | 4 | 9500 | 8500 | home | recall | Near-maximum velocity, home-directed state and non-identity motif return |
| outro | closure | 4 | 2500 | 2500 | home | release | Abruptly lower velocity and cadential melody release; backing roles remain active |

### Checked-in form template B

`intro-statement-arrival-contrast-build-final-outro` has weight 2 and always contains
28 bars:

| Section | Function | Bars | Energy | Density | Cadence | Foreground | Effective current change |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| intro | opening | 4 | 3000 | 3000 | continuation | introduce | Same opening mechanism as template A |
| verse_a | statement | 4 | 5500 | 5000 | continuation | present | Medium velocity and statement motif behavior |
| drop_a | arrival | 4 | 9500 | 8500 | home | present | Loud home/arrival section without extra layers |
| break | contrast | 4 | 4000 | 3500 | continuation | develop | Lower velocity and transformed motif, but the backing roles continue unchanged |
| build | preparation | 4 | 8000 | 7500 | arrival | develop | Higher velocity and preparation center without a progressive density increase |
| final | return | 4 | 10000 | 9000 | home | recall | Maximum velocity, home-directed state and transformed recall |
| outro | closure | 4 | 2500 | 2500 | home | release | Low-velocity full backing plus cadential melody release |

### Explicit non-features of the current bridge

The current bridge does not yet derive the following from section function or section
targets:

- role entry and exit, mute masks or gradual layer accumulation;
- kick/snare/clap/hat separation or function-specific drum patterns;
- density-dependent onset count, rhythmic subdivision or rest probability;
- bass-pattern changes between intro, build, drop, break and outro;
- harmony-specific voicing width, inversion, register, rhythm or gate changes;
- within-section energy ramps, filter automation, send automation or stereo motion;
- function-specific transition effects, pickups, impacts, risers or tail releases;
- gradual outro removal of parts.

Consequently, the implemented form is structurally ordered but much of its audible
contrast currently comes from stepwise velocity changes, three tonal-center prototypes
and motif event changes. These limitations are normative facts about the current bridge,
not permission for an evaluator to infer missing arrangement behavior from section names.

## Version 2.1 transition-expression successor

The normative successor changes transition generation from the current shared final-bar
hit to an ordered-pair-conditioned three-phase contract. It treats the source/destination
function pair as input and selects one deterministic weighted bundle covering
`pre_boundary`, `boundary` and `post_boundary` behavior. The complete payload, operation
set, collision rules, failure precedence and schema are defined in:

- `docs/composition_transition_expression_2_1.md`
- `backend/songprogram_conformance/schemas/composition_transition_expression_policy_2_1.schema.json`

This is a versioned 2.1 change. A 2.0 consumer must not infer or apply it, and the current
shared boundary hit remains active only until the 2.1 profile, fixtures and lowering are
implemented together.

The corresponding realization successor for motif, drums, bass, reference-functional
harmony, active density, role masks, composite energy and instrumented preview rendering
is specified in:

- `docs/composition_realization_profile_2_1.md`
