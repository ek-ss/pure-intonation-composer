# Vital Pack Composer

## Status

Implemented experimental arrangement environment at `/vital-pack-composer`,
based on the Pure Intonation Vital Pack specification, its eight pitched Vital
profiles, four Vital drum profiles, and an external piano scale-run role.

## Implemented

- `GET /api/instruments/vital-pack`: PI01–PI12 preset profiles plus the
  external `PIANO` role; PI09–PI12 are kick, snare, closed hat, and percussion;
- `POST /api/compose/vital-pack`: seeded 8–64 bar song plan at 130–175 BPM;
- Major, Minor, or Mixed tonal character with adjustable mode strength and
  progression contrast;
- standard Intro, A, Build, Drop 1, Break, Final Drop, Outro form;
- role-aware PI01–PI12 events and an exact-ratio piano scale-run track;
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
- extraction of an octave-normalized motif scale, bar-level chord progression
  generation using motif prominence/consonance/common-tone scoring, scale-
  constrained accompaniment, and matching motif-derived Scala export;
- phase overlap, source-motif coverage, development-operation, and provenance
  quality measurements, plus harmony variety and motif-scale conformance.
- adjustable motif activity and `breathing`/`sparse`/`driving` rest phrasing:
  PI04 and PI07 use an exported play/rest schedule, stop after three
  consecutive active bars, periodically leave a full motif breath, and cap
  repeated statements inside each bar. Motif-synchronised hats/perc follow
  the lead activity instead of running continuously.
- polyphonic motif-step transfer: PI04/PI07 render one- to four-voice
  `harmony_tones` stacks with shared timing, per-voice velocity taper, scale
  constraint, transformation provenance, and microtonal MIDI output.
- optional `PIANO` part with adjustable activity and density. `Scale run`
  uses ascending, descending, turnaround, or zigzag contours, leaves
  whole-bar phrase rests, and lands on the root at cadences. Ordinary plans
  use the active Major/Minor scale; Development Tree plans use exact
  fractional ratios from the extracted motif scale. `Transferred motif`
  instead performs the assigned developed motif, preserving its rests and
  simultaneous `harmony_tones`.
- selectable Motif Development prime bases such as `[3,7,13]` are retained in
  metadata and constrain the motif scale, harmony, transformed stacks, and
  every pitched Vital event.

## Tonal Character and Progression Variety

`Tonal character` selects Major, Minor, or Mixed. Major and Minor use
different tonic, predominant, dominant, and substitute-degree ratio
palettes. Mixed selects a target mode per section.

`Mode strength` controls modal clarity:

- `1.0`: every bar follows its section's selected Major or Minor target;
- middle values: occasional parallel-mode borrowing;
- `0.0`: Major/Minor colour is approximately balanced.

`Progression contrast` controls harmonic movement:

- low: primary T/PD/D chords, more tonic retention, stronger common tones;
- high: more PD/D transitions, vi/iii/ii/V7 or bIII/bVI/ii-dim/v/bVII
  substitutes, wider motif-derived root selection, and fewer locked common
  tones.

Every section closes with dominant-to-tonic function. In transferred-motif
plans, the final chord selects the motif-scale pitch nearest 1/1 as its root.
The Form summary shows modal clarity, chord count, and variety score.

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

Adaptive mode uses role-appropriate subsets of the pitched Vital presets.
Showcase mode activates all pitched Vital profiles for inspection. The
independent `PIANO` role is included when `Piano scale run` is enabled and
should be assigned to a microtonal-capable piano instrument in the DAW.

PI09–PI12 replace the former external `DRUMS` sampler track. Their Vital files
are downloadable from Fractional Pop Composer, and generated MIDI and REAPER
manifests keep kick, snare, hat, and percussion on separate named tracks. See
[vital_pop_drums.md](vital_pop_drums.md).
