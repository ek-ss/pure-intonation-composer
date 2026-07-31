# G14 Motif Development Engine

**Project:** Pure Intonation Composer
**Document ID:** PIC-MDE-PLAN-001
**Version:** 0.1
**Status:** Experimental core implemented; remaining delivery phases planned
**Source specification:** PIC-MDE-SPEC-001
**Primary tuning model:** configurable odd-prime basis with implicit octave prime 2

## 1. Purpose

The Motif Development Engine (MDE) generates a short motif from a three- or
four-note anchor chord and develops it across a complete form. It preserves
recognizable pitch, rhythm, contour, and harmonic features while allowing
their controlled transformation.

MDE connects the existing harmonic, lattice, rhythm, arrangement, tuning, and
export systems:

```text
Anchor chord and prime-lattice domain
              |
              v
       Motif generation
              |
              v
       Signature extraction
              |
       +------+------+
       |             |
       v             v
Harmony adaptation  Variation engine
       |             |
       +------+------+
              v
       Section development
              |
              v
 Arrangement / tuning / MIDI / JSON
```

Theme and variation are compared in two distinct pitch spaces:

1. prime-lattice coordinates represented by `2^o` times a configurable
   product such as `3^a 7^b 13^c`;
2. octave-cyclic pitch-circle position.

These dimensions remain separate so that comma shifts, octave displacement,
and lattice transposition are not collapsed into one ambiguous similarity
score.

## 2. Implementation Boundary

The initial P1-P6 backend core and an initial P8 workbench are implemented at
`/motif-development`. Available endpoints are `/api/motif/generate`,
`/api/motif/compare`, `/api/motif/variation`, and `/api/motif/develop`.

The current implementation supports bounded configurable-prime generation, signatures,
component distances, initial pitch/rhythm transformations, deterministic
section development, browser audition, and generic pitch-bend MIDI/JSON
export, plus Development Tree transfer into Vital Pack.

The default exploration basis is `[3,5,7]`, while the workbench accepts one
to five unique odd primes such as `[3,7,13]`. Prime 2 remains implicit for
octave placement. For basis `P` and radius `R`, candidate exponent deltas
satisfy `sum(abs(delta_i)) <= R`; no unselected prime is introduced by motif
generation, harmony stacks, lattice transpose, neighbour substitution,
Development Tree generation, or Vital transfer.

The browser workbench reconciles Development harmony after motif generation.
If a custom basis excludes a prime used by the previous harmony text, it
constructs four rotating three- or four-tone chords from the valid Anchor and
generated motif pool. This keeps **Send Development Tree to Vital Pack**
basis-safe while the API continues to reject invalid direct requests.

Persistent motif IDs, DTW insertion/deletion alignment, per-attribute locks,
and direct Prime Explorer/Lattice transfer remain outside the current
boundary.

The implementation must reuse:

- ratio parsing, normalization, cents, and monzo analysis from `app.tuning`;
- exact exponent-vector operations and candidate enumeration from `app.lattice`;
- prime-basis exploration and chord data from G12;
- deterministic Euclidean and Compose-native rhythm generation from G10;
- section, performance-pattern, MIDI, JSON, and render contracts from G11;
- Vital Pack role and tuning-policy metadata where instrument assignment is
  requested.

MDE owns motif identity, motif-to-variation comparison, transformation chains,
and the motif tree. It does not duplicate the harmony, rhythm, tuning, audio,
or export engines.

## 3. Design Principles

1. A three- or four-note anchor chord is required before motif generation.
2. Pitch-class and sounding-register representations are both retained.
3. Every distance component is stored independently.
4. Section roles target a distance range rather than minimum difference.
5. Important identity features can be locked independently.
6. Harmony selection and motif adaptation work in both directions.
7. The same input, seed, and engine version produce the same result.
8. Browser playback, JSON, MIDI, and rendering consume one canonical event
   sequence.

## 4. Pitch Model

### 4.1 Canonical pitch

