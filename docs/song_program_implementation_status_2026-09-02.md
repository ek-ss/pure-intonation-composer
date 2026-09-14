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

Historical note: at this checkpoint the compiler returned
`UNSUPPORTED_COMPILER_SLICE` for melody-intent and multi-occurrence progression
lowering. That limitation was removed by the later GEN0-B work recorded in the
2026-09-12 continuation below.

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
search runner should not begin until the Mutation applicator has conformance
coverage and GEN0-B compiler lowering has golden equality.

### Recently closed Mutation specifications

- `rotate_rhythm.parameters.steps` is a displacement over an invariant
  rhythm-derived GCD quantum, with an exact inverse rule;
- `replace_distribution_choice` resolves through a content-addressed
  MutationChoiceCatalog bound by Search RunManifest 1.2;
- mutation-created LineageIndex roots use the action, mutation, creation
  ordinal, and canonical material core; mutation edges have a closed string
  encoding and sort order.

These decisions, their schemas, and fixed preimage fixtures are now ready for
the eight-op Mutation applicator. The complete normative application order,
actual dependency roots, root-exact lock behavior, eight operation effects,
Project invalidation, lineage behavior, and failure priority are now fixed in
`song_program_mutation_application_contract.md`; the former Mutation semantic
specification blocker is closed. Sampler-to-complete-SongProgram construction
remains separate from the deterministic choice-stream primitive.

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

## 2026-09-12 continuation

The earlier “Not yet connected” list is historical. GEN0-B progression,
chord-member melody, all eight typed mutations, mutation-created lineage,
Structural Sampler 1.1, and the Structural-to-production handoff are now
implemented. SearchLoop13 contracts now also close genre calibration,
planner/patience authority, fixture graph traversal, parallel scheduling,
cancellation arrival barriers, and bootstrap rank validation.

Production additions landed in:

- `4654f3c` — typed Mutation and GEN0-B compiler connection;
- `ebe1886` — Structural Sampler 1.1 and production handoff;
- `be2f5ba` — calibration/parallel/cancellation cross-field validators.
- `cb74d95` — read-only FixtureSuiteIndex path/raw/schema/case/coverage validator.

The current test baseline is 464 passing tests for `backend/tests` plus
`backend/songprogram_conformance` (the read-only guard is run separately), and
15 passing read-only/structural/production focused tests after commit.

The next normative milestone is the complete SearchLoop13 runner. Its contract
is closed, but implementation acceptance is intentionally blocked until an
independent-oracle owner checks in the first authoritative
`SearchLoop13 FixtureSuiteIndex 1.0` and referenced case/schema/CAS bytes. The
production implementer MUST NOT synthesize or update those expected roots.
The suite validator is now implemented and can authenticate independently
provided case/schema bytes without generating expected outputs. Once the
authoritative suite is present, implementation order is RunContext factory,
event scheduler/replay, connected cache, then the 1/2/4/8 worker parity matrix.

## 2026-09-13 PIL continuation

The parallel Perceptual Interpretation Layer is implemented through Phase 4
(pitch projection, segmentation, chord similarity, voice matching and
trajectory similarity) without replacing Native JI evaluation. The following
oracle-facing implementation is now also present:

- closed PIL OracleSuiteIndex, OracleCase and MatrixReceipt schemas;
- raw case/schema byte closure, case/suite hashes and exact coverage checks;
- phase-exact asset and manifest binding validation;
- seventeen non-authoritative input templates compiled through the production
  SongProgram compiler into standalone-valid ArrangementProject 1.2 payloads;
- exact coverage of all twenty-five required Phase 1--4/cache/process labels;
- read-only expected report comparison and cold/hit/corrupt cache parity;
- fresh-interpreter `PYTHONHASHSEED` and 1/2/4/8 suite-concurrency matrix with
  canonical case-order restoration and a content-addressed receipt.

The backend plus conformance suite passes 537 tests. The remaining authority
boundary is intentional: an independent oracle owner must promote expected
report/case/suite hashes. Production code cannot synthesize those values.
Draft 2020-12 case-schema validation remains an explicit caller callback because
the runtime dependency set does not contain a pinned JSON Schema engine; no
ambient or partial schema implementation is silently selected.

## 2026-09-13 PIL oracle promotion and open-decision drafts

The authoritative PIL oracle suite is now promoted
(`backend/songprogram_conformance/fixtures/pil_oracle/`, commit `0a39ba9`).
Since then the implementation side added only non-authoritative support
material:

- two more input templates after promotion: `pil_trajectory_overlap_windows`
  (two consecutive template-length windows, promoted with the suite) and
  `pil_12tet_major_chord` (near-12-TET major third resolving to the major
  template; subsequently promoted by oracle-maintainer commit `ab9f96e` and
  included in both suite index and matrix receipt), plus three required coverage
  labels (`segment_boundary`, `passing_tone_regression`,
  `native_ji_separation`) anchoring contract section 9 items 8, 3 and 6 —
  twenty-eight labels, all covered by the nineteen templates;
- read-only guard tools enforced by pytest:
  `tools/check_pil_contract_schema_hashes.py` (contract section 2 hash
  bindings vs schema pack vs implementation constants),
  `tools/check_pil_oracle_case_templates.py` (template pre-flight:
  binding validation, null goldens, coverage, index mirroring) and
  `tools/check_pil_genre_draft_consistency.py` (genre draft alignment);
