# Development Plan

**Project:** Pure Intonation Composer

Version: 0.1

## Implementation Status

Phases P1–P9 are implemented on the `develop` branch; P10 (stable
release) is in progress. Work is now tracked by the Entonal-style
functional groups in section 3.

Recent additions beyond the original phase scope:

* GM-percussion rhythm MIDI export (`POST /api/export/rhythm/midi`)
* Reference-node layered grid graph layout (`docs/visualization.md`)
  alongside the force-directed graph viewer, with walk visualization
* Real-time-scaled timeline recorder with replay
* Compose and rhythm workbench panels (harmony/bass/melody generation,
  WAV render jobs, MIDI/JSON export)

Performance tuning and installer distribution remain release-operations
work and should be measured for each target platform before a production
release. The test suite currently covers all endpoints and engines
(40 tests); `ruff` and `mypy` are clean.

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

The Compose panel can generate harmony, bass, and melody, but its current
horizontal chord list does not make the relationship between those layers
legible over time. Add a linked **Composition Roll** as the primary
composition visualization. It must use a cents-based vertical axis rather
than MIDI-note rows, so that the actual sizes of pure intervals remain
visible.

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
It treats products of integer generators as points in an exponent lattice and
represents a harmony by one root pitch plus an ordered sequence of exponent
difference vectors.

Status

* Mathematical model and implementation plan — Defined below
* EV1 exact mathematical core (basis, products, normalization, prime
  matrix, dependency diagnostics) — Done (`app/lattice.py`)
* EV2 scale generation with collision grouping — Done
  (`POST /api/exponent-lattice/scale`)
* EV3 difference harmony (cumulative reconstruction, transforms) — Done
  (`POST /api/exponent-lattice/harmony`)
* EV4 seeded walks with boundary policies + analyze endpoint — Done: walk
  points reconstruct simultaneous difference-vector harmonies and the full
  walk can enter Compose for bass/melody generation, playback, and export
  (`POST /api/exponent-lattice/walk`, `/api/exponent-lattice/analyze`)
* EV5 experimental workbench (basis/domain editor, difference editor,
  seeded chord generation, scale table, 2-axis lattice projection,
  difference arrows, walk overlay, Pitch Circle layer, and ASD keyboard) —
  Partially done, behind the `Experimental` label
* EV6 persistence — Planned
* EV7 performance/docs — Partially done: API and usage documentation plus
  deterministic unit tests exist; benchmarks, worked examples, and browser
  regression coverage remain pending

Implementation audit (2026-07-25)

* Available now: exact exponent arithmetic, collision-aware scale generation,
  seeded unique-pitch chord generation, harmony reconstruction, four walk
  boundary policies, basis/distance analysis, 2-axis projection, Pitch Circle
  harmony markers, ASD keyboard audition, simultaneous difference-harmony
  playback, and chord/walk transfer to Compose.
* Still required for EV5: propagate coordinate provenance into derived
  bass/melody notes and export sidecars; add structured difference-row
  controls (add, remove, reorder, duplicate), optional root-coordinate
  editing, non-projected coordinate filtering, and Composition Roll
  exponent-coordinate lanes.
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

### G9.2 Root-and-Difference Harmony Representation

A harmony is stored as

```text
H = (rho, A, Delta)

rho   : positive rational root pitch
A     : ordered integer generator basis
Delta : ordered list (Δr1, Δr2, ..., Δrp), Δri ∈ Z^d
```

The difference vectors are interpreted cumulatively:

```text
s0 = (0, ..., 0)
si = sum(Δrj), j = 1..i
tone_i = N(rho * Q_A(si)).
```

Therefore `tone_0 = N(rho)`, and the root plus the difference-vector list is
sufficient to reconstruct the complete ordered harmony stack. Root-relative
offsets `(s0, s1, ..., sp)` are derived data and should be returned by the API
for inspection, but the canonical serialized form stores the differences.

The order is musically meaningful even when the result is played as a
simultaneous chord: it records the construction path, supports deterministic
stack display, and permits rotation or reversal transforms. The UI must offer
explicit ordering policies when converting an unordered pitch set:

* user-entered order;
* ascending cents;
* nearest-neighbor lattice path;
* generator-priority lexicographic order.

Changing only `rho` transposes the same harmonic shape. Replacing a difference
vector changes one local relation and propagates to all later cumulative
tones. This distinction must be visible in both the editor and undo history.

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

DifferenceHarmony
  root_ratio: Ratio
  root_vector: tuple[int, ...] | null
  basis: ExponentBasis
  differences: tuple[tuple[int, ...], ...]
  cumulative_offsets: derived tuple[tuple[int, ...], ...]
  tones: derived tuple[ExponentPitch, ...]
```

All dimensions must match the basis length. JSON import rejects dimension
mismatches, zero/negative generators, an empty basis, invalid roots, and a
domain whose point count exceeds the configured limit.

### G9.4 Algorithms and Metrics

Core operations

* exact exponent-product evaluation and octave normalization;
* finite lattice enumeration with deterministic ordering;
* collision grouping by normalized `Fraction`;
* difference-to-cumulative and cumulative-to-difference round trips;
* harmony reconstruction from root plus differences;
* root transposition, path rotation, reversal, and sign inversion;
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
* editable difference-vector rows with add, remove, reorder, and duplicate;
* ordering and collision policies;
* allowed-step vocabulary, progression length, and random seed;
* audition, export, and "send harmony to Compose" commands.

Views

* scale table: vector, raw ratio, normalized ratio, octave shift, cents, and
  collision group;
* exponent lattice: selectable two-axis projection for dimensions `d > 2`,
  with other coordinates filterable or encoded by color;
* difference path: arrows labeled `Δri`, with the root and cumulative points
  clearly distinguished;
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
  root, basis, ordered difference vectors
  -> cumulative offsets, reconstructed tones, relation metrics

POST /api/exponent-lattice/chord
  root, basis, allowed differences, tone count, seed, exponent domain
  -> seeded unique-pitch difference path and reconstructed tones

POST /api/exponent-lattice/walk
  root ratio, root vector, allowed walk differences, harmony differences,
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

EV3 — Difference harmony

* Implement cumulative reconstruction and inverse differencing.
* Add root transposition and deterministic ordering conversion.
* Add harmony endpoint and JSON serialization.

EV4 — Walk and composition bridge

* Implement allowed-difference walks with fixed seeds and boundary policies
  (`stop`, `reflect`, `wrap`, `reject-and-resample`).
* Send reconstructed harmony stacks to voice leading, bass, melody, playback,
  and export without changing their existing contracts.

EV5 — Experimental UI

* Add basis/domain editor, difference-sequence editor, scale table, lattice
  projection, difference arrows, Pitch Circle layer, and Composition Roll
  coordinate lanes.
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
* The same basis, domain, difference list, root, and seed always reproduce the
  same output.
* Difference/cumulative conversion round-trips without loss.
* Root plus differences reconstructs every displayed harmony tone exactly.
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

Every module contains

Unit tests

Integration tests

Regression tests

Property tests where applicable

Coverage target

90%

---

# Performance Targets

Graph generation

< 1 second

Random walk

10000 transitions per second

Offline rendering

10× real time

Memory

< 1 GB

---

# Code Style

Python 3.12

PEP8

Type hints mandatory

black

ruff

mypy

pytest

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
