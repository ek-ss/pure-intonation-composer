# Mixed Meter Drum Section

`/compose/mixed-meter-drums` generates deterministic multi-track drum parts
whose meter cycles create tension and then realign with a four-beat grid.

## Workflow

1. Select a preset such as `3/5/7/5` or define meters and additive groupings.
   Each grouping must sum to its meter numerator. Quarter- and eighth-note
   denominators are supported.
2. Choose Direct Resolution, Two-stage Resolution, or a custom sequence of
   `stable`, `tension`, `pre_resolution`, and `resolved` section roles.
3. Select a density profile and adjust variation, syncopation, humanization,
   and the seed. Each drum row also exposes density mode, base density, tension
   response, syncopation, mute, and solo controls.
4. Generate and inspect section bands, meter boundaries, four-beat phase, and
   individual hits on the timeline. Gold hits are structural/locked anchors.
5. Play, pause, stop, or loop the result. Export type-1 MIDI, WAV preview, or
   lossless project JSON.

MIDI contains a conductor track with tempo, section markers, and a time
signature event at every bar boundary. Drum roles are exported to separate
tracks on General MIDI percussion notes.

## Density Model

The generator combines the chosen profile, section role, per-track tension
response, mandatory structural anchors, and minimum/maximum clamps. Random
selection and humanization are derived from the project seed, track, and
section, so identical requests produce identical projects.

## Compose Transfer

**Send timeline to Compose** transfers the shared clock, sections, and bar
boundaries through session storage, opens the main Workbench, and sets its
tempo. The next Compose JSON export preserves this under
`mixed_meter_timeline`; pitched-part rhythm mapping remains intentionally
separate from the drum-event project.

**Send to Composition Explorer** transfers the complete generated project,
including drum hits, meter bars, phase state, form sections, track settings,
and seed. The Explorer selects `Imported project`, adopts its tempo, and can
either replace its native drums or layer the imported events beneath its
instrument-constrained song. Mixed drum roles are mapped to compatible
selected PI drum presets; the metric cycle repeats to the Explorer song end.
Explorer Project JSON and MIDI preserve the resulting metric timeline.

## API

- `GET /api/rhythm/mixed-meter/patterns`
- `POST /api/rhythm/mixed-meter/validate`
- `POST /api/rhythm/mixed-meter/generate`
- `POST /api/rhythm/mixed-meter/preview`
- `POST /api/rhythm/mixed-meter/export/midi`