- non-normative open-decision drafts for the remaining SPEC-BLOCKERs:
  `song_program_pil_genre_interpretation_draft.md` (G1–G7, with draft
  schemas and examples under `docs/pil_genre_draft/`),
  `song_program_pil_calibration_promotion_draft.md` (C1–C6),
  `song_program_pil_metric_id_registry_draft.md` (candidate metric IDs) and
  `song_program_pil_negative_pack_draft.md` (N1–N5);
- unit coverage for every 1.0 failure code
  (`tests/test_perceptual_failure_codes.py`), including section 4.3
  precedence checks; `PIL_GENRE_FAILED` remains blocked with Phase 5.

All PIL metrics remain audit-only: genre interpretation (G1–G7) and
CalibrationDecision promotion (C1–C6) are owner decisions, and no PIL metric
is connected to QD/archive/challenger/stopping.

## 2026-09-13 PIL Phase 5 authority closure and implementation

The owner closed every remaining PIL spec blocker: G1–G7 by the normative
`song_program_pil_genre_phase5_contract.md` (harmony-only launch profile,
build `pil.phase5.1.0.0`, closed integer scoring, authoritative oracle under
`fixtures/pil_genre_phase5/`), C1–C6 by
`song_program_pil_calibration_promotion_contract.md` (dotted `pil.*` registry
artifact, aggregations, `unavailable` missing policy, evidence closure), and
N1–N5 by the promoted `fixtures/pil_negative/pack.json`.

The production Phase 5 implementation is
`backend/app/songprogram/perceptual_genre.py`: model/feature-record binding
validation, harmony feature extraction from a successful Phase 4 report, the
five harmonic-detail scores plus typicality/idiomaticity/cliche/novelty,
canonical result hashing and ordering, and the Phase 5 cache with
cold/hit/corrupt byte parity. It is byte-exact against the independent
conformance oracle on the authoritative success and failure fixtures, and
cross-process `PYTHONHASHSEED` parity is tested
(`tests/test_perceptual_genre_phase5.py`). The earlier design drafts remain
as superseded history; the consistency checker now tracks the closure.

Every PIL metric — including the Phase 5 scores — remains audit-only: the
promotion-readiness artifact still reports `missing_external_authority` for
the calibration evidence chain, `pil.genre.*` promotion needs a future
decision version, and no PIL metric is connected to
QD/archive/challenger/stopping.

## 2026-09-14 PIL Phase 5 cross-process worker matrix

The production Phase 5 side now also executes the contract section 5
seed/concurrency matrix: `execute_genre_matrix` runs every case in a fresh
interpreter per `PYTHONHASHSEED` x worker-count coordinate (the worker
exercises cache cold, hit and corrupt runs internally) and requires
byte-identical ordered canonical results across all coordinates, emitting a
content-addressed `cps.pil-genre-matrix-receipt` 1.0.0 that
`validate_genre_matrix_receipt` independently recomputes
(`backend/app/songprogram/perceptual_genre.py`,
`backend/app/songprogram/pil_genre_phase5_worker.py`, commit `c6a3595`).
This mirrors the Phase 1--4 `execute_pil_oracle_matrix` evidence shape; the
authoritative oracle-side matrix remains the conformance suite's own.

## 2026-09-14 Resolved cross-stream schema-pack closure issue

`tests/test_songprogram_schema_pack.py::test_every_schema_is_closed_and_has_identity`
previously failed on the schema
`backend/songprogram_conformance/schemas/calibration_decision_1_1.schema.json`
(added by commit `1731ac0`, SearchLoop13 stream), because conditional object
schemas omitted an explicit `additionalProperties` policy. The SearchLoop13
stream has now closed those conditional schemas without changing decision
semantics. The schema-pack failure is no longer an active PIL blocker.

## 2026-09-15 Remaining external PIL promotion boundary

`pil_12tet_major_chord` is authoritative and is not a remaining task. The
remaining production boundary is narrower: `pil.genre.*` metrics stay
audit-only until an owner issues the future PIL CalibrationDecision version
and independently collected listener cohort, calibration fixture set,
acceptance policy, and evidence summary replace the four
`missing_external_authority` rows. SearchLoop13's synthetic fixture-only
CalibrationDecision exercises bindings and MUST NOT satisfy or replace this
external authority requirement.

## 2026-09-15 GEN0 cohort gate specification closure

The previously implicit output boundary for the preregistered 1,000-seed gate
is now closed by `song_program_gen0_cohort_gate_contract.md` and three schemas:
manifest, per-coordinate candidate record, and aggregate report. It fixes the
1,000-coordinate domain, includes every failed coordinate in every rate
denominator, separates exact and near duplicates, defines order-2 root/chord
mode prevalence and the combined harmony-rhythm mode, freezes integer
round-half-even rates and threshold comparators, and defines canonical hashes
and validation failure precedence. Near-duplicate measurement remains
audit-only until a matching CalibrationDecision is promoted; this does not
block the other GEN0 gates and grants no PIL authority.

Production aggregation and the real 1,000-seed run remain implementation and
evidence work. Authoritative conformance expected hashes must come from an
independent oracle owner rather than the production implementation.
