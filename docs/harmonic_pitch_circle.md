# Harmonic Pitch Circle

**Status:** implemented browser learning tool

## Purpose

The Harmonic Pitch Circle is a standalone, 12-EDO study page for understanding
chord shapes in fifth-step coordinates. It keeps a chord's generating fifth
steps visible while also showing the corresponding chromatic pitch-class set.

Open the page at `/harmonic-pitch-circle`, or use **Harmonic Pitch Circle** in
the Workbench header.

## Coordinate Model

The reference is `0 = C`. One positive integer step is one perfect fifth.

```text
fifth step:       0  1  2  3  4  5  6  7  8  9  10 11
fifth spelling:   C  G  D  A  E  B  F# C# Ab Eb Bb F
chromatic pc:     0  7  2  9  4  11 6  1  8  3  10 5
```

For a fifth-step coordinate `f`, its 12-EDO pitch class is:

```text
pc = (7 * f) mod 12
```

A chord pattern stores relative fifth steps. With root fifth step `r`, the
materialized values are:

```text
absolute fifth steps = relative steps + r
mod-12 fifth steps   = absolute fifth steps mod 12
chromatic pcs        = (7 * mod-12 fifth steps) mod 12
```

Negative relative steps remain visible in the detail panel. This preserves the
spelling-oriented learning distinction between, for example, `-3 = Eb` and its
mod-12 representative `9 = D#/Eb`.

## Interface

The standalone page provides:

- direct root buttons for `C, G, D, A, E, B, F#, C#, Ab, Eb, Bb, F`;
- **Fifth circle** and **Chromatic circle** placements;
- fifth-step, note-name, and combined node labels;
- chord polygons whose edge order follows the selected circle order;
- distinct root and chord-tone emphasis;
- a numeric panel for steps, pitch classes, notes, and interval labels;
- a chord library containing triads, sevenths, add/six, tension, and
  altered/symmetric patterns;
- progression history with shared notes, exchanged notes, and Johnson distance;
- optional Auto audition: changing a root or chord pattern immediately replaces
  the sounding block chord through Web Audio.

Initial state is `C major`, Fifth circle, and combined labels.

## Chord Vocabulary

The page implements the specification's relative-fifth-step vocabulary:

| Category | Included patterns |
| --- | --- |
| Triads | Major, Minor, Diminished, Augmented, Sus2, Sus4 |
| Seventh chords | Maj7, 7, m7, mMaj7, m7b5, dim7, augMaj7, aug7 |
| Add / six chords | add9, 6, m6, 6/9 |
| Tension chords | 9, maj9, m9, 11, m11, 13, maj13, m13 |
| Altered / symmetric | 7b9, 7#9, 7#11, 7b13, whole tone, chromatic cluster |

## Progression Metric

History entries are compared as mod-12 fifth-step sets. For two equal-cardinality
pitch-class sets `A` and `B`, with `k = |A| = |B|`:

```text
shared_count    = |A intersection B|
johnson_distance = k - shared_count
```

The history table lists the shared spellings and the removed-to-added exchange.
When chord cardinalities differ, distance is displayed as `n/a`, because the
two sets are not vertices of the same Johnson graph `J(12, k)`.

## Implementation

The feature is intentionally browser-only: no API or persistent project state
is introduced. It uses vanilla JavaScript state, inline SVG for the circle, and
Web Audio for 12-EDO block-chord audition. Audition uses `C = 220 Hz` and
transposes that root frequency by the selected chromatic pitch class. The route is served by FastAPI from
`app/static/harmonic_pitch_circle.html`.

## Future Work

The larger exact-tuning extension is specified separately in
[Prime-Limit Harmonic Explorer Development Plan](development_plan_prime_limit_harmonic_explorer.md).
It preserves this page as the fixed 12-EDO learning surface while adding
prime-basis exploration, continuous cents, scale search, chord discovery, and
progression transport.

- chord-spelling policy that selects a single enharmonic spelling by chord;
- link to Arrange/Compose chord vocabulary;
- export of a chord-shape SVG or image;
- 7-limit and 11-limit pitch-set overlays;
- explicit Johnson graph navigation for equal-cardinality chord families;
- persistent study histories and comparison presets.