```json
{
  "ratio": "7/6",
  "monzo": [-1, -1, 0, 1],
  "pitch_circle_cent": 266.87091,
  "register_cent": 266.87091
}
```

The monzo fields represent:

```text
ratio = 2^octave * 3^p3 * 5^p5 * 7^p7
```

Pitch-class comparison adjusts the octave exponent until the ratio is in
`[1, 2)`. Sounding-register comparison preserves the original octave.

### 4.2 Pitch-circle position

For an octave-normalized ratio `r`:

```text
circle(r) = 1200 * log2(r) mod 1200
```

The default circle mode is continuous cents. Future modes may compare scale
indices or use a weighted hybrid.

### 4.3 Distance components

The circular distance is:

```text
D_circle(p, q) = min(abs(xp - xq), 1200 - abs(xp - xq))
normalized_circle = D_circle / 600
```

Signed contour comparison uses the shortest difference in `[-600, 600)`;
actual ascending or descending motion comes from sounding register.

The default prime-weighted monzo distance is:

```text
D_monzo = 1.00 * abs(delta_p3)
        + 1.25 * abs(delta_p5)
        + 1.55 * abs(delta_p7)
```

Register distance is measured in octaves:

```text
D_register = abs(register_cent_p - register_cent_q) / 1200
```

When the Prime Lattice graph is available, shortest-path cost is retained as
an additional diagnostic. It does not replace the raw monzo components.

## 5. Canonical Models

### 5.1 Anchor chord

```json
{
  "id": "anchor-01",
  "tones": [
    {"ratio": "1/1", "monzo": [0, 0, 0, 0], "role": "root"},
    {"ratio": "5/4", "monzo": [-2, 0, 1, 0], "role": "third"},
    {"ratio": "3/2", "monzo": [-1, 1, 0, 0], "role": "fifth"},
    {"ratio": "7/4", "monzo": [-2, 0, 0, 1], "role": "colour"}
  ]
}
```

Each candidate pitch is classified as:

| Class | Meaning |
| --- | --- |
| `exact` | Same pitch-class monzo as an anchor tone |
| `near` | Within the configured near-lattice threshold |
| `related` | Normally two or three lattice steps away |
| `contrast` | Allowed domain pitch with weak anchor relation |
| `external` | Outside the candidate domain |

Chord affinity combines monzo and pitch-circle proximity and weights strong
beats, long notes, accents, and terminal notes more heavily.

### 5.2 Terminal-role policy

The public anchor-chord array assigns roles by position: `root`, `third`,
`fifth`, and optional `colour`. The generator records the applied terminal
policy and resulting `terminal_role` in the motif identity features.

| Policy | Final-note selection |
| --- | --- |
| `root` | Root anchor tone in the requested register |
| `stable` | Seeded selection between root and fifth |
| `colour` | Seeded selection between third and optional colour tone |
| `nearest_anchor` | Anchor tone with the smallest final sounding leap |
| `weighted` | Seeded role draw: root 45%, fifth 30%, third 18%, colour 7% |
| `random` | Seeded uniform draw from all available anchor tones |
| `free` | Retain the generated final tone; Anchor membership is not forced |

For all policies other than `free`, the final tone is `exact` relative to the
Anchor chord. A missing requested role falls back to the available Anchor
tones deterministically.

### 5.3 Motif

```text
Motif
  id, seed, engine_version, anchor_chord_id
  notes[]
    id, ratio, monzo
    pitch_circle_cent, register_cent
    onset_beat, duration_beats, velocity, accent
    chord_relation
  interval_signature[]
    monzo_delta, circle_delta_cent
    register_delta_cent, duration_ratio
  rhythm_signature
  contour_signature
  anchor_membership
  chord_affinity
  identity_features
  evaluation
```

Required identity features include:

- direction and size of the first two intervals;
- position of the highest or lowest note;
- position of the longest note;
- chord relation of strong-beat notes;
- anchor role of the terminal note;
- characteristic rhythm cells and repeated segments;
- position of 7-limit material;
- characteristic interval-signature subsequences.

