# Genre Arrangement Pipeline Development Plan

**Project:** Pure Intonation Composer

**Status:** GA1–GA6 are implemented (MVP). Section or part-level regeneration,
general project import beyond the 1.0-to-1.1 migration, stems, rendered effect
automation, and structured listening evaluation remain planned.

This plan defines a higher-level composition pipeline that turns a generated
scale and a user-selected vocabulary of basic chords into a complete,
genre-guided arrangement. The result must be playable in the workbench and
must drive MIDI export, JSON export, and offline rendering from the same
compiled event timeline.

The initial genre profiles are:

* Pop
* Ambient
* Alternative Rock
* Future Bass

Genre profiles are editable parameter bundles, not claims that one fixed
template represents an entire genre. A profile establishes useful defaults
and constraints while exposing the musical decisions that produced the
result.

---

## 1. Goals

The pipeline must:

1. accept any generated scale supported by the project;
2. accept a small vocabulary of exact-ratio chords chosen by the user;
3. generate section-aware harmony and harmonic rhythm;
4. generate coordinated drum, bass, harmony, melody, and optional texture
   parts;
5. preserve exact ratios until playback, MIDI encoding, or audio rendering;
6. reproduce the same arrangement from the same inputs, profile version, and
   seed;
7. export a multitrack MIDI file, a complete JSON project, and rendered audio.

The first release is an arranger, not an automatic mastering system. It may
generate instrument, articulation, dynamics, and effect-automation intent,
but it must keep those decisions editable.

## 2. Design Principles

### Exact tuning remains authoritative

Genre logic may classify intervals by cents, harmonic distance, scale degree,
or user tags, but it may not replace an input ratio with a 12-EDO pitch.
Equal-tempered chord names are descriptive hints only.

### Adapt instead of assuming

A scale may not contain conventional major/minor triads, dominant sevenths,
or power fifths. A profile therefore requests musical properties such as
stability, roughness, common-tone retention, root motion, and chord size. The
arranger selects the closest valid chord from the supplied vocabulary and
reports any unmet preference.

### One canonical timeline

Harmony, drums, bass, comping, melody, automation, workbench playback, MIDI,
JSON, and rendering must compile to integer-tick events. Exporters may not
regenerate or reinterpret the arrangement independently.

### Profiles are inspectable

Every profile contains ordinary values and weighted rules. Users can duplicate
and edit a built-in profile. The JSON result records the resolved profile,
profile schema version, seed, and generator decisions.

### Variation is bounded and deterministic

Variation must preserve section length, required cadences, instrument ranges,
and event limits. Seeded tie-breaking is used whenever candidates have equal
scores.

---

## 3. Input Contract

```text
GenreArrangementRequest
  scale
    scale_id: str | null
    ratios: list[Ratio]
    base_frequency: float
  chord_vocabulary: list[BasicChord]
  genre_profile: str | GenreProfile
  clock
    tempo_bpm: float | null
    beats_per_bar: int | null
    subdivisions_per_beat: int
    bars: int | null
  form: FormPlan | null
  controls: ArrangementControls
  seed: int
```

```text
BasicChord
  id: str
  name: str
  mode: absolute | degree_template | ratio_template
  tones: list[Ratio | ScaleDegree]
  root_degree: int | null
  allowed_root_degrees: list[int] | null
  tone_vectors: list[list[int]] | null
  tags: list[str]
```

Recommended chord tags include `stable`, `tense`, `open`, `dense`, `cadential`,
`suspended`, `power`, and `color`. Tags guide the profile but never alter the
stored ratios. Lattice chords retain their coordinate vectors alongside their
ratios.

An `absolute` chord always uses its stored pitch classes. A `degree_template`
stores scale-degree offsets and may be moved only to allowed roots in the
input scale. A `ratio_template` multiplies exact interval ratios by an allowed
root; pitches outside the input scale are permitted only when the request
explicitly enables them. Materialized chord instances always record their
template id, root, exact ratios, and source coordinates where available.

Global user controls:

```text
ArrangementControls
  energy: 0..1
  density: 0..1
  syncopation: 0..1
  harmonic_complexity: 0..1
  repetition: 0..1
  section_contrast: 0..1
  humanization: 0..1
  melody_enabled: bool
  drums_enabled: bool
```

