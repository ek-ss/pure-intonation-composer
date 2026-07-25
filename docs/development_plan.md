# Development Plan

**Project:** Pure Intonation Composer

Version: 0.1

## Implementation Status

This document is the active roadmap and retains detailed feature designs.
The audited, concise source of truth for completed work, partial work, known
gaps, and verification counts is [status.md](status.md).

Phases P1-P9 are implemented in their original scope. P10 remains open for
project persistence, automated browser regression, performance validation,
and distribution. Per-group status notes below explain the detailed boundary
between current behavior and planned work.

---

# 1. Purpose

This document defines the implementation roadmap for the project.

Development proceeds incrementally.

Every phase must produce a fully working system.

No unfinished features should block subsequent phases.

---

# 2. Development Principles

1. Build small working systems.
2. Every feature must have automated tests.
3. Public APIs require documentation.
4. New features must not break existing projects.
5. All algorithms must be deterministic when using the same random seed.

---

# 3. Functional Structure

Feature development is organized by function groups mirroring the
Entonal Studio manual (Rev 2.1), so the roadmap reads the same way a
microtonal workstation is used: browser → input → retuning → sound →
views → editing → global controls.

## G1. Scale Browser and Import/Export

Entonal: scale Browser (Public/User tabs), Preset/XML/Scala import/export.

Status

* Scala export — Done (`POST /api/export/scala`, workbench save button)
* JSON export — Done (`POST /api/export/json`)
* Scale browser panel (named, savable user scales, load/delete) — Done
  (in-memory store, `/api/scales*`)
* Scala import — Done (`POST /api/scales/import`)

Planned

* Persistent (on-disk) scale storage
* Preset files containing full workbench state

## G2. Input

Entonal: MIDI/MPE input type, input pitch-bend range.

Status

* PC-keyboard and pointer input with per-note ratios — Done (workbench
  keyboard, circle/graph clicking)

Planned

* MIDI input (WebMIDI) with configurable pitch-bend range
* MPE input (Version 0.2)

## G3. Retuner / Output Routing

Entonal: retuner types MIDI, MPE, Multichannel, MTS-ESP Master.

Status

* Pitched MIDI export (nearest-note quantization) — Done
* GM-percussion rhythm MIDI export — Done (`POST /api/export/rhythm/midi`)
* Pitch-bend-accurate MIDI retuning — Done (`pitch_bend` option on
  `POST /api/export/midi`, one note per channel with 14-bit bend)

Planned

* MPE and multichannel output (Version 0.2)
* MTS-ESP master (Version 0.2)

## G4. Sound Engine

Entonal: hosted plugins + SimpleSynth (wave shape, ADSR, tone, delay,
volume, mix).

Status

* Oscillators (sine/triangle/saw/square/additive) — Done
* ADSR envelope — Done
* Delay and reverb — Done
* Offline WAV rendering with async jobs — Done

Planned

* FM and noise oscillators
* Instrument presets (AudioPreset model)

## G5. Views

Entonal: Info, Radial Graph, Table, Lattice, Mapping views.

Status

* Info (interval table with ratio/cents/monzo) — Done
* Radial graph (pitch circle with harmony relations, click-to-play) — Done
* Radial graph harmonic guides (odd harmonics 5–64) — Done
* Relative-interval display between two held notes — Done
* EDO and prime-limit snapping of all scale notes — Done
  (`POST /api/tuning/snap`)
* Lattice/graph views (force-directed Johnson graph; reference-node
  layered grid with walk visualization) — Done
* Timeline view with recorder and replay — Done

Planned

* Per-note retuning by dragging on the radial graph
* MIDI-note table (128 notes with frequency and cents deviation)

### G5.1 Composition Visualizer

This work introduced a linked **Composition Roll** because the original
horizontal chord list did not make harmony, bass, and melody relationships
legible over time. The implemented view uses a cents-based vertical axis
rather than MIDI-note rows, so the actual sizes of pure intervals remain
visible. The remaining interaction work is listed below.

Status

* Stage 1 Composition Roll — Done: cents axis, octave guides, harmony stacks,
  bass and melody paths, layer toggles, chord selection, and playback playhead
  are available in the Compose workbench.
* Stage 2 linked stack display — Done: the generated harmonic path and active
  node are highlighted in the Johnson graph; the active chord's ratio stack is
  shown in both graph layouts and as an outer stack on the Pitch Circle.
* Voice-leading connectors, zoom/pan, mobile layer mode, and project-view
  persistence remain planned.

#### Primary View: Composition Roll

* **Horizontal axis:** chord step and musical time. The grid follows the
  current tempo, with bar boundaries and a movable playhead.
* **Vertical axis:** cents relative to the selected base frequency. Zooming
  and panning must preserve the cents scale; octave guides appear every
  1200 cents.
