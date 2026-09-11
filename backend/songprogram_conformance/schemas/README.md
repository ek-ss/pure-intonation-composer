# SongProgram Conformance Schemas

These Draft 2020-12 JSON Schemas define the closed, machine-readable envelope
for the SP0 conformance pack.

- `arrangement_project_1_2.schema.json`: immutable playable Project, including
  pitch-provenance unions and inline exact resolved chords.
- `compiler_manifest.schema.json`: compiler identity, exact resolver identity,
  and the SP0 operation-budget profile.
- `charge_receipt.schema.json`: deterministic root and child logical charges.
- `mutation_application_request.schema.json`: fully bound inline Mutation input.
- `mutation_application_request_1_1.schema.json`: legacy batch request; one
  atomic request carries the complete ordered fallback mutation batch.
- `mutation_application_request_1_2.schema.json`: RunManifest 1.3 batch request
  with context, source decision, and planner/fallback proposal provenance.
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
- `fallback_request_1_1.schema.json`, `mutation_application_request_1_2.schema.json`,
  and `fallback_result_1_1.schema.json`: SearchLoop13 planner/fallback origin
  provenance and its single mutation-application receipt chain.
- `broad_prior_production_manifest.schema.json`: role-by-role instrument,
  register, polyphony, drum-map, gain, and pan lowering. Completed instrument
  maps are deliberately not representable.
- `broad_prior_production_request.schema.json` (legacy complete-Program input),
  `broad_prior_production_request_1_1.schema.json` (SearchLoop13 structural input), and
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
  bound evidence selection, closed operator proof, and
  integer-or-explicit-missing evaluation output. The independent operator and
  evidence-hash reference is `../evaluation_operator_oracle.py`.
- `compile_only_{request,result,cache_entry}.schema.json`: phase-3-only compile
  input, replayable output, and the result-bound logical cache entry. They never
  apply a mutation.
- `cancellation_inbox_record_1_1.schema.json` and
  `cancellation_decision_1_1.schema.json`: immutable SearchLoop13 external
  cancellation intake and digest-selected cutoff; legacy cancellation schemas
  remain unchanged.
- `search_loop_13_event_payload.schema.json`: closed outer event binding whose
  `payload_hash`, rather than its inner `artifact_hash`, is stored in the
  RunRecord. The exhaustive kind-to-artifact-schema binding table is normative
  in `docs/song_program_search_loop_13_payload_contract.md`.
- `render_dispatch_authorization.schema.json`, `render_cache_entry.schema.json`,
  and `render_cache_corruption_receipt.schema.json`: sealed phase-7 dispatch
  authority and non-event render-cache evidence for SearchLoop13.
- `audio_artifact.schema.json`: closed 48 kHz, stereo-interleaved little-endian
  PCM32 descriptor binding exact PCM bytes and its reference render report.
- `cache_publication_index.schema.json`: append-only coordinate-ordered root for
  cold compile/render cache publications.
- `search_loop_13_fixture_case.schema.json`: closed authority selecting every
  fixture input and binding transcript, CAS, cache, checkpoint, and PCM roots.
- `search_loop_13_cas_index.schema.json`: runtime-bound canonical inventory of
  every transcript-reachable JSON artifact and raw PCM byte object.
- `render_failure.schema.json`: closed typed render failure causally bound to
  request, charge, and dispatch authorization.
- `fixture_edge_registry.schema.json`: fixture-bound declaration of every
  traversable hash pointer, target kind, cardinality, and canonical root role.
- `genre_feature_record.schema.json`: pinned-extractor signed-Q1.31 embedding
  bound to its exact source audio segment.
- `genre_similarity_spec.schema.json`: exact normalized-L1 and lower-median
  aggregation contract for calibrated genre similarity.

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
