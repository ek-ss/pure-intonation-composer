# Implementation Status

**Last audited:** 2026-07-26
**Branch:** `develop`

This is the canonical status document for Pure Intonation Composer. It is
based on `backend/app/`, the OpenAPI schema, the browser workbench, and the
automated tests. Detailed design intent remains in the roadmap and algorithm
documents.

## Verification Baseline

- 39 OpenAPI paths plus one WebSocket transport endpoint
- 152 passing pytest tests
- `ruff check app tests` passes
- `mypy app` passes
- Browser workbench implemented in vanilla JavaScript without a build step

The existing automated suite covers the mathematical engines and API
contracts thoroughly. Browser interaction and screenshot checks are currently
manual rather than part of continuous integration.

## Functional Status

| Area | Status | Available now | Remaining work |
| --- | --- | --- | --- |
| Scale and tuning | Implemented, non-persistent | CPS, Euler-Fokker, harmonic/subharmonic series, ratio/cents/EDO input, EDO and prime-limit snapping, Scala import/export, named scale CRUD | On-disk scale storage, complete workbench presets, custom repeating intervals |
| Harmonic graph | Implemented | Johnson graph, harmonic/monzo/cent metrics, shortest/random/weighted walks, deterministic layered layout | Large-graph performance benchmarks |
| Composition | Implemented | Seeded harmony, voice leading, bass strategies, multi-voice melody, browser playback, MIDI/JSON/WAV export | One-shot project composition endpoint, persisted project import |
| Drum rhythm | Implemented core | Euclidean layers, rotation optimization, bounded polymetric analysis, phase offsets, state graph, humanization, metrics, MIDI/JSON export | Coordinated state transitions, fill generator, preset library, continuous phase drift |
| Compose Rhythm Orchestration | Implemented core | Chord-tone and role mapping, overflow/voice policies, Harmony/Bass/Melody-specific generators, integer-tick events, playback and export integration | Project schema migration/import, structured listening comparisons, performance benchmarks |
| Genre Arrangement Pipeline | Planned | Design completed for scale/chord input, genre profiles, form, harmony, coordinated parts, type-1 MIDI, JSON, and rendering | All implementation; initial profiles are Pop, Ambient, Alternative Rock, and Future Bass |
| Visualization | Implemented core | Pitch Circle, force graph, reference-layered grid, walk overlays, harmonic stack highlighting, time-proportional Composition Roll | Voice-leading connectors, zoom/pan, per-voice mobile mode, persisted view state, automated browser regression |
| Exponent Lattice Lab | Experimental, partial | Exact exponent math, collision groups, seeded chords, root-motion progressions, bounded walks, analysis, 2D projection, chord playback, keyboard, Compose transfer | Structured vector editor, non-projected filtering, coordinate provenance through bass/melody/export, exponent lanes, versioned persistence, benchmarks |
| Audio and export | Implemented core | WebAudio audition, five offline oscillator modes, ADSR, delay/reverb, synchronous and queued WAV, pitched and percussion MIDI, pitch-bend retuning, Scala and JSON | FM/noise synthesis, instrument presets, durable render jobs |
| Real-time input and transport | Partial | Pointer/PC keyboard performance, timeline record/replay, WebSocket play/pause/stop/improvise | WebMIDI, MPE, MTS-ESP, OSC, DAW synchronization, MIDI learn |
| Project and release | Partial | Editable Python package, FastAPI workbench, deterministic seeds, documented local workflow | Versioned project save/load, undo/redo, authentication if deployed remotely, packaging/installer, target-platform benchmarks |

## Persistence Boundaries

The following state is process-local and disappears when the server restarts:

- named scales in `app/scales.py`;
- asynchronous render job status and audio in `app/jobs.py`;
- full browser workbench and view state, beyond the composition JSON export.

JSON export is available, but there is no corresponding full-project import
or migration pipeline. This is the main cross-cutting gap before a stable
release.

## Next Priorities

1. Define a versioned project schema and implement save, load, migration, and
   durable scale storage.
2. Add automated desktop/mobile browser workflows for Compose, Rhythm
   Orchestration, Composition Roll, and Lattice Lab.
3. Record performance baselines for graphs, long polymetric rhythms, lattice
   enumeration, MIDI export, and WAV rendering.
4. Complete Lattice coordinate provenance and structured vector editing.
5. Implement the Genre Arrangement Pipeline models and a thin Pop
   end-to-end path, then expand the other three profiles.
6. Add WebMIDI/MPE and mapping workflows after project persistence is stable.

Research features such as form generation, spatialization, adaptive harmonic
models, and distributed rendering remain later work and are not release
blockers for the current browser workbench.
