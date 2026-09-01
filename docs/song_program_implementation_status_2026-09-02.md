# SongProgram Implementation Status — 2026-09-02

## Summary

The repository now contains deterministic production primitives for GEN0-A/B,
a GEN0-C integer renderer, GEN0-D search-artifact and fingerprint primitives,
and the first SongProgram-to-ArrangementProject 1.2 compiler vertical slice.
The checked-in contracts and conformance pack remain the authority. The system
does not yet provide an end-to-end broad-prior search loop.

The current backend suite passes `309` tests. Ruff, mypy, and `git diff
--check` pass. The working tree was clean when this status was recorded.

## Implemented

### Contracts and conformance data

- SongProgram 0.1 and strict ArrangementProject 1.2 schemas and contracts;
- exact numeric, budget-ledger, capability, GEN0-A, GEN0-B, GEN0-C, and GEN0-D
  contracts;
- golden, negative, boundary, cache-parity, and cross-process fixtures;
- content-addressed GEN0-C instrument catalog with fixed PCM32 assets for 2/1,
  3/1, and drums;
- closed sampler, descriptor, fingerprint, QD, planner, mutation, lineage, run
  record, checkpoint, render report, and catalog schemas.

### GEN0-A and GEN0-B

- exact ordered top-K joint chord resolution;
- exact layered progression search;
- injective voice matching, common-tone, crossing, voice-motion, comma-drift,
  and lattice-distance costs;
- self-contained candidate-core payload processing;
- deterministic tie-breaking and conformance-oracle comparison.

Implementation: `backend/app/songprogram/resolver.py`.

### GEN0-C

- integer-only Q1.31 sample renderer with half-even multiplication;
- pitched sample playback, Q32 phase, linear interpolation, loop and release;
- drum note-to-asset resolution;
- velocity, mapped-sample, kit/catalog, track-gain, and pan ordering;
- track/catalog polyphony enforcement and checked signed-int64 accumulation;
- final PCM32 stereo saturation and RIFF/WAVE construction;
- per-track PCM32 stereo-interleaved hashes, including silent tracks;
- typed catalog, asset, mapping, polyphony, and accumulator failures.

Implementation: `backend/app/songprogram/renderer.py`.

The renderer has deterministic vertical-slice coverage, but the complete
acceptance matrix from the GEN0-C contract—100 renders, block-size parity, and
every interpolation/release/pan boundary golden—has not yet been completed.

### GEN0-D primitives

- canonical artifact bytes and domain-separated manifest hashes;
- path-addressed sampler streams and weighted selection;
- canonical action IDs and sealed run-record identities;
- local content-addressed storage and framed append-only run records;
- deterministic QD champion and lineage-diverse runner selection;
- descriptor aggregation with half-even median handling;
- fingerprint component and full-record hashes;
- padded Hamming, set Jaccard, multiset Jaccard, and weighted near distance.

Implementation: `backend/app/songprogram/search.py`.

### Project 1.2 compiler

- direct-vector and rhythm-cell SongProgram compilation;
- drum-lane lowering with explicit note-map failures and GEN0-C rendering;
- single-occurrence resolved harmony through the production GEN0-A resolver;
- authoritative resolved-triad Project golden equality;
- contiguous form and clock lowering;
- realization repeats and rotate transforms;
- deterministic MaterialInstance IDs, semantic addresses, and Event IDs;
- half-even velocity and gate scaling;
- exact vector-ratio arithmetic and deterministic register placement;
- canonical Project ordering and authoritative minimal-direct golden equality;
- cross-process and `PYTHONHASHSEED` parity.
- compiler-origin LineageIndex with content-derived material lineage, Project
  artifact binding, and normalized identity/rotate transform edges;
- standalone direct, drum, and resolved-chord Project validation, including all
  checked-in Project negative cases;
- Project-derived descriptor and six-component musical fingerprint extraction.

Implementation: `backend/app/songprogram/compiler.py`.

The compiler still returns `UNSUPPORTED_COMPILER_SLICE` for melody-intent and
multi-occurrence progression lowering rather than introducing fallback
semantics.

## Not yet connected

The following remain required before the requested autonomous composition loop
is operational:

1. extend the compiler from single GEN0-A harmony occurrences to GEN0-B
   progression selection and chord-member melody;
2. implement the complete standalone Project 1.2 semantic validator and
   CompileReport/budget receipts;
3. extend canonical LineageIndex records through mutation-created material;
4. complete descriptor/fingerprint invariance and cross-process corpora;
5. implement all eight typed Mutation applications, dependency closure, locks,
   and locality/inverse tests;
6. connect sample, mutate, compile, render, evaluate, deduplicate, archive,
   checkpoint, and replay into one deterministic search runner;
