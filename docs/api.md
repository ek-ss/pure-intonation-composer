# REST API Reference

**Project:** Pure Intonation Composer

Version: 0.1 (implemented API)

---

# 1. Overview

This document describes the API as implemented by `backend/app/main.py`.
The original design specification targeted `/api/v1`; the current
implementation serves unversioned `/api/*` routes. Versioning,
authentication, presets, and project storage remain planned work.

All endpoints accept and return JSON unless otherwise specified.
Errors return the FastAPI standard shape:

```json
{ "detail": "ratio must be a positive fraction" }
```

Interactive documentation (Swagger UI) is available at `/docs` and
ReDoc at `/redoc` when the server is running.

Base URL: `http://127.0.0.1:8000`

---

# 2. Meta

## GET /health

```json
{ "status": "ok" }
```

## GET /

Serves the browser workbench (`app/static/index.html`).

---

# 3. Scale Generators

All scale endpoints return the same payload:

```json
{
  "count": 6,
  "pitches": [
    { "ratio": "3/2", "cents": 701.955, "monzo": { "2": -1, "3": 1 } }
  ]
}
```

## POST /api/cps

Generate a Combination Product Set.

```json
{
  "factors": [1, 3, 5, 7],
  "choose": 2,
  "kind": "harmonic",
  "octave_reduce": true
}
```

- `factors`: 1–16 unique positive integers
- `choose`: 1–16, combination size
- `kind`: `"harmonic"` or `"subharmonic"`

## POST /api/euler-fokker

```json
{ "factors": [3, 5, 7], "octave_reduce": true }
```

Factors must be integers greater than one.

## POST /api/harmonic-series · POST /api/subharmonic-series

```json
{ "count": 16, "octave_reduce": true }
```

## POST /api/analyze-ratio

```json
{ "ratio": "15/8" }
```

Returns `{ "ratio", "cents", "monzo" }` for one ratio.

## POST /api/analyze-interval

Parses a free-form interval expression and returns the same shape as
`/api/analyze-ratio`.

```json
{ "value": "5\\12" }
```

Accepted forms: ratio (`5/4`), cents (`748.2`), EDO degree (`5\12`),
decimal ratio (`1.33`), math expression (`=2^(6/12)`).

## POST /api/tuning/snap

Snap ratios to an EDO grid or to ratios within a prime limit.

```json
{ "ratios": ["3/2", "5/4"], "mode": "edo", "value": 12 }
```

- `mode`: `"edo"` | `"prime_limit"`
- `value`: EDO divisions or prime limit (2–31)

Response: `{ "pitches": [{ "original", "ratio", "cents" }] }`.

---

# 3b. Scale Store

In-memory store for named scales (lost on server restart).

## GET /api/scales

```json
[{ "name": "Eikosany", "count": 20 }]
```

## POST /api/scales

Save or overwrite a named scale; returns a pitch payload.

```json
{ "name": "Eikosany", "ratios": ["1/1", "9/8", "5/4"] }
```

## POST /api/scales/import

Import Scala `.scl` file content, save it, and return a pitch payload.

```json
{ "name": "my-scale", "content": "! my.scl\nMy scale\n3\n100.0\n3/2\n2/1" }
```

## GET /api/scales/{name} · DELETE /api/scales/{name}

Return a scale (404 if missing) or delete it.

---

# 4. Harmonic Graph

## POST /api/harmonic-graph

Build the CPS Johnson graph and optionally traverse it.

```json
{
  "factors": [1, 3, 5, 7],
  "choose": 2,
  "operation": "weighted_walk",
  "start": 0,
  "end": null,
  "steps": 12,
  "seed": 42,
  "metric": "harmonic"
}
```

- `operation`: `"graph"` | `"shortest_path"` | `"random_walk"` | `"weighted_walk"`
- `metric`: `"harmonic"` | `"monzo"` | `"cent"` (weighted walk only)
- `end` is required for `shortest_path`

Response:

```json
{
  "node_count": 6,
  "edge_count": 15,
  "nodes": [{ "index": 0, "factors": [1, 3], "ratio": "3/2" }],
  "edges": [{ "source": 0, "target": 1 }],
  "walk": [0, 3, 0, 2]
}
```

`walk` appears only when a traversal operation is requested.
All traversals are deterministic for a given seed.

---

# 4b. Exponent Lattice (Experimental)

Products of integer generators treated as points in an exponent lattice
(G9 in `development_plan.md`). All ratio math is exact; validation
limits: at most 8 generators, exponents −16…16, 4096 enumerated
coordinates per request.

## POST /api/exponent-lattice/scale

```json
{ "generators": [3, 5], "minimum": [-2, -2], "maximum": [2, 2], "collision_policy": "keep" }
```

Response: basis diagnostics (`prime_matrix`, `dependencies`, `warnings`)
plus `points[]` with `vector`, `ratio` (raw), `normalized_ratio`,
`octave_shift`, `cents`, `pitch_class_id`, `collision_group`.
`collision_policy: "merge"` returns one point per pitch class.

## POST /api/exponent-lattice/harmony

```json
{ "root": "1/1", "generators": [3, 5], "chord_vectors": [[0, -1], [-1, 0]] }
```

Every `chord_vectors` entry is an independent, root-relative offset. The
implicit first offset is `[0, 0]`, so this request produces the chord
`(0,0) + (0,-1) + (-1,0)`. Response: `offsets` and `tones[]` with exact
reconstructed ratios.

For compatibility with cached clients from the earlier experimental API,
`differences` is accepted as a deprecated input alias for `chord_vectors`.

## POST /api/exponent-lattice/chord

