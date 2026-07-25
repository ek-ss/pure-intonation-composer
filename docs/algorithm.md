# Algorithm Specification

**Project:** Pure Intonation Composer

Version: 0.1

---

# 1. Overview

This document specifies the musical algorithms used by the Pure Intonation Composer.

> **Status:** design specification. The CPS/Euler–Fokker generators, harmonic
> graph, transition scoring, bass/melody/voice-leading engines, Euclidean
> rhythm, state graphs, phase shifting, humanization, and Compose-native
> Semi-Markov/interlocking rhythm are implemented. The form generator, global
> texture-density conductor, and spatialization are planned work. See
> [status.md](status.md) for the audited boundary.

Unlike conventional DAWs or algorithmic composition systems based on equal temperament, this project defines music as motion through harmonic state spaces generated from integer frequency ratios.

Every musical layer is represented as a state machine.

The complete composition emerges from interactions between independent state machines.

---

# 2. Global Composition Model

The composition consists of five independent generators.

```
Harmony
Bass
Melody
Rhythm
Form
```

Each generator evolves independently while exchanging contextual information with the others.

The conductor synchronizes timing but does not dictate musical content.

---

# 3. Harmonic Space

The harmonic space is generated from

* Combination Product Sets (CPS)
* Euler–Fokker genera

Each harmonic state is represented as

```
State

S = {r1,r2,r3,...}
```

where each ri is a normalized frequency ratio.

Ratios are always normalized into

```
1 ≤ ratio < 2
```

to represent pitch classes.

---

# 4. Harmonic Graph

Each harmonic state becomes one graph node.

Example

```
Node

(3,5,7)
```

Edges connect states that differ by exactly one integer.

For CPS(6,3), the resulting graph is the Johnson Graph J(6,3).

Edge weights are computed from

* harmonic distance
* Monzo distance
* shared tones
* cent displacement

---

# 5. Harmonic Transition

For every composition step

```
Current Node

↓

Candidate Nodes

↓

Score

↓

Choose Next Node
```

Transition score

```
Score

=

α HarmonicSimilarity

+

β SharedToneCount

+

γ Simplicity

−

δ LargeLeapPenalty

+

ε Randomness
```

The weights are configurable.

Randomness prevents repetitive cycles.

---

# 6. Harmonic and Subharmonic Duality

Every harmonic state possesses a mirrored subharmonic state.

Example

```
15/8

↓

16/15
```

The mirror transformation is

```
Mirror(r)

=

2^k / r
```

where k is chosen to normalize the ratio into one octave.

The form generator may continuously interpolate between harmonic and subharmonic spaces.

---

# 7. Bass Generator

The bass does not simply double the chord root.

Instead it stabilizes movement between harmonic and subharmonic spaces.

Candidate bass notes include

* mirrored ratios
* roots
* fifths
* octave equivalents
* low-complexity ratios

Score

```
Score

=

w1 Simplicity

+

w2 Continuity

+

w3 HarmonicSupport

−

w4 JumpPenalty

−

w5 RegisterPenalty
```

Register optimization seeks the lowest usable octave while avoiding excessive muddiness.

---

# 8. Melody Generator

Melody voices include

* strings
* choir
* solo instruments

Each voice performs an independent random walk inside the current harmonic state.

Constraints

Maximum leap

Common tone preference

Voice crossing forbidden

Phrase memory

Cadential attraction

The melody is generated from graph traversal rather than scale traversal.

---

# 9. Voice Leading

Voice leading minimizes total movement.

Cost

```
VoiceCost

=

Σ

CentDistance

+

LeapPenalty

+

CrossingPenalty
```

The optimal assignment is found using the Hungarian algorithm.

---

# 10. Rhythm Generator

Rhythm is independent from harmonic progression.

Each percussion layer possesses

```
Pattern

Cycle Length

Phase

Velocity Profile
```

Implemented drum processes

* Euclidean rhythm
* manual pattern editing
* Hamming-distance state graphs
* discrete phase offsets
* seeded timing/velocity humanization

Implemented Compose pitch-rhythm processes

* transition-aware harmonic durations
* seeded Semi-Markov onset generation
* interlocking onset allocation
* experimental ratio-derived cycles

Coordinated state transitions, fills, and preset libraries remain planned.

---

# 11. Drum State Graph

Each drum pattern is one node.

Example

```
Kick

1000100010001000
```

Edges connect patterns whose Hamming distance equals one.

Weighted random walks gradually transform rhythms without abrupt changes.

---

# 12. Phase Shifting

Every rhythmic layer owns an independent cycle length.

Example

```
Kick      16

Snare     15

Hat        13

Perc       17
```

Because the least common multiple is large, the complete rhythmic texture evolves continuously over long durations.

Optional tempo-independent phase drift may also be enabled.

---

# 13. Form Generator

The form generator controls macro-scale evolution.

This remains planned. Its first concrete implementation is specified by the
[Genre Arrangement Pipeline](development_plan_genre_arrangement.md), which
adds exact section lengths, energy curves, genre profiles, and locked-section
regeneration.

Candidate forms

ABA

ABACA

Through-composed

Minimal Process

Continuous Transformation

Each section defines

Harmony Density

Rhythm Density

Instrument Density

Mirror Ratio

Tempo

Register

Dynamics

---

# 14. Texture Density

Texture is represented by a continuous value

```
Density

0.0

↓

1.0
```

Density controls

Number of active voices

Rhythmic activity

Chord complexity

Register width

Dynamic level

---

# 15. Humanization

Small random deviations improve realism.

Pitch

±2 cents

Timing

±5 ms

Velocity

±5%

Envelope

±10%

These parameters are configurable.

---

# 16. Spatialization

Each voice owns

Pan

Distance

Reverb Send

Delay Send

Future versions may map harmonic graph coordinates directly into spatial positions.

---

# 17. Audio Rendering

Supported oscillators

Sine

Triangle

Saw

Square

Additive

Future support

FM

Noise

Physical modeling

Sample playback

Granular synthesis

---

# 18. Rendering Pipeline

```
Harmony

↓

Bass

↓

Melody

↓

Rhythm

↓

Mixer

↓

Effects

↓

Master

↓

WAV

MIDI

Scala
```

---

# 19. Determinism

Every composition is reproducible.

The random seed is stored together with

* generator parameters
* tuning definition
* graph definition
* instrument presets

Identical inputs must always produce identical outputs.

---

# 20. Future Research

Possible extensions include

* reinforcement learning for transition weighting
* adaptive harmonic distance metrics
* graph neural networks
* real-time performer interaction
* OSC synchronization
* MPE support
* distributed composition
* spectral harmony analysis

The architecture intentionally separates mathematical representation, composition logic, and audio rendering to facilitate future research.
