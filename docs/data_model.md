# Data Model Specification

**Project:** Pure Intonation Composer

Version: 0.1

---

# 1. Overview

This document defines the canonical data model used throughout the project.

> **Status:** design specification. Ratios, scales, harmonic graphs, melody,
> bass, rhythm patterns, and render settings are implemented. Presets,
> effect chains, projects, and SQL storage are planned work. The REST API
> exchanges a practical subset of these models — see [api.md](api.md) for
> the exact wire shapes and [status.md](status.md) for implementation
> boundaries.

These models define the intended public and persistence boundaries. Internal
code currently uses a mix of dataclasses, Pydantic request models, and plain
response dictionaries that map to the implemented subset.

The models are independent of

* UI
* Storage
* REST API
* Audio Engine

---

# 2. Ratio

Represents one just-intonation pitch.

Fields

```text
id: UUID

numerator: int

denominator: int

frequency: float

cents: float

monzo: list[int]

octave: int

label: str
```

Example

```json
{
  "numerator":15,
  "denominator":8,
  "frequency":825.0,
  "cents":1088.27,
  "monzo":[0,1,1,0],
  "label":"15/8"
}
```

---

# 3. CPSDefinition

Defines one Combination Product Set.

```text
source_numbers

combination_size

harmonic

normalize_octave
```

Example

```json
{
 "source_numbers":[1,3,5,7,9,11],
 "combination_size":3,
 "harmonic":true
}
```

---

# 4. Scale

Collection of ratios.

```text
id

name

description

ratios[]

limit

generator
```

Example

```json
{
 "name":"Eikosany",
 "ratios":[...]
}
```

---

# 5. Chord

Represents one harmonic state.

```text
id

ratios[]

root

complexity

centroid

label
```

Example

```json
{
 "root":"1/1",
 "ratios":[
   "15/8",
   "21/16",
   "35/32"
 ]
}
```

---

# 6. HarmonicNode

Graph node.

```text
id

combination

chord

position

metadata
```

Example

```json
{
 "combination":[3,5,7]
}
```

---

# 7. HarmonicEdge

```text
source

target

shared_tones

harmonic_distance

monzo_distance

transition_cost
```

---

# 8. HarmonicGraph

```text
nodes[]

edges[]

generator

seed
```

---

# 9. MelodyNote

```text
pitch

start

duration

velocity

voice

articulation
```

---

# 10. MelodyTrack

```text
instrument

notes[]

pan

volume

mute
```

---

# 11. BassTrack

```text
strategy

notes[]

mirror_ratio

continuity_score
```

---

# 12. CompositionClock

```text
beats_per_bar

subdivisions_per_beat

tempo_bpm

bars

ticks_per_beat
```

---

# 13. CompositionTrack

```text
id

role

voice_index

chord_tone_index
```

---

# 14. CompositionRhythmGenerator

```text
target

strategy

profile

density

syncopation
```

---

# 15. RhythmicNoteEvent

```text
track_id

chord_index

ratio

start_tick

duration_ticks

velocity

articulation

source_layer
```

---

# 16. DrumHit

```text
instrument

step

velocity

probability
```

---

# 17. DrumPattern

```text
id

hits[]

cycle_length

phase

density
```

---

# 18. DrumState

```text
pattern

graph_node

transition_probability
```

---

# 19. RhythmLayer

```text
generator

cycle

phase

patterns[]
```

---

# 20. FormSection

```text
name

start

end

harmony_density

rhythm_density

mirror

tempo
```

---

# 21. Composition

Top-level object.

```text
metadata

scale

graph

form

tracks

tempo

seed
```

---

# 22. AudioPreset

```text
name

oscillator

harmonics

adsr

effects
```

---

# 23. EffectChain

```text
reverb

delay

chorus

compressor

eq
```

---

# 24. RenderSettings

```text
sample_rate

bit_depth

channels

normalize

dither
```

---

# 25. Project

Represents one saved project.

```text
name

version

composition

presets

history

created

modified
```

---

# 26. Metadata

```text
title

composer

seed

license

description
```

---

# 27. Serialization

Implemented exchange boundaries

* JSON request and response payloads
* Pydantic validation for REST request models
* Dataclass and dictionary serialization for the implemented domain objects
* Composition JSON export from the workbench

Planned persistence boundaries

* Versioned project JSON import, validation, and migration
* YAML only where a human-authored configuration format is useful
* SQLite or another on-disk store for local persistence
* PostgreSQL only if a remote multi-user deployment requires it

---

# 28. Validation

All ratios

* denominator > 0
* normalized into one octave

All graphs

* connected

All tracks

* sorted by start time

All UUIDs

* globally unique

---

# 29. Immutability

Musical objects are immutable.

Editing produces new objects rather than modifying existing ones.

---

# 30. Versioning

Every serialized file contains

```json
{
 "schema_version":"0.1"
}
```

Backward compatibility should be maintained whenever possible.

---

# 31. Genre Arrangement Models (Planned)

The genre arrangement pipeline adds the following versioned project models.
Their detailed contract is defined in
[development_plan_genre_arrangement.md](development_plan_genre_arrangement.md).

```text
BasicChord
  id
  name
  mode
  tones
  root_degree
  allowed_root_degrees
  tone_vectors
  tags

GenreProfile
  id
  display_name
  schema_version
  tempo_range
  allowed_meters
  default_form
  harmony
  rhythm
  parts
  arrangement
  render

ArrangementSection
  id
  role
  start_bar
  bars
  energy_start
  energy_end
  harmony_density
  part_presence

ArrangementProject
  schema_version
  metadata
  source_scale
  chord_vocabulary
  requested_profile
  resolved_profile
  seed
  form
  harmony_progression
  clock
  tracks
  events
  automation
  mix
  render_settings
  decision_trace
```

`ArrangementProject` extends the conceptual `Project` boundary rather than
introducing a second persistence format. Exact ratio and lattice-coordinate
provenance must survive JSON round-trips.