```json
{
  "root": "1/1",
  "generators": [3, 5],
  "allowed_differences": [[1, 0], [0, 1], [-1, 0], [0, -1]],
  "tone_count": 4,
  "seed": 42,
  "minimum": [-2, -2],
  "maximum": [2, 2]
}
```

Generates deterministic root-relative chord vectors by exploring a
self-avoiding path.
Candidates outside the exponent domain or colliding with an already selected
normalized pitch class are skipped. Response: `chord_vectors`, `offsets`, and
the exact reconstructed `tones`. A 422 response is returned when the current
domain and step vocabulary cannot produce the requested number of unique
tones.

The response temporarily also includes deprecated `differences`, equal to
`chord_vectors`, for cached-client compatibility.

## POST /api/exponent-lattice/progression

```json
{
  "generators": [3, 5],
  "root": "1/1",
  "start_vector": [0, 0],
  "chord_vectors": [[0, -1], [-1, 0]],
  "progression_differences": [[1, 0], [0, 1]]
}
```

`progression_differences` accumulate to form the root path
`(0,0) -> (1,0) -> (1,1)`. The same root-relative chord vectors are added
independently at every root, producing the absolute tone-vector stacks:

```text
(0,0) + (0,-1) + (-1,0)
(1,0) + (1,-1) + (0,0)
(1,1) + (1,0) + (0,1)
```

Response: cumulative root `path`, root `pitches`, root-relative
`chord_offsets`, and one simultaneous tone stack in `harmonies` per root.

## POST /api/exponent-lattice/walk

```json
{
  "generators": [3, 5],
  "start_vector": [0, 0],
  "allowed_differences": [[1, 0], [0, 1], [-1, 0], [0, -1]],
  "root": "1/1",
  "chord_vectors": [[0, -1], [-1, 0]],
  "length": 16,
  "seed": 42,
  "minimum": [-2, -2],
  "maximum": [2, 2],
  "boundary": "reflect"
}
```

`boundary`: `"stop"` | `"reflect"` | `"wrap"` | `"resample"`. Response:
coordinate `path`, root `pitches`, root-relative `chord_offsets`, and
`harmonies`, one reconstructed tone stack per walk point. At step `i`, every
tone is evaluated as `root · Q(path[i] + chord_offset)` and octave
normalized; all tones in that stack are intended to sound simultaneously.
The domain boundary constrains walk roots, not the harmony's offset tones.
Deterministic per seed. Omitting `chord_vectors` produces a root-only stack.
`harmony_differences` is accepted as a deprecated input alias, and
`harmony_offsets` mirrors `chord_offsets` in the response for cached clients.

## POST /api/exponent-lattice/analyze

```json
{ "generators": [3, 9], "vectors": [[2, 0], [0, 1]] }
```

Response: basis prime matrix, multiplicative dependencies (e.g. 9 = 3²),
warnings (generator 2 is octave-only), and pairwise lattice L1/L2,
monzo, and cents distances. The three distance families are distinct
values and must not be treated as equivalent.

---

# 5. Composition

## POST /api/compose/harmony

Generate a seeded, connected CPS harmony progression.

```json
{ "factors": [1, 3, 5, 7], "choose": 2, "length": 8, "seed": 42, "metric": "harmonic" }
```

Response:

```json
{
  "length": 8,
  "seed": 42,
  "metric": "harmonic",
  "chords": [
    { "node": 0, "factors": [1, 3], "ratio": "3/2", "transition_score": null }
  ]
}
```

`transition_score` is `null` for the first chord.

## POST /api/compose/voice-leading

Optimize a chord sequence for compact, non-crossing voice movement.

```json
{ "chords": [["1/1", "5/4", "3/2"]], "max_leap_cents": 700, "register_low_cents": 0, "register_high_cents": 2400 }
```

All chords must have the same number of voices (1–8).

## POST /api/compose/bass

```json
{ "chords": [["1/1", "5/4", "3/2"]], "strategy": "hybrid", "max_leap_cents": 900 }
```

- `strategy`: `"mirror"` | `"root"` | `"fifth"` | `"hybrid"`
- Default register: −2400…0 cents below the base frequency

Response: `notes[]` with `ratio`, `cents`, `leap_cents`, `strategy`.

## POST /api/compose/melody

```json
{ "chords": [["1/1", "5/4", "3/2"]], "voice_count": 1, "seed": 42, "contour": "arch", "phrase_memory": 3 }
```

- `contour`: `"ascending"` | `"descending"` | `"arch"` | `"free"`

Response: `voices[]`, one per voice, each a list of `{ "ratio", "cents" }`.

## POST /api/compose/rhythm/apply

Map existing Rhythm layers onto ordered chord tones or Compose roles:

```json
{
  "clock": {
    "beats_per_bar": 4,
    "subdivisions_per_beat": 4,
    "bars": 2,
    "ticks_per_beat": 480,
    "tempo_bpm": 96
  },
  "composition": {
    "chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]],
    "bass": ["1/2", "9/16"],
    "melody": [["3/2", "5/3"]]
  },
  "layers": [
    { "name": "kick", "pattern": [1, 0, 0, 0] },
    { "name": "snare", "pattern": [0, 0, 1, 0] }
  ],
  "mappings": [
    { "source_layer": "kick", "target": "bass" },
    { "source_layer": "snare", "target": "harmony", "collision": "retrigger" }
  ]
}
```

Targets: `harmony`, `bass`, `melody:i`, `chord_tone:i`, or `mute`.
Chord-tone policies: `fixed-index`, `voice-led`, `rotate-per-chord`, and
`register-spread`. Overflow: `drop`, `wrap`, or `clamp`. Each mapping also
accepts `gate`, `register_octave`, `velocity_scale`, `collision`, and
`articulation`. Polymetric patterns use modular projection and optional
per-bar `phase_offsets`.

