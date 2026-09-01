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

### Project 1.2 compiler vertical slice

- direct-vector and rhythm-cell SongProgram compilation;
- contiguous form and clock lowering;
- realization repeats and rotate transforms;
- deterministic MaterialInstance IDs, semantic addresses, and Event IDs;
- half-even velocity and gate scaling;
- exact vector-ratio arithmetic and deterministic register placement;
- canonical Project ordering and authoritative minimal-direct golden equality;
- cross-process and `PYTHONHASHSEED` parity.

Implementation: `backend/app/songprogram/compiler.py`.

This vertical slice intentionally returns `UNSUPPORTED_COMPILER_SLICE` for
harmony, melody-intent, and drum compilation rather than introducing fallback
semantics.

## Not yet connected

The following remain required before the requested autonomous composition loop
is operational:

1. extend the compiler from direct vectors to drums, GEN0-A chord occurrences,
   GEN0-B progression selection, and chord-member melody;
2. implement the complete standalone Project 1.2 semantic validator and
   CompileReport/budget receipts;
3. generate canonical LineageIndex records during compilation and mutation;
4. derive descriptor and fingerprint payloads from actual Project 1.2 plus
   LineageIndex rather than pre-normalized inputs;
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

1. drum Project 1.2 lowering;
2. single-occurrence resolved harmony using GEN0-A;
3. multi-occurrence progression using GEN0-B;
4. LineageIndex generation;
5. Project-derived descriptor/fingerprint extraction;
6. typed Mutation application;
7. the replayable search-run orchestrator.

Each milestone should land with an authoritative golden, negative and boundary
fixtures, an independent oracle where identity bytes are involved, cache
parity where applicable, and cross-process byte equality.

## Relevant commits

- `7602196` — GEN0 SongProgram resolvers;
- `ce47b25`, `5639b07` — GEN0-B payload, budget, matching, and progression
  contract closure;
- `b3add2a`, `dbb01dc`, `fdce6ec` — GEN0-C catalog, render identity, per-track
  hashes, and integer renderer;
- `86a2594`, `52c197e`, `754c152` — GEN0-D contracts, run/search primitives,
  and fingerprint evaluation;
- `ee6b13e` — direct SongProgram to ArrangementProject 1.2 compiler slice.
