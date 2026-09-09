# SongProgram Conformance Schemas

These Draft 2020-12 JSON Schemas define the closed, machine-readable envelope
for the SP0 conformance pack.

- `arrangement_project_1_2.schema.json`: immutable playable Project, including
  pitch-provenance unions and inline exact resolved chords.
- `compiler_manifest.schema.json`: compiler identity, exact resolver identity,
  and the SP0 operation-budget profile.
- `charge_receipt.schema.json`: deterministic root and child logical charges.
- `mutation_application_request.schema.json`: fully bound inline Mutation input.
- `mutation_application_request_1_1.schema.json`: RunManifest 1.3 batch request;
  one atomic request carries the complete ordered fallback mutation batch.
- `mutation_impact_report.schema.json`: ordered pre/post closure and invalidation.
- `mutation_application_receipt.schema.json`: cache-neutral atomic audit receipt.
- `compiler_manifest_1_1.schema.json`: GEN0-B compiler/progression authority.
- `resolver_profile.schema.json`: content-addressed GEN0-A BnB profile bound by
  CompilerManifest 1.1.
- `logical_opcode_stream.schema.json`: canonical logical charge records.
- `charge_receipt_1_1.schema.json`: typed GEN0-B root/child receipt.
- `gen0b_compiler_evidence.schema.json`: query/result/Project lowering proof.
- `compile_report_1_1.schema.json`: cold GEN0-B outcome and evidence binding.
- `chord_member_melody_report.schema.json`: exact melody-to-selected-voice proof.
- `connected_executor_manifest.schema.json`: connected pipeline contract/schema identity.
- `connected_request.schema.json`: fully inline connected semantic request.
- `connected_logical_output.schema.json`: cache- and worker-neutral logical result.
- `opcode_stream_bundle.schema.json`: root/child replay authority.
- `connected_cache_entry.schema.json`: whole-pipeline cache envelope.
- `connected_execution_telemetry.schema.json`: nonsemantic cache/worker telemetry.
- `connected_runner_request.schema.json`: worker/cache execution controls.
- `connected_runner_result.schema.json`: ordinal-published semantic results.
- `connected_runner_matrix.schema.json`: exact 1/2/4/8 by cold/hit/corrupt matrix.
- `connected_fixture_manifest.schema.json`: bound connected fixture files/corruptions.
- `compile_report.schema.json`: success/failure report, cache telemetry, search
  totals, and typed failure details. It is not part of Project identity.
- `cache_entry.schema.json`: content-addressed exact chord-query cache envelope.
- `fixture_manifest.schema.json`: paths, digests, expected status, and exact
  error metadata for independently verified fixtures.
- `archive_admission_*`: QD cell eligibility and deterministic replacement.
- `challenger_acceptance_*`: GenreIntent-bound Pareto comparison; these schemas
  deliberately contain no fixed minimum score or consecutive-round gate.
- `near_duplicate_decision.schema.json`: symbolic duplicate decision committed
  before render selection.
- `stopping_policy.schema.json` and `round_decision.schema.json`: material
  archive improvement, patience, and stop precedence.
- `cancellation_*`: barrier-observed cancellation and its canonical cutoff.
- `render_selection_policy.schema.json`, `render_request.schema.json`, and
  `render_charge.schema.json`, and `render_result.schema.json`: deterministic
  preview selection, reservation, cache/failure outcome, and frame budget.
- `search_run_manifest_1_3.schema.json`, `search_run_record_1_1.schema.json`, and
  `search_checkpoint_1_1.schema.json`: fully policy-bound orchestration. The
  older 1.2/1.0 schemas remain available for stored legacy runs.
- `fallback_manifest.schema.json`, `fallback_request.schema.json`, and
  `fallback_result.schema.json`: deterministic typed-mutation fallback,
  independent attempt stream, exact locks, and atomic success/failure envelopes.
- `broad_prior_production_manifest.schema.json`: role-by-role instrument,
  register, polyphony, drum-map, gain, and pan lowering. Completed instrument
  maps are deliberately not representable.
- `broad_prior_production_request.schema.json` and
  `broad_prior_production_result.schema.json`: causal input/output binding,
  rejection counters, ordered role decisions, and hash-complete traces.
- `candidate_source_decision.schema.json`: exact initial/archive source choice,
  candidate coordinate, policy, and lock binding for SearchLoop 1.3.
- `structural_sampler_request.schema.json` and
  `structural_sampler_result.schema.json`: immutable broad-prior invocation and
  success/failure result without embedding the produced SongProgram bytes.
- `planner_request.schema.json` and `planner_response.schema.json`: immutable
  planner evidence/budget input and typed mutation-or-diagnostic outcome.
- `evaluation_manifest.schema.json`, `evaluation_request.schema.json`, and
  `evaluation_report.schema.json`: closed evaluator declarations, causally
  bound evidence selection, and integer-or-explicit-missing evaluation output.
- `compile_only_{request,result,cache_entry}.schema.json`: phase-3-only compile
  input, replayable output, and the result-bound logical cache entry. They never
  apply a mutation.
- `cancellation_inbox_record_1_1.schema.json` and
  `cancellation_decision_1_1.schema.json`: immutable SearchLoop13 external
  cancellation intake and digest-selected cutoff; legacy cancellation schemas
  remain unchanged.

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
