# Multi-Part Drum Alignment and Phase-Shift Algorithm

**Project:** Pure Intonation Composer
**Component:** Rhythm Engine
**Version:** 0.1

> **Document status:** mixed implementation and design specification.
> Euclidean generation, rotation optimization, bounded polymetric analysis,
> phase offsets, metrics, state graphs, accent velocities, and humanization
> are implemented. Coordinated transitions, fill generation, presets, and
> continuous phase drift remain planned; see [status.md](status.md).

---

## 1. Purpose

This section defines how the kick, snare, hi-hat, and percussion layers are generated, rotated, phase-shifted, and combined.

The objective is not merely to generate independent Euclidean rhythms. The system must coordinate the layers so that:

* important accents remain perceptible;
* excessive simultaneous hits are avoided;
* complementary rhythmic spaces are created;
* gradual phase movement produces long-term variation;
* the result remains reproducible for a fixed random seed.

The rhythm engine treats each percussion part as an independent cyclic process that is optimized relative to the other active layers.

---

## 2. Drum Layers

The default drum configuration contains four layers:

```text
kick
snare
hat
perc
```

Each layer owns the following parameters:

```text
steps
pulses
rotation
phase
phase_rate
velocity_pattern
probability_pattern
accent_pattern
cycle_length
transition_interval
```

Recommended initial ranges:

| Layer | Steps | Pulses | Typical role                                   |
| ----- | ----: | -----: | ---------------------------------------------- |
| Kick  | 12–16 |    3–6 | Low-frequency pulse and metric anchor          |
| Snare | 12–16 |    2–5 | Backbeat, counter-accent, structural marker    |
| Hat   |  8–17 |   6–13 | Subdivision, continuity, high-frequency motion |
| Perc  |  9–19 |    3–9 | Syncopation, irregular accents, phase contrast |

These ranges are defaults rather than hard constraints.

---

## 3. Base Pattern Generation

Each layer first generates a base binary pattern.

Supported generators include:

* Euclidean rhythm;
* manually supplied pattern;
* probabilistic pattern;
* state-graph-derived pattern;
* transformed pattern from another layer.

A binary pattern is represented as:

```text
1 = hit
0 = rest
```

Example:

```text
kick = 1001001000100000
```

Euclidean generation uses:

```text
pattern = E(steps, pulses)
```

The generated pattern is normalized so that a hit begins at index zero before layer-specific rotation is applied.

---

## 4. Rotation

Rotation determines the static starting offset of a cyclic pattern.

For a pattern (P) of length (N):

```text
rotate(P, r)[i] = P[(i-r) mod N]
```

A positive rotation moves the pattern to the right.

Rotation is selected independently for each layer.

The kick should normally retain a stable metric anchor, while snare, hat, and percussion may be rotated more freely.

Recommended defaults:

```text
kick.rotation = 0
snare.rotation = optimized
hat.rotation = optimized
perc.rotation = optimized
```

The kick may also be rotated when the composition explicitly requests metric ambiguity.

---

## 5. Global Alignment Grid

Layers may have different cycle lengths.

To compare their relative hit positions, patterns are projected onto a shared analysis grid.

The grid length is:

```text
analysis_length = lcm(layer cycle lengths)
```

Example:

```text
kick  = 16 steps
snare = 15 steps
hat   = 13 steps
perc  = 17 steps
```

The full least common multiple may be very large. Therefore the optimizer may use a bounded analysis window:

```text
analysis_length = min(
    lcm(cycle lengths),
    configured maximum analysis steps
)
```

Recommended maximum:

```text
256–1024 steps
```

Patterns are repeated cyclically across the analysis window.

---

## 6. Collision Types

A collision occurs when multiple layers produce hits at the same analysis-grid position.

Collisions are not always undesirable. Some combinations reinforce the groove, while others reduce clarity.

The engine distinguishes the following collision types.

### 6.1 Kick–Snare Collision

Simultaneous kick and snare hits produce a strong accent.

They should be:

* allowed at section boundaries;
* allowed at selected downbeats;
* discouraged when they occur too frequently.

### 6.2 Kick–Hat Collision

Kick and hat alignment is normally acceptable.

It can reinforce the pulse and does not require a strong penalty.

### 6.3 Kick–Percussion Collision

This is permitted occasionally but should be discouraged when percussion occupies a similar transient or low-frequency role.

### 6.4 Snare–Hat Collision

Usually acceptable, especially when the hat reinforces the snare accent.

### 6.5 Snare–Percussion Collision

Should be limited when both sounds function as strong mid-frequency accents.

### 6.6 Hat–Percussion Collision

Usually receives a low penalty unless both patterns are dense.

### 6.7 Four-Layer Collision

All four parts sounding simultaneously should be rare and reserved for:

* downbeats;
* section boundaries;
* fills;
* explicit climax events.

---

## 7. Rotation Optimization

For each non-anchor layer, the engine evaluates all possible rotations.

