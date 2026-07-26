# Dual-Rhythm Harmonic Phase-Shift Composition Specification

**Project:** Pure Intonation Composer

**Status:** Planned G11 extension

This specification extends the Genre Arrangement Pipeline with two rhythmic
streams that use the same ordered chord progression. The streams begin from a
shared harmonic source, articulate it with clearly different rhythms, move
through controlled phase relationships, and converge again at configured
structural points.

The feature is not limited to shifting a drum pattern. It treats phase as a
compositional relationship between two pitched arrangement streams while
preserving exact ratios, G11 section structure, deterministic generation, and
the canonical event timeline.

---

## 1. Musical Goal

Given one G11 arrangement progression:

```text
P = (C0, C1, C2, ... Cn-1)
```

generate two streams `A` and `B` such that:

* both reference the same ordered progression `P`;
* each stream has a distinct rhythm and orchestration;
* their attacks and, optionally, their chord positions move out of phase;
* simultaneous material remains musically bounded and inspectable;
* selected section boundaries or convergence points realign the streams;
* playback, MIDI, JSON, and rendering use the same compiled result.

A common rhythm section may remain phase-locked while pitched streams move.
The system must not duplicate every G11 part automatically, because two full
arrangements in the same register would usually obscure the phase relation.

## 2. Phase Modes

### 2.1 Shared Chord Clock

Both streams use the chord active on the original G11 harmony timeline:

```text
chord_A(t) = chord_B(t) = source_chord(t)
```

Their onset, gate, accent, and rest patterns differ. Phase shift changes only
how the current chord is articulated.

This is the first implementation target because it guarantees harmonic
identity while making rhythmic phase audible.

Typical result:

* stream A: sustained or metrically anchored chord attacks;
* stream B: shorter syncopated attacks whose rotation changes by section;
* shared bass or drums: structural reference.

### 2.2 Independent Chord Clock

Both streams traverse the same chord order but use independent duration
sequences:

```text
chord_A(k) = P[k mod n]
chord_B(k) = P[k mod n]

start_s(k) = sum(duration_s(j), j = 0 .. k-1)
```

At a given time, `A` and `B` may therefore sound different members of `P`.
This creates harmonic phase as well as rhythmic phase.

Removing rests, repeated holds, and orchestration events from either stream
must recover the same progression order. Strict mode may not reorder or
silently substitute chord ids to improve an overlap.

### 2.3 Phase Process

Supported processes:

| Process | Meaning | Initial status |
| --- | --- | --- |
| Static | Fixed rotation or start delay | Planned MVP |
| Discrete | Offset changes by an integer number of subdivisions at selected boundaries | Planned MVP |
| Polymetric | Different bounded rhythm cycles produce changing relative phase | Planned MVP |
| Convergent | A bounded correction window moves the streams toward a protected alignment point | Planned MVP |
| Fractional drift | One stream uses a slightly different effective step duration | Experimental later work |

Fractional drift is not part of the first MIDI implementation. It requires a
rational-time scheduler and deterministic error diffusion when converted to
integer MIDI ticks.

## 3. Formal Phase State

For stream `s` at time `t`:

```text
rhythmic_phase_s(t)
  = active pattern position modulo its cycle length

chord_visit_s(t)
  = current visit number in the repeated source progression

chord_phase_s(t)
  = chord_visit_s(t) modulo progression length
```

Relative state:

```text
rhythm_offset(t)
  = rhythmic_phase_B(t) - rhythmic_phase_A(t)

chord_offset(t)
  = (chord_phase_B(t) - chord_phase_A(t)) mod n
```

An alignment point occurs when the requested phase dimensions match:

```text
rhythm_offset(t) = target_rhythm_offset
chord_offset(t) = target_chord_offset
```

The most common convergence target is `(0, 0)`, but a composition may preserve
a deliberate rhythmic offset while returning to the same chord.

Phase state is calculated incrementally with modular arithmetic. The engine
must not allocate a full least-common-multiple timeline merely to find a
future alignment.

## 4. Request Model