* **Harmony layer:** each generated chord is a softly connected vertical
  stack of ratio-labelled note chips. A translucent band spans its duration;
  its color identifies the corresponding harmonic-graph node.
* **Bass layer:** a heavier line below the chord stack joins successive bass
  notes. The segment label shows the chosen strategy (`root`, `fifth`, or
  `mirror`) and may expose its cent leap on hover.
* **Melody layer:** each independent voice is a separately colored polyline
  above or through the harmony, with note markers showing ratio and optional
  cents. The same voice must retain its color throughout a piece.
* **Voice-leading layer:** optionally draw faint connectors between adjacent
  chord tones. Connector opacity represents movement size, making common
  tones and large leaps immediately apparent without crowding the default
  view.

#### Linked Harmonic-Trajectory View

Provide a compact companion view above the roll: the existing Johnson graph
with only the generated harmony path emphasized. The active timeline step,
the active graph node, the chord band, and the pitch-circle focus must stay
synchronized. Selecting any one of them selects the same composition step in
the other views.

This two-view approach separates two questions which should not compete for
the same space: **where the harmony travels** (graph trajectory) and **how
the voices move** (composition roll).

#### Controls and Interaction

* Layer toggles: harmony, bass, each melody voice, and voice-leading.
* Label modes: ratio, cents, monzo, or compact labels; ratio is the default.
* Click a note to audition it; click a chord band to audition its complete
  chord; drag the playhead or click the time ruler to seek during replay.
* Hover/selection inspector: ratio, absolute cents, interval from the prior
  note, graph node/factors, transition score, and bass strategy.
* Zoom controls must be icon buttons; scroll/pinch zoom is centered on the
  pointer. A reset-view command returns to the full composition extent.
* On narrow screens, retain the time axis but show one selected layer at a
  time; the harmonic trajectory remains as a compact strip above it.

#### Data and Rendering Contract

The client should derive a normalized `CompositionViewModel` from the existing
`composeState`: chord index/start/duration, harmonic-node id and factors,
all chord tones, bass note and strategy, melody voice/note, and transition or
leap metadata. Rendering may use Canvas for performant paths and an HTML
overlay for accessible labels/selection. Keep the view model serializable so
the exact visualization can be restored from a JSON project export.

#### Delivery Sequence

1. Add the read-only composition roll with harmony, bass, melody, and a
   playback playhead. — Done
2. Link selection to the harmonic graph and pitch circle; add layer and label
   controls. — Done for harmony-path selection and ratio stacks
3. Add voice-leading connectors, inspector, zoom/pan, and mobile layer mode.
4. Persist view settings and selected step in project JSON; add screenshot and
   interaction regression tests at desktop and mobile breakpoints.

Acceptance criteria

* A generated eight-step harmony with bass and two melody voices is readable
  without opening the raw JSON response.
* Selecting a timeline step highlights exactly one harmonic-graph node and
  its chord band.
* Common tones, voice crossings (if present), and leaps larger than the
  configured limit can be visually identified.
* Playback playhead remains aligned with the scheduled audio within one UI
  frame, and the visualization remains usable on a narrow mobile viewport.

## G6. Scale Editor

Entonal: add/remove notes, enter cents/ratios/EDO degrees/math
expressions, repeating interval (octave, tritave, …).

Status

* Generative scale sources (CPS, Euler–Fokker, harmonic/subharmonic
  series) — Done
* Manual note add/remove with cents/ratio/EDO-degree/math-expression
  entry — Done (`POST /api/analyze-interval`, workbench add/remove)

Planned

* Custom repeating interval (non-2/1 normalization)

## G7. Mapping Editor

Entonal: root note/frequency, auto/custom mapping, notes-in-scale,
black-keys switch, unmapped notes.

Status

* Base frequency control — Done (workbench sound panel)

Planned

* Root note selection and learn
* Custom key mapping with unmapped notes
* Notes-in-scale forcing for 12-note keyboards

## G8. Global Controls and Real-Time

Entonal: undo/redo, scale quick-load, virtual keyboard, groups,
MIDI note names.

Status

* WebSocket transport (play/pause/stop/improvise) — Done
* Virtual performance keyboard — Done

Planned

* Undo/redo of scale and composition edits
* Scale quick-load (previous/next)
* MIDI note names for exported files
* Project save/load with grouped state

## G9. Exponent-Lattice Harmony Laboratory

This is a new experimental platform alongside CPS, not a CPS generator mode.
It treats products of integer generators as points in an exponent lattice.
A chord is represented by independent root-relative exponent vectors, while
a progression or walk moves the root by cumulative difference vectors.

Status

