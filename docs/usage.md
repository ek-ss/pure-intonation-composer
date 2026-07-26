# Usage Guide

**Project:** Pure Intonation Composer

Version: 0.1

This guide covers every implemented function: the browser workbench
(panel by panel) and the HTTP/WebSocket API. For exact request/response
schemas see [api.md](api.md); for copy-paste commands see
[examples.md](examples.md). Current limitations and remaining work are tracked
in [status.md](status.md).

---

# 1. Getting Started

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

* Workbench: `http://127.0.0.1:8000`
* Interactive API docs (Swagger): `http://127.0.0.1:8000/docs`
* Health check: `GET /health`

Everything stochastic accepts a seed; the same inputs always produce the
same output.

---

# 2. Workbench

The workbench is a single page organized in panels. All sound plays
locally in the browser via WebAudio; all generation runs on the server.

## 2.1 Generator panel

Creates a scale (a set of rational pitch classes) and displays it on
the pitch circle.

1. Choose a generator:
   * **Combination Product Set** — CPS(n,k) over your factors. Choose
     harmonic or subharmonic is fixed to harmonic in the UI; subharmonic
     CPS is available via the API (`kind`).
   * **Euler–Fokker genus** — all products of the given prime factors.
   * **Harmonic series** — the first N harmonics.
   * **Subharmonic series** — the first N subharmonics.
2. Enter **factors** (comma-separated positive integers, e.g.
   `1, 3, 5, 7`) or a **count** for the series generators.
3. For CPS, set **組合せの数** (k, the combination size).
4. **1オクターブ内に正規化** folds every ratio into one octave.
5. Press **音階を生成** (generate).

### Snapping

Below the generate button, the snap row rewrites all current notes:

* **EDO** — snap each note to the nearest step of N equal divisions of
  the octave (N = 2–31).
* **Prime limit** — snap each note to the closest ratio built from
  primes up to the given limit (e.g. 5-limit, 7-limit).

API: `POST /api/tuning/snap`.

## 2.2 Pitch circle (radial graph)

Each dot is a scale note, placed by cent value around the circle.

* **Click a dot** (or a table row, or keys `A S D F …`) to sound it.
* While notes are held, lines to the focus note are colored by harmonic
  strength (legend below the circle).
* Hold **exactly two notes** to display their relative interval ratio on
  the connecting line.
* **倍音 (harmonics)** toggle overlays dashed guide rays for the odd
  harmonics 3, 5, 7, … up to the chosen count (5–64), labelled with
  their octave-reduced ratios.

## 2.3 Graph view

With a CPS scale, the **Graph** button switches the circle to the
Johnson graph J(n,k): nodes are factor combinations, edges connect
combinations differing by one factor.

Two layouts are available:

* **force-directed** — physics-style layout, computed deterministically
  in the browser.
* **layered grid** (`reference_layered_grid`, see
  [visualization.md](visualization.md)) — layers nodes by how many
  factors they share with the reference node (`Shared N · Distance M`
  labels on the left). **Double-click a node** to make it the new
  reference; layers reorganize around it. Sort within layers by
  lexicographic order, factor product, or pitch.

Both layouts:

* Single-click a node to play its pitch.
* The **Walk** controls traverse the graph from node 1:
  * `random walk` — uniform random neighbor, seeded;
  * `weighted walk` — neighbor choice weighted by harmonic/monzo/cent
    closeness, seeded;
  * `shortest path` — to the chosen target node.
* The walk is drawn as a highlighted path with step numbers (`#1 #2 …`).
* The label selector switches node ratio labels between **harmonic**
  and **subharmonic** readings of each combination.

API: `POST /api/harmonic-graph` (`operation`, `layout`, `reference`,
`sort_mode`).

## 2.4 Sound panel

Performance controls applied to live playing and WAV rendering:

* **基音** — base frequency (110–440 Hz) that `1/1` maps to.
* **波形** — sine, triangle, sawtooth, square.
* **ADSR** sliders — attack, decay, sustain, release.
* **Stop all** — release every sounding note.
* The on-screen keyboard mirrors the first 16 scale notes (PC keys
  `A S D F G H J K L ; Q W E R T Y`).

## 2.5 Intervals panel (scale editor)

A table of all notes: key binding, ratio, cents, monzo (prime
exponents).

* **Play** sounds a note; **×** removes it from the scale.
* The input above the table adds a note in any of these forms:
  * ratio — `5/4`
  * cents — `748.2`
  * EDO degree — `5\12` (5 steps of 12-EDO)
  * decimal ratio — `1.33`
  * math expression — `=2^(6/12)`