Response: integer-tick `clock`, `chord_spans`, compiled `events`, and
event-density/polyphony `metrics`.

## POST /api/compose/rhythm/generate

Generate rhythm inside Compose without a Rhythm-panel source:

```json
{
  "clock": { "bars": 4, "tempo_bpm": 96 },
  "composition": {
    "chords": [["1/1", "5/4", "3/2"], ["9/8", "4/3", "5/3"]],
    "bass": ["1/2", "9/16"],
    "melody": [["3/2", "5/3"]],
    "transition_scores": [null, 500]
  },
  "seed": 42,
  "generators": [
    {
      "target": "harmony",
      "strategy": "transition-aware",
      "profile": "sparse",
      "density": 0.2,
      "syncopation": 0.1
    },
    {
      "target": "bass",
      "strategy": "semi-markov",
      "profile": "grounded",
      "density": 0.35,
      "syncopation": 0.25
    },
    {
      "target": "melody:0",
      "strategy": "interlocking",
      "profile": "flowing",
      "density": 0.55,
      "syncopation": 0.65
    }
  ]
}
```

Strategies: `transition-aware`, `semi-markov`, `interlocking`, and
experimental `ratio-derived`. Profiles: `grounded`, `interlocking`, `sparse`,
and `flowing`. Every `generators[]` entry independently controls one exact
target. The UI expands its Melody row into `melody:0`, `melody:1`, and so on.
Harmony's strategy controls harmonic chord durations; the other strategies
control their own onset patterns. For backward compatibility, requests may
still use top-level `strategy`, `profile`, `density`, `syncopation`, and
`targets`.

The response includes the effective `generators`, generated `layers`,
`mappings`, subdivision-based `chord_durations`, and the same compiled event
contract as `/apply`. Output is deterministic for identical inputs and seed.

---

# 5b. Genre Arrangement (Experimental)

Section-aware, genre-guided arrangement pipeline. A generated scale plus a
small exact-ratio chord vocabulary compiles into one canonical integer-tick
timeline (form, harmony, drums, bass, comping, melody, texture). Exact ratios
are preserved until playback, MIDI encoding, or rendering. See
`development_plan_genre_arrangement.md` for the full contract.

The browser client at `/fractional-pop-composer` specializes this pipeline for
pop composition from an exact fractional-ratio scale. It builds
degree-template chord vocabulary from the selected scale, uses the `pop`
profile, and maps generated tracks to Vital-oriented roles. The canonical
event timeline is sent unchanged to the MIDI and render endpoints. See
`fractional_pop_composer.md` for the page workflow and tuning guarantees.

The dedicated `/jpop-composer` client uses `POST /api/compose/jpop` for an
A-melody/B-melody/chorus form with section-specific exact-ratio rules. See
`jpop_composer.md` for its musical and Vital integration contract.

## POST /api/compose/jpop

```json
{
  "seed": 81301,
  "tempo_bpm": 118,
  "cycles": 2,
  "base_frequency": 220,
  "vocal_activity": 0.78,
  "chorus_shift_depth": 1
}
```

`cycles` is 1-3 and `chorus_shift_depth` is 1-2. The response contains
`metadata`, `sections`, bar-level `harmony`, canonical `events`, PI13-PI16
`profiles`, vocal metrics, quality counters, and a REAPER-oriented preset
manifest. Harmony entries include exact `root_ratio`, `tones`, the applied
rule, and a `(3,5,13)` `lattice_vector`. PI16 events also carry `lyric` and
`phrase_id` guide metadata. Send the returned events unchanged to
`POST /api/compose/vital-pack/midi` for pitch-bend MIDI export.

## POST /api/compose/kawaii-future-pop

```json
{
  "seed": 260801,
  "tempo_bpm": 154,
  "cycles": 1,
  "base_frequency": 220,
  "scale_ratios": ["1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3", "7/4"],
  "minimalism": 0.68,
  "drop_intensity": 0.86,
  "vocal_activity": 0.72,
  "phase_shift_steps": 1,
  "vocal_style": "hooky"
}
```

The scale requires 7-12 unique ratios after octave reduction and must include
`1/1`. `phase_shift_steps` is 0-3 quarter-beat subdivisions. `vocal_style`
accepts `hooky`, `airy`, or `chopped`. The response contains exact-ratio
`scale`, `sections`, bar-level `harmony`, canonical `events`, PI17-PI21
`profiles`, `minimal_process`, `sidechain_envelope`, vocal metadata, and
quality counters. The same event list can be sent to
`POST /api/compose/vital-pack/midi`.

## GET /api/arrange/profiles

Lists the built-in genre profiles (`pop`, `ambient`, `alternative_rock`,
`future_bass`) with tempo ranges, meters, form roles, preferred chord tags,
and part roles.

## POST /api/arrange/generate

```json
{
  "scale": { "scale_id": null, "ratios": ["1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "7/4", "15/8"], "base_frequency": 220 },
  "chord_vocabulary": [
    { "id": "tonic", "name": "Just major triad", "mode": "absolute",
      "tones": ["1/1", "5/4", "3/2"], "tags": ["stable"] },
    { "id": "color", "name": "Suspended color", "mode": "ratio_template",
      "tones": ["1/1", "4/3", "3/2", "7/4"], "allowed_root_degrees": [0, 3, 4],
      "tags": ["color", "suspended"] },
    { "id": "diatonic", "name": "Diatonic triad", "mode": "degree_template",
      "tones": [0, 2, 4], "allowed_root_degrees": [0, 1, 3, 4], "tags": ["stable"] }
  ],
  "genre_profile": "pop",
  "clock": { "tempo_bpm": null, "beats_per_bar": 4, "subdivisions_per_beat": 4, "bars": 16 },
  "form": null,
  "controls": { "energy": 0.5, "density": 0.5, "syncopation": 0.5,
    "harmonic_complexity": 0.5, "repetition": 0.5, "root_variety": 0.0,
    "section_contrast": 0.5,
    "humanization": 0.0, "melody_enabled": true, "drums_enabled": true },
  "harmony_performance": {
    "mode": "arpeggio", "allowed_modes": ["arpeggio"],
    "rate_subdivisions": 2,
    "arpeggio": { "order": "up_down", "octave_span": 1 }
  },
  "seed": 42
}
```

