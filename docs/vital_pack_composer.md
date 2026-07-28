# Vital Pack Composer

## Status

Experimental MVP at `/vital-pack-composer`, based on the Pure Intonation
Vital Pack specification and its eight instrument profiles.

## Implemented

- `GET /api/instruments/vital-pack`: PI01–PI08 preset profile catalogue;
- `POST /api/compose/vital-pack`: seeded 8–64 bar song plan at 130–175 BPM;
- standard Intro, A, Build, Drop 1, Break, Final Drop, Outro form;
- role-aware PI01–PI08 events plus GM drum events;
- 5-limit/7-limit functional harmony, PI05 mono root anchor, PI07 Euclidean
  pulse, PI04 arpeggio, PI06 sparse cadence accents;
- declared dynamic tuning policies, semantic automation timelines, and a
  REAPER track/preset manifest;
- browser form/energy view, profile activity view, tuning-policy view,
  Web Audio excerpt, project JSON, and REAPER manifest downloads.

## Current Boundary

The generator records tuning policy and exact ratios, but it does not control
Vital directly. It does not yet produce MTS-ESP, MPE MIDI files, `.scl` files,
sidechain envelopes, or a REAPER import script. Those are the next P3–P7
stages from the supplied specification.

Adaptive mode uses role-appropriate subsets of the eight presets. Showcase
mode activates all eight profiles for inspection rather than asserting a
production-ready mix.
