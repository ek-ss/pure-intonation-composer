# SongProgram SP0 Conformance Pack

**Status:** normative handoff contract. The executable pack lives in
`backend/songprogram_conformance`; tests live in `backend/tests/test_songprogram_*`.
It must not import `app` production helpers when computing expected values.

## Canonical JSON v1

Accepted values are null, booleans, arbitrary-precision integers, NFC strings,
arrays, and string-keyed objects. Floats and unpaired surrogates are forbidden.
Object keys sort by raw UTF-8 bytes. Strings use UTF-8 directly, escaping quote
and backslash, the short JSON escapes for U+0008/9/A/C/D, and lowercase
`\u00xx` for other U+0000..U+001F characters. Arrays preserve order. Output has
no whitespace, BOM, or trailing newline. Digests are lowercase 64-character
SHA-256 hex unless a field explicitly requires the `sha256:` prefix.

The independent reference is `songprogram_conformance.canonical`; its Unicode
golden prevents platform serializers from silently defining artifact identity.

## Required handoff artifacts

The pack is complete only when it contains:

1. strict JSON schemas for Project, CompilerManifest, CompileReport,
   ChargeReceipt, CacheEntry, FixtureManifest, OracleQuery, and OracleResult;
2. a fixture manifest giving every case an input, expected success or exact
   `{code,stage,pointer}`, expected IDs/hashes, applicable contract versions,
   and independent-verification status;
3. complete direct-note, resolved-triad, chord-member, drum, and 3/1 examples;
4. numeric JSONL goldens and exhaustive-oracle query/result pairs;
5. complete logical opcode receipts for direct-note and resolved-triad;
6. cold, valid-hit, and corrupt-cache cases with identical semantic outcome;
7. a one-JSON-line subprocess protocol and environment matrix.

## Independence rule

Reference numeric calculations, exhaustive oracle, fixture hashing, and cache
verification may use standard-library primitives and this conformance package,
but may not import `app` compiler, resolver, serializer, cache, or model code.
Production tests run the production implementation and compare its bytes to the
checked-in sidecars. Updating a sidecar requires recording both generator and
independent verifier in the fixture manifest.

## Handoff decision

The pack is ready for parallel implementation handoff when the repository tests
named `test_songprogram_*` pass. Assigned agents do not need to invent wire
formats or expected values:

- schema/compiler agent implements strict models from `schemas/` and runs the
  complete direct/triad and negative mutation fixtures;
- numeric/oracle agent compares production functions against the 1,000-record
  corpus and the 2/1, 3/1, and adversarial query/result pairs;
- budget/cache agent implements the atomic ledger from the boundary cases and
  compares cold/hit/corrupt logical projections;
- determinism agent invokes the one-line runner under the 100-process matrix
  and compares canonical bytes and identity sidecars.

The checked-in Project files are expected outputs, not templates. Production
code must not regenerate an expected file during a test. A fixture change is a
contract change and requires updating its manifest digest and independent
verification record.

## Cross-process protocol

The runner reads exactly one UTF-8 JSON object from stdin and writes exactly one
CPS Canonical JSON object plus newline to stdout. Logs go to stderr. The request
is the closed object `{operation:"run_fixture",case,cache}`. A comparison
must include canonical Project bytes, program/artifact hashes, semantic IDs,
logical root/child receipts, and stable failure payload; it excludes only the
telemetry pointers declared in the fixture manifest.

Every deterministic fixture runs in fresh processes under at least:

- `PYTHONHASHSEED=0` and `PYTHONHASHSEED=4294967295`;
- `TZ=UTC` and `TZ=Asia/Tokyo`;
- `LC_ALL=C` and one available UTF-8 locale;
- caller Decimal precision 6/FLOOR and 80/HALF_EVEN.

Each environment combination runs twice. The complete matrix is repeated until
100 process executions have been compared; all included bytes must equal the
checked-in expected sidecar. An unavailable locale is reported as a skipped
matrix cell, never silently replaced.