### 5.3 Variation

```text
MotifVariation
  id, source_motif_id, parent_variation_id
  target_chord_id
  transformation_chain[]
  notes[]
  alignment[]
  distance_vector
    absolute_monzo
    relative_monzo_shape
    pitch_circle
    register
    contour
    rhythm
    chord_affinity_change
  identity_retention
  target_distance_score
  current_chord_affinity
  evaluation
```

### 5.4 Motif tree

Every tree edge stores the applied transformations and component distance
change. Parent references must remain valid after selective branch
regeneration.

```text
M0 Original
 |- M1 A-prime: neighbour substitution
 |- M2 Build: rhythmic diminution
 |   `- M3 Drop: chord projection and expansion
 |- M4 B: lattice transpose
 |   `- M5 Development: fragmentation
 `- M6 Recapitulation: restored contour
     `- M7 Coda: liquidation
```

## 6. Motif Generation

### 6.1 Input controls

- three- or four-note anchor chord;
- motif note count, normally four to eight;
- total length in beats;
- sounding register;
- target proportions for membership classes;
- target pitch-circle step distribution;
- prime limit and maximum lattice radius;
- rhythm profile;
- beam width and output candidate count;
- deterministic seed.

### 6.2 Candidate pool

```text
candidate pool =
    exact anchor tones
  + near lattice neighbours
  + related lattice pitches
  + explicitly enabled contrast pitches
```

Every candidate carries anchor distance, circle distance, harmonicity, prime
complexity, estimated roughness, register placements, and membership class.

Candidates are rejected before search when they exceed the prime/exponent
limit, register, leap limit, or external-tone policy. Weakly related pitches
are not placed on strong beats unless the profile explicitly permits them.

### 6.3 Seeded stochastic beam search

1. Normalize the anchor chord.
2. Enumerate and annotate the candidate pool.
3. Generate or select a rhythm template.
4. Start from an anchor tone.
5. Expand candidates one note at a time.
6. Prune using partial anchor, circle, contour, rhythm, leap, and complexity
   scores.
7. Apply complete-motif closure and identity scoring.
8. Cluster near-duplicate candidates.
9. Select deterministically from top clusters.
10. Extract interval, rhythm, contour, and identity signatures.

The initial completed-motif weighting is:

| Component | Weight |
| --- | ---: |
| Chord affinity | 0.28 |
| Circle-step profile | 0.20 |
| Contour | 0.17 |
| Rhythm identity | 0.17 |
| Closure | 0.08 |
| Identity features | 0.10 |

Raw component scores and penalties are returned for inspection.

### 6.4 Exploration evaluation and filtering

The implemented explorer evaluates a batch of one to 32 deterministic seeds,
instead of presenting a single unranked random result. It retains all
candidates for inspection but promotes hard-filtered candidates first.

Hard filters reject a candidate when its anchor affinity is below the selected
profile floor, fewer than 34% of tones are exact/near anchor members, a
register leap exceeds an octave, or the duration ratio exceeds six to one.
When no candidate passes, the ranked results remain available with explicit
rejection reasons rather than returning an empty result.

Each candidate retains these normalized evaluation components:

| Component | Meaning |
| --- | --- |
| Harmony | Anchor affinity, exact/near membership, and terminal stability |
| Melody | Pitch-circle step share and contour-turn restraint |
| Rhythm | Duration entropy, syncopation, controlled duration contrast, and a moderate rest ratio |
| Identity | Exact terminal, non-static opening intervals, and 7-limit colour |
| Novelty | Distance from earlier candidates in the same exploration batch |
| Complexity | Prime-exponent pressure, applied as a penalty |

Profiles set the final weighting without discarding the component vector:
`balanced`, `consonant`, `lyrical`, `rhythmic`, and `colourful`. The
workbench displays candidate rank, total, Harmony/Melody/Rhythm components,
and any filter reason. A user may reveal filtered candidates and select any
candidate for audition or development.