Chord modes: `absolute` (stored pitch classes), `degree_template` (integer
scale-degree offsets materialized over `allowed_root_degrees`), and
`ratio_template` (exact interval ratios multiplied by an allowed root).
`genre_profile` accepts a built-in id or an inline profile object
(`resolved_profile.profile` from a previous response can be edited and sent
back). `clock` fields left `null` fall back to profile defaults; a custom
`form.sections[]` must span exactly `clock.bars`.
`subdivisions_per_beat` must divide the canonical 480-tick beat.
`harmony_performance` is optional: profile defaults select `block`,
`arpeggio`, or `stride` per section when omitted. Explicit modes support
arpeggio order/rate and stride low-note, shell, and bass-conflict policies.

The response is canonical `ArrangementProject` 1.1: `schema_version`,
`metadata`, `source_scale`, materialized `chord_vocabulary` (with cents span,
complexity, tension), `requested_profile`, `resolved_profile` (profile plus
resolved macro controls), `seed`, `form` (sections with exact bar ranges and
energy curves), `harmony_progression` (chord instances, roots, durations,
transition metrics), `clock`, `tracks`, `events` (stable ids, exact `ratio`
or GM `drum_note`, ticks, velocity, articulation, section), `automation`
(energy curves and, for Future Bass drops, sidechain-pump intent),
`mix`, `render_settings`, and `decision_trace` (per-stage decisions including
relaxed profile preferences such as a missing `power` chord tag).
`harmony_gestures` records the resolved mode and settings for every chord
slot. Harmony events reference their gesture and identify `block`, `tone`,
`low`, or `chord` components.

Identical request + profile version + seed produce identical JSON. Validation
failures (unknown profile, empty vocabulary, meter outside the profile,
over-budget forms or event counts) return `422` with an actionable message.

## POST /api/arrange/midi

```json
{ "arrangement": { "...": "ArrangementProject returned by /generate" } }
```

Exports the project as a Standard MIDI File **type 1** (`audio/midi`
download): track 0 carries tempo, meter, and section markers; each
arrangement part becomes one named track. Pitched notes are retuned with
per-note pitch bend; channel allocation is global (channel 10 reserved for GM
percussion) and simultaneous notes needing different bends never share a
channel — over-budget arrangements return `422` instead of quantizing. The
exporter never regenerates the arrangement.

The returned project is validated again before export. Schema version, clock
consistency, contiguous form ranges, track/section references, event bounds,
ratios, drum notes, velocities, mix values, and render settings must remain
valid; malformed or edited projects return `422`.

## POST /api/arrange/render

Same request body as `/api/arrange/midi`. Renders a mono preview mixdown
(`audio/wav`, 22050 Hz) through per-role instrument presets (waveform +
envelope), using the same event ids and timing as MIDI/JSON. Drum parts are
approximated as short untuned blips; effect automation is not rendered yet.
Preview rendering is bounded to 4,000,000 samples (about 181 seconds at the
default 22050 Hz, including release tails). Longer projects return `422`
before synthesis; reduce bars or increase tempo.

## POST /api/arrange/migrate

```json
{ "arrangement": { "...": "ArrangementProject 1.0" } }
```

Migrates a 1.0 project to 1.1 without regenerating audible events. Existing
harmony events receive explicit block-gesture provenance. An already-current
project is returned unchanged.

## POST /api/arrange/phase-shift

```json
{
  "arrangement": { "...": "ArrangementProject 1.0 or 1.1" },
  "mode": "shared_chord_clock",
  "stream_a": {
    "id": "a",
    "rhythm": { "source": "euclidean", "cycle_steps": 16, "pulses": 4 }
  },
  "stream_b": {
    "id": "b",
    "rhythm": {
      "source": "euclidean", "cycle_steps": 15, "pulses": 5, "rotation": 2
    }
  },
  "phase_plan": {
    "process": "polymetric",
    "initial_offset_steps": 2,
    "convergence_points": [
      { "bar": 0, "chord_offset": 0, "protected": true },
      { "bar": 8, "chord_offset": 0, "protected": true }
    ]
  },
  "overlap_policy": {
    "resolution": "strict_full_chord",
    "maximum_active_tones": 12
  },
  "seed": 42
}
```

Compiles two measurably different exact-ratio harmony streams. Modes:
`shared_chord_clock` and `independent_chord_clock`. Processes: `static`,
`discrete`, `polymetric`, and `convergent`. The response is an
`ArrangementProject` 1.1 accepted directly by `/api/arrange/midi` and
`/api/arrange/render`, with `phase_shift` metadata containing stream
definitions, per-bar offsets, convergence results, overlap windows, rhythm
distinctness, density, and omission metrics. `fractional` is reserved for
HP5 and currently returns `422`.

---

# 6. Rhythm

## POST /api/rhythm/euclidean

```json
{ "steps": 13, "pulses": 5, "rotation": 2 }
```

Response: `{ "pattern": [1, 0, ...], "steps": 13, "pulses": 5 }`.

## POST /api/rhythm/state-graph

```json
{ "steps": 4 }
```

Binary rhythm state graph; edges connect patterns with Hamming distance
one. `steps` ≤ 12.

## POST /api/rhythm/phase-shift

