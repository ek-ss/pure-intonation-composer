# SongProgram Specification Review — 2026-08-30

**Reviewed artifacts:** `song_program_spec.md`, `adr_song_program.md`,
`development_plan_llm_lattice_music_loop.md`
**Method:** three independent reviews, one disclosed rebuttal round, arbiter
decision
**Freeze result:** **SP0 strict specification frozen; implementation GO**

## 0. Development Readiness

### Overall decision: GO for SP0 implementation

The strict SP0 compiler and 8-bar 2/1 vertical slice may now be implemented.
The full generator, production UI, LLM loop, and broad search remain later
gates.

| Work item | Decision | Reason |
| --- | --- | --- |
| Strict model skeleton and canonical JSON | GO | exposes remaining type/hash contradictions early |
| NumericContract implementation and golden vectors | GO | normative contract is frozen |
| Generic exact vector/equave core | GO | well-bounded and independently testable |
| Small-domain exhaustive chord oracle | GO | becomes the truth source for later optimization |
| Project 1.2 provenance-union models | GO | strict schema and equations are frozen |
| 8-bar 2/1 vertical slice | GO | merge remains gated by all specified fixtures |
| Optimized branch-and-bound / progression Viterbi | Specification GO | GEN0-A/B contracts frozen; implementation equality gates remain |
| Broad sampler / 1,000-song cohort | Specification GO | sampler/QD contract frozen; probability manifest is a cohort artifact |
| 3/1 full composition and rendering | Specification GO | native/render/export capability boundary frozen |
| QD selection, perceptual gates, LLM loop | Specification GO | orchestration frozen; perceptual promotion requires calibration artifact |
| Production UI and compatibility commitments | Semantic specification GO | compatibility/cancellation semantics frozen; UI layout is product design outside the normative scope |

The four blocking artifacts now exist:

1. `NumericContract v1` with independently verified golden vectors;
2. strict SongProgram core schema with canonical-order/hash fixtures;
3. strict Project 1.2 schema with provenance union and `resolved_chords[]`;
4. a typed operation-budget ledger and small-domain limits.

Their required tests are implementation acceptance criteria. Failure must be
fixed against the contract or explicitly reopened by ADR; silent fallback is
forbidden.

## 1. Arbiter Decisions

### Equave scope

The variable-equave architecture remains accepted. SP0 exact arithmetic,
reduction, register, hashing, and small-domain chord-oracle fixtures must run
through the same generic code path for both `2/1` and `3/1`.

The first end-to-end 8-bar composition and existing exporter integration are
limited to `2/1`. Full `3/1` composition, broad search, rendering quality, and
listening calibration form the immediately following capability milestone.
Unsupported output must return `UNSUPPORTED_EQUAVE_CAPABILITY`; silent octave
conversion is forbidden.

### Search completeness

Only `exact` small-domain harmony-search results may enter an SP0 native Project.
`beam_bounded` remains a reserved/experimental search artifact and is forbidden
from SP0 Project, viability, and QD inputs. Budget exhaustion returns no partial
Project.

### Audible-color exposure

Audible-color share, section exposure, and recurrent-color metrics are
audit-only until calibrated by matched listening tests. They do not reject an
individual SP0 or first-cohort candidate. Cohort collapse still triggers a
sampler review. A later ADR may promote a calibrated metric to a gate.

### Scope split

The work is split into:

```text
SP0-A  exact generic pitch core (2/1 and 3/1 fixtures)
SP0-B  small-domain exact joint chord resolver
SP0-C  8-bar 2/1 Project 1.2 vertical slice
GEN0-A optimized resolver checked against the SP0 oracle
GEN0-B progression search, broader sampler, diversity archive
GEN0-C renderer and perceptual calibration
```

Interactions, production envelopes, broad mutation locality, relational
neighbor/approach melody, harmony backtracking, and approximate beam results do
not block SP0.

## 2. Consolidated Issue Register

### SP-P0-001 — Contradictory operation budgets

- **Severity:** P0
- **Evidence:** the draft declares a 50-million-point domain, 1-million global
  operations, 2-million joint nodes, and 4-million progression edges.
- **Failure:** a documented valid program cannot satisfy its own budgets;
  implementations can choose different counters.
- **Decision:** replace the global scalar with a versioned budget ledger.
  SP0's placed-pitch domain ceiling is at most 100,000 until benchmarked.
- **Acceptance:** every loop charges exactly one declared counter; boundary
  fixtures succeed/fail at `limit`/`limit+1`; no partial Project on exhaustion.
- **Cost:** M

### SP-P0-002 — Domain cardinality is ambiguous