## 7. Rhythm and Identity

Rhythm signatures retain onset intervals, duration ratios, accents, rests,
syncopation, and metrical positions. Generation sources include fixed
templates, Euclidean patterns, short-long and question-answer grammars,
user-supplied rhythms, and adaptation to drum or pulse grids.

The implemented generator exposes `rest_density` from 0 to 0.7. It preserves
each rhythmic cell onset and shortens the sounding gate, then serializes the
derived gaps and normalized rest ratio. Browser audition and MIDI therefore
use real silence rather than a display-only rest marker. Candidate evaluation
rewards moderate breathing and filters excessive silence.

### 7.1 Polyphonic motif steps

`max_polyphony` selects one to four simultaneous voices. The first ratio of
each step remains the contour-bearing motif tone; zero to three
`harmony_tones` form a bounded chord stack at the same onset and duration.
Companion selection ranks pure-interval consonance, anchor-chord relation,
and current chord affinity. Accented and terminal steps realize the requested
maximum when enough legal register candidates exist, while intervening steps
may thin to fewer voices.

Lattice transpose and pitch retrograde operate on the whole stack.
Chord projection remaps companion voices to the target chord, and scale
constraint snaps every voice rather than only the contour tone. Development
Tree and Vital events carry `source_note_index` and `stack_voice`, so MIDI and
audio preserve simultaneous attacks without losing motif provenance.

A variation must preserve at least two configured rhythmic identity features,
such as the opening cell, longest-note position, rest position, strong-beat
accent, syncopation position, or terminal duration ratio.

## 8. Variation Engine

### 8.1 Pitch operations

- lattice transpose and selective lattice shift;
- circle-targeted transpose;
- inversion and pitch retrograde;
- sequence;
- neighbour substitution;
- projection onto the current chord;
- prime-colour shift;
- octave displacement.

### 8.2 Rhythm operations

- augmentation and diminution;
- onset shift and syncopation;
- note split, merge, and rest insertion;
- Euclidean remapping and phase shift;
- accent rotation.

### 8.3 Structural operations

- fragmentation and recombination;
- prefix or suffix retention;
- call and response;
- interpolation and liquidation;
- registral expansion or compression;
- voice exchange and accompaniment embedding.

Locked note attributes constrain these operations. Pitch, rhythm, chord
relation, interval direction, register, metrical role, and terminal-note
status can be locked separately.

## 9. Comparison and Target Distance

Motifs of different lengths use dynamic time warping or edit-distance dynamic
programming. Local alignment cost combines monzo, circle, register, duration,
and accent difference. Insert/delete costs are higher for strong beats,
longest notes, and identity-bearing notes.

The engine calculates ordinary and transformation-normalized comparisons:

- identity;
- inversion-normalized;
- retrograde-normalized;
- transposition-normalized;
- augmentation-normalized rhythm.

The distance vector is always persisted. A weighted total may be used for
ranking and visualization, but selection primarily targets a multidimensional
range:

```text
target score = exp(-((total distance - target)^2) / (2 * sigma^2))
```

This prevents every section from selecting the closest possible variation.

## 10. Formal Development

| Section role | Theme distance | Chord affinity | Rhythm change |
| --- | ---: | ---: | ---: |
| Introduction | 0.15-0.35 | High | Small |
| Theme A | 0.00-0.15 | High | None to small |
| A-prime | 0.15-0.35 | High | Small to medium |
| B | 0.35-0.60 | Medium to high | Medium |
| Development | 0.55-0.90 | Variable | Medium to large |
| Climax | 0.35-0.70 | High | Medium |
| Recapitulation | 0.05-0.25 | High | Small |
| Coda | 0.00-0.20 | Very high | Decreasing |

The planner accepts a section plan, harmony plan, instrument profile, target
distance envelope, and seed. It returns the motif tree, section assignments,
variation events, distance analysis, and canonical note events.

## 11. Engine Integration

### 11.1 Harmony

