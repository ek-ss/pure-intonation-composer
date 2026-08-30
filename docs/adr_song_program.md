# SongProgram Architecture Decisions

## ADR-SP-001: Variable Equave

**Status:** accepted
**Decision date:** 2026-08-30

### Decision

`SongProgram 0.1` stores `lattice.equave` as a positive reduced ratio greater
than `1/1`. Conforming v0.1 compilers must support at least `2/1` and `3/1`.
Additional equaves are capability-gated and become part of the compiler build
identity.

Register placement, pitch-class reduction, sounding-pitch fingerprints, and
all equivalence calculations use the declared equave rather than assuming an
octave. Existing exporters that cannot preserve a non-`2/1` repeating interval
must declare the limitation in their compatibility projection instead of
silently octave-reducing it.

### Rationale

The project already includes both octave-based pure-intonation work and
Bohlen–Pierce `3/1` work. Fixing SongProgram to `2/1` would split the new
generative representation along an avoidable boundary.

### Acceptance tests

- equivalent `2/1` and `3/1` fixtures compile deterministically;
- equave exponent placement recomputes every final ratio exactly;
- pitch-class normalization and fingerprints differ correctly between the two
  equaves;
- an exporter either preserves the declared equave or returns an explicit,
  stable unsupported-capability error.

## ADR-SP-002: Calibrated Mutation Bands

**Status:** accepted
**Decision date:** 2026-08-30

### Decision

Mutation locality uses a versioned `MutationEvaluationProtocol`, separate from
the compiler. The compiler enforces dependency-scope locality; the evaluator
stores a distance vector rather than one scalar:

```text
event edit ratio, onset distance, pitch-cents distance, rhythm-histogram
distance, loudness distance, spectral distance, frozen-embedding distance
```

Human calibration uses a blinded, anchor-relative three-way judgment:
`smaller than anchor`, `similar to anchor`, or `larger than anchor`, with a
separate broken/not-broken question. Automated bounds are fitted from these
labels and are used only when all protocol, dataset, renderer, catalog, and
model hashes match. Ambiguous human cases are classified `uncertain`, never
automatically small.

### Rejected alternatives

- one embedding or weighted scalar hides materially different failure modes;
- automated metrics without human calibration confuse proxy distance with
  perceptual distance;
- human review on every mutation is too expensive for search.

### Acceptance tests

- dependency-closure leakage is zero;
- repeated human trials achieve within-rater weighted kappa at least `0.6` and
  ordinal inter-rater agreement at least `0.5`;
- the lower 95% confidence bound for automated `small` precision is at least
  `0.8`, with broken/large false acceptance at most `10%`;
- changing any protocol dependency invalidates the band rather than silently
  mixing measurements.

## ADR-SP-003: Immutable Instrument Catalog and Reference Renderer

**Status:** accepted
**Decision date:** 2026-08-30

### Decision

GEN0 uses one deterministic CPU reference renderer and a content-addressed
`InstrumentCatalog`. Entries record ID/version, engine, immutable asset
digests, role/range/polyphony, pitch policy, velocity response, tail duration,
parameter schema, and license/provenance. Missing or modified assets fail; no
fallback instrument is permitted.

The authoritative comparison format is 48 kHz with a fixed channel layout,
block size, resampler, summing order, and disabled dither. DAW/MIDI output is a
derived production artifact, not the evaluation renderer.

A frozen renderer-ceiling corpus contains focused human-authored fixtures for
drums/bass separation, chord/lead layering, sidechain/drop contrast, and
audible lattice tuning under both `2/1` and `3/1` equaves. Search evaluation
does not start until the renderer represents these properties adequately.

### Acceptance tests

- 100 repeated renders on the reference build have identical PCM hashes;
- cross-environment tolerances, if exact identity is unavailable, are declared
  in the render contract and include onset error no greater than one sample;
- all catalog entries pass non-silent, finite, unclipped smoke renders;
- changing one asset byte changes the catalog digest;
- blinded listeners recognize at least three of four intended production
  properties in at least three of four ceiling fixtures.

## ADR-SP-004: Project 1.2 Authority and Legacy Isolation

**Status:** accepted
**Decision date:** 2026-08-30

### Decision

