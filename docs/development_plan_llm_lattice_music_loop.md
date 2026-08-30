# LLM-Driven Lattice Music Generation Loop

**Project:** Pure Intonation Composer
**Status:** design proposal

## 1. Objective

A user supplies a genre description such as `kawaii future bass`. The system
then generates exact-ratio music from an exponent lattice, renders it, evaluates
both its genre-level listening experience and its lattice-music integrity, and
continues revising candidates until a declared stopping policy is satisfied.

The target is similarity of listening experience and production grammar, not
reproduction of a particular copyrighted recording. Artist or track names may
be accepted as analysis references, but prompts, stored features, and evaluation
reports should be converted into abstract attributes such as form, energy,
rhythmic density, timbre, register, contrast, and spatial character.

## 2. Core Principle

The LLM is a planner and critic, not the note renderer and not the sole judge.

```text
genre brief
  -> LLM: structured GenreIntent + experiment proposal
  -> deterministic lattice-constrained composer
  -> canonical Project JSON
  -> WAV preview + MIDI/stems
  -> symbolic checks + audio feature models + listening rubric
  -> score, diagnostics, and comparison with the current champion
  -> LLM: one bounded revision
  -> repeat
```

All pitched events must retain exact ratios and lattice coordinates. The LLM
may choose parameters, profiles, and mutation operations, but may not emit an
unvalidated free-form note list directly into the canonical project.

## 3. Current Generator Is Not a Sufficient Search Space

The present Kawaii generator is useful as a regression fixture and export
demonstration, but it must not be used as the population generator for this
project. Its musical choices are mostly constants:

- one fixed section template;
- four fixed root-degree cycles per section role;
- one staged Drop voicing sequence;
- fixed drum onsets for each role;
- one fixed eight-degree vocal hook;
- fixed comping, sparkle, bass, and sidechain gestures;
- a fixed five-instrument role map.

Changing the seed therefore changes mostly velocities, phrase omissions, and
small selections inside the same composition. Generating more seeds does not
create meaningful musical breadth. The Composition Explorer broadens this to
several hand-written grammars and patterns, but it still searches a finite
template neighborhood.

This changes the project order: **build a generative representation with a
large, navigable search space before building the optimization loop**. An
evaluator cannot recover material that the generator is incapable of
expressing.

## 4. Reuse From the Current Repository

Reuse the existing components as validators, primitives, and exporters rather
than treating the current song generators as the new inner engine:

- exponent-lattice primitives and exact-ratio validation (the new generator
  searches a finite lattice domain directly rather than fixing a scale size);
- genre arrangement metrics and profile vocabulary;
- Kawaii Fractional Future Pop as one baseline preset and regression fixture;
- Composition Explorer candidate generation and interpretable scores;
- seeded Project JSON, MPE-oriented MIDI, and bounded WAV rendering;
- exact-ratio membership and event-bound validators.

The main missing capability is a hierarchical generative representation.
Rendered-audio evaluation, an experiment store, bounded automatic mutation,
and an LLM orchestration layer come after it.

## 5. Generative Representation

This section is a long-term architecture target, not the normative SP0/GEN0
implementation contract. SP0 and early GEN0 use the linear, non-nesting subset
defined in [song_program_spec.md](song_program_spec.md). General graphs, nested
operators, InteractionGraph generation, and ProductionGraph search require
later ADRs after the exact compiler core is frozen.

Represent a composition as a program/graph rather than a filled note grid or
a choice among complete templates. It has four independently transformable
levels:

```text
SongProgram
  FormGraph          sections, returns, interruptions, transitions
  MaterialGraph      motifs, chords, lattice regions, transformations
  InteractionGraph   rhythmic roles, call/response, masking, sidechain
  ProductionGraph    instruments, layers, effects, automation, spatial motion
```

### FormGraph

Generate variable-length directed form graphs with constraints instead of
choosing from four arrays. Nodes carry duration and energy trajectories; edges
can repeat, vary, compress, expand, interrupt, or recall previous material.

