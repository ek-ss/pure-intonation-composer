# Rhythm Generation Development Plan

This section defines the development roadmap for Euclidean rhythm generation, multi-part drum coordination, phase shifting, state-transition graphs, humanization, and rhythm export.

The rhythm system must support four primary percussion layers:

```text
kick
snare
hat
perc
```

Each milestone must produce a usable and testable rhythm-generation pipeline.

---

## R1. Core Rhythm Representation

**Priority:** Must
**Status:** Done or verify against current implementation

### Tasks

* define immutable binary rhythm-pattern model;
* define cycle length, pulse count, rotation, phase, and velocity fields;
* define drum-hit and rhythm-layer models;
* support unequal cycle lengths;
* add JSON serialization and schema validation.

### Acceptance Criteria

* pattern length always matches configured cycle length;
* hit values are restricted to binary values;
* rotation is normalized modulo the cycle length;
* rhythm layers serialize and deserialize without information loss;
* malformed patterns produce descriptive validation errors.

### Tests

* empty rhythm;
* all-hit rhythm;
* rotated rhythm;
* unequal cycle lengths;
* round-trip JSON serialization.

---

## R2. Euclidean Rhythm Generator

**Priority:** Must
**Status:** Done or verify against current implementation

### Tasks

* implement Bjorklund Euclidean-rhythm generation;
* support `steps`, `pulses`, and `rotation`;
* normalize output to a pulse-first canonical form;
* expose generator through Python API and REST API;
* include rhythm-text and step-index utilities.

### Acceptance Criteria

* output contains exactly `steps` values;
* output contains exactly `pulses` hits;
* pulse spacing differs by no more than one step where mathematically possible;
* fixed inputs produce identical output;
* edge cases `pulses=0` and `pulses=steps` are supported.

### Tests

* `E(8,3)`;
* `E(13,5)`;
* `E(16,5)`;
* every valid pulse count for steps 1–32;
* rotation invariance of hit count.

---

## R3. Layer Rotation Optimizer

**Priority:** Must
**Status:** Planned

### Tasks

* implement static rotation search for one layer;
* implement sequential placement order:
  `kick → snare → hat → perc`;
* implement complement score;
* implement collision penalties by instrument pair;
* implement layer-similarity penalty;
* implement metric-anchor scoring;
* return score breakdown for every candidate rotation.

### Acceptance Criteria

* all possible rotations are evaluated;
* the selected rotation has the maximum score under deterministic tie-breaking;
* kick may remain fixed while other layers are optimized;
* optimizer supports patterns of unequal lengths;
* score components are included in analysis output;
* fixed seed and configuration produce the same rotation choices.

### Tests

* simple two-layer complement case;
* kick–snare collision avoidance;
* equal-score deterministic tie break;
* unequal cycle lengths;
* all-rest and all-hit edge cases.

---

## R4. Shared Analysis Grid

**Priority:** Must
**Status:** Planned

### Tasks

* calculate least-common-multiple analysis length;
* support configurable maximum analysis window;
* repeat patterns across the shared window;
* calculate combined onset sequence;
* calculate pairwise and multi-layer collisions;
* calculate local and global density.

### Acceptance Criteria

* patterns with lengths 13, 15, 16, and 17 are compared correctly;
* bounded analysis windows are deterministic;
* collision counts match brute-force reference calculations;
* density metrics remain within `[0,1]`;
* no unnecessary full-LCM allocation occurs when a maximum is configured.

### Tests

* equal-length patterns;
* coprime-length patterns;
* bounded-LCM analysis;
* four-layer collisions;
* zero-density patterns.

---

## R5. Rhythm Quality Metrics

**Priority:** Must
**Status:** Planned

### Tasks

* implement pairwise collision metrics;
* implement local-density penalty;
* implement cluster penalty;
* implement normalized Hamming similarity;
* implement basic syncopation score;
* implement inter-onset interval statistics;
* implement global rhythm score.

### Acceptance Criteria

* identical patterns have similarity 1;
* complementary patterns receive higher interlock scores than identical patterns;
* dense collision-heavy patterns receive lower global scores;
* score weighting is configurable;
* API responses include a complete score breakdown.

### Tests

* identical versus complementary pattern comparison;
* sparse versus dense pattern comparison;
* syncopated versus metrically aligned example;
* score-weight override;
* metric invariance under common rotation where applicable.

---

## R6. Discrete Phase-Shift Engine

**Priority:** Must
**Status:** Planned

### Tasks

* define base rotation and time-dependent phase offset separately;
* support phase increment;
* support phase-update interval in bars or cycles;
* support positive and negative phase directions;
* apply phase updates only at structural boundaries;
* preserve all phase events in the generated timeline.

### Acceptance Criteria