- **Severity:** P0
- **Evidence:** `maximum_domain_points` does not state whether register exponents
  participate.
- **Failure:** identical inputs can pass or fail before enumeration depending
  on implementation.
- **Decision:** define `coordinate_cardinality = product(axis widths)` and
  `placed_pitch_cardinality = coordinate_cardinality * register width`; the
  ceiling applies to the latter using checked 128-bit arithmetic.
- **Acceptance:** 1D/3D boundary and overflow golden fixtures.
- **Cost:** S

### SP-P0-003 — Approximate results conflict with compiler truth

- **Severity:** P0
- **Evidence:** `beam_bounded` is accepted while domain/budget monotonicity and
  deterministic best results are required.
- **Failure:** search approximation differences appear as musical differences.
- **Decision:** SP0 native Project accepts `search_completeness: exact` only.
- **Acceptance:** optimized small-domain results exactly match an exhaustive
  oracle; beam artifacts are rejected by the native Project validator.
- **Cost:** M

### SP-P0-004 — Harmony register has two authorities

- **Severity:** P0
- **Evidence:** progression search chooses voicing/register while a later
  compiler pass independently places every harmony tone.
- **Failure:** pair errors, voice paths, and comma movement become invalid after
  lowering.
- **Decision:** ResolvedChord/progression search exclusively owns harmony
  anchor, register, and equave exponent. Lowering only validates them.
- **Acceptance:** lowering never changes a harmony exponent; stored transition
  costs recompute exactly.
- **Cost:** S

### SP-P0-005 — Numeric contract is incomplete

- **Severity:** P0
- **Evidence:** EDO targets are irrational, while log precision, intermediate
  rounding, pair RMS square root, weight accumulation, and threshold equality
  are not normative.
- **Failure:** different platforms select different chords at ties/boundaries.
- **Decision:** freeze `NumericContract v1` before resolver implementation.
- **Acceptance:** two independent implementations agree byte-for-byte on 1,000
  golden targets including threshold ±1 millicent and exact ties.
- **Cost:** M

### SP-P0-006 — Near-class clustering is not normative

- **Severity:** P0
- **Evidence:** “deterministic bounded-diameter” omits circular cut, boundary
  equality, representative, tie-break, and ID derivation.
- **Failure:** Project hashes and audit metrics depend on enumeration order.
- **Decision:** keep near classes audit-only in SP0 and define a separate
  versioned clustering protocol before GEN0 selection uses them.
- **Acceptance:** chain, equave-boundary, equality, and all-input-permutation
  fixtures produce one canonical partition.
- **Cost:** M

### SP-P0-007 — Project 1.2 provenance cannot represent every source

- **Severity:** P0
- **Evidence:** every event requires `material_vector`, but relational melody
  and resolved chord voices do not originate from that field.
- **Failure:** validators require fabricated provenance or contradictory formulas.
- **Decision:** use a discriminated union:
  `direct_vector | resolved_chord_voice | resolved_melody`.
- **Acceptance:** each variant round-trips and rejects altered source/final-vector
  equations; every final ratio recomputes exactly.
- **Cost:** M

### SP-P0-008 — ResolvedChord storage/reference is undefined

- **Severity:** P0
- **Evidence:** the draft alternates between inline singular artifact, external
  immutable artifact, and event ID reference; runner-up schema is absent.
- **Failure:** a strict Project 1.2 schema cannot be implemented.
- **Decision:** SP0 stores `resolved_chords[]` inline in canonical ID order;
  ID is the hash of canonical resolved core. Candidate archives and runner-ups
  remain separate diagnostics.
- **Acceptance:** strict round-trip, dangling/duplicate/core-hash mutation
  rejection.
- **Cost:** M

### SP-P0-009 — Melody reference and backtracking are ambiguous

- **Severity:** P0
- **Evidence:** the pre-freeze draft referred variously to 12-EDO, the
  pitch-policy reference grid, and active ChordIntent.
- **Failure:** target pitch and budget consumption are not deterministic.
- **Decision:** SP0 through LLM4 supports `chord_member` only, inheriting the
  active ChordIntent. Mixed-reference relational melody and melody-to-harmony
  backtracking are reserved for a new schema/ADR and are not implicit GEN0 work.
- **Acceptance:** chord-member vectors are identical to resolved chord voices;
  unsupported relations and mixed references fail with stable errors.
- **Cost:** S

### SP-P0-010 — Unspecified ranking costs change the composition

- **Severity:** P0
- **Evidence:** roughness, openness, stability, recall, and character fields lack
  normative formulas/scales.