Motif-to-harmony search favors chords containing identity-bearing strong-beat
notes, retaining common tones and providing a route back to the anchor.

Harmony-to-motif adaptation first changes passing or ornamental notes,
projects selected notes onto the current chord, retains identity-bearing
notes where possible, and recalculates chord affinity and voice leading.

### 11.2 Arrangement

Motifs may be assigned to melody, bass motif, inner voice, arpeggio, chord
rhythm, pad top note, bell accent, or pitched pulse. Multiple assignments may
use different start phase, rhythm multiplier, lattice transpose, register,
duration, timbre, and chord-projection strength.

G11 owns generic arrangement events. The Vital Pack adapter maps motif roles
to PI01-PI08 profiles without introducing Vital-specific fields into the core
Motif model.

### 11.3 Tuning and export

Every emitted note retains ratio, monzo, current chord reference, and tuning
policy. Evaluation includes comma drift, common-tone retention, MPE/MTS
feasibility, and simultaneous pitch-bend channel pressure.

JSON analysis export preserves the complete motif tree and distance vectors.
MIDI/WAV export consumes the same flattened note-event sequence used by
browser audition.

## 12. Proposed API

All endpoints are planned and must use versioned request/response models.

### `POST /api/motif/generate`

Creates ranked motif candidates from an inline anchor chord and generation
profile.

```json
{
  "anchor_chord": {"tones": ["1/1", "5/4", "3/2", "7/4"]},
  "prime_limit": 7,
  "note_count": 6,
  "length_beats": 2,
  "register": [60, 84],
  "membership_profile": "anchor_balanced",
  "circle_profile": "mostly_stepwise",
  "rhythm_profile": "kawaii_syncopated",
  "beam_width": 64,
  "candidate_count": 16,
  "seed": 72801
}
```

### `POST /api/motif/variation`

Generates and ranks variations for a supplied source motif, target chord,
formal role, allowed transformation set, and target distance ranges.

### `POST /api/motif/develop`

Builds a motif tree and section assignments from a motif, harmony plan,
section plan, instrument profile, distance envelope, and seed.

### `POST /api/motif/compare`

Returns alignment, component distance vector, recognized transformations,
identity retention, and chord-affinity change for two motifs.

Generated motifs remain inline in MVP requests. Persistent motif IDs are
deferred until the versioned project save/load contract is available.

## 13. Proposed Modules

```text
backend/app/motif/
  models.py
  pitch.py
  distance.py
  candidate_pool.py
  rhythm.py
  generator.py
  signature.py
  transforms.py
  alignment.py
  variation.py
  development.py
  harmony_adapter.py
  arrangement_adapter.py
  evaluation.py
```

Core modules must not import FastAPI, browser, audio, or storage code.
Adapters translate between the MDE domain models and existing composition
contracts.

## 14. Workbench

A dedicated `/motif-development` page is planned with two primary views.

Motif Generator:

- anchor-chord input and transfer from Prime Explorer or Lattice Lab;
- linked Prime Lattice and continuous Pitch Circle;
- motif sequence with membership colors and interval arcs;
- ranked candidates and score breakdown;
- fixed seed, Generate, Mutate, and per-attribute note locks.

Development:

- motif tree and section timeline;
- target and actual theme-distance curves;
- monzo-versus-circle distance plot;
- current-chord affinity and transformation history;
- variation audition;
- selected-branch regeneration;
- JSON and MIDI export plus transfer to Arrange/Vital Pack.

Selection and playback state must be shared across all views. The UI must
remain usable without a mouse and at narrow mobile widths.

## 15. Delivery Plan

### P1: Pitch and distance core

- canonical 7-limit monzo conversion;
- octave normalization and pitch-circle operations;
- weighted monzo, circle, register, and relative-shape distances;
- interval signatures and invariant tests.

### P2: Anchor-based motif generator

- anchor validation and membership classes;
- bounded lattice candidate pool;
- rhythm templates and seeded stochastic beam search;
- candidate clustering, evaluation, and diagnostics.