* New notes are inserted in pitch order. Press Enter to add.

API: `POST /api/analyze-interval`. Single-ratio analysis:
`POST /api/analyze-ratio`.

## 2.6 Scales panel (browser)

Named scale storage (in-memory on the server; cleared on restart).

* **現在の音階を保存** — save the current scale under the given name
  (saving again overwrites).
* **Load** — replace the current scale with a saved one.
* **×** — delete a saved scale.
* **Scala をインポート** — load a `.scl` file from disk; it is parsed,
  saved under its filename, and adopted as the current scale.
* **Scala を保存** (in the Intervals panel) — download the current
  scale as a `.scl` file.

API: `GET/POST /api/scales`, `GET/DELETE /api/scales/{name}`,
`POST /api/scales/import`, `POST /api/export/scala`.

## 2.7 Compose panel

Builds a full texture from a CPS harmonic graph.

1. Set factors, combination size, **length**, **seed**, and distance
   **metric**, then press **和声進行を生成** (generate progression).
   Chords appear as chips with transition scores; click a chip to hear
   its tones (root × each factor, octave-reduced).
2. **ベース生成** — bass line under the progression. Strategies:
   `mirror` (subharmonic mirror), `root`, `fifth`, `hybrid`.
3. **旋律生成** — independent melody voices above the chords. Set voice
   count and contour (`arch`, `ascending`, `descending`, `free`).
4. **▶ 再生 / 停止** — play or stop chords + bass + melody in the
   browser at the chosen tempo.

**Rhythm Orchestration**

* `Rhythm layers` maps the current kick/snare/hat/perc patterns to ordered
  chord tones or to Harmony/Bass/Melody roles. Presets cover `Chord tones`,
  `Roles`, and `Hybrid`; every row can change target, assignment policy,
  overflow, gate, velocity, octave, articulation, and collision handling.
  On/Solo checkboxes control which source tracks compile.
* `Generate` gives Harmony, Bass, and Melody independent Strategy, Profile,
  Density, and Syncopation controls. Each row can use transition-aware
  harmonic rhythm, seeded Semi-Markov generation, interlocking onset
  allocation, or experimental ratio-derived cycles. The Melody row applies
  to every generated melody voice; bars and seed remain shared.
* **Apply rhythm / Generate rhythm** compiles an integer-tick event timeline.
  Playback and all exports use those exact events. **Clear rhythm** restores
  the original fixed two-beat-per-chord behavior.
* Composition Roll switches to proportional musical time, draws attack and
  sustain blocks, and shows the source-pattern lanes below the pitched events.

Exports:

* **MIDI** — download the composition as a MIDI file. Check
  **ピッチベンドで正確な音程** to place each note on its own channel
  with an exact pitch bend (microtonally correct; unchecked quantizes
  to nearest 12-TET semitone).
* **JSON** — download the composition structure.
* **WAV レンダリング** — offline-render on the server via an async job;
  the finished audio appears in a player under the button. The render
  uses the Sound panel's waveform and ADSR plus a touch of reverb.

API: `POST /api/compose/harmony`, `/api/compose/bass`,
`/api/compose/melody`, `/api/compose/voice-leading`,
`/api/compose/rhythm/apply`, `/api/compose/rhythm/generate`, `/api/export/midi`
(`pitch_bend`), `/api/export/json`, `POST /api/render/jobs` +
`GET /api/render/jobs/{id}` + `GET /api/render/jobs/{id}/audio`.

## 2.8 Rhythm panel (drum sequencer)

A coordinated four-layer drum sequencer (kick, snare, hat, perc),
implementing `algorithm_rhythm.md`:

* Each row has its own **steps** and **pulses** (Euclidean base
  pattern); unequal cycle lengths are supported. Click a cell to toggle
  a hit manually.
* **ドラムを生成** — sends the layers to the server, which optimizes
  each non-kick layer's rotation for interlock (collision, complement,
  density, cluster, similarity, syncopation scoring), assigns accent
  velocities, and computes per-bar phase offsets (snare/hat/perc drift
  over bars; kick stays anchored). The `rot N` badge shows the chosen
  rotation.
* Cells outlined in red **clash** — two or more layers hit together on
  the shared analysis grid. Cell opacity shows accent velocity.
* **▶ 再生 / 停止** — loop playback with per-layer timbres (kick,
  snare, hat, perc sound distinct) and a moving playhead; phase offsets
  are applied per bar as the loop progresses.
* **MIDI** — one GM-percussion file (channel 10) with each layer on its
  note (36/38/42/46), phase-expanded across all bars with velocities.
