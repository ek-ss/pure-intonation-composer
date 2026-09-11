# SongProgram SP0 Conformance Pack

This directory contains two complementary, production-independent conformance
surfaces. Neither may import `app.*` or production composition helpers.

## Compiler protocol

The compiler/cache protocol is implemented by `canonical.py`, `protocol.py`,
and `runner.py`. Its strict Draft 2020-12 schemas live in
[`schemas/`](schemas/README.md), and executable opcode/cache cases live in
`fixtures/`.

From `backend/`, run a fixture with:

```text
python -m songprogram_conformance.runner --case minimal_direct_note --cache cold
python -m songprogram_conformance.runner --case minimal_direct_note --cache hit
python -m songprogram_conformance.runner --case minimal_direct_note --cache corrupt
```

Cold, valid-hit, and corrupt-cache fallback must produce identical logical
results and charge receipts; cache telemetry is non-authoritative.

## Numeric and exhaustive-oracle protocol

The NumericContract reference, finite oracle universe, query/result schemas,
fixed datasets, and oracle goldens are documented in
[`numeric_oracle.md`](numeric_oracle.md).

```text
pytest -q songprogram_conformance/test_conformance.py
```

## Handoff layout and comparison rule

- `schemas/` contains closed SongProgram, Project, manifest, report, receipt,
  cache, fixture-manifest, and error-registry schemas.
- `fixtures/pack/` contains complete direct/triad inputs, compiler identity,
  hash sidecars, and negative-test metadata.
- `goldens/` contains 2/1 and 3/1 oracle pairs, the independent-nearest
  adversary, and the frozen 1,000-record numeric corpus.
- `canonical.py` and `identifiers.py` are independent byte/identity references.

Fresh-process conformance compares Project bytes, semantic IDs, artifact hashes,
logical receipts, and stable failure payloads. Only `execution_telemetry` may
differ. The full environment matrix and independence rule are normative in
`docs/song_program_conformance_pack.md`.

Search orchestration 1.3 additionally binds archive admission, GenreIntent
challenger comparison, fingerprint duplicate classification, stopping, and
render selection by policy hash. Its normative ordering and cancellation
barrier are documented in `docs/song_program_search_decision_contract.md` and
`docs/song_program_search_loop_1_3_contract.md`.
Near-duplicate decisions are always recorded before any render reservation.

Genre calibration uses closed `calibration_statistic_operator`,
`calibration_response_set`, and `calibration_bootstrap_trace` schemas. Together
with the acceptance policy and evidence summary they make agreement,
classification counts, and bootstrap intervals independently recomputable by
integer arithmetic; the normative formulas and rejection precedence are in
`docs/song_program_evaluation_operator_contract.md`.

Fallback and broad-prior production have a production-independent reference in
`fallback_sampler_oracle.py`. Its maintainer builder and authoritative
success/retry/lock/exhaustion, weighted-boundary, and register-endpoint cases
live under `fixtures/fallback_sampler/`; consumers must not invoke the builder.

`search_decision_oracle.py` is the production-independent semantic authority
for archive, challenger, near-duplicate, stopping, cancellation, and preview
render decisions. It additionally validates action-ID derivation, component
source uniqueness, comparison-set membership/hash, and render charge
arithmetic. Authoritative success, negative, and exact-boundary inputs and
expected sidecars live in `fixtures/search_decisions/`; regenerate them only
with `python -m backend.songprogram_conformance.build_search_decision_fixtures`
from the repository root.

## Phase-5 authoritative fixtures

- `fixtures/mutation/` contains 41 independently evaluated cases covering all
  eight typed operations across success, negative, scope, lock, and boundary
  behavior. `build_mutation_fixtures.py` generates them and
  `verify_mutation_fixtures.py` verifies checked-in bytes without production
  applicator imports.
- `fixtures/compiler/` freezes the closed GEN0-A BnB resolver profile, a
  three-occurrence progression query/result, expected Project, complete root
  and child opcode streams/ChargeReceipt, GEN0-B evidence/CompileReport, and
  chord-member melody report plus failures. `gen0b_receipt_oracle.py` and
  `gen0b_melody_oracle.py` generate the numeric/search and binding authority
  without production compiler imports.
- `fixtures/connected/` freezes the outer cache/runner protocol around a
  cacheable Mutation failure, including cold/hit/corrupt parity and the exact
  1/2/4/8-worker matrix. Connected success may bind the compiler authority
  above without regenerating it.

Fixture builders are oracle-maintainer tools. Production implementation and
conformance tests consume the checked-in files read-only and MUST NOT invoke a
builder to replace an expected value after a mismatch.

## Read-only enforcement and oracle updates

Run the guard from `backend/` as part of the normal test command:

```text
python -m songprogram_conformance.verify_fixture_readonly
pytest -q
python -m songprogram_conformance.verify_fixture_readonly
```

It rejects production imports or literal invocations of fixture builders, and
uses `git status --porcelain` to reject modified or untracked authoritative
fixtures, goldens, schemas, oracle references, and contract documents. This
does not require a CI base ref, merge-base, or network access; the same command
works in a normal local Git worktree. CI should run it before and after tests so
that a test-time write is caught as well.

Only an oracle maintainer deliberately changing the authority may use the
explicit exception below. They must review every protected diff, run the
independent verifier(s) and the full test suite, and commit the builder/oracle
change together with its resulting fixtures. Production changes must never use
this exception.

```text
python -m songprogram_conformance.build_mutation_fixtures
python -m songprogram_conformance.verify_fixture_readonly --allow-authoritative-update
pytest -q
```
