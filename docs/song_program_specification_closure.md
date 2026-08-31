# SongProgram Specification Closure Ledger

**Closure scope:** SongProgram 0.1, Project 1.2, SP0, GEN0-A/B/C/D, and LLM1-4

## Decision

No known implementation-semantic choice remains implicit in the closure scope.
Implementation and calibration work remains, but it must instantiate frozen
schemas/manifests or satisfy acceptance gates; it may not redefine behavior.

## Normative contract map

| Area | Authority |
| --- | --- |
| genotype/compiler boundary | `song_program_spec.md` |
| architecture and phase gates | `adr_song_program.md`, review document |
| numeric pitch/chord ranking | NumericContract v1 |
| deterministic stopping/cache charges | OperationBudgetLedger v1 |
| Project/provenance/hash | ArrangementProject 1.2 contract |
| schemas, goldens, oracle, process parity | SP0 Conformance Pack |
| optimized single-chord search | GEN0-A optimized resolver contract |
| progression/voice correspondence | GEN0-B progression contract |
| preview audio/pitch audit/calibration | GEN0-C renderer/evaluation contract |
| instrument assets/release/drum mapping/render identity | Instrument Catalog and RenderManifest Contract v1 |
| sampler/descriptors/QD/planner/run state | GEN0-D/LLM search-loop contract |
| 3/1/export/projection/legacy | capability/compatibility contract |

When two older passages conflict, the more specific contract in this table is
authoritative. Any semantic change requires a new version and ADR plus updated
fixtures; profile/data digest changes cannot reinterpret an existing artifact.

## Remaining work that is not a specification change

- production Pydantic/compiler/resolver/renderer/exporter implementation;
- checked probability tables in `SamplerManifest`;
- immutable instrument assets and catalog entries;
- fingerprint component weights and calibrated near-duplicate threshold;
- licensed/internal genre references;
- listener cohort data and CalibrationDecision thresholds;
- QD cohort population and benchmark measurements;
- UI layout and visual design;
- performance tuning that preserves byte/result equality.

These are content-addressed artifacts or implementation evidence. Missing data
means the dependent feature remains disabled or audit-only; it does not permit
a guessed default.

## Explicitly excluded future schema work

The following are not residual requirements and cannot enter 0.1 by accident:

- transforms other than `rotate`;
- neighbor/approach melody and melody-to-harmony backtracking;
- general form/material/interaction/production graphs;
- bounded repair or arbitrary JSON Patch;
- approximate/beam results in native Project or QD;
- tempo/meter modulation, synthesizer graphs, and general reharmonization;
- legacy-to-native provenance inference.

Each requires a new schema version, ADR, migration/capability rule, and
independent positive/negative/conformance fixtures.

## Change-control test

A proposed implementation decision is already specified if it can be derived
from canonical input plus the authority map. If not, development stops and
opens an ADR; it must not choose a convenient local behavior. Calibration may
promote a metric only through a content-addressed CalibrationDecision. A test
failure reopens the owning contract rather than introducing fallback.

## Closure verification

Closure requires:

1. every machine schema parses and every object is closed or a typed map;
2. all local schema references resolve;
3. numeric/oracle/identity/budget/cache/process fixtures pass;
4. static checks and full repository tests pass;
5. searches for TBD/unspecified/implicit fallback find no item inside closure
   scope;
6. deferred vocabulary is explicitly tied to a future schema/ADR.