Each value acts as a macro over explicit profile parameters. The resolved
parameters are included in the response.

## 4. Genre Profile Model

```text
GenreProfile
  id: str
  display_name: str
  schema_version: str
  tempo_range: [float, float]
  allowed_meters: list[Meter]
  default_form: FormTemplate
  harmony: HarmonyStyle
  rhythm: RhythmStyle
  parts: list[PartStyle]
  arrangement: ArrangementStyle
  render: RenderStyle
```

Profiles define ranges and weights rather than a single frozen pattern.
Built-in profiles are versioned application data. User profiles are copied
into the project JSON so later software updates do not silently change an
existing arrangement.

## 5. Generation Pipeline

```text
scale + basic chords + genre profile + seed
  -> validate and analyze chord vocabulary
  -> resolve meter, tempo, form, and energy curve
  -> generate section-aware chord progression
  -> generate harmonic rhythm
  -> voice chords and assign registers
  -> generate coordinated part patterns
  -> add articulation, velocity, fills, and automation
  -> compile one ArrangementTimeline
  -> playback / MIDI / JSON / render
```

Every stage returns both its result and a short decision trace. A stage can be
locked and later stages regenerated without changing it.

### 5.1 Chord Vocabulary Analysis

For every basic chord, calculate:

* pitch-class cardinality and ordered tones;
* root confidence, if the user did not supply a root;
* cents span and adjacent interval sizes;
* harmonic, monzo, and optional lattice complexity;
* roughness or interval-tension proxy;
* common-tone compatibility with every other chord;
* available inversions and register-safe octave placements.

The analyzer builds a directed chord-transition graph. Edges contain root
motion, common-tone count, voice-leading cost, tension change, and coordinate
distance where available.

Template chords are materialized over their allowed root degrees before graph
construction. Duplicate sounding instances may share analysis data, but their
template and coordinate provenance remain distinct.

### 5.2 Form and Energy

The form generator produces named sections with exact bar ranges:

```text
ArrangementSection
  id
  role: intro | verse | pre_chorus | chorus | bridge | breakdown | drop | outro
  start_bar
  bars
  energy_start
  energy_end
  harmony_density
  part_presence
```

Section names are profile vocabulary rather than mandatory song forms.
Ambient profiles may use `opening`, `field`, `bloom`, and `dissolve` aliases
that map to the same structural roles. Users may supply a custom form or lock
individual sections.

### 5.3 Harmonic Progression

Generate progressions phrase by phrase over the chord-transition graph. Each
candidate transition is scored by:

```text
cost =
  w_voice_leading * voice_leading_cost
  + w_root_motion * root_motion_cost
  + w_complexity * complexity_mismatch
  + w_repetition * repetition_penalty
  + w_section * section_energy_mismatch
  + w_cadence * cadence_mismatch
  - w_common_tone * common_tone_reward
  - w_motif * progression_motif_reward
```

A bounded beam search is preferred because section-level repetition and
cadence constraints require more context than a first-order random walk.
The final progression must fit the exact section length. The response records
the selected chord ids, roots, inversions, durations, and transition metrics.

Profiles describe cadential behavior using stability and tension change. They
must not require a Western functional label when the input chord vocabulary
does not support one.

### 5.4 Rhythm and Part Coordination

Harmonic rhythm and pitched note events use the existing G10 Compose Rhythm
Orchestration clock and event compiler. Drum generation uses the existing
Rhythm engine. The new arranger adds section-scale coordination:

* density and syncopation envelopes by section;
* drum fills at selected boundaries;
* shared accent landmarks across drums, bass, harmony, and melody;
* call-and-response and onset-competition constraints;
* pickup, breakdown, drop, and final-cadence handling;
* deterministic variation of repeated phrases.

Part generation order:

1. harmony durations and voiced chord spans;
2. drums or pulse layer;
3. bass, coordinated with low-frequency drum accents;
4. harmony articulation or comping;
5. primary melody;
6. optional counter-melody, texture, and transition effects.

Each part receives a register, density target, maximum leap, articulation
vocabulary, velocity curve, and instrument-family hint. A generated part can
be muted, locked, regenerated, or replaced without invalidating other tracks.

Pitch-source rules remain explicit:

