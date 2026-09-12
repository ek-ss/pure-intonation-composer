# SongProgram Conformance Schemas

These Draft 2020-12 JSON Schemas define the closed, machine-readable envelope
for the SP0 conformance pack.

- `perceptual_interpretation_manifest.schema.json` and
  `perceptual_interpretation_report.schema.json`: optional parallel PIL
  authority. These artifacts never replace or reinterpret Native JI evidence.
- `perceptual_segmentation_policy.schema.json`: closed integer-only Phase 2
  harmonic-boundary, event-weight and merge authority.
- `perceptual_chord_feature_spec.schema.json`,
  `perceptual_chord_feature_record.schema.json`, and
  `perceptual_chord_vocabulary.schema.json`: closed Phase 3 continuous chord
  features and conventional soft-similarity authority. Native JI metrics remain
  external evidence referenced by hash.
- `perceptual_voice_matching_policy.schema.json`,
  `perceptual_voice_matching_record.schema.json`,
  `perceptual_transition_feature_record.schema.json`,
  `perceptual_trajectory_template_set.schema.json`, and
  `perceptual_trajectory_result.schema.json`: closed Phase 4 perceptual voice
  assignment, transition evidence, consecutive alignment and trajectory score
  authority. These artifacts do not reuse Native GEN0-B matching.

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
- `broad_prior_production_request.schema.json` and
  `broad_prior_production_result.schema.json` are the legacy 1.0 pair.
  `broad_prior_production_request_1_1.schema.json` and
  `broad_prior_production_result_1_1.schema.json` are the SearchLoop13 structural
  input pair with complete run/context/source/manifest/catalog causality,
  rejection counters, ordered role decisions, and hash-complete traces.
- `candidate_source_decision.schema.json`: exact initial/archive source choice,
  candidate coordinate, policy, and lock binding for SearchLoop 1.3.
- `structural_sampler_request.schema.json`, `structural_sampler_trace.schema.json`,
  and `structural_sampler_result.schema.json` are legacy v1.0 envelopes.
  Their `_1_1` counterparts bind the sampler/lowering/payload/evidence schemas,
  inline every rejection proof, and close complete-versus-incomplete candidate
  hash nullability.
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
- `tokenizer_manifest.schema.json` and `planner_tool_catalog.schema.json`:
  closed planner token-counting and tool-declaration authorities.
- `search_loop_13_fixture_suite_index.schema.json`: ordered authoritative suite
  root with mandatory success/failure/cache/cancel/parallel coverage.
- `pil_oracle_suite_index.schema.json` and `pil_oracle_case.schema.json`:
  read-only PIL suite closure with exact Phase 1–4, cache, process and worker
  coverage; expected report hashes remain owner-supplied authority.
- `pil_oracle_matrix_receipt.schema.json`: ordered fresh-interpreter
  PYTHONHASHSEED and 1/2/4/8 subprocess-concurrency parity evidence.

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

Genre authority is closed by `genre_license_policy.schema.json`,
`reference_source_provenance.schema.json`, `listener_cohort_manifest.schema.json`,
`blinded_assignment_manifest.schema.json`, `calibration_dataset_manifest.schema.json`,
`calibration_acceptance_policy.schema.json`, and
`calibration_evidence_summary.schema.json`. Thresholds remain required policy
values; none are silently supplied by these schemas.
