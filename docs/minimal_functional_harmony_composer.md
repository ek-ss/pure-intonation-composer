# Minimal Functional Harmony Composer

## Status

Experimental MVP, implemented at `/minimal-functional-composer`.

This page turns the attached design proposal into a bounded, deterministic
study generator. It deliberately focuses on the core relation between
functional harmony, independently cycling voices, and a global form rather
than duplicating the general-purpose Arrange workbench.

## Implemented Contract

`POST /api/minimal-functional/generate` accepts a compact composition
configuration:

```json
{
  "duration_bars": 32,
  "tempo_bpm": 112,
  "voice_count": 5,
  "seed": 12345,
  "tuning": "5-limit",
  "climax_start": 0.62,
  "resolution_start": 0.78
}
```

The response contains a form-aware `chords` sequence, independently phased
`voices`, exact-ratio note `events`, and per-bar `analysis`. The browser page
uses this one result for form/function, rhythm-lane, and process-curve views,
preview playback, JSON export, and microtonal MIDI export.

Prime-Limit Harmonic Explorer progressions can be sent directly from its
Progression panel, or imported from its JSON export. Imported `chord-*` IDs
become choices for the T, S, and D role mappings. The selected ID supplies the
actual exact-ratio tone set whenever that harmonic function occurs.
Each role accepts multiple selected IDs; the seeded generator chooses among
that role's selected chords for every occurrence.

Lattice Lab can likewise transfer either a generated root-motion progression
or a generated walk. Its `JSON` controls export the same portable progression
shape, so those files are accepted by this page's Import JSON action as well.
Lattice-derived IDs are named `lattice-progression-01` or
`lattice-walk-01`.

### Harmonic Function

- `12-tet`: functional triads are generated at equal-tempered semitone
  positions, then represented as close rational frequency ratios for the
  shared Web Audio and MIDI pipeline.
- `T`: 1/1, 5/4, 3/2 in 5-limit JI
- `S`: 4/3, 5/3, 2/1
- `D`: 3/2, 15/8, 9/4
- `7-limit` adds a function-dependent colour tone.

The six form regions are Introduction, Accumulation, Development, Climax,
Resolution, and Coda. Function selection is seeded. The coda is forced to
Tonic and finishes with a root drone; resolution and coda align voice phases.

### Independent Rhythm

Each voice has a stable cycle length and phase offset. A Euclidean pattern is
regenerated from the current form density. Voice count and density grow into
the climax, then contract. The implementation preserves deterministic output
for an identical request and seed. Every voice also receives a deterministic
`time_delta_beats` offset per bar: it grows with density to prevent repeated
unison attacks, then contracts during Resolution and Coda.

## UI

The dedicated page shows:

- form regions and a T/S/D harmonic-function lane;
- density, tension, phase-dispersion, and stability curves;
- an eight-bar preview of each active voice rhythm;
- kick, snare, hat, and percussion lanes synchronized to the same form;
- the final resolution bars;
- Web Audio preview plus JSON and type-1 pitch-bend MIDI downloads, including
  a separate GM percussion track.

## Deliberate MVP Boundary

The original design's concepts are broader than this initial implementation.
The following remain planned:

- user-authored function grammars, chord substitutions, and per-section edits;
- independently editable cycle maps and continuous phase evolution;
- richer voice-leading and register constraints;
- alternate tuning systems beyond the current 12-TET, 5-limit, and 7-limit
  choices;
- 7-limit prime-pressure scheduling and high-prime retirement policies;
- a full score/timeline editor, persistent project import, and automated
  browser regression coverage.

For the project-wide source of truth, see [status.md](status.md).