* a layer can shift by one or more steps after a configured number of bars;
* kick can remain phase-locked while other layers drift;
* phase offsets wrap modulo the layer cycle length;
* generated MIDI and WAV reflect phase changes;
* fixed parameters produce reproducible phase timelines.

### Tests

* one-step shift every bar;
* negative shift;
* wraparound;
* unequal cycle lengths;
* disabled phase shift;
* phase events at valid boundaries only.

---

## R7. Rhythm State-Transition Graph

**Priority:** Must
**Status:** Done in basic form; extend for coordinated layers

### Tasks

* represent each rhythm state as pattern, rotation, density, and accent data;
* connect states by configurable Hamming-distance criteria;
* support pulse-count-preserving transitions;
* support transitions that add or remove one hit;
* verify graph connectivity;
* expose graph through REST API.

### Acceptance Criteria

* Hamming-distance-one mode creates only valid edges;
* disconnected state sets produce a clear warning or repair strategy;
* random walks never leave the state graph;
* state IDs remain stable across repeated generation;
* graph creation is deterministic.

### Tests

* small four-step state graph;
* Hamming-distance validation;
* connectedness;
* deterministic node and edge ordering;
* random walk validity.

---

## R8. Coordinated Multi-Layer State Transitions

**Priority:** Must
**Status:** Planned

### Tasks

* assign independent transition intervals to kick, snare, hat, and percussion;
* prevent kick and snare from making strong transitions simultaneously by default;
* permit simultaneous transitions at section boundaries;
* support transition-priority and transition-strength metadata;
* recompute rotation or phase compatibility after state changes.

### Acceptance Criteria

* each layer follows its own transition schedule;
* strong-accent layers are staggered outside structural boundaries;
* state changes remain valid graph transitions;
* global density remains below configured maximum after transition;
* transition history is included in JSON export.

### Tests

* staggered kick/snare schedule;
* section-boundary simultaneous transition;
* transition conflict resolution;
* post-transition density validation;
* deterministic scheduling.

---

## R9. Velocity and Accent Generation

**Priority:** Should
**Status:** Partial or planned

### Tasks

* define metrical-accent profiles;
* assign base velocity by layer;
* emphasize selected Euclidean pulses;
* support cyclic accent patterns with lengths different from onset patterns;
* support ghost notes;
* clamp all velocities to valid output ranges.

### Acceptance Criteria

* kick downbeats receive configurable emphasis;
* snare backbeats receive configurable emphasis;
* hat and percussion may use independent accent cycles;
* ghost-note velocities remain below main-hit velocities;
* MIDI export preserves generated velocity values.

### Tests

* accent-profile application;
* mismatched accent and onset cycle lengths;
* velocity clamping;
* ghost-note generation;
* deterministic velocity variation.

---

## R10. Humanization

**Priority:** Should
**Status:** Done in basic form; extend and verify

### Tasks

* support timing deviation;
* support velocity deviation;
* support hit probability;
* support per-layer humanization ranges;
* ensure structural downbeats may be protected from timing drift;
* use injected seeded random generator.

### Acceptance Criteria

* timing and velocity deviations remain within configured limits;
* protected events remain unchanged;
* no event receives negative start time;
* fixed seed reproduces all deviations;
* humanization can be disabled globally or by layer.

### Tests

* timing range;
* velocity range;
* protected downbeat;
* zero-humanization mode;
* deterministic output.

---

## R11. Fill and Structural Accent Generator

**Priority:** Should
**Status:** Planned

### Tasks

* generate fills at configured section boundaries;
* temporarily relax collision and density penalties;
* support snare, hat, percussion, and full-kit fills;
* reserve four-layer collisions for explicit accent events;
* return to the previous groove or next graph state after the fill.

### Acceptance Criteria

* fills occur only at configured boundaries;
* fill density is greater than the surrounding groove;
* fill events remain within the section duration;
* normal collision rules resume after the fill;
* fixed seed reproduces the same fill.

### Tests

* one-bar fill;
* half-bar fill;
* section transition;
* density restoration;
* deterministic fill generation.

---

## R12. Rhythm Workbench UI

**Priority:** Must
**Status:** Partial

### Tasks

* display all four layers in a step-sequencer grid;
* show cycle length, pulse count, rotation, and phase;
* expose rotation optimization controls;
* show current state-graph node;
* animate phase shifts;
* display collision and density overlays;
* allow click-to-toggle editing;
* support audition and loop playback.

### Acceptance Criteria

* all layers remain visually aligned on the transport timeline;
* unequal cycle lengths are clearly indicated;
* optimized rotations update the view;
* phase changes animate without losing transport position;
* collision-heavy steps are visible;
* edited patterns can be regenerated, replayed, and exported.

### Tests

* UI state serialization;
* pattern editing;
* rotation update;
* phase animation;
* transport synchronization;
* browser-level integration test.