### P3: Signature and comparison

- identity-feature extraction;
- DTW/edit-distance alignment;
- complete distance vector;
- transformation-aware comparisons.

### P4: Variation engine

- lattice transpose, neighbour substitution, inversion, and retrograde;
- rhythm augmentation/diminution and fragmentation;
- transformation chains, locks, and deterministic ranking.

### P5: Harmony integration

- current-chord affinity;
- chord projection and motif-driven harmony scoring;
- voice-leading and common-tone evaluation;
- Prime Explorer and Lattice Lab transfer adapters.

### P6: Development planner

- section distance envelope;
- motif-tree construction;
- A/A-prime/B/Development/Recapitulation planning;
- selected-branch deterministic regeneration.

### P7: Arrangement and export

- G11 part-role mapping and canonical note events;
- Vital Pack adapter and drum/pulse synchronization;
- tuning feasibility diagnostics;
- analysis JSON and type-1 microtonal MIDI.

### P8: UI, audition, and release validation

- linked lattice, pitch circle, motif sequence, and tree;
- candidate comparison and branch regeneration;
- Web Audio audition and Arrange/Vital transfer;
- desktop/mobile visual regression, accessibility, performance, and
  deterministic export tests.

P1-P3 form the analysis foundation. P4-P6 form the composition MVP. P7-P8
complete user-facing integration.

## 16. Tests and Performance Gates

Pitch and distance tests cover ratio/monzo round trips, octave boundaries,
signed circle differences, comma-neighbour recognition, octave displacement,
relative shape under lattice transpose, inversion, and retrograde.

Generation tests cover anchor membership targets, circle-step distribution,
register/leap bounds, terminal resolution, three- and four-note anchors, and
byte-for-byte deterministic JSON for a fixed seed.

Development tests cover identity retention in A-prime, target distance in
Development, decreasing distance in Recapitulation, chord-affinity floors,
valid motif-tree references, and stable insertion/deletion alignment.

MVP performance targets on the documented reference machine:

| Workload | Target |
| --- | ---: |
| 32-128 pitch candidate pool | Bounded, no unbounded enumeration |
| 4-8 note motif, beam width 32-128 | <= 500 ms |
| One section variation set | <= 1 s |
| 64-bar development plan | <= 5 s |

Roughness calculations and audio-based evaluation move to bounded background
jobs if they prevent these targets.

## 17. MVP Acceptance Criteria

1. Accept a three- or four-note anchor chord as exact ratios/monzos.
2. Generate deterministic four- to eight-note motifs.
3. Control the target share of anchor and near-anchor notes.
4. Control pitch-circle interval distribution.
5. Extract interval, rhythm, contour, and identity signatures.
6. Generate lattice-transposed, neighbour-substituted, and rhythmic
   variations.
7. Return independent motif-to-variation distance components.
8. Evaluate current-chord affinity.
9. Produce at least A, A-prime, Development, and Recapitulation assignments.
10. Regenerate the same result for the same seed and engine version.
11. Export analysis JSON and microtonal MIDI.
12. Identify a comma shift as circle-near but monzo-nonzero.

## 18. Deferred Extensions

- arbitrary prime limits above 7;
- motif extraction from performed or imported MIDI;
- contrapuntal generation between multiple motifs;
- audio-embedding identity and learned perceptual scoring;
- real-time DAW variation generation and MTS-ESP control;
- timbre-specific motif suitability;
- theme-family clustering and whole-song motif-recovery metrics;
- generated prose explaining the development path.

## 19. Open Decisions Before P1

1. Whether the canonical monzo is fixed to `[2,3,5,7]` in schema version 1 or
   stores an explicit prime basis.
2. Whether scale-index circle mode belongs in MDE core or a scale adapter.
3. The default DTW insertion/deletion importance weights.
4. How candidate clustering identifies musically equivalent octave/register
   variants.
5. The project-schema identity format for motif and variation IDs.

These decisions require fixtures and documented migration behavior before
their associated models become public API.
