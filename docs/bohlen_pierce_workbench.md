# Bohlen-Pierce Pure Intonation Workbench

`/compose/bohlen-pierce` is an experimental composition environment whose
equave is the exact ratio `3/1` (a tritave), rather than `2/1`.

## Workflow

1. Choose a scale preset or enter exact ratios. Manual entries accept ordinary
   fractions such as `25/21` and exponent products such as `3^-1*5^2`.
2. Inspect the scale on the tritave Pitch Circle or the 5 × 7 exponent lattice.
   Enable 13-EDT to compare each pure pitch with its nearest tempered step.
3. Shift-click pitches to require them in a chord search. Search results expose
   harmonicity, odd-harmonic overlap, root clarity, compactness, roughness,
   complexity, and their weighted score.
4. Generate a 4-16 chord progression against a target tension curve, then
   audition the selected chord or the complete progression.
5. Generate Harmony, Bass, Melody, Rhythm, and optional Drone parts. Playback
   uses the chosen odd/full/sine/pluck timbre without octave normalization.
6. Export the complete project as JSON, a tritave Scala `.scl`, rendered WAV,
   or type-1 MPE-style MIDI with per-note pitch bend.

The scale editor maintains an undo/redo history. The two multiply controls use
exact rational arithmetic and normalize the result into `[1/1, 3/1)` on the
server.

## Reproducibility and Data

Scale, chord, progression, and composition results include exact fraction
strings. Progression and composition generation are deterministic for the same
request and seed. Project JSON can be imported back into the page; browser
state is otherwise not persisted.

## API

- `POST /api/bp/scales/generate`
- `POST /api/bp/chords/search`
- `POST /api/bp/progressions/search`
- `POST /api/bp/compose/generate`
- `POST /api/bp/render/audio`
- `POST /api/bp/export/midi`
- `POST /api/bp/export/scala`

MIDI playback requires the receiving instrument's pitch-bend range to match
the export setting. Scala files declare `3/1` as the repeating interval.
