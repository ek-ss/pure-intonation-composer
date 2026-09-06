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
