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