```json
{ "patterns": [[1, 0, 0], [1, 0, 1, 0]], "length": 12, "phases": [0, 1] }
```

Expands independent cycles into one shared timeline.

## POST /api/rhythm/humanize

```json
{ "pattern": [1, 0, 1, 0], "seed": 42, "timing_amount_ms": 12, "velocity_amount": 10, "base_velocity": 100 }
```

Response: `hits[]` for active steps with `step`, `timing_offset_ms`,
`velocity`. Deterministic for a given seed.

## POST /api/rhythm/optimize-rotations

Choose each layer's rotation to maximize interlock (algorithm:
`algorithm_rhythm.md`). Layers with `rotation: null` are optimized in
placement order against already-placed layers; the kick normally stays
fixed.

```json
{
  "layers": [
    { "name": "kick", "steps": 16, "pulses": 5, "rotation": 0 },
    { "name": "snare", "steps": 16, "pulses": 3, "rotation": null },
    { "name": "hat", "steps": 13, "pulses": 8, "rotation": null },
    { "name": "perc", "steps": 17, "pulses": 6, "rotation": null }
  ],
  "max_analysis_steps": 512
}
```

Response: `analysis_length` plus per-layer `pattern`, `rotation`,
`score`, and a score `breakdown` (anchor, complement, collision,
density, cluster, similarity, syncopation).

## POST /api/rhythm/analyze

```json
{ "layers": [{ "name": "kick", "pattern": [1, 0, 0, 0] }], "max_analysis_steps": 512 }
```

Projects patterns onto the shared LCM grid (bounded) and returns
per-layer and combined density, pairwise collision counts, four-layer
collision count, pairwise Hamming similarity, average inter-onset
interval, syncopation score, and cluster count.

## POST /api/drums/generate

One-shot coordinated drum generation: Euclidean base patterns, rotation
optimization, accent velocities, and per-bar phase offsets.

```json
{
  "layers": [
    { "name": "kick", "steps": 16, "pulses": 5, "rotation": 0, "phase_increment": 0 },
    { "name": "snare", "steps": 16, "pulses": 3, "rotation": null, "phase_increment": 1, "phase_update_bars": 4 }
  ],
  "bars": 8,
  "seed": 42,
  "optimize": true
}
```

Response: per-layer `pattern`, `rotation`, `velocities`,
`phase_offsets` (per bar), plus `metrics` (the analysis output).
Identical seeds produce identical results.

---

# 7. Audio Rendering

## POST /api/render/wav

Synchronous render; returns the WAV file directly (`audio/wav`).

```json
{
  "events": [{ "ratio": "3/2", "start_seconds": 0, "duration_seconds": 1, "velocity": 100 }],
  "base_frequency": 220,
  "waveform": "sine",
  "attack_seconds": 0.02,
  "decay_seconds": 0.14,
  "sustain_level": 0.65,
  "release_seconds": 0.28,
  "sample_rate": 22050,
  "delay_seconds": 0,
  "reverb_amount": 0
}
```

- `waveform`: `"sine"` | `"saw"` | `"square"` | `"triangle"` | `"additive"`

## POST /api/render/jobs

Async render. Same body as `/api/render/wav`; returns `202`:

```json
{ "job_id": "f8d7ec1c-…", "status": "queued" }
```

## GET /api/render/jobs/{job_id}

```json
{ "job_id": "…", "status": "queued|running|completed|failed" }
```

## GET /api/render/jobs/{job_id}/audio

Returns the finished WAV (`audio/wav`); `409` while the job is not
completed, `404` for unknown jobs.

---

# 8. Minimal Functional Harmony Composer

## POST /api/minimal-functional/generate

Builds a deterministic T/S/D minimal-process composition. The response is a
self-contained composition payload with exact-ratio events, function chords,
voice cycle metadata, and per-bar process analysis.

```json
{
  "duration_bars": 32,
  "tempo_bpm": 112,
  "voice_count": 5,
  "seed": 12345,
  "tuning": "5-limit",
  "climax_start": 0.62,
  "resolution_start": 0.78
}
```

- `duration_bars`: 8 to 128; default 32
- `voice_count`: 3 to 8; default 5
- `tuning`: `12-tet`, `5-limit`, or `7-limit`
- `climax_start` must precede `resolution_start`

Use the returned `events` directly with `POST /api/export/midi` for a
pitch-bend microtonal MIDI file. The dedicated browser page also provides the
same export flow.

`prime_progression` accepts the `progression` array exported by Prime-Limit
Harmonic Explorer. Assign its chord IDs with `function_chord_ids`, for example
`{"T":["chord-21","chord-24"],"S":["chord-22"],"D":["chord-23"]}`. The generated payload
also includes `drum_events` for kick, snare, hat, and percussion.

## POST /api/minimal-functional/midi

Exports a type-1 MIDI file containing a microtonally retuned Harmony track
and a GM percussion track. Send generated `events` as `notes` and generated
`drum_events` as `drums`.

---

# 9. Vital Pack Composer

## GET /api/instruments/vital-pack

Returns PI01–PI12 plus the downloadable `PI22` Fractional Piano role, with filenames,
ranges, polyphony, and declared tuning policies. PI09–PI12 are Vital-based
kick, snare, closed hat, and percussion profiles with fixed trigger notes 36,
38, 42, and 39 and `fixed_drum_note` tuning policy.

## POST /api/compose/vital-pack

Generates a seeded role-aware Vital Pack song plan.

```json
{"seed":72801,"tempo_bpm":150,"length_bars":64,"tuning":"7-limit","preset_mode":"adaptive","tonal_character":"major","mode_strength":0.85,"progression_contrast":0.7,"piano_run_enabled":true,"piano_part_mode":"scale_run","piano_run_activity":0.5,"piano_run_density":0.65}
```