Native `ArrangementProject 1.2` is the only authoritative SongProgram
phenotype. It uses strict validation, complete pitch/material/automation
provenance, and nullable `chord_index` for non-harmonic events.

Project 1.2 to 1.1 is a versioned lossy `CompatibilityProjection` carrying
source/projector hashes and a JSON-pointer loss manifest.

Existing 1.1 projects may be loaded only into a distinct
`LegacyProjectEnvelope` with `provenance_status: legacy_unverified`. This is
not a migration to native 1.2. It preserves timeline event cores for playback,
render regression, MIDI export, and old-generator baseline features. It is
forbidden as input to SongProgram reconstruction, mutation, lineage analysis,
lattice-provenance metrics, or the native QD archive.

### Acceptance tests

- native 1.2 validates and canonical-round-trips without hash change;
- every pitched native event recomputes its exact ratio from provenance;
- capability-supported 1.2-to-1.1 projection passes existing exporters and
  enumerates all losses; unsupported equaves return a stable error without
  silent conversion;
- 1.1-to-Legacy-to-1.1 preserves canonical clock/track/form/event cores;
- provenance-required APIs reject legacy input with `PROVENANCE_REQUIRED`;
- property tests demonstrate that no legacy artifact can enter a native QD
  archive.

## ADR-SP-005: Versioned Broad Sampler and Viability Gate

**Status:** accepted
**Decision date:** 2026-08-30

### Decision

GEN0 begins with `broad_prior_v1`, not a Kawaii-specific or LLM sampler. A
content-addressed `SamplerManifest` fixes discrete probability/weight tables,
named-choice algorithm, seed derivation, schema range, constraints, catalog
digest, and code digest. Every sample stores the manifest hash, root seed,
decision trace, and failures; failed candidates remain in the denominator.

Sampling order is form, materials, realizations, interactions, then production.
Roles are assigned as descriptive labels after structural choices. The prior
generates 3–8 sections/16–64 bars, 2–5 seed materials, at least three sounding
roles, and at least one non-identity transformed recall. No single permitted
choice receives all probability mass.

Minimum musical viability is separate from preference and genre quality. The
automatic gate checks compilation, section coverage, sounding-role count,
silence, register/polyphony, technical render validity, density change, and
transformed recall. A blinded human audit asks only whether intentional
repetition, formal segmentation/development, part coordination, and technical
listenability are present.

### Acceptance tests

- identical manifest and 1,000-seed cohort reproduce identical program hashes,
  traces, and failure ledger across processes;
- compile success is at least `95%`;
- automatic viability is at least `70%` initially and must reach `80%` before
  the LLM planner is introduced;
- blind audit false acceptance is at most `10%` and false rejection at most
  `15%`;
- exact duplicates are below `1%` and musical-fingerprint near duplicates are
  below `10%`;
- changing a distribution creates a new manifest/cohort rather than overwriting
  prior results.

## ADR-SP-006: Initial Quality-Diversity Coordinates

**Status:** accepted for GEN0; mandatory review after baseline cohort
**Decision date:** 2026-08-30

### Decision

The first archive uses two symbolic, renderer-independent axes:

1. `rhythmic_syncopation_q`: metrical-weighted foreground/drum offbeat activity;
2. `material_recurrence_distance_q`: ornament-resistant, normalized event-core
   distance between appearances with the same material lineage.

Each versioned `DescriptorSpec` fixes formula/code digest, input schema,
quantization, missing policy, calibration dataset, and bin edges. GEN0 starts
with a 5×5 archive. Descriptor values are integers `0..10000`.

`section_contrast_q` and `sounding_lattice_excursion_q` are mandatory audit
columns for every cell, not selection coordinates. Lattice excursion combines
declared-equave-reduced sounding cents and canonical lattice motion so
coordinate respelling cannot create diversity by itself.

This choice is diagnostic: it directly tests whether the new generator escapes
the current fixed rhythm and fixed material-development neighborhood. It is not
a claim that these two axes define musical quality.

### Rejected alternatives

- recurrence × section contrast can fill the archive while rhythm remains
  fixed;
- syncopation × lattice excursion can reward unrelated jumps and ignore
  introduction/development/recall;
- three or more initial axes are too sparse for the 1,000-candidate cohort.

### Acceptance tests and review trigger