```text
HarmonicPhaseShiftRequest
  arrangement: ArrangementProject
  source_progression
    scope: whole_form | section | selected_slots
    section_ids: list[str]
    repeat: bool
  mode: shared_chord_clock | independent_chord_clock
  stream_a: PhaseStreamSpec
  stream_b: PhaseStreamSpec
  phase_plan: PhasePlan
  overlap_policy: OverlapPolicy
  seed: int
```

```text
PhaseStreamSpec
  id: a | b
  track_ids: list[str]
  generated_roles: list[harmony | bass | melody | texture]
  rhythm
    source: existing | euclidean | semi_markov | interlocking | manual
    cycle_steps: int
    pulses: int | null
    pattern: list[int] | null
    rotation: int
    density: float
    syncopation: float
    gate: float
  chord_durations: list[int] | null
  register_low_cents: float
  register_high_cents: float
  gain: float
  pan: float
```

```text
PhasePlan
  process: static | discrete | polymetric | convergent | fractional
  initial_offset_steps: int
  increment_steps: int
  update_interval_bars: int
  direction: forward | backward | alternate
  convergence_points: list[PhaseAnchor]
  maximum_supercycle_bars: int
```

```text
PhaseAnchor
  bar: int
  rhythm_offset: int | null
  chord_offset: int
  tolerance_ticks: int
  protected: bool
```

The source `ArrangementProject` remains immutable. The result records its
canonical digest and adds phase streams, alignment analysis, and newly
compiled events.

## 5. Rhythm Distinctness

Two streams must be measurably different, not merely renamed copies.
After projecting both patterns onto a bounded shared analysis window, compute:

```text
onset_hamming_distance
onset_overlap_ratio
complement_ratio
density_difference
syncopation_difference
inter_onset_interval_distance
```

Default generation constraints:

* onset Hamming distance must exceed a profile threshold;
* neither stream may contain all onsets of the other unless explicitly
  requested;
* at least one stream retains a recognizable reference pulse;
* local combined density remains below the overlap policy limit;
* protected structural attacks may be shared.

If generated rhythms are too similar, regenerate only the moving stream with
a deterministic seed offset. Failure after a bounded number of attempts
returns diagnostics rather than an arbitrary result.

## 6. Progression Preservation

Each compiled harmonic event stores:

```text
source_progression_id
source_slot_index
source_chord_id
stream_id
visit_index
phase_iteration
```

For `shared_chord_clock`, both streams must reference the source chord slot
active at the event time.

For `independent_chord_clock`, the chord-id sequence of each stream, after
collapsing repeated holds, must equal a prefix of the cyclic source progression.
The phase planner may lengthen or shorten allowed durations but may not change
the order.

Convergence planning must not jump directly to another chord index. It searches
bounded duration adjustments or holds so both streams arrive naturally at the
required source slot. When that is impossible within the configured section
length and duration limits, the request fails or falls back to
`shared_chord_clock` only when the user selected that fallback.

## 7. Harmonic Overlap Management

In independent-clock mode, chord `Ci` from stream A may overlap chord `Cj`
from stream B. The engine analyzes every maximal window in which the active
chord pair is constant.

Overlap cost:

```text
cost =
  w_interval * pairwise_interval_tension
  + w_complexity * combined_ratio_complexity
  + w_cardinality * excess_active_tones
  + w_bass * low_register_conflict
  + w_crossing * voice_crossing
  + w_retrigger * attack_collision
  - w_common * common_tone_reward
  - w_register * register_separation_reward
```

The values are calculated from exact ratios, cents, monzos, and lattice
coordinates where available.

### 7.1 Resolution Policies

Resolution is applied in this order:

1. choose inversions and octave placements;
2. separate stream registers and stereo positions;
3. change gate length or delay a non-protected attack;
4. reduce velocity or duck one stream during dense overlap;
5. omit only explicitly optional chord tones;
6. report or reject an unresolved overlap.

The chord model may provide required and optional tone indices. Without that
metadata, full-chord strict mode treats every tone as required.

`adaptive_voicing` may omit optional color tones while retaining the chord id,
root, and required tones. It must record every omission. `strict_full_chord`
may change only inversion, octave, dynamics, and timing within tolerance.

### 7.2 Bass and Melody Rules

The default configuration keeps bass in the shared phase-locked group. Two
independently moving bass lines require an explicit opt-in and a separate
low-register collision limit.