* **JSON** — the full rhythm configuration and generated state.
* The metrics line reports combined density, total collisions,
  all-four collisions, and syncopation.

API: `POST /api/drums/generate`, `/api/rhythm/optimize-rotations`,
`/api/rhythm/analyze`, `/api/rhythm/euclidean`, `/api/rhythm/humanize`,
`/api/rhythm/phase-shift`, `/api/rhythm/state-graph`,
`/api/export/rhythm/midi` (single-pattern or multi-layer mode).

## 2.9 Timeline (recorder)

* **Record** — start/stop recording; every note you play (keyboard,
  circle, graph) is captured with its real timestamp.
* Events are placed on the timeline by actual time with a seconds axis.
* **▶** — replay the recording with original timing.
* **Clear** — discard the recording.

## 2.10 Transport WebSocket

`ws://127.0.0.1:8000/api/ws/transport` accepts JSON commands
`play`, `pause`, `stop`, and `improvise` (with `seed`), and replies
with transport state messages. See [examples.md](examples.md).

## 2.11 Lattice Lab (Experimental)

An exponent-lattice harmony laboratory alongside CPS (G9 in
`development_plan.md`). A basis of integer generators `(a, b, …)` maps
exponent vectors to exact ratios `aⁿ¹ · bⁿ² · …`.

* **格子を生成** — enumerate the lattice over per-generator exponent
  ranges (min/max lists, one value per generator). The canvas shows a
  2-axis projection (choose the axes); points are colored by collision
  group — distinct vectors that sound the same pitch share a color.
  Click a point to hear it. The table lists vector, raw ratio,
  octave-normalized ratio, octave shift, cents, and group. `merge`
  collapses duplicates.
* **和音を生成** — create a seeded chord of the requested size from the
  allowed-step vocabulary. The generator avoids duplicate sounding pitch
  classes and writes its independent root-relative offsets back to the chord
  vector editor for further editing.
* **ハーモニーを再構成** — build a harmony from a root ratio plus
  ordered chord vectors (one root-relative tone per line). Each arrow starts
  at the root, which is ringed. The root itself is included implicitly.
* **Compose に送る** — adopt the reconstructed tones as one Compose chord,
  preserving its lattice vectors in JSON while making the complete tone
  stack available to bass/melody generation, playback, MIDI, and WAV.
* **和声進行を生成** — accumulate the progression difference vectors into
  a root path, then apply the unchanged root-relative chord vectors at every
  root. The progression can be auditioned or sent to Compose as a complete
  chord sequence.
* **ウォーク** — seeded random walk through the lattice using an
  allowed-step vocabulary (one vector per line) and a boundary policy
  (`reflect`, `stop`, `wrap`, `resample`) against the min/max domain.
  **和声ウォーク再生** treats every walk point as a moving root and
  simultaneously sounds the same root-relative chord at every root.
  **Compose に送る** converts the complete walk to a progression with one
  simultaneous chord per walk point.
* **Lattice Keyboard** — after generating or reconstructing a chord, its first
  tones are assigned to `A S D F ...`. When the Lattice Lab panel has focus,
  key-down starts the tone and key-up releases it; the on-screen keys provide
  the same interaction.
* Warnings appear for octave-only generator `2` and multiplicatively
  dependent bases (e.g. `3, 9`).

API: `POST /api/exponent-lattice/scale`, `/harmony`, `/chord`,
`/progression`, `/walk`, `/analyze`.

---

## 2.12 Arrange panel (Experimental)

Genre-guided arrangement: a scale plus a small exact-ratio chord vocabulary
becomes a complete section-aware arrangement (form, harmony, drums, bass,
comping, melody) on one canonical timeline.

* **ジャンルプロファイル** — built-in profiles: Pop, Ambient, Alternative
  Rock, Future Bass. Profiles are inspectable parameter bundles (tempo range,
  meters, form, harmony weights, parts), not fixed templates.
* **小節数 / 拍子 / テンポ** — blank fields fall back to profile defaults;
  the tempo is clamped into the profile range with a note in the trace.
* **Macro sliders** — Energy, Density, Syncopation, Harmonic complexity,
  Repetition, Section contrast, Humanization, plus Melody/Drums toggles. Each
  macro reshapes explicit profile parameters; the resolved values are stored
  in the project's `resolved_profile.resolved_controls`.
* **スケール** — comma-separated ratios; **現在のスケールを使う** copies the
  scale currently generated in the workbench.