* harmony uses the materialized exact-ratio chord instance;
* bass selects the chord root or an allowed low chord tone, with profile-
  controlled passing notes from the input scale;
* melody and counter-melody select from the input scale, weighting active
  chord tones and section motifs;
* texture parts may sustain any declared chord or scale tone but may not invent
  an untracked 12-EDO pitch.

### 5.5 Harmony Performance Patterns

The current MVP realizes every `harmony` onset as a block chord: all voiced
tones attack together. GA6 separates three decisions that must remain
independently editable:

1. **harmonic identity** selects the active exact-ratio chord;
2. **voicing** places its tones in registers and minimizes voice movement;
3. **performance pattern** expands the voiced chord span into timed events.

Changing a performance pattern must not regenerate the chord progression or
change its ratios. The first pattern vocabulary is:

| Mode | Event behavior | Main controls |
| --- | --- | --- |
| `block` | Attack the complete voicing together | gate, velocity curve, retrigger/tie |
| `arpeggio` | Attack ordered chord tones over the chord span | rate, order, octave span, rotation, gate |
| `stride` | Alternate a low root/chord tone with a mid-register chord or shell | meter pattern, low-note source, chord size, bass-conflict policy |
| `auto` | Select block, arpeggio, or stride per section or phrase from bounded profile weights | allowed modes, section roles, energy thresholds, repetition |

`auto` is a selection policy, not a fourth note generator. Every resolved
section records the concrete mode it selected.

Proposed profile model:

```text
HarmonyPerformanceStyle
  mode: auto | block | arpeggio | stride
  allowed_modes: list[block | arpeggio | stride]
  mode_weights: map[mode, float]
  rate_subdivisions: int
  gate: float
  velocity_curve: flat | metrical | phrase
  arpeggio
    order: up | down | up_down | outside_in | seeded
    octave_span: int
    rotate_per_chord: bool
  stride
    low_note_source: root | lowest_voiced | bass_note
    chord_tones: full | shell
    bass_conflict: yield | coordinate | double
  section_overrides: map[section_role, partial style]
```

`auto` resolves one of the allowed concrete modes using the genre profile,
section role, energy, density, available chord size, meter, and seed. A user
selection always overrides automatic choice. Pattern rates use integer
subdivisions of the canonical clock; no floating-point time or unbounded LCM
is introduced.

#### Arpeggio realization

For each chord slot, sort the already voiced tones by sounding pitch, then
build the selected order. `up_down` does not duplicate the end tones at the
turnaround. `outside_in` alternates the lowest and highest remaining tones.
`seeded` creates one deterministic permutation per repeated phrase and may
rotate it at chord boundaries.

Onsets repeat at `rate_subdivisions` until the chord slot ends. Events are
clamped to the slot unless an explicit tie policy permits a common tone to
continue into the next chord. Octave expansion must stay inside the harmony
part register. Chords with changing cardinality restart or rotate their order
without indexing a missing tone.

#### Stride realization

Stride is meter-aware rather than hard-coded to 4/4:

```text
2/4 or 4/4: low on strong beats, chord/shell on following weak beats
3/4:        low on beat 1, chord/shell on beats 2 and 3
6/4:        two bounded low/chord groups, aligned to beats 1 and 4
```

The low event remains part of the harmony gesture even when it uses the root
or generated bass pitch. It is tagged `gesture_component=low`; the upper
attack is tagged `gesture_component=chord`. This keeps one musical gesture
traceable without silently rewriting the independent bass part.

When a bass track is enabled, `bass_conflict` is mandatory:

* `yield`: omit a coincident stride-low event;
* `coordinate`: retain it only when register separation and onset spacing pass
  the profile thresholds;
* `double`: allow intentional doubling and record that decision in the trace.

The default is `yield`, preventing accidental low-frequency doubling.

#### Compiler integration and canonical data

Add a bounded `HarmonyGestureCompiler` between voicing and final event
assembly. It emits virtual G10-compatible sources:

```text
block      -> full_chord source
arpeggio   -> ordered chord_tone sources
stride low -> root | lowest_voiced | bass_note source
stride high-> full_chord | shell source
```

Pitch source and output track are separate fields. This permits a stride-low
event to use a root or bass pitch while remaining on the harmony track. The
compiler reuses the G10 clock, gate, collision, tie, and stable-id rules
instead of adding a second timing system.

