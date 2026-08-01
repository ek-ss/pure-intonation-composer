# Instrument-Constrained Composition Explorer

## Status

Implemented experimental workflow at `/composition-explorer`.

The explorer provides a common structural search layer for Fractional Pop,
Fractional J-Pop, and Kawaii Fractional Future Pop. It does not replace the
three dedicated composers. It generates a group of alternative song plans in
which the selected PI Vital presets are constraints on part writing rather
than names applied after composition.

## Workflow

1. Select a style and exact-ratio scale.
2. Select the PI01-PI21 presets that may appear in the score.
3. Set Form, Harmony, Part assignment, and Rhythm temperatures.
4. Optionally lock a component across all candidates.
5. Generate 4-64 candidates. The default is 32 candidates in 6 clusters.
6. Compare and audition one quality-weighted representative per cluster.
7. Like or dislike representatives to adjust future evaluation weights.
8. Export a representative, including its genome, harmony, assignments,
   features, evaluation, and score events, as JSON.

Ratings and learned weights are stored in browser `localStorage` under
`pure-intonation.composition-explorer-feedback`. They are sent with the next
exploration request and do not modify hard musical constraints.

## Composition Genome

Every candidate records a versioned genome with a master seed and independent
Form, Harmony, Melody, Rhythm, Arrangement, and Performance seeds. A locked
component uses the same derived seed for every candidate, while unlocked
components receive independent reproducible seeds.

The style adapters use probabilistic form grammars. Section roles and lengths
are sampled in four-bar blocks while preserving the requested total length.
The selected presets influence the grammar: for example, a pulse-capable
preset enables Minimal sections.

Harmony uses a bounded beam of root-degree sequences. The final sequence is
sampled from the top candidates using a temperature-weighted Boltzmann
distribution instead of always selecting the minimum-cost path. Costs include
style targets, root motion, repetition, and section cadences. Chord size is
bounded by the selected harmony preset. PI18 begins its section with three
voices before four-voice stacks are permitted.

## Instrument-First Assignment

Each PI profile declares semantic roles, MIDI range, maximum polyphony,
articulation, spectral band, section affinities, and tuning policy. A
section-level assignment score combines role affinity, section fit, range,
polyphony, and user priority. Generated events use only selected preset IDs.

`Missing bass` provides three policies:

- `warn`: omit bass and report the missing capability;
- `omit`: omit bass without a warning;
- `substitute`: assign low-mid root support to the selected pitched preset
  with the lowest available range.

Drum profiles retain fixed MIDI trigger notes. Pitched parts retain exact
fractional ratios and are octave-positioned inside each preset's declared
range.

## Evaluation And Clustering

The feature vector measures form variety, section contrast, root variety and
motion, tension smoothness, harmony repetition, melodic density, rest space,
syncopation, drum density, instrument coverage, and part turnover. These feed
separate heuristic scores for structure, harmony, melody, rhythm, repetition,
ratio color, and instrument fit.

Candidates are clustered with deterministic k-medoids over normalized shared
features. A representative balances heuristic quality (65 percent) with
centrality inside its cluster (35 percent). The browser auditions up to eight
bars from the first Chorus, Drop, or Final section of the representative.

## Boundaries

- Evaluation is symbolic and metadata-based; it does not yet analyze rendered
  Vital audio spectra.
- Learned weights are local to one browser profile and are not synchronized.
- The explorer exports Project JSON. Direct MIDI, WAV, stems, and transfer back
  into each dedicated composer remain follow-up work.
- The existing dedicated composers retain their current fixed-generation APIs.
  The explorer is the shared broad-search surface.
