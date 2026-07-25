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

# 8. Export

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

# 9. Real-Time Transport

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

# 10. Planned (Not Yet Implemented)

From the original specification, still open:

- `/api/v1` route versioning
- Authentication (JWT/OAuth)
- Instrument presets and project persistence
- Form generator, full `/compose` one-shot endpoint
- Server-Sent Events (`/events`)
- Scala file import