The response includes `sections`, exact-ratio `harmony`, instrument `events`,
`tuning_timeline`, `mts_timeline` (a JSON retuning timeline with absolute
frequencies), a `.scl`-compatible `base_scale`, `sidechain_envelope`, semantic
`automation`, quality measurements, and a `reaper_manifest`.

`tonal_character` is `major`, `minor`, or `mixed`. `mode_strength` (0–1)
controls how consistently bars retain their section's requested mode instead
of borrowing the opposite-mode colour. `progression_contrast` (0–1) moves
from tonic-heavy primary chords toward more PD/D motion, substitute degrees,
root changes, and seventh colour. Section endings enforce D→I/i cadential
motion.

Ordinary Vital plans use pure-ratio major and minor palettes including
I/vi/iii/IV/ii/V/V7 and i/bIII/bVI/iv/ii-dim/V/v/bVII. Harmony events expose
`tonal_character`, `section_tonal_target`, and `degree`. Quality output
reports major/minor ratios, mode clarity, unique chords, functional
transitions, and `harmony_variety_score`.

`piano_run_enabled` adds an independent PI22 Fractional Piano track.
`piano_part_mode` is `scale_run` for ordinary song plans. The `motif` mode is
available when Development Tree material is supplied to the motif endpoint.
`piano_run_activity` (0–1) controls the probability of a run entering in each
bar, while `piano_run_density` (0–1) moves from sparse quarter-note motion to
denser eighth/sixteenth-note motion. Runs select seeded ascending, descending,
turnaround, or zigzag contours and resolve to the harmonic root at cadences.

## POST /api/compose/motif-vital-pack

Arranges Development Tree nodes through the Vital Pack form and profiles. The
request uses the normal Vital Pack options plus an anchor chord and selected
Tree nodes. Each node provides its target chord, notes, formal role, and
optional transformation/identity metadata.

```json
{
  "seed": 72801,
  "length_bars": 64,
  "section_count": 9,
  "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
  "prime_basis": [3, 5, 7],
  "tonal_character": "minor",
  "mode_strength": 0.9,
  "progression_contrast": 0.75,
  "development_amount": 0.7,
  "motif_activity": 0.68,
  "motif_rest_style": "breathing",
  "phase_shift_mode": "progressive",
  "phase_shift_beats": 0.5,
  "phase_shift_increment": 0.125,
  "phase_shift_cycle_bars": 4,
  "nodes": [{
    "id": "motif-section-0",
    "source_motif_id": "motif-72801",
    "formal_role": "theme",
    "target_chord": ["1/1", "5/4", "3/2"],
    "notes": [
      {"ratio":"1/1","harmony_tones":["5/4","3/2"],"onset_beat":0,"duration_beats":0.5,"velocity":104},
      {"ratio":"5/4","onset_beat":0.5,"duration_beats":0.5,"velocity":92}
    ]
  }]
}
```

The response is a normal Vital Pack plan with `metadata.composition_source`
set to `motif-development-tree`, plus `motif_arrangement`. Pitched and drum
events retain their Development Tree provenance and can be exported using the
standard Vital Pack MIDI endpoint.

`motif_arrangement.motif_scale` contains the octave-normalized scale extracted
from the selected Development Tree nodes. Every returned harmony chord and
pitched accompaniment event uses this scale. Harmony events also expose the
motif tones selected for that bar, retained common tones, and motif-tone
coverage. `base_scale` mirrors the motif scale for Scala export.

`section_count` may be 3–12 and cannot exceed `length_bars`.
`development_amount` controls repetition-level cyclic rotation, chord
transposition, retrograde, chord projection, and rhythmic displacement.
`motif_activity` (0.2–1.0) controls how often PI04/PI07 motif lanes enter.
`motif_rest_style` may be `breathing`, `sparse`, or `driving`; every style
inserts structured lane rests, limits a lane to three consecutive active
bars, and reserves periodic full motif-breath bars. The complete decisions
are returned in `motif_arrangement.activity.schedule`, with active ratios,
full-rest count, and matching quality measurements.
`prime_basis` is retained from Motif Development and written into both
`metadata` and `motif_arrangement`; the motif-derived scale, chords, PI04/PI07
stacks, and other pitched events remain inside that basis.
For motif-derived scales, tonal character does not inject ratios outside the
scale. Instead it ranks available chord tones by proximity to the pure major
third (386.31 cents) or minor third (315.64 cents). Contrast expands the
root-candidate range and reduces common-tone locking. Harmony events expose
the target and realized modal-third error.
`phase_shift_mode` may be `off`, `static`, `progressive`, or `polymetric`.
Phase-enabled responses include A/B lane metadata, a per-bar phase schedule,
and overlap measurements.

The same piano controls apply to Development Tree arrangements.
`piano_part_mode: "scale_run"` traverses exact `Fraction` ratios from
`motif_arrangement.motif_scale`; octave placement may change, but its
octave-normalized pitch class never leaves that set.
`piano_part_mode: "motif"` renders the assigned node's developed motif,
including its rests and simultaneous `harmony_tones`, on the PI22 track.
Both modes leave full motif-breath bars silent and retain motif provenance.
Quality output separates `piano_scale_run_notes` and `piano_motif_notes` and
reports `piano_run_scale_conformance`.

## POST /api/compose/vital-pack/section

Regenerates one numbered form section with a deterministic seed offset. Send
the normal Vital Pack request plus `section_index` (0 through 11) and a scope
of `harmony`, `rhythm`, `voicing`, or `instruments`. The returned section
window includes its matching harmony, events, tuning/MTS events, automation,
and sidechain envelope so a client can replace that window in its plan.

```json
{"seed":72801,"length_bars":64,"section_count":9,"section_index":3,"scope":"harmony"}
```