* Mathematical model and implementation plan — Defined below
* EV1 exact mathematical core (basis, products, normalization, prime
  matrix, dependency diagnostics) — Done (`app/lattice.py`)
* EV2 scale generation with collision grouping — Done
  (`POST /api/exponent-lattice/scale`)
* EV3 root-relative chord reconstruction and cumulative root motion — Done
  (`POST /api/exponent-lattice/harmony`)
* EV4 explicit progressions, seeded walks with boundary policies, and analyze
  endpoint — Done: progression/walk points reconstruct the same simultaneous
  root-relative chord and the full sequence can enter Compose for bass/melody
  generation, playback, and export (`POST /api/exponent-lattice/progression`,
  `/api/exponent-lattice/walk`, `/api/exponent-lattice/analyze`)
* EV5 experimental workbench (basis/domain editor, chord/progression editors,
  seeded chord generation, scale table, 2-axis lattice projection,
  chord/root-motion arrows, walk overlay, Pitch Circle layer, and ASD keyboard) —
  Partially done, behind the `Experimental` label
* EV6 persistence — Planned
* EV7 performance/docs — Partially done: API and usage documentation plus
  deterministic unit tests exist; benchmarks, worked examples, and browser
  regression coverage remain pending

Implementation audit (2026-07-25)

* Available now: exact exponent arithmetic, collision-aware scale generation,
  seeded unique-pitch chord generation, harmony reconstruction, four walk
  boundary policies, basis/distance analysis, 2-axis projection, Pitch Circle
  harmony markers, ASD keyboard audition, simultaneous chord playback, and
  chord/progression/walk transfer to Compose.
* Still required for EV5: propagate coordinate provenance into derived
  bass/melody notes and export sidecars; replace both vector text areas with
  structured rows (add, remove, reorder, duplicate), add optional
  root-coordinate editing, non-projected coordinate filtering, and
  Composition Roll exponent-coordinate lanes.
* Still required for EV6: versioned project JSON, migration handling,
  coordinate-plus-ratio persistence, and Scala/MIDI/WAV interoperability rules.
* Still required for EV7 and promotion from Experimental: performance
  benchmarks, documented worked examples, and automated desktop/mobile
  interaction and JSON round-trip tests.

### G9.1 Mathematical Model

Let the ordered generator basis be

```text
A = (a1, a2, ..., ad),  aj ∈ Z, aj >= 2
```

and let an exponent coordinate be

```text
r = (n1, n2, ..., nd) ∈ Z^d.
```

The exact rational represented by the coordinate is

```text
Q_A(r) = product(aj ^ nj), j = 1..d.
```

Negative exponents are allowed, so `Q_A` must be calculated with exact
fractions. Octave normalization is

```text
N(q) = 2^k q, with the unique k such that 1 <= N(q) < 2.
```

The generated scale for an exponent domain `D ⊂ Z^d` is

```text
S(A, D) = {N(Q_A(r)) | r ∈ D}.
```

The first implementation uses a finite rectangular domain defined by an
inclusive minimum and maximum exponent for every generator. Arbitrary point
sets and constrained domains may be added later.

Generator coordinates and sounding pitch classes must remain separate.
Composite or multiplicatively dependent generators can map distinct vectors
to the same octave-normalized ratio. Define

```text
r ~ s iff N(Q_A(r)) = N(Q_A(s)).
```

The laboratory preserves every lattice coordinate while also assigning a
shared pitch-class id to equivalent coordinates. Users can choose whether a
view shows all coordinates or merges equivalent sounding pitches. The basis
value `2` is allowed for analysis, but its exponent disappears after octave
normalization and the UI must warn that it is an octave-only/null direction.

### G9.2 Root-Relative Chords and Root-Motion Progressions

A chord shape is stored separately from a root-motion sequence:

```text
H = (rho, A, C)
P = (r0, Delta)

rho   : positive rational reference root pitch
A     : ordered integer generator basis
C     : ordered chord vectors (c1, c2, ..., cp), cj ∈ Z^d
r0    : starting root coordinate
Delta : ordered root-motion differences (Δr1, ..., Δrq), Δri ∈ Z^d
```

Chord vectors are independent offsets from the current root. The zero vector
is implicit and represents the root itself:

```text
c0 = (0, ..., 0)
chord(r) = { N(rho * Q_A(r + cj)) | j = 0..p }.
```

Progression differences apply only to root motion and are cumulative:

```text
r_i = r_(i-1) + Δr_i
progression = (chord(r0), chord(r1), ..., chord(rq)).
```

For example, chord vectors `(0,-1), (-1,0)` and root-motion differences
`(1,0), (0,1)` produce roots `(0,0) -> (1,0) -> (1,1)` and these absolute
tone-vector stacks:

```text
(0,0) + (0,-1) + (-1,0)
(1,0) + (1,-1) + (0,0)
(1,1) + (1,0) + (0,1)
```

A random walk replaces the explicit root-motion list with a seeded path but
applies the same `C` at each root. The order of `C` remains musically
meaningful for keyboard assignment and display. The UI offers explicit
ordering policies when converting an unordered pitch set:

* user-entered order;
* ascending cents;
* nearest-neighbor lattice path;
* generator-priority lexicographic order.

Changing only `rho` transposes the complete result. Replacing a chord vector
changes one voice at every root without affecting the other voices. Replacing
a root-motion difference changes that root and all later roots. This
distinction must be visible in both the editor and undo history.

### G9.3 Canonical Data Models

```text
ExponentBasis
  generators: tuple[int, ...]
  labels: tuple[str, ...]
  prime_matrix: matrix[int]       # generator prime decompositions
  dependencies: list[vector[int]] # detected null/equivalent directions

ExponentDomain
  minimum: tuple[int, ...]
  maximum: tuple[int, ...]
  max_points: int

ExponentPitch
  vector: tuple[int, ...]
  raw_ratio: Ratio
  normalized_ratio: Ratio
  octave_shift: int
  cents: float
  pitch_class_id: str

LatticeChord
  root_ratio: Ratio
  root_vector: tuple[int, ...] | null
  basis: ExponentBasis
  chord_vectors: tuple[tuple[int, ...], ...]
  chord_offsets: derived tuple[tuple[int, ...], ...] # zero plus chord_vectors
  tones: derived tuple[ExponentPitch, ...]

LatticeProgression
  chord: LatticeChord
  start_vector: tuple[int, ...]
  progression_differences: tuple[tuple[int, ...], ...]
  root_path: derived tuple[tuple[int, ...], ...]
  harmonies: derived tuple[LatticeChord, ...]
```

All dimensions must match the basis length. JSON import rejects dimension
mismatches, zero/negative generators, an empty basis, invalid roots, and a
domain whose point count exceeds the configured limit.

### G9.4 Algorithms and Metrics

Core operations

* exact exponent-product evaluation and octave normalization;
* finite lattice enumeration with deterministic ordering;
* collision grouping by normalized `Fraction`;
* root-relative chord reconstruction;
* root-motion difference-to-path and path-to-difference round trips;
* root transposition plus root-path rotation, reversal, and sign inversion;
* nearest lattice coordinate search for an imported rational pitch;
* seeded walks using a configurable vocabulary of allowed difference vectors.

Distance views

* lattice distance: weighted `L1` or `L2` distance in exponent coordinates;
* prime/monzo distance: transform coordinates through the basis prime matrix;
* acoustic distance: absolute cents after octave normalization;
* path cost: sum of local difference costs plus collision and large-leap
  penalties.

Lattice distance and acoustic distance must never be presented as equivalent.
A short lattice move may wrap across the octave boundary, and a nontrivial
null direction may produce zero acoustic distance.

### G9.5 Experimental Workbench

Add a separate **Exponent Lattice Lab** source next to, rather than inside,
the CPS controls.

Controls

* ordered generator list `a,b,c,...` with optional labels;
* per-generator minimum/maximum exponent;
* root ratio and optional root lattice coordinate;
* editable chord-vector and root-motion rows with add, remove, reorder, and
  duplicate;
* ordering and collision policies;
* allowed-step vocabulary, progression length, and random seed;
* audition, export, and "send harmony to Compose" commands.

Views

* scale table: vector, raw ratio, normalized ratio, octave shift, cents, and
  collision group;
* exponent lattice: selectable two-axis projection for dimensions `d > 2`,
  with other coordinates filterable or encoded by color;
* chord shape: arrows from the root to each `cj`;
* root path: arrows between roots labeled `Δri`;
* Pitch Circle: sounding pitch classes, with collisions grouped and the active
  harmony stack highlighted;
* Composition Roll: root and reconstructed tones over time, with an optional
  lane for each exponent coordinate;
* inspector: lattice distance, monzo distance, cents distance, and exact
  reconstruction formula for the selected relation.

The first 2D projection must be deterministic and user-selected by generator
axes. PCA or force-directed projections may be offered later, but must not be
the only representation because they obscure the integer coordinates.

### G9.6 Proposed API

```text
POST /api/exponent-lattice/scale
  basis, exponent domain, collision policy
  -> coordinates, pitch classes, collision groups, basis diagnostics

POST /api/exponent-lattice/harmony
  root, basis, ordered root-relative chord vectors
  -> chord offsets and reconstructed tones

POST /api/exponent-lattice/chord
  root, basis, allowed differences, tone count, seed, exponent domain
  -> seeded unique-pitch chord vectors and reconstructed tones

POST /api/exponent-lattice/progression
  root, basis, start vector, chord vectors, root-motion differences
  -> cumulative root path and one reconstructed chord per root

POST /api/exponent-lattice/walk
  root ratio, root vector, allowed walk differences, chord vectors,
  length, seed, boundary policy
  -> deterministic coordinate path, root pitches, and one reconstructed
     harmony stack per walk point

POST /api/exponent-lattice/analyze
  basis and vectors or ratios
  -> prime matrix, dependencies, lattice/monzo/cents distances
```

