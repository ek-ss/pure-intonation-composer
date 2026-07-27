# Prime-Limit Harmonic Explorer Development Plan

**Version:** 0.1
**Status:** Proposed
**Roadmap ID:** G12
**Related foundation:** [Harmonic Pitch Circle](harmonic_pitch_circle.md)

## 1. Purpose and Boundary

The Prime-Limit Harmonic Explorer extends the implemented 12-EDO
Harmonic Pitch Circle into an exploratory environment for exact prime-lattice
pitches, generated scales, prime-native chords, and progression search.

The two features have deliberately different responsibilities:

| Feature | Responsibility |
| --- | --- |
| Harmonic Pitch Circle | Fixed 12-class fifth-step chord vocabulary, chord-shape learning, and Johnson-distance history |
| Prime-Limit Harmonic Explorer | Arbitrary prime bases, exact exponent vectors, continuous cents, scale search, chord discovery, authoritative lattice views, and progression construction |

The initial Explorer is a browser application. Its mathematical engine must be
independent of rendering and audio so it can be tested deterministically.

Development principles:

1. Complete a scale explorer that can be heard before adding advanced harmonic ranking.
2. Keep exact lattice points separate from octave-reduced pitch-class clusters.
3. Display independent metrics instead of hiding decisions in one aggregate score.
4. Preserve exponent-coordinate provenance in every scale, chord, and progression state.
5. Prefer the repository's current FastAPI/static-page integration and naming conventions where they conflict with the greenfield structure below.

## 2. Technical Direction

The target implementation is an isolated TypeScript application built into the
existing FastAPI workbench rather than a replacement for the current vanilla
pages.

| Area | Preferred technology | Reason |
| --- | --- | --- |
| Domain and math | TypeScript | Shared types across search, views, persistence, and audio |
| UI | React | Coordinated controls, multiple synchronized views, and inspectors |
| Build | Vite | Small isolated build and development configuration |
| Circle and lattice | SVG | Labels, selection, hit testing, and export |
| Audio | Web Audio API | Direct arbitrary-frequency playback without 12-EDO quantization |
| Background search | Web Worker | Responsive UI and audio during large searches |
| Local persistence | IndexedDB | Versioned sessions, ratings, and memos |
| Unit tests | Vitest | Pure TypeScript domain and search tests |
| Browser tests | Playwright | Interaction, audio lifecycle, and visual regression |
| Large chord graph | Cytoscape.js, optional | Add only after native SVG/Canvas limits are measured |

Proposed source boundary:

```text
frontend/prime-limit-explorer/
  src/
    app/
    domain/
      types.ts
      constants.ts
    math/
      primes.ts
      octave.ts
      clustering.ts
      scaleMetrics.ts
      scaleSearch.ts
      chordEnumeration.ts
      chordMetrics.ts
      voiceLeading.ts
      progressionGraph.ts
    audio/
      AudioEngine.ts
      voicing.ts
      roughness.ts
    workers/
      exploration.worker.ts
      protocol.ts
    components/
      controls/
      circle/
      lattice/
      scales/
      chords/
      progression/
      transport/
    state/
    persistence/
    presets/
  tests/
    unit/
    integration/
    e2e/
```

The production build will be served at `/prime-limit-explorer` through the
existing FastAPI application. P0 must document the build-output boundary and
ensure backend-only development remains possible.

## 3. Domain Invariants

These invariants must be fixed by tests before broad GUI work:

- exponent vectors are immutable integer arrays with a declared prime basis;
- exact ratio or log-pitch provenance is retained for every lattice point;
- octave-reduced cents are always in `[0, 1200)`;
- circular distance is symmetric and no greater than 600 cents;
- circular clustering handles the 0/1200-cent boundary;
- a pitch-class cluster retains all source lattice points and spellings;
- one scale cannot contain the same cluster more than once;
- tied search candidates use deterministic ordering;
- audio frequencies are positive and finite;
- every chord metric includes an algorithm version;
- every progression edge references existing `ChordState` objects.

