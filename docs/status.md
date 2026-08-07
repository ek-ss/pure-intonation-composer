# Implementation Status

**Last audited:** 2026-08-07
**Branch:** `main`

This is the canonical status document for Pure Intonation Composer. It is
based on `backend/app/`, the OpenAPI schema, the browser workbench, and the
automated tests. Detailed design intent remains in the roadmap and algorithm
documents.

## Verification Baseline

- 75 OpenAPI paths plus one WebSocket transport endpoint
- 226 passing pytest tests, including G12 chord/progression, Vital Pack export,
  fractional-pop scale-membership, fractional J-Pop harmony/Vital export,
  kawaii future-pop phase/vocal/Vital coverage, and Worker asset coverage
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
| Minimal Functional Harmony Composer | Experimental MVP | Dedicated T/S/D form generator; Prime Explorer progression transfer/JSON import with chord-ID role mapping; independent Euclidean voices; kick/snare/hat/perc; 12-TET/5-limit/7-limit; Web Audio, JSON, and type-1 MIDI at `/minimal-functional-composer` | Editable function grammar and section form, continuous phase evolution, register-aware voice leading, project persistence, automated browser regression |
| Vital Pack Composer | Experimental arrangement environment | PI01–PI08 pitched roles, PI09–PI12 downloadable Vital drums, and downloadable PI22 Fractional Piano switchable between motif-scale runs and transferred developed motifs; seeded form, tonal character, functional progressions, scoped regeneration, multi-motif arrangement, rests, phase lanes, Web Audio, separate drum-track and pitch-bend MIDI, tuning/sidechain JSON, project JSON, and REAPER manifest at `/vital-pack-composer` | Direct Vital/DAW automation, user-editable palette weights, binary MTS-ESP, REAPER project generation, measured drift correction, spectral evaluation, motif section locks, convergent phase anchors |
| Motif Development Engine | Experimental core | Seeded selectable-prime anchor-chord motif generation (`[3,5,7]` default; subsets such as `[3,7,13]`) with bounded exponent deltas, adjustable gate rests, one- to four-voice chord stacks, and rest-aware evaluation; 1-32 candidate exploration, profile-weighted evaluation, hard filtering with diagnostics, dynamic-basis pitch-circle/monzo/rhythm/polyphony signatures, comparison, stack-aware variations, section motif trees, browser audition, JSON/MIDI, multi-candidate selection, and basis-preserving Development Tree transfer to Vital Pack at `/motif-development` | DTW insertion/deletion alignment, locks, Prime/Lattice transfer, persistent project IDs, motif section regeneration, performance and browser regression |
| Drum rhythm | Implemented core | Euclidean layers, rotation optimization, bounded polymetric analysis, phase offsets, state graph, humanization, metrics, MIDI/JSON export | Coordinated state transitions, fill generator, preset library, continuous phase drift |
| Compose Rhythm Orchestration | Implemented core | Chord-tone and role mapping, overflow/voice policies, Harmony/Bass/Melody-specific generators, integer-tick events, playback and export integration | Project schema migration/import, structured listening comparisons, performance benchmarks |
| Genre Arrangement Pipeline | Experimental MVP | Pop, Ambient, Alternative Rock, and Future Bass profiles; sounding-aware harmony; block/arpeggio/stride performance; coordinated parts; Project 1.1 and 1.0 migration; bounded WAV; type-1 microtonal MIDI; responsive Arrange workbench | Section regeneration, broader project import, stems/effect rendering, structured listening comparisons, automated browser regression |
| Fractional Pop Composer | Experimental implementation | Dedicated exact-ratio pop page with 5-limit/7-limit/custom scales, generated scale-degree chord vocabulary, bright/bittersweet/open harmonic colors, pop form and rhythm controls, downloadable PI09–PI12 Vital drums, separate drum tracks, form/pitch-circle/progression views, audition, Project JSON, pitch-bend MIDI, and WAV at `/fractional-pop-composer` | DAW/Vital automation, editable chord templates, saved projects, stems, structured listening tests, automated browser regression |
| Fractional J-Pop Composer | Experimental implementation | Dedicated A-melody/B-melody/chorus page; pure-fifth A harmony, `6/5` B harmony, 13-limit chorus root shifts, structured rhythm/bass/hook, rest-aware vocal guide, PI13–PI16 downloadable Vital presets, form/harmony/vocal views, Web Audio, JSON, and pitch-bend MIDI at `/jpop-composer` | Human vocal synthesis, lyric import, singer-range constraints, section regeneration, stems, automated browser regression |
| Kawaii Fractional Future Pop | Experimental implementation | Dedicated kawaii future-bass/pop/minimal page; editable 7/13-limit ratio palettes, Verse/Pre/Drop form, sidechain Drop stacks, A/B phase-shift cells, hooky/airy/chopped vocal guide, PI17–PI21 Vital presets, Pitch Circle, arrangement rolls, JSON, and pitch-bend MIDI at `/kawaii-future-pop` | Human vocal synthesis, phoneme/lyric import, rendered sidechain DSP, stems, section regeneration, structured listening tests |
| Instrument-Constrained Composition Explorer | Experimental implementation | Common CompositionGenome for three fractional-pop styles plus ratio-controlled Mixed Style; hierarchical seeds and locks; probabilistic form grammar; temperature-sampled top-K harmony; PI01-PI22 capability constraints including Fractional Piano; part score generation; symbolic feature/evaluation vectors; 4-64 candidate deterministic k-medoids; representative audition, type-1 pitch-bend MIDI, JSON, and browser-local preference learning at `/composition-explorer` | Rendered-audio evaluation, WAV/stems, transfer into dedicated composers, shared user profiles, automated browser screenshot regression |
| Bohlen-Pierce Pure Intonation | Experimental implementation | Exact `3/1` normalization; scale presets and exact editor; tritave circle and 5×7 lattice; 13-EDT comparison; constrained chord metrics/search; tension-curve progression; Harmony/Bass/Melody/Rhythm/Drone composition; odd-harmonic audition; JSON/MPE MIDI/WAV/Scala at `/compose/bohlen-pierce` | Persistent projects, editable metric weights in the GUI, large-lattice performance study, automated browser regression |
| Mixed Meter Drum Section | Experimental implementation | Pattern library and validated custom cycles; Stable/Tension/Pre-resolution/Resolved forms; phase timeline; section/tension-aware density; per-track controls; deterministic events and humanization; playback; JSON/type-1 MIDI/WAV; Compose timeline transfer at `/compose/mixed-meter-drums` | Direct event-to-Compose orchestration mapping, interactive hit editing/locks, saved preset library, automated browser regression |
| Harmonic Phase-Shift Composition | Experimental MVP | Shared and independent chord clocks; static/discrete/polymetric/convergent phase; distinctness and overlap metrics; strict/adaptive resolution; convergence markers; dual-lane workbench; MIDI/JSON/WAV | HP5 fractional drift, track-role assignment UI, overlap matrix audition, automated browser regression, structured listening evaluation |
| Visualization | Implemented core | Pitch Circle, force graph, reference-layered grid, walk overlays, harmonic stack highlighting, time-proportional Composition Roll | Voice-leading connectors, zoom/pan, per-voice mobile mode, persisted view state, automated browser regression |
| Harmonic Pitch Circle | Implemented | Standalone fifth-step chord-shape study page; fifth/chromatic circles, 32 chord patterns, numeric pitch-set detail, Johnson-distance history, and Web Audio block-chord audition | Enharmonic spelling policy, shape export, persistent histories |
| Prime-Limit Harmonic Explorer | Experimental release-candidate core | Prime-basis vector enumeration, boundary-aware clustering, continuous Pitch Circle, chord discovery, lattice/progression views, Worker-mediated searches, local session persistence, and JSON/SVG export at `/prime-limit-explorer` | Measured cancellation, CI screenshot/accessibility audit, session migration, cross-browser audio evaluation |
| Exponent Lattice Lab | Experimental, partial | Exact exponent math, collision groups, seeded chords, root-motion progressions, bounded walks, analysis, 2D projection, chord playback, keyboard, Compose transfer, and Minimal Composer transfer/JSON for progressions and walks | Structured vector editor, non-projected filtering, coordinate provenance through bass/melody/export, exponent lanes, versioned persistence, benchmarks |
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
5. Evaluate and tune the Genre Arrangement Pipeline with structured listening
   comparisons, then add section regeneration and project migration.
6. Add WebMIDI/MPE and mapping workflows after project persistence is stable.
7. Complete G12 P8-P9 with worker performance gates, accessibility/visual
   regression, portable export/migration, and release validation.
8. Complete G14 alignment, lock, transfer, Arrangement/Vital adapter, and
   project-persistence work after the prime-basis schema is fixed.

Research features such as form generation, spatialization, adaptive harmonic
models, and distributed rendering remain later work and are not release
blockers for the current browser workbench.