Existing CPS endpoints and models remain unchanged. Export endpoints accept
the reconstructed rational tones through the existing Scala, MIDI, JSON, and
WAV pathways.

### G9.7 Delivery Plan

EV1 — Exact mathematical core

* Implement immutable basis, vector, domain, and pitch models.
* Implement exact products, normalization, prime matrix, and dependency
  diagnostics.
* Add property tests for normalization and vector arithmetic.

EV2 — Scale generation

* Enumerate bounded exponent domains and group pitch collisions.
* Add scale endpoint and table-oriented response.
* Enforce initial limits: at most 8 generators, exponents `-16..16`, and
  4096 enumerated coordinates per request.

EV3 — Chord and progression representation

* Implement independent root-relative chord reconstruction.
* Implement cumulative root-motion reconstruction and inverse differencing.
* Add root transposition and deterministic ordering conversion.
* Add harmony endpoint and JSON serialization.

EV4 — Walk and composition bridge

* Implement allowed-difference walks with fixed seeds and boundary policies
  (`stop`, `reflect`, `wrap`, `reject-and-resample`).
* Send reconstructed harmony stacks to voice leading, bass, melody, playback,
  and export without changing their existing contracts.

EV5 — Experimental UI

* Add basis/domain editor, chord-vector and progression editors, scale table,
  lattice projection, chord/root-motion arrows, Pitch Circle layer, and
  Composition Roll coordinate lanes.
* Keep the feature behind an `Experimental` label until EV1-EV6 acceptance
  criteria pass.

EV6 — Persistence and interoperability

* Add versioned JSON project schema and migration field.
* Store both generator coordinates and exact reconstructed ratios.
* Export deduplicated pitch classes to Scala and ordered tones to MIDI/WAV.

EV7 — Performance and documentation

* Benchmark enumeration, collision grouping, and seeded walks.
* Add worked examples such as bases `(3,5)`, `(3,5,7)`, and a deliberately
  dependent basis `(3,9)`.
* Document coordinate/pitch equivalence, generator `2`, negative exponents,
  and conversion to monzos.

### G9.8 Acceptance Criteria

* Every generated ratio is exact and normalizes to `[1, 2)`.
* The same basis, domain, chord vectors, root motion, root, and seed always
  reproduce the same output.
* Root-motion difference/path conversion round-trips without loss.
* Root plus independent chord vectors reconstructs every displayed harmony
  tone exactly.
* Chord vectors `(0,-1), (-1,0)` and root differences `(1,0), (0,1)` produce
  the three absolute stacks specified in G9.2.
* `(3,5)` with vector `(1,-1)` produces `3/5`, normalized to `6/5`.
* Dependent bases report collisions without discarding their source vectors.
* Lattice, monzo, and cents distances are exposed as distinct values.
* Existing CPS generation, Compose, playback, and export tests remain green.
* Desktop and mobile UI tests cover vector editing, collision display,
  harmony audition, and JSON round-trip.

### G9.9 Open Design Decisions

Resolve these experimentally before promoting the laboratory to a stable
scale source:

* whether duplicate sounding pitches remain independently playable or only
  independently inspectable;
* whether the canonical harmony order should always be user-authored or may
  default to a nearest-neighbor lattice path;
* how generator dependencies should constrain editing, if at all;
* whether boundary policies operate on exponent coordinates, sounding pitch
  classes, or both;
* how much coordinate metadata MIDI/Scala sidecar JSON should preserve.

## G10. Compose Rhythm Orchestration

The original Compose implementation gave every chord, bass note, and melody
note one fixed duration, while the Rhythm workbench only articulated
percussion. G10 added a rhythm orchestration stage between pitch generation
and playback/export. Harmony, bass, and melody remain pitch-domain operations;
rhythm orchestration converts their results into timed note events without
changing the selected ratios.

Status

* Rhythm layer generation, rotation optimization, phase shifting, velocity
  accents, humanization, and percussion MIDI export — Done
* Compose harmony, bass, melody, fixed-step playback, MIDI/JSON/WAV export,
  and Composition Roll — Done
* Rhythm-to-Compose chord-tone/role/hybrid assignment — Done
* Compose-native transition-aware, Semi-Markov, interlocking, and
  ratio-derived generation — Done
