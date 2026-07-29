# Vital Pack Composer

## Status

Implemented experimental arrangement environment at `/vital-pack-composer`,
based on the Pure Intonation Vital Pack specification and its eight instrument
profiles.

## Implemented

- `GET /api/instruments/vital-pack`: PI01–PI08 preset profile catalogue;
- `POST /api/compose/vital-pack`: seeded 8–64 bar song plan at 130–175 BPM;
- standard Intro, A, Build, Drop 1, Break, Final Drop, Outro form;
- role-aware PI01–PI08 events plus GM drum events;
- 5-limit/7-limit functional harmony, PI05 mono root anchor, PI07 Euclidean
  pulse, PI04 arpeggio, PI06 sparse cadence accents;
- declared dynamic tuning policies, semantic automation timelines, sidechain
  envelopes, quality-gate measurements, and a REAPER track/preset manifest;
- browser form/energy view, profile activity view, tuning-policy view,
- Web Audio excerpt, project JSON, type-1 MPE MIDI, JSON tuning and MTS-style
  retuning timelines, Scala base-scale, sidechain, and REAPER-manifest
  downloads;
- seeded section regeneration for harmony, rhythm, voicing, and instrument
  scopes. The regenerated section replaces its matching timing window in the
  browser plan.
- Development Tree transfer from Motif Development: tree nodes map to the
  3–12 section Vital form, drive harmony, PI04 lead motifs, PI05 bass, PI06
  accents, PI07 pulses, and motif-synchronised drum detail; provenance remains
  in project JSON and MPE MIDI source events.
- checkbox selection of multiple motif candidates, deterministic
  repetition-level development, and optional static/progressive/polymetric
  PI04/PI07 motif phase lanes over shared harmony;
- phase overlap, source-motif coverage, development-operation, and provenance
  quality measurements.

## Outputs and Boundaries

The generator records tuning policy and exact ratios, and produces a
per-instrument type-1 MIDI file with per-note pitch bend plus portable tuning
timelines. `MTS timeline` is a DAW-facing JSON retuning event sequence with
absolute frequency values; it is deliberately not a binary MTS-ESP protocol
packet. `Scala base` is a standard `.scl` reference scale, while the timeline
retains the time-varying chord context.

The REAPER manifest and sidechain JSON are deterministic import helpers, not a
generated REAPER `.rpp` project or direct Vital parameter automation. Direct
control of Vital requires an installed-plugin or DAW scripting API, which is
outside this browser/API application.

Adaptive mode uses role-appropriate subsets of the eight presets. Showcase
mode activates all eight profiles for inspection rather than asserting a
production-ready mix.
