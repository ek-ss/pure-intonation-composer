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

Planned

* Scale browser panel (named, savable user scales)
* Scala import
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

Planned

* Pitch-bend-accurate MIDI retuning (per-note pitch bend instead of
  nearest-note quantization)
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
* Lattice/graph views (force-directed Johnson graph; reference-node
  layered grid with walk visualization) — Done
* Timeline view with recorder and replay — Done

Planned

* Radial graph: relative-interval view between held notes
* Radial graph: harmonic rings (5–64 harmonics), EDO snapping,
  prime-limit snapping, force snap
* MIDI-note table (128 notes with frequency and cents deviation)

## G6. Scale Editor

Entonal: add/remove notes, enter cents/ratios/EDO degrees/math
expressions, repeating interval (octave, tritave, …).

Status

* Generative scale sources (CPS, Euler–Fokker, harmonic/subharmonic
  series) — Done

Planned

* Manual note add/remove with cents/ratio/EDO/expression entry
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