---

## R13. MIDI and JSON Export

**Priority:** Must
**Status:** GM-percussion MIDI export Done; extend metadata

### Tasks

* export General MIDI percussion notes;
* preserve event timing and velocity;
* preserve phase-shifted events;
* preserve layer names and state IDs in JSON;
* include generation seed and rhythm configuration;
* optionally export separate MIDI tracks per layer.

### Acceptance Criteria

* kick, snare, hat, and percussion use valid GM percussion note numbers;
* note timing matches the generated timeline;
* unequal cycle lengths and phase shifts are preserved;
* JSON round-trip reconstructs the same rhythm;
* repeated exports from the same composition are byte-stable where practical.

### Tests

* GM note mapping;
* timing validation;
* velocity validation;
* phase-shift export;
* multi-track export;
* JSON round trip.

---

## R14. WAV Rendering Integration

**Priority:** Must
**Status:** Basic rendering Done; verify full rhythm pipeline

### Tasks

* provide synthesized or sampled sounds for each percussion layer;
* render velocity-sensitive hits;
* support per-layer pan, volume, and effects;
* prevent clipping using headroom and limiting;
* verify phase-shifted events against MIDI timing.

### Acceptance Criteria

* all generated drum events are audible;
* no unbounded clipping occurs;
* per-layer balance is configurable;
* WAV duration matches composition duration;
* MIDI and WAV event timing agree within one audio sample or documented tolerance.

### Tests

* single-hit rendering;
* full four-layer rendering;
* dense collision handling;
* output duration;
* peak-level validation;
* deterministic rendering.

---

## R15. Rhythm REST API

**Priority:** Must
**Status:** Partial

### Required Endpoints

```text
POST /api/rhythm/euclidean
POST /api/rhythm/optimize-rotations
POST /api/rhythm/analyze
POST /api/rhythm/state-graph
POST /api/rhythm/phase
POST /api/drums/generate
POST /api/export/rhythm/midi
```

### Tasks

* define request and response Pydantic models;
* return score breakdowns and analysis metrics;
* document deterministic seed behavior;
* expose validation errors consistently;
* include representative OpenAPI examples.

### Acceptance Criteria

* all endpoints appear in Swagger UI;
* requests reject invalid cycle and pulse counts;
* optimization and generation endpoints support all four layers;
* fixed-seed examples are reproducible;
* endpoint behavior is covered by integration tests.

---

## R16. Rhythm Presets

**Priority:** Could
**Status:** Planned

### Tasks

* define reusable rhythm-engine presets;
* include minimalist, dense, sparse, polymetric, and phase-shift examples;
* support save and load;
* include scoring weights and transition schedules;
* version preset schema.

### Acceptance Criteria

* presets restore all rhythm parameters;
* old presets fail gracefully after schema changes;
* bundled examples generate valid rhythms;
* presets can be included in project save files.

---

## R17. Continuous Phase Drift

**Priority:** Could
**Target:** Version 0.2

### Tasks

* support fractional timing drift;
* decouple selected layers from the discrete step grid;
* retain stable transport synchronization;
* define MIDI approximation behavior;
* expose drift visualization.

### Acceptance Criteria

* drift rate is configurable per layer;
* event timing remains monotonic;
* audio rendering supports sub-step event times;
* MIDI export either approximates or explicitly rejects unsupported resolution;
* drift can be disabled without changing discrete output.

---

## R18. Performance and Release Validation

**Priority:** Must for stable release
**Status:** Ongoing

### Tasks

* benchmark generation for long compositions;
* benchmark state-graph construction;
* benchmark rotation optimization;
* profile shared-grid analysis;
* test WAV rendering on supported platforms;
* document practical limits.

### Performance Targets

```text
Euclidean pattern generation:
< 1 ms per pattern for ordinary step counts

Four-layer rotation optimization:
< 50 ms for cycles up to 32 steps

Shared-grid rhythm analysis:
< 100 ms for an analysis window up to 1024 steps

State-graph random walk:
>= 10,000 transitions per second

One-minute rhythm WAV render:
>= 10× real time where supported
```

### Acceptance Criteria

* benchmarks run automatically or through documented scripts;
* no benchmark exceeds the release threshold without documented justification;
* memory usage remains bounded for long polymetric patterns;
* target-platform results are recorded before stable release.

---

## Rhythm Definition of Done

A rhythm feature is complete only when:

* the algorithm is implemented;
* deterministic seed behavior is verified;
* unit and integration tests are included;
* REST API behavior is documented where applicable;
* workbench controls are added where applicable;
* MIDI and JSON export behavior is defined;
* WAV rendering is verified;
* analysis metrics are available;
* `ruff` passes;
* `mypy` passes;
* regression tests pass;
* an example configuration is included.