- descriptor recalculation is byte-identical and invariant to IDs, velocities,
  instruments, production settings, and event array order;
- silent or extremely short ornaments cannot move recurrence bins;
- syncopation and recurrence metamorphic fixtures move only in the expected
  direction;
- the two axes have absolute Spearman correlation below `0.7`;
- at least 15 of 25 cells are occupied by viable candidates and no cell holds
  more than `20%` of them;
- every cell reports section-contrast and sounding-lattice-excursion
  distributions;
- after 1,000 candidates, replace an axis through a new ADR if either audit
  metric collapses into one bin in at least 75% of occupied cells or if blind
  review shows that archive coverage is being obtained through metric gaming.

## ADR-SP-007: Audible Pitch-Space Breadth

**Status:** accepted
**Decision date:** 2026-08-30

### Context

Earlier generators moved through lattice coordinates but used a narrow domain
and frequently produced few distinct equave-reduced sounding pitches. Raw
coordinate distance can also be inflated by alternate spellings, generator
dependencies, or nearly coincident pitch classes without increasing audible
microtonal variety.

### Decision

SongProgram separates four concepts:

1. coordinate-domain breadth;
2. exact equave-reduced sound classes;
3. perceptually merged near sound classes;
4. audible non-reference-grid exposure in the rendered composition.

The sampler first selects a collision-corrected sound class and then selects a
vector spelling. Coordinate count and L1 excursion are diagnostics only. They
never directly increase novelty, quality, or QD fitness.

`PitchExplorationPolicy` records finite point/complexity budgets, deterministic
near-class clustering, active-palette separation, an explicit comparison grid,
target distinct-class and audible-event-share bands, section-exposure and
recurrent-color requirements, and a sounding melodic-jump ceiling.

The default comparison grid is 12 equal divisions for `2/1` and 13 equal
divisions for `3/1`. It measures prominence relative to a familiar reference;
it does not quantize the generated pitches. Other grids require a new policy
hash and calibration cohort.

Different exact equaves and pitch-policy hashes form separate evaluation/QD
cohorts. Cross-cohort dashboards may show within-cohort percentiles but must not
place raw class count or entropy values into the same archive cells.

### Evaluation metrics

Project 1.2 stores and permits exact recomputation of:

- coordinate, exact-class, near-class, and used-class counts;
- coordinate-inflation ratio and collision count;
- used sound-class count as a descriptive value only;
- duration/accent/foreground-weighted audible-color share;
- exposure by section and maximum one-section concentration;
- recurrent non-unison color relations across phrases/sections;
- sounding-interval entropy;
- coordinate-axis span as a diagnostic only.

Color relations are clustered from equave-circular sounding interval distance,
not vector delta. Duplicate simultaneous events and near-identical spellings do
not increase exposure or entropy.

For finalists, the evaluator creates a matched reference-grid projection in
which only pitch is snapped. Timing, event identity, dynamics, articulation,
automation, instruments, and production remain identical. Evaluation separates:

- ABX distinguishability;
- musical-naturalness preference;
- genre-fit non-inferiority;
- automatic audio-distance vector.

Audibility alone is not success: an unpleasant or genre-damaging tuning can be
easy to distinguish.

### Acceptance tests

- equave shifts, generator-kernel spellings, input order, IDs, and register
  changes do not inflate sound-class count;
- adding near-collision points increases collision diagnostics but not audible
  class count or entropy;
- exact reduction is idempotent for `2/1` and `3/1`, and stored summaries
  recompute exactly from the class table/events;
- expanding coordinate bounds is accepted only if median near-sound-class count
  and sounding-interval entropy improve over the old-domain cohort;
- at least 80% of viable GEN0 candidates meet policy bands for distinct class,
  audible share, section exposure, recurrent relations, and entropy;
- median coordinate-inflation ratio is no greater than `1.5` and its 95th
  percentile no greater than `2.0`;
- a matched snapped projection changes pitch fields only;
- in a preregistered 30-pair, five-listener audit, ABX accuracy is at least
  `70%`, original genre-fit preference is non-inferior within 10 percentage
  points, and clearly worse musical naturalness occurs in fewer than `25%` of
  pairs.

### Review trigger