### MaterialGraph

Start from several short latent musical objects, not a full-song template:

- rhythmic cells with rests, tuplets, ties, swing, and accent hierarchy;
- melodic contours separated from their concrete pitches;
- chord/set objects represented by lattice coordinates;
- bass-motion and countermelody objects;
- timbral gestures and automation envelopes.

Derive phrases through composable operators: transpose in lattice space,
invert, rotate, augment, diminish, fragment, interpolate, reharmonize, displace,
substitute, ornament, thin, stack, and cross-map rhythm to pitch. Operators are
parameterized and may be nested, producing a much larger space than enumerated
patterns while retaining ancestry and reproducibility.

### InteractionGraph

Generate relationships before individual notes: lead/support, call/response,
unison/divergence, onset avoidance, density exchange, kick/bass interlock, and
foreground/background turnover. Parts are realized from these constraints so
they do not sound like independent pattern generators layered together.

### ProductionGraph

Genre identity depends heavily on sound and mix behavior. Search must include
instrument/sample selection, synthesis macro states, octave/register, layer
count, envelope, distortion, filtering, reverb/delay sends, stereo width,
sidechain shape, transition effects, and section-level automation. MIDI-only
variation is not an adequate search space for Kawaii Future Bass.

The concrete score compiler remains deterministic and validates every proposed
program. The LLM can construct or revise graphs using a typed DSL, but cannot
write arbitrary executable code.

## 6. Search-Space Requirements

Before adding an LLM, benchmark the generator itself:

- sample at least 1,000 low-cost symbolic candidates;
- reject exact and near duplicates using event fingerprints and feature-space
  distance;
- measure coverage across form, rhythm, harmony, melody, interaction, and
  production features;
- require seed changes to alter phrase identity and section development, not
  only velocity or note omission;
- compare within-seed mutations against between-seed diversity;
- maintain an archive with quality-diversity search such as MAP-Elites rather
  than immediately collapsing everything to one scalar optimum.

Useful behavior axes include syncopation, phrase entropy, repetition distance,
lattice displacement, consonance/roughness, drop contrast, foreground turnover,
spectral density, transient sharpness, and microtonal prominence. Empty archive
cells expose missing generator capabilities directly.

## 7. Proposed Development Environment

Keep the current Python/FastAPI backend and vanilla browser workbench. Add a
separate worker process so model calls and audio analysis never block the API.

```text
FastAPI / browser UI
  -> run coordinator
       -> planner adapter (LLM, structured JSON only)
       -> existing composition engine
       -> render worker
       -> evaluator worker
       -> SQLite experiment store + artifact directory
```

Recommended local-first components:

- Python 3.12 environment managed by the existing `pyproject.toml`;
- FFmpeg for deterministic preview conversion and loudness normalization;
- `librosa`/Essentia-style DSP for tempo, onset, spectral, loudness, and section
  features;
- an audio-text embedding model behind an adapter for genre similarity;
- SQLite for runs, candidates, scores, prompts, model/version metadata, and
  parent-child lineage;
- optional GPU worker for embeddings; CPU-only mode remains functional using
  symbolic and DSP scores;
- provider-neutral `Planner` and `AudioEmbedder` protocols, allowing local or
  hosted models without changing the composition core.

Do not make a DAW the control plane in the first implementation. Generate short
16- or 32-bar previews in-process, then export the winning project to Vital or a
DAW for final sound design. Full-song rendering on every iteration is too slow
for useful search.

## 8. Contracts

### GenreIntent

The planner must return schema-validated JSON:

```text
GenreIntent
  genre_label: str
  genre_version: str
  bpm_range: [float, float]
  form_roles: list[str]
  energy_curve: list[float]
  rhythm:
    syncopation: float
    half_time_probability: float
    subdivision_density: float
  harmony:
    stability_target: float
    roughness_target: float
    chord_size_range: [int, int]
    lattice_motion_budget: int
  melody:
    register: [int, int]
    repetition: float
    phrase_space: float
  production:
    sidechain_depth: float
    transient_brightness: float
    stereo_width: float
    spectral_density: float
  forbidden_imitation: list[str]
```