* Shared event playback, Composition Roll, MIDI/JSON/WAV integration — Done
* Structured listening comparisons and performance benchmarks — Planned

### G10.1 Shared Time and Event Model

Both imported Rhythm patterns and Compose-native algorithms must compile to
one serializable event model:

```text
CompositionClock
  beats_per_bar: int
  subdivisions_per_beat: int
  tempo_bpm: float
  bars: int

CompositionTrack
  id: str
  role: harmony | chord_tone | bass | melody
  voice_index: int | null
  chord_tone_index: int | null

RhythmicNoteEvent
  track_id: str
  chord_index: int
  ratio: Ratio
  start_tick: int
  duration_ticks: int
  velocity: int
  articulation: gate | legato | tie | accent
  source_layer: str | null
```

Use integer ticks internally rather than floating-point seconds. Tempo
conversion happens only at playback or render time. A chord change and a note
onset are separate concepts: the harmony timeline selects the active chord,
while track patterns decide which tones attack, sustain, tie, or rest inside
that chord. Events may not cross a chord boundary unless their mapping rule
explicitly permits `tie`.

The compiler must accept polymetric Rhythm layers with different cycle
lengths. Each pattern is projected onto the composition clock by exact modular
indexing; it must not expand to an unbounded least common multiple. Phase
offsets, per-hit velocities, probability, and humanized timing are preserved
as metadata until final scheduling.

### G10.2 Assign Existing Rhythm Layers to Chord Tones

The first strategy treats the ordered tones of every generated chord as
independent playable tracks. For a three-note chord:

```text
kick  -> chord_tone:0 (root)
snare -> chord_tone:1
hat   -> chord_tone:2
perc  -> configurable: double, wrap, rest, or auxiliary voice
```

At every active hit, the mapped ratio from the current chord is triggered.
This makes the example assignment of root, second tone, and third tone
explicit rather than inferring pitch from percussion names.

Required mapping policies

* `fixed-index`: keep each source layer on the same ordered chord-tone index;
* `voice-led`: match the prior sounding pitch to the nearest octave placement
  of the new chord, minimizing cents movement;
* `rotate-per-chord`: rotate the tone assignment by chord index or a seeded
  sequence;
* `register-spread`: preserve the index but place each track in a configured
  register without changing its pitch class.

When a chord has fewer tones than the mapping expects, the user selects
`drop`, `wrap`, or `clamp`. When it has more tones, unassigned tones may be
silent, sustained as a pad, or distributed round-robin over a selected source
layer. Lattice chords must use their stored ordered `tone_vectors`; ordinary
CPS chords use their serialized tone order. Reordering a chord therefore
changes fixed-index assignment but not voice-led assignment.

The percussion instrument name is only a default hint. The mapping table is
authoritative and supports arbitrary custom layer names.

### G10.3 Assign Rhythm Layers by Musical Role

The second strategy maps patterns to the existing Compose layers rather than
individual chord tones. A useful default is:

```text
kick  -> bass
snare -> harmony (complete chord attack)
hat   -> melody:0
perc  -> melody:1 or harmony ornament
```

Role targets behave differently:

* `harmony`: one hit attacks all chord tones simultaneously; gate length
  controls a stab, sustain, or tie into the next subdivision;
* `bass`: one hit attacks the generated bass note for the active chord;
* `melody:i`: one hit attacks the current note in melody voice `i`;
* `chord_tone:i`: one hit attacks only the indexed chord tone;
* `mute`: the source layer remains visible but produces no pitched event.

One Rhythm layer may fan out to multiple targets, and several source layers
may feed one target. Collision policy is selectable per target:
`merge` keeps the strongest velocity, `retrigger` creates a new envelope,
and `stack` preserves every event. The initial UI defaults to `merge` for
bass/melody and `retrigger` for harmony.

A hybrid preset combines both models, for example kick-to-bass,
snare-to-complete-harmony, hat-to-third-tone, and perc-to-melody. Presets must
store mappings by stable track ids, not display labels.

### G10.4 Compose-Native Rhythm Generation

Compose-native generation now supports rhythm that does not depend on patterns
created in the Rhythm panel. The following algorithms share one seeded
interface; their implementation status is recorded in G10.7.

#### A. Transition-Aware Harmonic Rhythm

Generate chord durations before generating note onsets. Candidate durations
are a bounded vocabulary such as `{1/2, 1, 2, 4}` beats. Score each duration
using metrical position, phrase boundary, transition score, common-tone count,
and cents/monzo/lattice movement:

```text
cost =
  w_meter * weak_boundary_penalty
  + w_motion * transition_distance
  + w_density * local_change_density
  - w_cadence * cadence_reward
```

