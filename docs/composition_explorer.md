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
   `Mixed Style` exposes independent Fractional Pop, Fractional J-Pop, and
   Kawaii Future Pop weights.
2. Select the PI01-PI22 presets that may appear in the score.
3. Set Form, Harmony, Part assignment, and Rhythm temperatures.
4. Optionally lock a component across all candidates.
5. Optionally enable Mixed Meter Drums. Generate a meter project for each
   candidate, or import/transfer one exact project from the Mixed Meter page.
6. Generate 4-64 candidates. The default is 32 candidates in 6 clusters.
7. Compare and audition one quality-weighted representative per cluster.
8. Like or dislike representatives to adjust future evaluation weights.
9. Export a representative as PI-separated pitch-bend MIDI or Project JSON.
   JSON includes its genome, harmony, assignments, features, evaluation, and
   score events.

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

Mixed Style normalizes the three user weights. It samples one source form
grammar per candidate from that distribution, while harmony targets are the
weighted mean of all three styles' 12-TET semitone targets. This lets one song
retain a coherent form while its root motion occupies a genuinely blended
harmonic space. Every section records `form_style`; the genome and metadata
record the normalized `style_mix`.

Harmony uses a bounded beam of root-degree sequences. The final sequence is
sampled from the top candidates using a temperature-weighted Boltzmann
distribution instead of always selecting the minimum-cost path. Style target
numbers are 12-TET semitone offsets, not scale-array indexes: each target is
converted to `2^(n/12)` and matched to the nearest ratio in the supplied scale.
Target, root-motion, and cadence distances are measured in cents, so denser
scales retain the same target intervals. Costs also include repetition and
section cadences. Chord size is bounded by the selected harmony preset. PI18
begins its section with three voices before four-voice stacks are permitted.

## Instrument-First Assignment

Each PI profile declares semantic roles, MIDI range, maximum polyphony,
articulation, spectral band, section affinities, and tuning policy. A
section-level assignment score combines role affinity, section fit, range,
polyphony, and user priority. Generated events use only selected preset IDs.

The Mixed Style default palette is the union of presets used by every style
whose weight is above zero. A preset's assignment priority rises with the
combined weight of the styles whose standard palettes contain it. Manually
selected presets remain hard constraints on which instruments may be used.

`Missing bass` provides three policies:

- `warn`: omit bass and report the missing capability;
- `omit`: omit bass without a warning;
- `substitute`: assign low-mid root support to the selected pitched preset
  with the lowest available range.

Drum profiles retain fixed MIDI trigger notes. Pitched parts retain exact
fractional ratios and are octave-positioned inside each preset's declared
range.

## Mixed Meter Drum Integration

Mixed Meter is an optional drum layer beneath the Explorer's form, harmony,
and instrument-first arrangement. It has two source modes:

- `Generate per candidate` derives a Mixed Meter seed from each candidate's
  hierarchical Rhythm seed. Pattern, form, density profile, repeats,
  subdivision, variation, syncopation, and humanization remain reproducible.
- `Imported project` tiles one exact Mixed Meter project across every
  candidate. Use **Send to Composition Explorer** on the Mixed Meter page or
  import its lossless Project JSON. The Explorer adopts the imported tempo.

`Replace native drums` removes the Explorer's ordinary drum events before
mapping the Mixed Meter kick, snare, hat, tom, crash, and percussion roles to
compatible selected PI drum presets. `Layer with native drums` retains both.
The source cycle is repeated in quarter-beat coordinates and truncated at the
song boundary; its section phases do not replace the Explorer's song sections.

Candidate Project JSON preserves the complete source project and the tiled
bar/section timeline. The feature vector adds meter variety, phase
displacement, and metric resolution. These affect rhythmic/structural scores
and k-medoids distance, so candidates can differ by metric behavior rather
than only by notes and instrumentation. MIDI export writes the resulting time
signature changes and semantic song-section markers to the conductor track.

## Evaluation And Clustering

The feature vector measures form variety, section contrast, root variety and
motion, tension smoothness, harmony repetition, melodic density, rest space,
syncopation, drum density, meter variety, meter displacement, metric
resolution, instrument coverage, and part turnover. These feed
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
- The explorer exports type-1 pitch-bend MIDI and Project JSON. WAV, stems,
  and transfer back into the three dedicated melodic composers remain
  follow-up work.
- The existing dedicated composers retain their current fixed-generation APIs.
  The explorer is the shared broad-search surface.