- **Failure:** candidate order differs across implementations.
- **Decision:** SP0 ranks by hard pair limits, pair RMS/max error, exact ratio
  complexity, and canonical tie-break only. Additional costs require later ADRs
  and oracle fixtures.
- **Acceptance:** every component is hand-recomputable on small-domain golden
  chords; removed fields are rejected by SP0 schema.
- **Cost:** M

### SP-P0-011 — Search knobs are mixed into the musical genotype

- **Severity:** P0
- **Evidence:** beam width, node budgets, and resolver weights are SongProgram
  fields.
- **Failure:** planners can optimize approximation behavior as if it were music;
  identical intent has multiple compiler truths.
- **Decision:** move resolver algorithm/budgets/profile into the compiler/cohort
  manifest. SongProgram retains musical intent and hard recognition/complexity
  limits only.
- **Acceptance:** planner/mutation schema contains no search-control fields;
  compiler-manifest changes create a new cohort/build identity.
- **Cost:** S

### SP-P0-012 — Viability thresholds contradict each other

- **Severity:** P0
- **Evidence:** one draft requires 95% to compile and pass viability; the ADR
  requires compile ≥95%, initial automatic viability ≥70%, and ≥80% before LLM.
- **Failure:** GEN0 pass/fail is subjective.
- **Decision:** ADR-SP-005 is authoritative; report compile, automatic, human,
  and audibility results as separate denominators/columns.
- **Acceptance:** fixed 1,000-seed ledger includes every failure and reproduces
  all four rates.
- **Cost:** S

### SP-P1-001 — Transform DSL no longer matches relational material

- **Severity:** P1
- **Evidence:** vector transpose/invert remain after pitch material became
  chord-relative intent.
- **Failure:** transforms either do nothing, mutate the wrong layer, or break
  joint chord recognition after resolution.
- **Decision:** SP0 retains temporal rhythm transforms only. Root-anchor
  translation and relational pitch transformation return after separate
  semantics are specified.
- **Cost:** S

### SP-P1-002 — Canonical material/step order is contradictory

- **Severity:** P1
- **Evidence:** materials are called ordered but canonicalized by ID; steps are
  both sorted by time and declared order-preserving.
- **Failure:** hashes, semantic addresses, keyed randomness, and event IDs drift.
- **Decision:** material collection sorts by ID. Rhythm-step input order is
  semantic, must be nondecreasing by onset, and is preserved; same-onset order
  remains meaningful.
- **Cost:** S

### SP-P1-003 — Hash exclusions reference an undefined field

- **Severity:** P1
- **Evidence:** `/annotations` is excluded from hash but absent from strict schema.
- **Failure:** parse/hash behavior diverges.
- **Decision:** annotations stay outside SongProgram; only `/program_id` is
  excluded. `program_id` is non-referenceable metadata outside the symbol table.
- **Cost:** S

### SP-P1-004 — CandidateGenome duplicates SongProgram truth

- **Severity:** P1
- **Evidence:** development plan repeats lattice, chords, production, and seeds
  outside SongProgram.
- **Failure:** competing authoritative values can coexist.
- **Decision:** reduce CandidateGenome to `song_program_hash`, locks, mutation
  metadata, and lineage only.
- **Cost:** S

### SP-P1-005 — Fixed harmony cycles can recreate the old generator

- **Severity:** P1
- **Evidence:** root anchors and intent IDs still cycle as arrays.
- **Failure:** seeds vary only voicing while progression/rhythm remains fixed.
- **Decision:** retain the simple representation but add sampler diagnostics for
  root-anchor n-grams, intent n-grams, and harmony-rhythm fingerprints. No
  single n-gram mode may exceed a preregistered concentration ceiling.
- **Cost:** M

### SP-P1-006 — Compatibility/export requirements ignore capabilities

- **Severity:** P1
- **Evidence:** one clause allows unsupported equave errors; another requires
  all Projects to pass old exporters.
- **Failure:** 3/1 cannot satisfy both.
- **Decision:** capability-supported projects must export; unsupported projects
  return a stable error and never silently alter equave.
- **Cost:** S

### SP-P1-007 — Current v0.1 scope is too broad

- **Severity:** P1 (scope blocker)
- **Evidence:** joint search, progression, relational melody, clustering,
  interactions, production automation, mutation, migration, sampler, QD, and
  listening tests are all described as one freeze.
- **Failure:** failures cannot be attributed and the first implementation never
  reaches a trustworthy baseline.
- **Decision:** use the SP0/GEN0 milestone split in section 1. Remove interactions,
  envelopes, broad mutation, approximate search, and listening gates from the
  SP0 critical path.
- **Cost:** S documentation work; large implementation-risk reduction.

