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