The canonical project adds:

```text
harmony_gestures[]
  id, section_id, chord_index, mode
  start_tick, duration_ticks
  resolved_settings

events[]
  source_gesture_id: str | null
  gesture_component: block | tone | low | chord | null
```

This is a project-schema change. GA6 must introduce a new schema version and a
migration that maps existing projects to `mode=block`; their existing event
arrays and audible output must remain unchanged.

#### Profile and workbench defaults

Initial listening-test defaults:

* Pop: arpeggio or block in intros/verses, block emphasis in choruses;
* Ambient: slow arpeggio or sustained/rolled block; stride disabled by default;
* Alternative Rock: block or riff-like repeated attacks; stride user-selectable;
* Future Bass: syncopated block in drops, optional fast arpeggio in builds.

The Arrange workbench adds a compact mode control (`Auto`, `Block`,
`Arpeggio`, `Stride`), rate and order menus, and a bass-coordination menu that
appears for stride. Composition Roll displays simultaneous block notes,
staggered arpeggio tones, and separate stride-low/chord components. Pattern
regeneration can lock progression, voicing, and all non-harmony parts.

## 6. Initial Genre Profiles

The following ranges are starting defaults for listening tests, not hard
validation limits.

| Profile | Pulse and form | Harmony behavior | Default parts |
| --- | --- | --- | --- |
| Pop | Usually 4/4, 90-130 BPM, 4/8-bar phrases, clear section repetition | Stable loops, audible cadence, moderate common-tone voice leading, controlled contrast between verse and chorus | Drum kit, bass, chordal comping, lead melody, optional counter-line |
| Ambient | 50-90 BPM or very slow pulse, long sections, gradual energy curves | Long chord spans, high common-tone retention, low transition rate, open registers, non-functional motion allowed | Pad, low drone/bass, sparse pulse or no drums, slow melody, texture layer |
| Alternative Rock | Usually 4/4, 80-160 BPM, riff-oriented repeated phrases | Open fifths or compact chord shells where available, parallel/root motion, stronger accents and section contrast | Drum kit, electric bass, rhythm-guitar role, lead-guitar/keyboard role, melody |
| Future Bass | Usually 4/4, 130-160 BPM with optional half-time feel, build/drop form | Extended or dense chord colors where available, wide voicing, syncopated chord gates, strong drop contrast | Trap-influenced drums, sub bass, chord stack, lead/chop melody, effects/automation |

### 6.1 Pop

* Prefer memorable two- or four-chord motifs with bounded variation.
* Place bass attacks on strong beats while permitting pickups into a chorus.
* Generate a melody with repeated rhythmic cells and section-specific contour.
* Increase register, density, or doubling in the chorus without changing the
  exact chord ratios.

### 6.2 Ambient

* Permit drumless output and free-feeling events on an underlying exact clock.
* Favor sustained tones, slow voice leading, drones, and sparse entrances.
* Treat timbral movement and register expansion as arrangement events.
* Avoid mandatory cadences; section identity may come from density and texture.

### 6.3 Alternative Rock

* Prefer rhythmic riffs and repeatable chord attacks over continuous pads.
* Coordinate bass with kick accents without forcing exact unison at every hit.
* Select `power`-tagged or open, low-complexity chords when the vocabulary
  provides them; otherwise use the closest stable two- or three-tone shell.
* Add fills and crash-like accents at section boundaries.

### 6.4 Future Bass

* Support half-time drum perception independently of the project tempo.
* Favor wide chord voicings and strong velocity/envelope shapes.
* Generate syncopated chord gates, sub-bass roots or selected low chord tones,
  and sparse lead phrases around dense chord events.
* Represent pumping/sidechain intent as automation metadata. Offline rendering
  implements it only after the effect-automation stage is available.

## 7. Output Contract

```text
ArrangementProject
  schema_version
  metadata
  source_scale
  chord_vocabulary
  requested_profile
  resolved_profile
  seed
  form
  harmony_progression
  clock
  tracks
  events
  automation
  mix
  render_settings
  decision_trace
```

### MIDI