Melodies may belong to one phase stream or remain shared. When both streams
generate melody, their contour, register, and onset-competition constraints
are optimized together. Neither melody may introduce a pitch outside the G11
source scale unless the original arrangement explicitly allowed it.

## 8. Section and Genre Behavior

Phase is planned around G11 section roles and energy curves.

| Genre profile | Suggested phase behavior |
| --- | --- |
| Pop | Short discrete divergence inside a verse or bridge; strong convergence before chorus and final cadence |
| Ambient | Long polymetric cycles, open registers, sparse attacks, gradual convergence, phase-locked drone optional |
| Alternative Rock | Anchor drums and bass; shift a guitar/keyboard riff against a second chordal rhythm; reunite at fills or section boundaries |
| Future Bass | Complementary gated chord streams; divergence during build, exact convergence at drop; half-time drums remain shared |

These are defaults, not validation rules. Phase settings are stored as a
resolved extension of the selected G11 genre profile.

Protected anchors should normally include:

* the first bar of the piece;
* chorus, drop, or major section entrances;
* final cadences;
* user markers.

Ambient profiles may protect fewer anchors and permit a phrase to end with a
non-zero rhythmic offset.

## 9. Compilation

Compilation stages:

```text
ArrangementProject
  -> select and freeze source progression
  -> generate distinct rhythms A and B
  -> build phase schedule and convergence constraints
  -> traverse source chords for each stream
  -> segment constant chord-overlap windows
  -> optimize voicing, register, gate, and dynamics
  -> assign tracks and instruments
  -> compile one integer-tick event timeline
  -> calculate phase and overlap metrics
```

Track phase groups:

```text
shared
anchor
moving
```

`shared` tracks preserve source G11 timing. `anchor` tracks use stream A.
`moving` tracks use stream B. A track belongs to exactly one group.

Events receive stable ids derived from the source event or source chord slot,
stream id, visit index, and local event index. Regeneration with the same
inputs and seed must preserve those ids.

## 10. Output Model

```text
PhaseShiftArrangementProject
  schema_version
  source_arrangement_digest
  source_progression
  resolved_phase_profile
  streams
  phase_schedule
  convergence_points
  overlap_windows
  tracks
  events
  metrics
  decision_trace
  midi
  mix
  render_settings
```

Metrics include:

```text
rhythm_distinctness
onset_overlap
phase_offset_by_bar
chord_offset_by_bar
alignment_points
maximum_overlap_cost
mean_overlap_cost
optional_tone_omissions
duration_adjustments
channel_budget_peak
```

JSON must contain enough information to reconstruct the phase state without
re-running generation.

## 11. MIDI, JSON, and Rendering

### MIDI

The phase project uses the G11 type-1 microtonal MIDI exporter:

* separate named tracks for stream A, stream B, and shared roles;
* section and convergence markers on the conductor track;
* global pitch-bend channel allocation across both streams;
* exact integer-tick event timing for static, discrete, and polymetric modes;
* actionable failure when simultaneous bends exceed the channel budget.

Fractional drift remains render-only until its MIDI approximation mode is
explicitly enabled and its maximum timing error is included in the response.

### JSON

JSON is the lossless phase-composition format. It embeds or references the
source G11 arrangement, stores both rhythm definitions, every phase update,
all overlap decisions, metrics, and compiled events.

### Rendering

Stream timbres should differ enough to make their phase relationship audible.
Default rendering uses controlled register, waveform, pan, and envelope
contrast while avoiding hard left/right isolation as the only distinction.

The renderer uses compiled events and does not recalculate phase. Preview mix
and future stems must retain identical event ids and timing. Optional
sidechain or ducking decisions are stored as automation rather than baked into
event velocities when the renderer supports that automation.

## 12. API

Proposed endpoint:

```text
POST /api/arrange/phase-shift
  arrangement, source_progression, mode,
  stream_a, stream_b, phase_plan, overlap_policy, seed
  -> PhaseShiftArrangementProject
```

The endpoint accepts a previously generated G11 `ArrangementProject`.
Generating the base arrangement and phase result in one request may be added
later as a convenience wrapper, but it must call the same two stages and
return both resolved inputs.

