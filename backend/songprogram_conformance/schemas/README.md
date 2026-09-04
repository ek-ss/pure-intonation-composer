# SongProgram Conformance Schemas

These Draft 2020-12 JSON Schemas define the closed, machine-readable envelope
for the SP0 conformance pack.

- `arrangement_project_1_2.schema.json`: immutable playable Project, including
  pitch-provenance unions and inline exact resolved chords.
- `compiler_manifest.schema.json`: compiler identity, exact resolver identity,
  and the SP0 operation-budget profile.
- `charge_receipt.schema.json`: deterministic root and child logical charges.
- `mutation_application_request.schema.json`: fully bound inline Mutation input.
- `mutation_impact_report.schema.json`: ordered pre/post closure and invalidation.
- `mutation_application_receipt.schema.json`: cache-neutral atomic audit receipt.
- `compiler_manifest_1_1.schema.json`: GEN0-B compiler/progression authority.
- `logical_opcode_stream.schema.json`: canonical logical charge records.
- `charge_receipt_1_1.schema.json`: typed GEN0-B root/child receipt.
- `gen0b_compiler_evidence.schema.json`: query/result/Project lowering proof.
- `compile_report_1_1.schema.json`: cold GEN0-B outcome and evidence binding.
- `compile_report.schema.json`: success/failure report, cache telemetry, search
  totals, and typed failure details. It is not part of Project identity.
- `cache_entry.schema.json`: content-addressed exact chord-query cache envelope.
- `fixture_manifest.schema.json`: paths, digests, expected status, and exact
  error metadata for independently verified fixtures.

All object schemas use `additionalProperties: false`; nullable values must be
present where listed as required. Cross-record invariants that JSON Schema
cannot express—ID uniqueness, canonical ordering, exact fraction reduction,
vector dimensions matching generator count, domain/hash recomputation,
timeline containment, union source equations, parallel-array lengths,
permutation checks, and status-dependent nullability—remain mandatory semantic
validation under the normative documents in `docs/`.

Schema references use the local filenames. Validators should register every
schema by its `$id` or resolve relative references from this directory. Validate
schemas with a Draft 2020-12 implementation before running fixture validation.

The schemas deliberately encode the SP0 capability boundary: resolved chords
are exact, Project automation and diagnostics are forbidden, and compiler
manifest limits describe the small exact profile. Generic `3/1` Project data is
schema-valid, but exporter capability is checked separately.