* **和音ボキャブラリー（JSON）** — a list of basic chords. Modes:
  `absolute` (fixed pitch classes), `degree_template` (integer degree offsets
  moved over `allowed_root_degrees`), `ratio_template` (interval ratios × an
  allowed root). Tags like `stable`, `power`, `color` guide the profile; they
  never alter the stored ratios.
* **アレンジを生成** compiles the arrangement. The form lane shows sections
  with their energy curves, chord slots, and event density; the part list
  shows instrument, register, and event count per track; the progression
  table lists every chord slot (click a row to audition the chord). The trace
  line reports per-stage decisions, including profile preferences that had to
  be relaxed (e.g. no `power`-tagged chord for the rock profile).
* **▶ 再生 / 停止** — browser playback of the canonical events (pitched
  tracks through the workbench synth, GM drum notes as short blips).
* **MIDI / JSON / Render WAV** — type-1 multitrack microtonal MIDI with
  section markers (global pitch-bend channel allocation; over-budget
  arrangements return an actionable error instead of quantizing), the
  lossless canonical project JSON, and a preview WAV mixdown through
  per-role instrument presets. All three share the same event ids and timing.
  MIDI/WAV export validates the returned project again, so malformed events
  and out-of-range timing return `422`. WAV previews are limited to 4,000,000
  samples (about 181 seconds at 22050 Hz); longer arrangements remain
  available as JSON/MIDI and can be shortened or rendered at a faster tempo.

The same inputs, profile version, and seed reproduce the same arrangement.

API: `GET /api/arrange/profiles`, `POST /api/arrange/generate`,
`/api/arrange/midi`, `/api/arrange/render`.

---

# 3. API Overview

Base URL `http://127.0.0.1:8000`; all bodies JSON; errors are
`{"detail": "…"}` with status 422 for invalid musical input.

| Group | Endpoints |
| --- | --- |
| Scales (generators) | `POST /api/cps`, `/api/euler-fokker`, `/api/harmonic-series`, `/api/subharmonic-series` |
| Analysis | `POST /api/analyze-ratio`, `/api/analyze-interval`, `/api/tuning/snap` |
| Scale store | `GET/POST /api/scales`, `GET/DELETE /api/scales/{name}`, `POST /api/scales/import` |
| Graph | `POST /api/harmonic-graph` (build + walks + layered layout) |
| Composition | `POST /api/compose/harmony`, `/api/compose/voice-leading`, `/api/compose/bass`, `/api/compose/melody`, `/api/compose/rhythm/apply`, `/api/compose/rhythm/generate` |
| Rhythm | `POST /api/rhythm/euclidean`, `/api/rhythm/state-graph`, `/api/rhythm/phase-shift`, `/api/rhythm/humanize`, `/api/rhythm/optimize-rotations`, `/api/rhythm/analyze`, `/api/drums/generate` |
| Lattice lab | `POST /api/exponent-lattice/scale`, `/api/exponent-lattice/harmony`, `/api/exponent-lattice/chord`, `/api/exponent-lattice/progression`, `/api/exponent-lattice/walk`, `/api/exponent-lattice/analyze` |
| Arrangement | `GET /api/arrange/profiles`, `POST /api/arrange/generate`, `/api/arrange/midi`, `/api/arrange/render` |
| Rendering | `POST /api/render/wav`, `POST /api/render/jobs`, `GET /api/render/jobs/{id}`, `GET /api/render/jobs/{id}/audio` |
| Export | `POST /api/export/midi`, `/api/export/rhythm/midi`, `/api/export/scala`, `/api/export/json` |
| Real-time | `WS /api/ws/transport` |

Full schemas: [api.md](api.md). Runnable commands:
[examples.md](examples.md).

---

# 4. Typical Workflows

## 4.1 Explore a CPS scale

Generate CPS over `1, 3, 5, 7` with k=2 → play notes on the circle →
toggle 倍音 to see harmonic alignment → hold two notes to read their
interval → snap to 12-EDO to hear the tempered equivalent.

## 4.2 Compose and export a piece

Generate a harmony progression (seed 42) → add hybrid bass and an arch
melody → 再生 to audition → export MIDI with pitch bend for your DAW,
and WAV for listening.

## 4.3 Walk the harmonic graph

Switch to Graph view → layered grid layout → double-click a distant
node to re-layer around it → run a weighted walk (harmonic metric,
seed) → the path shows one possible progression through the harmonic
space.

## 4.4 Build a rhythm track

Set steps/pulses per layer (e.g. kick 16/5, snare 16/3, hat 13/8,
perc 17/6) → ドラムを生成 to optimize rotations and phase drift →
audition with 再生, watching clashing cells → edit steps by hand if
needed → export the full kit as one MIDI file for a DAW.