Exact lattice points and clustered pitch classes are separate canonical types:

```text
LatticePoint
  basis: Prime[]
  vector: int[]
  ratio: ExactRatio | null
  log2Pitch: number
  cents: number
  octaveShift: int

PitchClassCluster
  id: string
  cents: number
  representative: LatticePoint
  sources: LatticePoint[]
  alternateSpellings: LatticePoint[]
```

## 4. Delivery Phases

### P0. Project Foundation

**Estimate:** 1-2 person-days

Deliver:

- isolated React/TypeScript/Vite application and FastAPI route;
- format, lint, unit-test, and production-build commands;
- left controls, central workspace, right inspector, and bottom transport shell;
- shared domain types and a versioned session schema;
- static example session that renders without audio.

Acceptance:

- one command starts the Explorer development environment;
- tests and production build run independently;
- FastAPI serves the built page without affecting existing routes.

### P1. Prime-Lattice Math Kernel

**Estimate:** 2-4 person-days

Deliver:

- prime-basis validation and exponent-vector enumeration;
- weighted-height filtering;
- ratio, log-pitch, cents, and frequency conversion;
- circular pitch clustering and representative spelling selection;
- fifth-step compatibility conversion.

Required tests:

- `3^12 / 2^19` is approximately `23.460` cents;
- fifth steps `{0, 1, 4}` map to chromatic classes `{0, 7, 4}`;
- clusters spanning the 0/1200 boundary merge correctly;
- alternate exponent spellings can be reconstructed;
- `[3, 5, 7]` produces deterministic points and clusters;
- 10,000 raw points can be enumerated in the test environment.

### P2. Scale Search and Continuous Circle

**Estimate:** 3-5 person-days

Deliver:

- target-note-count control;
- farthest-point greedy selection and one-point local refinement;
- circular-gap metrics;
- lattice MST and connectivity metrics;
- Pareto candidate generation;
- continuous-cents SVG circle and candidate comparison table.

Acceptance:

- at least five scale candidates can be compared;
- every circular gap is inspectable in cents;
- active-scale changes synchronize all views;
- the 12-note fifth-step preset can be reproduced.

### P3. Audio Audition

**Estimate:** 2-3 person-days

Deliver:

- robust AudioContext lifecycle;
- oscillator and gain envelopes;
- single-note, block-chord, and arpeggio audition;
- master limiter/compressor and voice-count gain normalization;
- reference frequency, waveform, register, and octave-spread controls.

Acceptance:

- displayed pitches and scales can be auditioned without 12-EDO quantization;
- oscillator frequencies match domain calculations;
- voices do not survive stop/release;
- repeated audition remains below the documented master ceiling;
- UI controls remain responsive during playback.

### P4. Chord Discovery

**Estimate:** 4-6 person-days

Deliver:

- root-fixed triad and tetrad enumeration;
- translation-normalized chord-shape IDs;
- MST, diameter, mean distance, connectivity, weighted height, and pair-consonance metrics;
- major/minor/dominant template distance and transposability metrics;
- metric scatter plot, filters, pinning, user ratings, and A/B playback.

Performance target:

- rank root-fixed triads and tetrads from a 37-note scale in under one second;
- move work beyond that budget to a worker with progress and cancellation.

Acceptance:

- candidate selection synchronizes Circle and inspectors;
- compactness and template similarity sort independently;
- two or more candidates can be pinned and auditioned;
- prime-native chords without conventional labels remain first-class results.

### P5. Authoritative Lattice

**Estimate:** 3-5 person-days

Deliver:

- selectable X/Y prime axes and controls for remaining exponent layers;
- fixed-coordinate SVG with unit-step lattice edges;
- scale, alternate-spelling, chord, and chord-MST overlays;
- pan, zoom, fit, and reset;
- clearly labeled experimental PCA overview.