7. add cache cold/hit and 1/2/4/8-process parity for the connected runner;
8. run the preregistered 1,000-seed viability/diversity gate;
9. add calibrated genre/listening evaluation before allowing perceptual metrics
   to influence acceptance;
10. connect the bounded LLM planner only after the non-LLM viability threshold
    reaches the contracted gate.

## Recommended implementation order

The next safe milestone is the compiler/validator layer:

1. multi-occurrence progression using GEN0-B;
2. chord-member melody lowering;
3. complete ResolvedChord metric replay in the standalone validator;
4. typed Mutation application;
5. the replayable search-run orchestrator.

Each milestone should land with an authoritative golden, negative and boundary
fixtures, an independent oracle where identity bytes are involved, cache
parity where applicable, and cross-process byte equality.

## Implemented milestone details (P1–P4)

The following work was identified as implementable without perceptual
calibration and is now present on `main`.

### P1 — Drum compiler lowering

Extend `compile_direct_sp0` into the next compiler capability slice:

- accept a `rhythm_cell` realization on a drums track;
- resolve every non-null rhythm `lane_id` through the track `drum_map`;
- emit Project 1.2 drum provenance with deterministic instance, semantic, and
  event IDs;
- apply rotate, repeat, velocity, gate, section bounds, event limits, and
  polyphony validation already used by the direct-note slice;
- reject missing lanes, pitched material on a drums track, and drum material on
  a pitched track with stable codes and JSON pointers.

Completion requires a drum golden, unmapped-lane negative, section-boundary
case, cross-process byte equality, and successful GEN0-C rendering against the
checked-in drum asset.

### P2 — Single-occurrence GEN0-A harmony lowering

Use the checked-in `minimal_triad_song_program.json` and
`resolved_triad_project.json` as the authoritative end-to-end target:

- build the exact resolver query from lattice, ChordIntent, root anchor, track
  range, and compiler manifest;
- call the production GEN0-A resolver and select its first canonical core;
- construct ResolvedChord, one HarmonyOccurrence, and chord-voice events;
- recompute intent/domain/chord/event identities independently;
- produce bytes identical to the stored triad Project and expected sidecar.

Completion requires golden equality, no-solution and budget-exhaustion typed
failures, cache cold/hit parity, input-order invariance, and cross-process
equality. GEN0-B is not needed for this milestone.

### P3 — Standalone Project 1.2 validator

The schema and Project contract already define the required validation order.
Implement semantic validation separately from the compiler so generated and
externally supplied Projects follow the same path. Start with direct and drum
unions, then add ResolvedChord validation with P2. Completion requires every
checked-in `project_negative_cases.json` case to fail at its declared stage and
pointer, while both Project goldens pass 100 parse/serialize cycles.

### P4 — Compiler-produced LineageIndex

After P1/P2 establish all emitted-instance kinds, generate one canonical
LineageIndex beside Project and CompileReport. This unlocks Project-derived
descriptor/fingerprint extraction. Mutation-derived lineage edges remain a
later extension; the initial compiler path needs only source lineage roots and
identity transform edges.

P1 through P4 are now implemented by `749d3d9` and `a239253`. The connected
search runner should not begin until the remaining Mutation semantics below are
closed and GEN0-B compiler lowering has golden equality.

### Current specification blockers

- `rotate_rhythm.parameters.steps` does not define whether one step is an
  ordinal permutation, a fixed tick grid, or a rhythm-derived quantum. Typed
  Mutation application cannot implement this operation without changing its
  musical meaning.
- `replace_distribution_choice` does not map each `(owner_kind,field,choice_id)`
  tuple to an authoritative SongProgram value source.
- mutation-created LineageIndex roots need an exact creating-action preimage
  and transform-edge operation encoding.

These three items should be resolved together before implementing the eight-op
Mutation applicator. Sampler-to-complete-SongProgram construction also remains
separate from the currently implemented deterministic choice-stream primitive.

## Relevant commits

- `7602196` — GEN0 SongProgram resolvers;
- `ce47b25`, `5639b07` — GEN0-B payload, budget, matching, and progression
  contract closure;
- `b3add2a`, `dbb01dc`, `fdce6ec` — GEN0-C catalog, render identity, per-track
  hashes, and integer renderer;
- `86a2594`, `52c197e`, `754c152` — GEN0-D contracts, run/search primitives,
  and fingerprint evaluation;
- `ee6b13e` — direct SongProgram to ArrangementProject 1.2 compiler slice.
- `749d3d9` — drum and GEN0-A harmony lowering, Project validation, and
  compiler-origin LineageIndex;
- `a239253` — Project-derived descriptor and fingerprint evaluation.