Large harmonic changes prefer strong beats or longer preparation; common-tone
transitions may move more quickly. The algorithm uses dynamic programming to
fit an exact requested bar count and breaks equal-cost choices by seed.

#### B. Seeded Semi-Markov Voice Rhythm

Generate each target track with states `REST`, `ATTACK`, `HOLD`, and `TIE`.
Transition probabilities depend on metrical weight, phrase position, active
chord change, previous state duration, and target role. Semi-Markov duration
distributions prevent mechanical one-step state changes. Bass favors attacks
on strong beats, melody permits pickup and syncopated attacks, and harmony
favors fewer, longer events.

The output remains deterministic for the same seed and settings. Profiles
such as `grounded`, `interlocking`, `sparse`, and `flowing` are parameter
bundles, not separate algorithms.

Harmony, Bass, and Melody expose independent strategy, profile, density, and
syncopation settings. Bars, tempo, and the root seed remain properties of the
shared composition clock; the Melody role settings expand to all generated
melody voices with deterministic per-voice seed offsets. — Done

#### C. Interlocking Onset Allocation

Starting from target densities, assign onsets one track at a time on a shared
grid. Optimize:

* required downbeat and chord-change anchors;
* complementarity between harmony, bass, and melody;
* maximum simultaneous attacks;
* minimum rest and sustain lengths;
* syncopation target;
* repeated-pattern similarity across a phrase.

Use the existing Rhythm collision, density, cluster, similarity, and
syncopation metrics where their definitions apply. Add pitched constraints
for chord-boundary ties and voice retrigger density. A beam search is preferred
to exhaustive enumeration; candidates and tie-breaking must be seed-stable.

#### D. Ratio-Derived Cycles (Experimental)

Derive bounded cycle characteristics from the composition itself without
turning exact ratio numerators directly into impractically long meters. Prime
exponent magnitude, chord cardinality, harmonic transition distance, or
lattice-vector distance may select from a user-bounded cycle/pulse vocabulary.
This mode is exploratory and must always expose the resulting ordinary
patterns and metrics. It may not bypass the shared event model.

Initial implementation priority is A plus B, followed by C. D remains
experimental until listening tests show that its musical behavior is more
useful than arbitrary parameter mapping.

### G10.5 Mapping and Generation API

Proposed endpoints:

```text
POST /api/compose/rhythm/apply
  clock, composition pitches, Rhythm layers, mapping rules, collision policy
  -> compiled tracks, note events, rhythm metrics

POST /api/compose/rhythm/generate
  clock, composition pitches, strategy/profile, densities, seed, constraints
  -> generated patterns, compiled tracks, note events, rhythm metrics
```

`composition pitches` contains the existing chord, bass, and melody response
objects rather than duplicating their generation parameters. This keeps the
operation usable for CPS, harmonic-graph, and Lattice Lab compositions.

The response must include both abstract patterns and compiled note events.
MIDI and WAV export consume the compiled events directly. JSON export stores
the clock, source pattern or generator parameters, mapping rules, seed, and
events so the result is reproducible and inspectable.

### G10.6 Compose UI and Visualization

The implemented Rhythm section inside Compose follows this control contract:

* source segmented control: `Rhythm layers` or `Generate`;
* mapping mode: `Chord tones`, `Roles`, or `Hybrid`;
* mapping table with source layer, target, gate, register, velocity scale, and
  collision policy;
* native generation controls for profile, density, syncopation, bar count,
  seed, and harmonic-rhythm mode;
* `Apply rhythm`, `Regenerate`, and `Clear rhythm` commands;
* per-track mute/solo and a compact event inspector.

The Composition Roll changes from one column per chord to a time-proportional
grid. It shows onset blocks and sustains for harmony tones, bass, and melody,
plus optional thin lanes for the source Rhythm patterns. Selecting an event
highlights its source layer, mapping rule, chord, and ratio. Playback,
playhead, MIDI, JSON, and WAV must all use the same compiled event timeline.

### G10.7 Delivery Plan

CR1 — Event timeline foundation — Done

* Add integer clock, track, mapping, and rhythmic-note-event models.
* Refactor fixed Compose playback/export into the shared event compiler while
  preserving current audible behavior as the default.

CR2 — Existing Rhythm integration — Done

* Add fixed-index chord-tone mapping, including root/second/third assignments.
* Add harmony/bass/melody role mapping, collision policies, gate lengths, and
  polymetric projection.
* Add mapping controls and source-pattern lanes to Composition Roll.

CR3 — Compose-native generation — Done

* Implement transition-aware harmonic rhythm with exact form-length fitting.
* Implement seeded semi-Markov voice rhythms and profile presets.
* Add interlocking optimization using shared Rhythm metrics.

CR4 — Persistence and export — Partially done

* Store clock, mappings, generator settings, patterns, and events in project
  JSON with schema migration. JSON export is done; project import/migration
  remains planned.