For a layer of length (N):

```text
candidate rotations = 0, 1, ..., N-1
```

Each candidate receives a score relative to already placed layers.

The best-scoring rotation is selected.

Recommended placement order:

```text
1. kick
2. snare
3. hat
4. percussion
```

This establishes the kick as the metric foundation and lets later layers fill unused rhythmic space.

An alternative mode may evaluate all layer rotations jointly, but sequential optimization is the required initial implementation.

---

## 8. Rotation Score

For candidate rotation (r), define:

```text
RotationScore(r)
=
w_anchor × AnchorScore
+
w_complement × ComplementScore
+
w_syncopation × SyncopationScore
+
w_balance × BalanceScore
+
w_repetition × RepetitionScore
-
w_collision × CollisionPenalty
-
w_density × DensityPenalty
-
w_cluster × ClusterPenalty
```

Higher scores are preferred.

---

## 9. Anchor Score

The anchor score rewards musically important alignments.

Examples:

* kick on the main downbeat;
* snare near configured backbeat positions;
* hat accents on beat subdivisions;
* percussion accents near phrase boundaries.

For a 16-step bar, typical target positions may be:

```text
downbeats = {0, 4, 8, 12}
backbeats = {4, 12}
offbeats  = {2, 6, 10, 14}
```

These positions are configurable and must not be hard-coded into the generic rhythm engine.

The score is calculated from the distance between actual hits and target positions.

---

## 10. Complement Score

The complement score rewards hits that occur where other layers are silent.

For candidate layer (L):

```text
ComplementScore
=
number of candidate hits occurring on currently empty steps
/
number of candidate hits
```

Optional weighted complement:

```text
empty step after kick      → medium reward
empty step after snare     → high reward
empty step between hats    → low reward
```

This encourages interlocking rhythms rather than duplicated patterns.

---

## 11. Collision Penalty

For each analysis step, calculate all simultaneously active layers.

Example penalty weights:

```text
kick + snare         = 0.5
kick + hat           = 0.1
kick + perc          = 0.4
snare + hat          = 0.1
snare + perc         = 0.5
hat + perc           = 0.2
kick + snare + perc  = 1.0
all four layers      = 2.0
```

These values are configurable.

Collision penalties may be reduced at:

* the first step of a bar;
* the first step of a section;
* explicit accent positions;
* generated fill positions.

---

## 12. Density Balance

The combined rhythm should not become uniformly dense.

For each local window, calculate:

```text
local density
=
number of active hits
/
number of possible layer-step positions
```

The optimizer penalizes windows exceeding the configured density target.

Example:

```text
window size = 4 steps
target density = 0.30
maximum density = 0.65
```

The penalty should grow nonlinearly after the target density is exceeded.

Suggested implementation:

```text
DensityPenalty = max(0, density - target_density)^2
```

---

## 13. Cluster Penalty

A cluster is a sequence of adjacent or nearly adjacent composite attacks.

Too many clustered attacks can obscure the Euclidean spacing.

For the combined onset sequence:

```text
combined[i] = 1 if any layer hits at i
```

Calculate inter-onset intervals.

Penalize:

* too many intervals of one step;
* repeated dense bursts;
* long sections with no contrasting space.

Cluster tolerance should be lower for minimalist sections and higher for fills or climaxes.

---

## 14. Syncopation Score

Syncopation is rewarded when a hit:

* occurs on a weak subdivision;
* is followed by silence on a stronger subdivision;
* anticipates a strong beat;
* does not destroy the main pulse.

The implementation may use a configurable metrical-weight vector.

Example for 16 steps:

```text
[4,1,2,1,3,1,2,1,4,1,2,1,3,1,2,1]
```

A simplified syncopation score may reward hits on low-weight steps that are followed by rests or sustained silence on higher-weight steps.

The initial implementation does not need a full musicological syncopation model, but its behavior must be deterministic and documented.

---

## 15. Pattern Similarity Penalty

Different layers should not use nearly identical onset patterns unless explicitly configured.

Similarity may be measured using normalized Hamming similarity:

```text
similarity(A,B)
=
1 - hamming_distance(A,B) / pattern_length
```

For unequal pattern lengths, compare them on the shared analysis grid.

Recommended rules:

* kick and snare: strong similarity penalty;
* kick and percussion: medium similarity penalty;
* hat and percussion: low-to-medium similarity penalty;
* deliberate canon mode: disable the penalty.

---

## 16. Phase Shifting

Rotation is static. Phase shifting changes the offset over time.

Each layer owns:

```text
phase
phase_rate
phase_update_interval
phase_direction
```

The effective rotation at time (t) is:

```text
effective_rotation(t)
=
base_rotation + phase_offset(t)
```

A discrete phase process may use:

```text
phase_offset(section)
=
floor(section / update_interval) × phase_increment
```

Example:

```text
snare shifts by 1 step every 4 bars
hat shifts by 1 step every 3 bars
perc shifts by 2 steps every 5 bars
kick remains fixed
```