Existing arrangement MIDI and render endpoints should accept the extended
project only after they validate phase metadata and event provenance. JSON
export is direct serialization of the returned project.

## 13. Workbench and Visualization

Add a **Phase** stage after Arrange:

* mode selector: Shared chord clock / Independent chord clock;
* A and B rhythm editors with cycle, pulses, rotation, density, and gate;
* phase process and convergence controls;
* role assignment table for shared, anchor, and moving tracks;
* overlap strictness, register separation, and maximum density controls;
* Generate phase, Regenerate B, Reset phase, MIDI, JSON, and Render commands.

The Composition Roll gains:

* separate chord-index lanes for A and B;
* rhythm-onset lanes aligned to the same tick axis;
* a phase-offset curve;
* convergence markers;
* colored overlap windows whose intensity represents overlap cost;
* synchronized selection with the existing chord and part views.

A compact alignment matrix shows which source chord indices overlap. Selecting
a matrix cell highlights every corresponding time window and auditions the
resolved voicing.

## 14. Delivery Plan

### HP1 - Shared-clock dual rhythm

* Add phase request/project models and source-arrangement digest.
* Generate two measurably distinct rhythms over the same chord clock.
* Assign G11 tracks to shared, anchor, or moving groups.
* Compile deterministic events and basic phase metrics.

### HP2 - Discrete and polymetric phase

* Add static offsets, scheduled discrete shifts, and unequal bounded cycles.
* Add convergence anchors and modular alignment analysis.
* Preserve phase events in JSON, MIDI markers, and the Composition Roll.

### HP3 - Independent chord clocks

* Traverse the same progression with separate chord-duration sequences.
* Add progression-order validation and bounded convergence planning.
* Add overlap-window analysis and strict/adaptive voicing resolution.

### HP4 - Export, rendering, and workbench

* Extend type-1 MIDI and preview rendering to phase projects.
* Add Phase controls, dual lanes, offset curve, and overlap matrix.
* Add desktop/mobile browser workflows and JSON round-trip tests.

### HP5 - Fractional drift experiment

* Add rational event times and deterministic integer-tick error diffusion.
* Quantify MIDI timing error and keep the mode opt-in.
* Compare discrete, polymetric, and fractional results in listening tests.

HP1 and HP2 form the MVP. HP3 introduces true harmonic phase and requires
more stringent musical evaluation. HP5 is experimental and must not delay the
discrete implementation.

## 15. Acceptance Criteria

* Both streams reference one immutable G11 source progression.
* Shared-clock mode never disagrees about the active source chord.
* Independent-clock mode preserves the same chord order in both streams.
* Generated rhythms meet configured distinctness and combined-density limits.
* The same source arrangement, configuration, profile version, and seed
  reproduce identical events, phase metrics, and canonical JSON.
* Protected convergence anchors are met within their tick tolerance without
  skipping a chord.
* Strict mode never removes a chord tone or substitutes a chord.
* Adaptive mode records every omitted optional tone and timing adjustment.
* Unresolvable overlaps or convergence plans return actionable diagnostics.
* Phase calculations remain bounded for unequal cycle lengths and long forms.
* Workbench playback, MIDI, JSON, and rendering share event ids, chord
  provenance, start ticks, durations, ratios, and velocities.
* MIDI channel budgeting includes simultaneous notes from both streams.
* Resetting the phase extension restores the original G11 arrangement without
  modifying its source project.

## 16. Test and Evaluation Matrix

Deterministic tests:

* identical seeds and source digest;
* static positive/negative offsets and wraparound;
* discrete shift at protected boundaries;
* unequal prime-length rhythm cycles without full-LCM allocation;
* shared-clock chord identity;
* independent-clock progression-order preservation;
* natural and planned convergence;
* impossible convergence diagnostics;
* strict and adaptive overlap policies;
* global MIDI pitch-bend channel exhaustion;
* JSON event and provenance round-trip.

Musical evaluation:

* the two rhythms are independently perceptible;
* phase motion remains audible without relying only on stereo separation;
* harmonic overlaps are useful rather than uniformly dense;
* convergence points sound structurally intentional;
* each initial G11 genre profile retains its identity;
* phase duration and complexity remain controllable by non-expert users.