`section_index` must be lower than the requested `section_count`.

## POST /api/compose/vital-pack/midi

Converts Vital Pack `events` into a type-1 MIDI arrangement: PI01–PI12 and
`PI22` retain their own tracks, pitch events receive per-note pitch bend, and
PI09–PI12 drum events retain their fixed trigger notes. Legacy `DRUMS` events
remain accepted for imported projects.

---

# 10. Motif Development Engine

The Motif Development Engine is an experimental configurable-prime
thematic-development API. It accepts inline anchor chords and motifs; project
persistence and Prime Explorer/Lattice transfer are planned follow-up work.

## POST /api/motif/generate

Generates a deterministic four- to eight-note motif from a three- or four-tone
anchor chord. The response retains per-note monzo, pitch-circle position,
register, chord relation, interval/rhythm/contour signatures, identity
features, and chord affinity.

```json
{
  "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
  "prime_basis": [3, 5, 7],
  "note_count": 6,
  "max_polyphony": 3,
  "length_beats": 2,
  "register": [60, 84],
  "max_lattice_radius": 2,
  "circle_profile": "mostly_stepwise",
  "rhythm_profile": "random_exploration",
  "rest_density": 0.18,
  "beam_width": 32,
  "candidate_count": 16,
  "evaluation_profile": "balanced",
  "terminal_policy": "root",
  "seed": 72801
}
```

`rhythm_profile` may be `even`, `kawaii_syncopated`, or
`random_exploration`. The latter allocates each note duration on a sixteenth
note grid using the supplied seed. `rest_density` (0–0.7, default 0.18)
shortens the sounding gate inside those rhythmic cells. The response exposes
the resulting gaps in both top-level `rests` and
`rhythm_signature.rests`, plus a normalized
`rhythm_signature.rest_ratio`. A value of zero restores fully connected note
cells.

`prime_basis` contains one to five unique odd primes. Prime 2 is implicit and
is used only for octave/register placement. The default is `[3,5,7]`; a basis
such as `[3,7,13]` restricts exploration to
`3^a * 7^b * 13^c`. Anchor, harmony, motif, and companion-tone ratios may use
only 2 and the selected primes. `max_lattice_radius` bounds the L1 norm of the
exponent delta, so radius 2 accepts `(2,0,0)` and `(1,-1,0)` but not
`(2,2,0)`. Each generated note exposes `exponent_delta`; the response records
both `prime_basis` and the serialized `monzo_basis: [2, ...prime_basis]`.
When the workbench detects that the existing Development harmony contains an
excluded prime after a basis change, it rebuilds four compatible chords from
the current Anchor and generated motif tones before calling
`/api/motif/develop`. Direct API calls remain strict and return 422 for
basis-incompatible harmony.

`max_polyphony` may be 1–4. One preserves a monophonic motif. Higher values
allow each motif step to add consonance-ranked companion pitches while never
exceeding the requested simultaneous voice count. The main contour pitch
remains in `note.ratio`; companion voices are stored in
`note.harmony_tones`. `polyphony_signature` reports per-step voice counts,
mean polyphony, and the realized maximum. Browser audition, Development Tree
events, JSON, microtonal MIDI, and Vital Pack transfer all render the complete
stack.

The endpoint explores `candidate_count` adjacent deterministic seeds (1-32),
applies hard filters, and returns the best result at the top level plus a
ranked `candidates` list and `exploration` summary. Each candidate has an
`evaluation` object with Harmony, Melody, Rhythm, Identity, Novelty, and
Complexity components, total score, filter decision, rejection reasons, and
diagnostics. `evaluation_profile` may be `balanced`, `consonant`, `lyrical`,
`rhythmic`, or `colourful`.

`terminal_policy` controls the final note. Anchor chord input order is
`root`, `third`, `fifth`, then optional `colour`: `root` selects root,
`stable` selects root/fifth, `colour` selects third/colour,
`nearest_anchor` minimizes the final leap, `weighted` samples roles with a
root-weighted distribution, `random` samples any anchor tone, and `free`
does not force an anchor-tone ending. The response records the selected
`identity_features.terminal_role`.

## POST /api/motif/compare

Compares two inline motifs without merging monzo, pitch-circle, register,
contour, rhythm, and chord-affinity dimensions. It returns a component
`distance_vector`, positional alignment, and `identity_retention`.

## POST /api/motif/variation

Transforms an inline source motif for a target chord. Supported initial
operations are `lattice_transpose`, `neighbour_substitution`,
`retrograde_pitch`, `rhythmic_diminution`, and `chord_tone_projection`.

## POST /api/motif/develop

Builds a deterministic section sequence and motif tree. Supply the source
motif, anchor chord, a sequence of three- or four-tone harmony chords, and
optional section roles. The response provides tree nodes/edges and flattened
MIDI-ready `events` with `ratio`, `start_beats`, `duration_beats`, and
`velocity`.

---

# 11. Export

## POST /api/export/midi

Pitched notes as a standard MIDI type-0 file (`audio/midi`).

```json
{
  "notes": [{ "ratio": "3/2", "start_beats": 0, "duration_beats": 1, "velocity": 100 }],
  "base_frequency": 220,
  "ticks_per_beat": 480,
  "pitch_bend": false,
  "pitch_bend_range_semitones": 2
}
```

By default ratios are quantized to the nearest 12-TET note number. With
`pitch_bend: true`, each note is placed on its own channel (skipping 10)
with a 14-bit pitch-bend event, so the exported pitches are microtonally
exact.

## POST /api/export/rhythm/midi

Binary rhythm pattern as GM percussion on channel 10 (`audio/midi`).