---

## 17. Continuous Phase Drift

An optional mode permits continuous phase drift.

Each layer is scheduled using its own effective step duration:

```text
effective_step_duration
=
base_step_duration × (1 + drift_rate)
```

Example:

```text
kick drift = 0
snare drift = +0.001
hat drift = -0.0007
perc drift = +0.0013
```

Continuous drift should be disabled by default because it can move events away from a discrete timeline and complicate MIDI export.

The discrete phase-shift mode is the required initial implementation.

---

## 18. Phase-Shift Constraints

Phase changes must preserve musical continuity.

A phase update should occur only:

* at a bar boundary;
* at a pattern-cycle boundary;
* at a state-transition event;
* at a configured structural point.

The maximum phase increment per update should normally be:

```text
1 or 2 steps
```

Larger phase jumps are reserved for fills or section transitions.

---

## 19. State-Transition Graph

Each layer may own a graph of related rhythmic patterns.

A node represents:

```text
pattern
rotation
accent profile
density
```

Edges connect states satisfying configured similarity constraints.

Default adjacency:

```text
Hamming distance = 1
```

Optional adjacency may permit:

```text
Hamming distance <= 2
rotation difference = 1
pulse-count difference = 1
```

The graph must remain connected for all states available to the random walk.

---

## 20. Coordinated State Transitions

Independent random walks may create abrupt global changes if all layers transition simultaneously.

The coordinator must therefore schedule transitions using staggered update intervals.

Example:

```text
kick transition every 8 bars
snare transition every 6 bars
hat transition every 3 bars
perc transition every 5 bars
```

At most one strong-accent layer should change state at the same boundary unless a structural transition is requested.

Strong-accent layers:

```text
kick
snare
```

High-frequency layers may change more frequently:

```text
hat
perc
```

---

## 21. Global Rhythm Score

After all layer rotations are selected, calculate a global score:

```text
GlobalRhythmScore
=
w_pulse × PulseClarity
+
w_interlock × Interlock
+
w_variation × Variation
+
w_syncopation × Syncopation
+
w_space × RhythmicSpace
-
w_collision × CollisionPenalty
-
w_density × DensityPenalty
-
w_similarity × LayerSimilarity
```

The generated rhythm may be rejected and regenerated if its score is below a configured threshold.

A maximum retry count must prevent infinite regeneration.

Recommended:

```text
maximum retries = 32
```

---

## 22. Suggested Default Configuration

```json
{
  "kick": {
    "steps": 16,
    "pulses": 5,
    "rotation": 0,
    "phase_increment": 0,
    "transition_bars": 8
  },
  "snare": {
    "steps": 16,
    "pulses": 3,
    "rotation": "optimize",
    "phase_increment": 1,
    "phase_update_bars": 4,
    "transition_bars": 6
  },
  "hat": {
    "steps": 13,
    "pulses": 8,
    "rotation": "optimize",
    "phase_increment": 1,
    "phase_update_bars": 3,
    "transition_bars": 3
  },
  "perc": {
    "steps": 17,
    "pulses": 6,
    "rotation": "optimize",
    "phase_increment": 2,
    "phase_update_bars": 5,
    "transition_bars": 5
  }
}
```

This default produces:

* stable kick anchoring;
* slower snare movement;
* active high-frequency phase motion;
* a longer irregular percussion cycle.

---

## 23. Determinism

All rotation optimization, state transitions, phase updates, velocity changes, and humanization must be reproducible with a fixed random seed.

The engine must use an injected random-number generator rather than global random state.

Example:

```python
rng = random.Random(seed)
```

or:

```python
rng = numpy.random.default_rng(seed)
```

---

## 24. Output Model

The rhythm generator returns:

```text
RhythmComposition
```

containing:

```text
layers
global timeline
phase events
state-transition events
tempo
seed
analysis metrics
```

Each event must include:

```text
instrument
start time
step index
velocity
duration
pattern state ID
phase offset
```

---

## 25. Analysis Metrics

The engine should expose:

* per-layer density;
* combined density;
* pairwise collision counts;
* four-layer collision count;
* pairwise Hamming similarity;
* average inter-onset interval;
* syncopation score;
* phase offsets over time;
* number of state transitions;
* generated pattern entropy.

These values should be available through the REST API and included in JSON exports.

---

## 26. Acceptance Criteria

The feature is complete when:

* four independent drum layers can be generated;
* non-anchor layers can be rotated by score optimization;
* simultaneous-hit penalties are configurable by layer pair;
* patterns with different cycle lengths can be analyzed together;
* phase shifts can occur at configurable structural intervals;
* each layer can traverse a rhythm-state graph;
* state changes are staggered across layers;
* identical seeds produce identical results;
* analysis metrics are returned;
* generated MIDI and WAV preserve the scheduled offsets and velocities;
* automated tests cover rotation, collision scoring, phase shifting, and determinism.