## 3. Implementation Order

1. Freeze NumericContract and strict core schemas.
2. Implement generic exact vector/equave core with 2/1 and 3/1 golden fixtures.
3. Define Project 1.2 provenance union and inline `resolved_chords[]`.
4. Implement a small-domain exhaustive joint-chord oracle.
5. Generate one deterministic 8-bar `2/1` Project using chord-member melody.
6. Add an optimized resolver and prove equality with the oracle.
7. Add progression-level selection and authoritative harmony registers.
8. Add the versioned broad sampler and cohort ledger.
9. Add QD/audit metrics, then renderer/listening calibration.
10. Enable full 3/1 composition after its own capability and genre fixtures.

## 4. Freeze Exit Criteria

SP0 may be frozen only when:

- P0-001 through P0-012 have accepted textual resolutions;
- NumericContract has independent golden verification;
- strict SongProgram and Project 1.2 schemas round-trip;
- small-domain joint resolver equals exhaustive oracle;
- 2/1 and 3/1 exact pitch fixtures share one generic implementation;
- one 8-bar 2/1 Project compiles byte-identically across processes;
- no beam, audio model, human rating, QD archive, interaction solver, or
  production envelope is needed to run the SP0 suite.

## 5. Closure Audit After Immediate Revisions

Three agents re-audited the revised documents against every issue ID. They
found no new architectural category; two newly exposed textual P0s (an invalid
ResolvedChord example and a missing harmony-resolver compiler pass) were fixed
immediately in the specification.

### Current status

| Issue | Status | Remaining closure artifact |
| --- | --- | --- |
| SP-P0-001 budget ledger | Specification closed | implementation and boundary fixtures |
| SP-P0-002 domain cardinality | Closed textually | boundary/overflow fixtures |
| SP-P0-003 exact-only SP0 | Closed textually | Project rejection and oracle fixtures |
| SP-P0-004 harmony register authority | Closed textually | lowering spy/recomputation fixtures |
| SP-P0-005 NumericContract | Specification closed | independent golden implementation |
| SP-P0-006 near-class authority | Closed for SP0 | moved to external audit report; later clustering protocol required |
| SP-P0-007 provenance union | Specification closed | strict model and negative fixtures |
| SP-P0-008 ResolvedChord collection | Specification closed | model/hash/reference fixtures |
| SP-P0-009 melody reference/backtracking | Closed for SP0 | unsupported-relation fixtures |
| SP-P0-010 ranking costs | Specification closed | oracle equality fixtures |
| SP-P0-011 search knobs/genotype | Closed | compiler-manifest schema |
| SP-P0-012 viability thresholds | Closed | GEN0 cohort ledger implementation |
| SP-P1-001 transforms | Closed for SP0 | only `rotate`; other transforms are draft GEN0 vocabulary |
| SP-P1-002 canonical order | Closed | hash fixtures |
| SP-P1-003 hash exclusions | Closed | hash fixtures |
| SP-P1-004 CandidateGenome duplication | Closed | future planner schema test |
| SP-P1-005 fixed harmony cycles | Closed textually | n-gram/fingerprint implementation and preregistration |
| SP-P1-006 exporter capability | Closed textually | 2/1 success and 3/1 explicit-error fixtures |
| SP-P1-007 scope | Closed textually | milestone enforcement in work plan |

### Specification closure and implementation gate

The four former specification blockers are now frozen in the three normative
contracts linked from `docs/README.md`: NumericContract v1,
OperationBudgetLedger v1, and ArrangementProject 1.2 (including ResolvedChord).
The strict SP0 specification is implementation-ready: development is GO.

The 8-bar feature is not yet complete. Its merge/release gate remains the
required golden, negative, boundary, oracle-equality, cache-parity, and
cross-process tests named by those contracts. A test failure reopens the
corresponding issue; it does not authorize an implementation-specific fallback.

### Final closure audit

After three correction/review rounds, the schema, musical-numeric, and compiler
reviewers independently reported zero remaining P0 specification issues. The
last closed items were canonical bass targeting, normative budget opcode
generation, EventId/address byte encoding, self-contained domain filters and
odd-limit arithmetic, inline recognition/eligibility authority, resolver
identity, and exact ResolvedChord hash preimages.

The subsequent executable Conformance Pack closes the handoff gap with closed
JSON schemas, complete direct and resolved-triad Projects, stable negative
errors, a frozen 1,000-record numeric corpus, 2/1/3/1 exhaustive-oracle
goldens, atomic budget boundaries, cache parity cases, identity sidecars, and a
100-process environment-matrix runner. Independent implementation work may now
be assigned without redefining test transport or expected values.