* Export event durations, velocities, ties, and microtonal channel allocation
  consistently to MIDI and WAV.

CR5 — Experimental evaluation — Partially done

* Add ratio-derived cycles behind an Experimental flag. — Done
* Run deterministic benchmarks and structured listening comparisons against
  Euclidean-only and fixed-step baselines.

### G10.8 Acceptance Criteria

* Kick, snare, and hat can independently trigger the root, second, and third
  tones of every chord; a fourth layer follows the selected overflow policy.
* Kick-to-bass, snare-to-harmony, hat-to-melody, and hybrid mappings produce
  the same event sequence in playback, MIDI, JSON, and WAV.
* Lattice and CPS chord order is preserved for fixed-index mappings.
* Chords with changing cardinality never cause an invalid tone lookup or a
  stuck note.
* Polymetric layers remain bounded in memory and preserve phase offsets.
* The same composition, clock, mappings, settings, and seed produce identical
  events and metrics.
* Native harmonic rhythm fills the exact requested number of bars.
* Composition Roll onset positions and durations agree with scheduled audio
  within one UI frame.
* Clearing rhythm restores the current fixed-step Compose behavior.

## G11. Genre Arrangement Pipeline

Status

* Planned

G11 will turn a generated scale and a user-selected vocabulary of basic exact-
ratio chords into a complete genre-guided arrangement. It sits above Compose
and G10: the new layer generates form, section-aware harmony, coordinated
drums, bass, comping, melody, and texture roles, then compiles them to the
existing integer-tick event model.

The first profiles are Pop, Ambient, Alternative Rock, and Future Bass.
Profiles are versioned, editable parameter bundles rather than opaque genre
labels. Exact ratios remain authoritative, and genre preferences must adapt
when the supplied scale or chord vocabulary does not contain conventional
12-EDO chord types.

The same arrangement timeline must drive workbench playback, type-1
microtonal MIDI, lossless JSON, preview rendering, and stems. Project JSON
import/migration, instrument presets, and section-level regeneration are
therefore part of the delivery boundary.

See
[development_plan_genre_arrangement.md](development_plan_genre_arrangement.md)
for the input/profile models, genre behavior, algorithms, API, staged delivery
plan, and acceptance criteria.

---

# 4. Historical Milestones

The original P1–P10 phasing was completed as follows; new work is
tracked in the functional groups above.

| Phase | Goal                  | Content                                    |
| ----- | --------------------- | ------------------------------------------ |
| P1    | Mathematical Core     | ratios, monzo, CPS, Euler–Fokker           |
| P2    | Harmonic Graph        | Johnson graph, walks, distance metrics     |
| P3    | Composition Engine    | harmony, voice leading, bass, melody       |
| P4    | Rhythm Engine         | euclidean, state graph, phase, humanize    |
| P5    | Audio Rendering       | oscillators, ADSR, effects, WAV            |
| P6    | Export                | MIDI, rhythm MIDI, Scala, JSON             |
| P7    | REST API              | FastAPI, OpenAPI, async jobs               |
| P8    | Web UI                | keyboard, graph viewer, circle, timeline   |
| P9    | Real-time Performance | WebSocket transport, improvisation         |
| P10   | Stable Release        | performance tuning, packaging (ongoing)    |

---

# Testing Strategy

Current verification:

* deterministic unit tests for mathematical and composition engines;
* API integration and validation tests;
* regression tests for lattice compatibility and export behavior;
* `ruff` and `mypy` checks.

Release additions:

* automated browser interaction and screenshot regression;
* property tests where they provide value;
* measured coverage with a 90% target;
* repeatable performance benchmarks.

---

# Performance Targets

These are unverified release targets, not current benchmark results:

| Operation | Target |
| --- | --- |
| Graph generation | < 1 second for documented ordinary inputs |
| Random walk | >= 10,000 transitions per second |
| Offline rendering | >= 10x real time |
| Process memory | < 1 GB for documented practical limits |

---

# Code Style

* Python 3.12 or newer
* PEP 8 and type hints
* `ruff` for linting
* `mypy` for type checking
* `pytest` for automated tests

---

# Branch Strategy

main

Stable releases

develop

Integration

feature/*

Individual issues

---

# Pull Request Rules

Every PR requires

Passing tests

Documentation updates

Type checking

Code review

---

# Definition of Done

A task is complete only if

* implementation finished
* tests added
* documentation updated
* API documented
* examples included
* lint passes
* type checks pass
* reproducible using fixed random seed

---

# Future Versions

Version 0.2

MPE

OSC

SuperCollider

VCV Rack

Version 0.3

GPU synthesis

Distributed rendering

AI-assisted composition

Adaptive harmonic models