Export Standard MIDI File type 1 with one named track per arrangement part.
Pitched tracks use the existing pitch-bend-accurate tuning path. Simultaneous
notes requiring different bends may not share a MIDI channel. Channel 10 is
reserved for GM percussion when the selected drum mapping uses it.

Channel allocation is global across all tracks, not reset per track. If exact
simultaneous tuning exceeds the available channel budget, exact mode returns
an actionable error. A future multi-port or explicitly selected approximation
mode may resolve the conflict, but the exporter may never silently quantize.

The file includes tempo, meter, section markers, track names, program hints,
velocities, durations, and pitch bends. Unsupported effect automation remains
in the JSON sidecar rather than being silently discarded.

### JSON

JSON is the lossless canonical arrangement export. It contains source ratios,
chord ids, profile version and resolved values, form, seeds, all generated
events, MIDI assignments, render intent, and decision traces. Re-import and
schema migration are required before this feature is considered stable.
Canonical comparison excludes presentation-only timestamps; all musical data
uses stable ordering and deterministic identifiers.

### Audio rendering

The first rendering milestone produces a stereo preview mix through instrument
presets. The next milestone adds per-track stems and supported automation.
Both use the same event ids and timing as MIDI and JSON. Render fallbacks must
be reported when an instrument or effect requested by a profile is unavailable.

## 8. API and Workbench

Proposed endpoint:

```text
POST /api/arrange/generate
  scale, chord_vocabulary, genre_profile, form, controls, clock, seed
  -> ArrangementProject
```

Existing export and render endpoints should accept an `ArrangementProject`
or its canonical events instead of introducing separate generation logic.
Profile management may later use:

```text
GET    /api/arrange/profiles
POST   /api/arrange/profiles
DELETE /api/arrange/profiles/{profile_id}
```

The workbench adds an **Arrange** stage after Compose:

* genre profile selector and editable macro controls;
* scale and basic-chord summary;
* form/section lane with energy curve;
* part list with mute, solo, lock, regenerate, instrument, and register;
* progression and event views linked to the Composition Roll;
* commands for Generate all, Regenerate section, MIDI, JSON, Render mix, and
  Render stems.

Profile details belong in an inspector, not in persistent explanatory text on
the main work surface.

## 9. Delivery Plan

### GA1 - Models and profile registry

* Add versioned `GenreProfile`, `BasicChord`, `FormPlan`, and
  `ArrangementProject` models. — Done (`app/arrangement/profiles.py`,
  `app/arrangement/models.py`, `app/arrangement/project.py`)
* Add built-in profiles and profile validation. — Done (`pop`, `ambient`,
  `alternative_rock`, `future_bass`; `GET /api/arrange/profiles`)
* Add project JSON import and migration before user profiles are persisted. —
  Planned (the canonical project JSON is exported and accepted back by the
  MIDI/render endpoints; schema migration is not implemented yet)

### GA2 - Harmony and form

* Implement chord-vocabulary analysis and transition graph construction. —
  Done (`app/arrangement/chords.py`)
* Implement seeded form, energy, progression, cadence, and voicing generation.
  — Done (`app/arrangement/form.py`, `app/arrangement/progression.py`,
  bounded beam search with the §5.3 cost function; repetition and motif
  identity use sounding pitch-class sets rather than template ids)
* Expose decision metrics and locked-stage regeneration. — Decision trace
  done; locked-stage regeneration Planned

### GA3 - Rhythm and parts

* Reuse G10 for harmonic and pitched-part rhythm. — Done
  (`app/arrangement/parts.py` compiles through `app/composition/rhythm.py`)
* Add section-aware drum generation, fills, and shared accent landmarks. —
  Done (euclidean per-section layers, boundary fills, crash accents,
  half-time backbeat for Future Bass)
* Implement bass, comping/pad/guitar, melody, and optional texture roles. —
  Done (texture = sustained chord tone)

### GA4 - Export and rendering

* Add type-1 multitrack microtonal MIDI export with section markers. — Done
  (`app/exporters/midi.py::arrangement_midi_bytes`, global pitch-bend channel
  allocation with actionable over-budget error)
* Add lossless arrangement JSON export/import. — JSON export Done (canonical
  response of `POST /api/arrange/generate`); re-import/migration Planned