After the first 1,000-candidate cohort, reopen the policy if coordinate use
outside the legacy bounds rises but audible class/entropy distributions do not,
or if more than 20% of high-excursion blind-audit candidates are judged broken.

## ADR-SP-008: Scale-Free Joint Lattice Harmony

**Status:** accepted
**Decision date:** 2026-08-30

### Context

A fixed list of scale tones imposes an arbitrary cardinality and prevents a
broad lattice from supplying different locally appropriate chord realizations.
Conversely, independently snapping each 12-TET chord tone to its nearest lattice
pitch can destroy the relationships among the other voice pairs, introduce
duplicates, and produce unstable comma drift over a progression.

### Decision

SongProgram does not define a scale or scale-tone count. It defines a finite,
implicit `LatticeDomain` through generators, coordinate/register bounds, and
complexity/operation budgets. Points are enumerated lazily for concrete
harmony and melody queries.

Harmony is specified by `ChordIntent`. Its EDO steps describe target frequency
relationships; they are independent of the lattice domain's equave. A 12-TET
major chord therefore remains a `1 : 2^(4/12) : 2^(7/12)` target even when the
search domain uses a `3/1` equave. Failure to find a valid lattice realization
is explicit; the compiler never silently adds a `2/1` generator or changes the
target.

The chord resolver jointly compares the complete signed pairwise interval
matrix. It enforces per-pair and RMS recognition limits before applying softer
complexity, roughness, openness, or stylistic costs. Per-note nearest snapping
and post-selection single-note repair are forbidden.

The resolver removes common-translation symmetry by fixing the first relative
vector to zero, lazily indexes target-near difference vectors, and constructs
chords with deterministic branch-and-bound. Exact/near-collision spellings are
deduplicated for candidate weight.

Each intent retains multiple chord-shape/register/anchor candidates. A layered
Viterbi/beam search selects the progression by chord cost plus voice-leading,
bass motion, common tones, crossing, lattice complexity, recall consistency,
and comma drift. Thus locally optimal chords are not committed before their
progression context is known.

Melody is relational (`chord_member`, `neighbor`, `approach`) and resolved over
short phrase windows after harmony-path selection. Chord members share exact
vectors. Other notes are jointly evaluated against active/next harmony and
resolution intent. An unsatisfied phrase returns to another harmony candidate
or fails; it never uses nearest-pitch fallback.

### Determinism and budgets

Domain, intent, resolver build, numeric contract, weight profile, and budget
policy are content-addressed. Candidate/operation counts—not wall-clock
timeouts—bound search. Results state `exact` or `beam_bounded`; truncated or
failed results cannot masquerade as proven optima. Cache hit/miss may change
diagnostics but never the artifact hash or selected chord.

### Evaluation

Chord evaluation stores:

- full pairwise and maximum/RMS frequency error;
- recognition pass/failure;
- exact ratio and lattice provenance for every voice;
- complexity, roughness, openness, and collision measures;
- voice-leading, common-tone, bass, crossing, and comma-drift transition costs;
- candidate/search completeness and operation statistics;
- matched 12-TET chord-recognition and genre-fit comparisons for finalists.

No metric rewards the number of scale tones because no scale cardinality
exists. Used sound-class count remains descriptive only.

### Acceptance tests

- known 5-limit major/minor and suitable seventh fixtures are found within
  declared pairwise tolerances;
- all pair errors recompute from exact output ratios;
- target voice permutation/common transposition and lattice anchor translation
  obey their declared invariances;
- independent-nearest counterexamples are rejected or replaced by valid joint
  solutions;
- exact/near-collision spellings do not improve candidate rank or audible
  class/interval diversity;
- small-domain branch-and-bound results match exhaustive enumeration;
- increasing a containing domain/budget does not worsen the best objective for
  the same resolver version;
- fixed counterexamples demonstrate progression-path cost no worse than greedy
  local chord choice;
- common-tone comma movement is zero unless explicitly represented in event
  provenance;
- 10,000 intent sequences terminate deterministically within declared budgets
  with zero nearest-snap fallback events;
- compared with the legacy generator, a 1,000-song cohort increases sounding
  interval-tuple diversity without developing a sharp mode in per-song used
  sound-class count;
- matched listening tests retain the ADR-SP-007 audibility, naturalness, and
  genre-fit non-inferiority gates.