### CandidateGenome

Only expose bounded, meaningful variables to the LLM:

```text
CandidateGenome
  song_program_hash: str
  locked_nodes: list[str]
  mutation_lineage: list[str]
  mutation_protocol_version: str
```

Every change is represented as a typed mutation such as
`adjust_syncopation`, `replace_drop_voicing`, `change_lattice_bound`, or
`regenerate_section`. This makes failures replayable and prevents prompt drift.

### EvaluationReport

```text
EvaluationReport
  hard_constraints:
    exact_ratio_membership: bool
    valid_lattice_coordinates: bool
    no_clipping: bool
    event_bounds_valid: bool
  scores:
    genre_audio_similarity: float
    structural_fit: float
    rhythmic_fit: float
    timbral_fit: float
    harmonic_coherence: float
    lattice_audibility: float
    novelty: float
    technical_quality: float
  confidence: map[str, float]
  diagnostics: list[str]
  suggested_mutations: list[Mutation]
```

No candidate with a failed hard constraint can become the champion.

## 9. Evaluation Strategy

Use an ensemble rather than asking an LLM whether audio is good.

1. **Symbolic validators** verify ratios, lattice coordinates, ranges, form,
   density, repetition, and section transitions.
2. **DSP metrics** measure tempo agreement, onset density, crest factor,
   loudness, spectral centroid, low-end occupancy, stereo width, and contrast.
3. **Audio-text similarity** compares the preview with a descriptive genre
   prompt, not only the raw genre label.
4. **Reference-set similarity**, when legally supplied by the user, compares
   aggregate embeddings and feature distributions. Do not optimize against one
   track or keep copyrighted audio in the project store by default.
5. **Pairwise preference** compares challenger versus champion. Pairwise
   decisions are more stable than asking for an absolute quality score.
6. **Human ratings** periodically calibrate weights. Store `prefer A`,
   `prefer B`, and rubric-specific feedback rather than a single star score.

`lattice_audibility` is essential: a candidate can be genre-convincing while
the tuning difference is inaudible, or prominently microtonal while losing the
requested listening experience. Treat these as separate objectives and retain
a Pareto frontier before choosing one champion.

## 10. Loop and Stopping Policy

An infinite loop is unsafe and usually converges poorly. Interpret “continue
until generated” as a budgeted convergence loop:

```text
initialize N diverse candidates
evaluate and retain Pareto frontier
while budget remains:
  planner reads compact reports, not raw project JSON
  propose K bounded mutations across exploration/exploitation buckets
  generate, validate, render, and evaluate in parallel
  update frontier and champion
  stop if acceptance thresholds hold for two rounds
  stop if improvement is below epsilon for three rounds
return champion, frontier, diagnostics, and reproducible lineage
```

Suggested initial defaults:

- 8 initial symbolic candidates;
- render the best 4 as 30–45 second previews;
- at most 20 rounds or 60 rendered previews;
- accept only when hard constraints pass, genre score is at least 0.78,
  technical quality is at least 0.85, and lattice audibility lies in a
  user-selected target band;
- require two consecutive successful rounds;
- preserve the best candidate even if the run times out or is cancelled.

Thresholds are product defaults to calibrate with listening tests, not claims
of perceptual truth.

## 11. LLM Responsibilities

The planner may:

- translate a genre phrase into `GenreIntent`;
- select an initial lattice family and bounded search region;
- inspect score deltas and diagnostics;
- propose a small number of typed mutations;
- write a concise rationale and listening checklist.

The planner may not:

- bypass schema validation or exact-ratio constraints;
- declare success without evaluator thresholds;
- change more than a configured mutation budget per round;
- silently change locked sections, the reference set, or evaluation weights;
- use a living artist or single song as a direct imitation target.

## 12. User Interface

Add an `LLM Generation Lab` rather than hiding the loop behind one button:

- genre brief and optional abstract reference descriptors;
- lattice palette, prime basis, and “microtonal prominence” control;
- render budget, maximum rounds, and acceptance threshold;
- current champion audio beside challenger audio;
- score radar/table, confidence, and failed constraints;
- lineage graph showing mutations and seeds;
- lock buttons for form, harmony, rhythm, instrumentation, and individual
  sections;
- Pause, Stop and keep best, Reject direction, and Export winner controls.

## 13. Implementation Phases

### GEN0 — Search-space replacement

- complete the SP0-A/B/C gates in
  [song_program_review_2026-08-30.md](song_program_review_2026-08-30.md);
- freeze the minimal contract in [song_program_spec.md](song_program_spec.md)
  using the review process in
  [multi_agent_design_review.md](multi_agent_design_review.md);
- implement the linear, non-nesting SongProgram subset and exact joint-chord
  oracle before optimized search;
- extract existing harmony, rhythm, lattice, render, and export code as leaf
  primitives;
- add optimized resolver/progression search only after oracle equality;
- defer general form/material/interaction/production graphs to later
  capability milestones;
- add symbolic fingerprints, near-duplicate detection, and feature coverage;
- populate a quality-diversity archive from at least 1,000 cheap candidates;
- keep the current Kawaii generator only as a baseline cell in that archive.

GEN0 is a gate. Do not begin automatic LLM optimization until generated
candidates occupy a meaningfully broad feature map and human review confirms
that different regions sound structurally different.

### LLM1 — Offline loop without an LLM

- define `GenreIntent`, `CandidateGenome`, `Mutation`, and `EvaluationReport`;
- wrap the existing Kawaii generator and renderer;
- implement hard constraints and DSP scores;
- add SQLite/artifact persistence and resumable run state;
- run deterministic random/evolutionary search.

This phase validates that the objective function can distinguish useful
candidates before model-call cost is introduced.

### LLM2 — Structured planner

- add the provider-neutral planner adapter;
- require JSON-schema output and reject unknown mutation types;
- pass compact score deltas and diagnostics to the planner;
- record prompts, responses, model id, schema version, and latency;
- fall back to deterministic search after planner errors.

### LLM3 — Audio embeddings and pairwise evaluation

- add audio-text embeddings behind an optional worker;
- build a licensed/internal genre reference set;
- add challenger/champion comparison and Pareto selection;
- calibrate thresholds with blinded listening sessions.

### LLM4 — Interactive lab and section regeneration

- add WebSocket/SSE progress events and cancellation;
- implement preview comparison, locks, and lineage UI;
- regenerate only the weak section and re-evaluate joins;
- export the champion Project JSON, MIDI, WAV, stems, and evaluation report.

## 14. Acceptance Criteria for the First Useful Release

- the same run configuration and model-independent fallback seed reproduce the
  same candidate lineage;
- every winning pitched event maps to an allowed exact ratio and lattice
  coordinate;
- a failed render or model response cannot terminate or corrupt the run;
- cancelling a run leaves a playable best candidate;
- the loop improves its declared objective over the initial population in a
  fixed benchmark suite;
- human listeners can identify the target genre above a calibrated baseline;
- listening tests separately report genre fit, musical preference, and
  perceptibility/appropriateness of the lattice tuning;
- all model, profile, evaluator, and prompt versions are stored with the run.
- the generator passes explicit diversity and duplicate-rate thresholds before
  evaluation-loop acceptance is considered;
- at least several distinct successful construction paths reach the same broad
  genre target, rather than one template family dominating all winners.

## 15. Immediate Recommendation

Start with GEN0, not LLM1. Treat `kawaii_future_pop` as a negative-control
baseline: generate many seeds and quantify how little its fingerprints and
feature vectors differ. Then replace the fixed song template with `SongProgram`
and demonstrate broad coverage with cheap symbolic rendering. Only after that
should 30–45 second audio previews, perceptual evaluation, or an LLM planner be
introduced.