* Add instrument presets, stereo preview mix, then stems and automation. —
  Preview mixdown Done (`POST /api/arrange/render`, per-role waveform/envelope
  presets, bounded sample budget, one-stem-at-a-time PCM accumulation);
  stems and rendered effect automation Planned (sidechain intent is recorded
  as automation metadata only)
* Validate canonical projects before MIDI/render export. — Done (version,
  clock/form consistency, event timing and pitch fields, track/section
  references, mix, and render settings return `422` on invalid input)

### GA5 - Workbench and evaluation

* Add the Arrange workbench and section-level regeneration. — Workbench Done
  (profile selector, macro controls, form/energy lane, part list, progression
  view, playback, MIDI/JSON/WAV export); section-level regeneration Planned
* Add deterministic browser workflows and export round-trip tests. — Planned
* Run structured listening comparisons for all four initial profiles. — Planned
* Tune profile defaults without changing their versioned historical values. —
  Planned

### GA6 - Harmony Performance Patterns

* Add versioned `HarmonyPerformanceStyle`, resolved `harmony_gestures`, event
  provenance, and migration of existing projects to explicit `block` mode. —
  Done (`ArrangementProject` 1.1 and `POST /api/arrange/migrate`)
* Implement bounded block, ordered arpeggio, and meter-aware stride compilers
  on the G10 integer clock. — Done (`app/arrangement/gestures.py`)
* Add bass-conflict policies, register validation, variable-cardinality chord
  handling, and deterministic section/phrase selection. — Done
* Add Arrange controls and Composition Roll visualization for each gesture. —
  Done for Arrange controls, provenance table, and arrangement/phase lanes;
  direct editing in the main Composition Roll remains Planned
* Add JSON/MIDI/WAV equivalence tests and structured listening comparisons for
  all four profiles. — Export equivalence tests Done; structured listening
  comparisons Planned

GA1-GA6 now share the same canonical event and export path. Further work
should prioritize listening evaluation and direct gesture editing without
changing embedded historical profile versions.

## 10. Acceptance Criteria

* A generated CPS or exponent-lattice scale and at least two basic chords can
  produce a complete arrangement without conversion to 12-EDO.
* Pop, Ambient, Alternative Rock, and Future Bass profiles produce observably
  different form, rhythm, voicing, part-density, and articulation decisions.
* Missing conventional chord types do not cause failure; the response reports
  which profile preferences were relaxed.
* The same request, profile version, and seed produce byte-equivalent canonical
  JSON and equivalent event timelines.
* All sections exactly fill their declared bar ranges.
* No generated pitch leaves its configured instrument range after octave
  placement.
* Workbench playback, type-1 MIDI, JSON, preview rendering, and stems share
  event ids, starts, durations, pitches, and velocities.
* MIDI channel allocation never applies one pitch bend to simultaneous notes
  that require different bends.
* A single section or part can be regenerated while locked material remains
  unchanged.
* Invalid profiles, chord references, or over-budget forms return bounded,
  actionable validation errors.
* Existing projects migrate to explicit `block` performance without changing
  their audible events.
* Arpeggio orders are deterministic, remain within the configured register,
  and never index a missing tone when chord cardinality changes.
* Stride follows the declared meter and applies the selected bass-conflict
  policy at every coincident low onset.
* Block, arpeggio, and stride produce identical canonical events in workbench
  playback, Composition Roll, JSON, MIDI, and WAV.

## 11. Evaluation Metrics

Automated metrics:

* exact form-length fit;
* repetition and variation by section;
* common-tone retention and voice-leading distance;
* onset density, syncopation, and part collision;
* register violations and pitch-bend channel conflicts;
* event equivalence across playback and exporters;
* generation time and peak memory for documented limits.
* harmony simultaneity ratio and arpeggio order accuracy;
* stride low/chord alternation accuracy and bass-onset collision count;
* performance-pattern register, chord-boundary, and event-budget violations;

Listening evaluation:

* profile recognizability without relying only on instrument names;
* musical usefulness of harmony substitutions in non-standard scales;
* clarity of section contrast;
* bass/drum and melody/harmony coordination;
* quality of repeated-phrase variation;
* recognizability and usefulness of block/arpeggio/stride changes without
  changing the underlying harmony;
* rendering fallbacks and balance.

Listening scores tune future profile versions; they must not mutate projects
that already embed an older resolved profile.