```json
{
  "pattern": [1, 0, 1, 0],
  "note": 36,
  "velocity": 100,
  "velocities": [100, 0, 60, 0],
  "steps_per_beat": 4,
  "cycles": 1,
  "ticks_per_beat": 480
}
```

- `note`: GM percussion note number (36 = kick, 38 = snare, 42 = closed hat)
- `velocities`: optional per-step velocities; `0` falls back to `velocity`
  (use `0` for inactive steps)
- `cycles`: repeat the pattern N times

Multi-layer mode exports several drum layers in one file (each on its
own GM note):

```json
{
  "layers": [
    { "pattern": [1, 0, 0, 0], "note": 36 },
    { "pattern": [0, 0, 1, 0], "note": 38, "velocities": [0, 0, 96, 0] }
  ],
  "cycles": 4,
  "steps_per_beat": 4
}
```

## POST /api/export/scala

```json
{ "name": "Pure Intonation Scale", "ratios": ["1/1", "9/8", "5/4"] }
```

Returns a `.scl` Scala tuning file (`text/plain`).

## POST /api/export/json

```json
{ "name": "Pure Intonation Composition", "composition": { "…": "any structured payload" } }
```

Echoes the payload back as structured JSON for saving.

---

# 12. Real-Time Transport

## WebSocket /api/ws/transport

Send JSON commands:

```json
{ "command": "play" }
{ "command": "pause" }
{ "command": "stop" }
{ "command": "improvise", "seed": 42 }
```

Responses:

```json
{ "type": "transport", "state": "playing" }
{ "type": "improvise", "state": "playing", "seed": 42 }
{ "type": "error", "message": "unknown transport command" }
```

---

# 13. Instrument-Constrained Composition Explorer

## GET /api/composition-explorer/profiles

Returns the PI01-PI22 semantic profiles, default palettes for each supported
style, style labels, and default evaluation weights.

## POST /api/composition-explorer/explore

Generates, evaluates, and clusters 4-64 reproducible song candidates. The
default request generates 32 candidates and six representatives.

```json
{
  "style": "mixed",
  "style_mix": {
    "fractional_pop": 0.25,
    "fractional_jpop": 0.25,
    "kawaii_fractional_future_pop": 0.5
  },
  "seed": 42810,
  "candidate_count": 32,
  "cluster_count": 6,
  "tempo_bpm": 150,
  "length_bars": 64,
  "base_frequency": 220,
  "scale_ratios": ["1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3", "7/4"],
  "instrument_palette": [],
  "missing_role_policy": "warn",
  "form_temperature": 0.55,
  "harmony_temperature": 0.65,
  "part_temperature": 0.5,
  "rhythm_temperature": 0.6,
  "locked_components": ["melody"],
  "evaluation_weights": {"harmonic_interest": 1.2}
}
```

`style` accepts `fractional_pop`, `fractional_jpop`,
`kawaii_fractional_future_pop`, or `mixed`. Mixed-style weights range from
zero to one, must contain at least one positive value, and are normalized by
the server. `length_bars` must be divisible by four.
`scale_ratios` accepts 5-24 unique octave-normalized ratios. Empty
`instrument_palette` uses the selected style's default palette.

Style progression targets are interpreted as 12-TET semitone offsets. For
example, target `5` means `2^(5/12)` (500 cents), independently of the number
of supplied scale tones. The generator selects and reports the nearest scale
degree; harmony entries expose `style_target_semitones_12tet`,
`style_target_ratio`, and `style_target_degree` for inspection.

The response contains candidate summaries, k-medoids cluster membership, and
full representative plans. Each representative contains the CompositionGenome,
form, exact-ratio harmony, section instrument assignments, score events,
feature vector, and evaluation scores.

The browser sends the selected representative's unchanged `events`, tempo,
and base frequency to `POST /api/compose/vital-pack/midi`. The resulting
standard MIDI type-1 file preserves PI instrument tracks, drum notes, and
per-note pitch bends for exact fractional ratios.

# 14. Bohlen-Pierce Pure Intonation

`POST /api/bp/scales/generate` creates exact-ratio tritave scales from core,
bounded-lattice, generator-chain, odd-harmonic, 13-EDT, or manual input.
Manual strings accept fractions and products such as `3^-1*5^2`.

`POST /api/bp/chords/search` evaluates constrained 2-6 voice combinations.
`POST /api/bp/progressions/search` selects 4-16 chords against a supplied
tension curve. `POST /api/bp/compose/generate` produces Harmony, Bass, Melody,
Rhythm, and optional Drone events.

`POST /api/bp/export/midi`, `POST /api/bp/render/audio`, and
`POST /api/bp/export/scala` return MPE-style MIDI, WAV, and tritave Scala data.

# 15. Mixed Meter Drum Section

`GET /api/rhythm/mixed-meter/patterns` returns the pattern library, density
profiles, and default track settings. `POST /api/rhythm/mixed-meter/validate`
checks meter/grouping arithmetic and optional unaligned cycles.

`POST /api/rhythm/mixed-meter/generate` accepts form, pattern, section,
density, track, humanization, and seed controls and returns bars, phase,
events, density diagnostics, and a Compose-compatible timeline.

`POST /api/rhythm/mixed-meter/export/midi` returns type-1 percussion MIDI with
section markers and per-bar time signatures. `POST
/api/rhythm/mixed-meter/preview` returns a rendered WAV preview.

# 16. Roadmap Candidates

These capabilities are not part of the current API:

- `/api/v1` route versioning
- Authentication for remote multi-user deployment
- Instrument presets and project persistence
- Transfer of explorer representatives into dedicated composer pages
- Server-Sent Events (`/events`)
- WebMIDI/MPE/MTS and OSC integration

Scala import is implemented at `POST /api/scales/import`. See
[status.md](status.md) for the prioritized gaps.