Acceptance:

- `[3, 5]` coordinates remain visually and numerically traceable;
- `[3, 5, 7]` chords can be inspected by switching the `7` layer;
- every projection states whether it preserves lattice distance;
- node selection synchronizes Lattice, Circle, and inspector.

### P6. Progression Graph and Transport

**Estimate:** 4-7 person-days

Deliver:

- canonical `ChordState` and progression-edge types;
- common-tone count and Johnson distance;
- minimum circular voice-leading assignment;
- lattice-centroid displacement and weighted transition costs;
- nearest-neighbour generation and chord-state graph;
- drag-and-drop timeline, tempo, duration, loop, and continuous playback;
- Circle and Lattice progression overlays.

Acceptance:

- an eight-chord or longer progression can be built and played;
- common tones, replacements, Johnson distance, and voice-leading cost are visible;
- selecting a graph edge auditions both endpoint chords;
- translation of one shape is distinguished from a one-note mutation.

### P7. Persistence and Export

**Estimate:** 2-3 person-days

Deliver:

- IndexedDB session repository, autosave, and named saves;
- versioned JSON import/export;
- ratings and memos;
- Circle and Lattice SVG export;
- session migration hook.

Acceptance:

- scales, chord selections, and progressions survive reload;
- export/import reproduces deterministic computed results;
- invalid or newer schemas return specific actionable errors.

### P8. Performance, Accessibility, and Validation

**Estimate:** 3-5 person-days

Deliver:

- worker migration for measured high-cost calculations;
- cancellation, progress protocol, memoization, and cache invalidation;
- keyboard navigation and visible focus state;
- selection cues that do not depend on color;
- desktop/tablet responsive validation;
- browser-level audio tests and visual regression.

Acceptance:

- pointer and audio remain responsive during search;
- long searches can be cancelled;
- every core control is keyboard reachable;
- target viewports have no label overlap or clipping.

### P9. Release Candidate

**Estimate:** 1-2 person-days

Deliver:

- frozen session-schema version;
- verified presets and defaults;
- documented metrics and known constraints;
- production build and static deployment path.

Acceptance:

- all phase acceptance criteria pass;
- no critical or high-severity issue remains;
- the compiled Explorer works under static hosting without a runtime backend dependency.

## 5. Cross-Feature Integration

Integration happens through versioned data, not shared mutable UI state.

- import the current Harmonic Pitch Circle fifth-step vocabulary as a preset;
- reuse G9 exponent-lattice terminology and coordinate provenance;
- allow selected Explorer scales/chords to become Compose and Arrange input;
- keep G10 rhythm orchestration and G11 arrangement downstream of pitch/chord discovery;
- export exact ratios and vectors before MIDI or 12-EDO conversion.

The Explorer must not silently replace the existing `/harmonic-pitch-circle` or
`/lattice` tools. Those remain lightweight, direct-entry workbenches.

## 6. Testing and Performance Gates

Every phase requires deterministic unit coverage for its pure domain layer and
at least one browser workflow for its user-visible acceptance path. P4 and P6
cannot close without recorded performance baselines. P7 cannot close without
round-trip fixtures from every earlier schema version.

Release verification includes:

- unit, integration, and browser suites;
- production TypeScript build;
- desktop and tablet screenshots;
- nonblank SVG/canvas pixel checks;
- audio lifecycle and frequency assertions;
- worker cancellation and stale-result rejection;
- JSON migration and deterministic round-trip checks.

## 7. Open Decisions

P0 must resolve and record:

1. whether exact ratios use bigint fractions, prime vectors only, or both;
2. the cents tolerance and representative policy for pitch-class clustering;
3. the weighted-height default and hard enumeration bounds;
4. whether the production artifact is copied into `backend/app/static` or mounted from a dedicated build directory;
5. the first supported session schema and migration ownership;
6. the threshold for enabling Cytoscape.js instead of native rendering.
