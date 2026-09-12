# PIL Oracle Suite Fixture Specification (Draft)

**Status:** draft structure specification. This document defines only the
*shape* of the authoritative Perceptual Interpretation Layer oracle suite
required by `song_program_perceptual_interpretation_layer_contract.md`
section 9. It contains **no golden values**: every expected output field is a
typed placeholder to be filled by the authorized fixture owner through the
existing authoritative-fixture process (`verify_fixture_readonly.py`).
Implementers MUST NOT generate, update, or check in the golden values.

## 1. Scope and authority

- The suite binds PIL manifest/report schemas
  (`perceptual_interpretation_manifest.schema.json`,
  `perceptual_interpretation_report.schema.json`) and the Phase 1+
  implementation contract.
- Suite bytes live under `backend/songprogram_conformance/fixtures/` and are
  read-only to implementation work, like every other authoritative fixture.
- Until this suite and a CalibrationDecision exist, all PIL metrics remain
  audit-only (contract section 9); this restriction never delays Native JI
  evaluation.

## 2. Suite index artifact

```yaml
schema: cps.pil-oracle-suite-index
schema_version: 1.0.0
suite_version: <unsigned integer, owner-assigned>
required_coverage:  # closed label set; every label must appear >= 1 time
  - success
  - failure
  - kernel_edge
  - kernel_tie
  - kernel_empty_support
  - chord_similarity
  - ambiguous_winner
  - missing_bass
  - voice_matching
  - matching_tie
  - unequal_voice_count
  - identity_constraint
  - trajectory_similarity
  - trajectory_missing_bass
  - equave_2_1
  - equave_3_1
  - phase_independence
  - cache_cold
  - cache_hit
  - cache_corrupt
  - cross_process
  - parallel_1
  - parallel_2
  - parallel_4
  - parallel_8
cases: [CaseIndexRow]   # sorted by case_id UTF-8 bytes, unique
suite_hash: <artifact hash, self member excluded>
```

`CaseIndexRow` mirrors the SearchLoop13 fixture-suite row shape
(`case_id`, `path`, `raw_file_sha256`, `case_hash`, `case_schema_hash`,
`coverage`). The byte-closure algorithm in `fixture_suite.py` is reused, but
its SearchLoop-specific fixed coverage constant is not: PIL requires a
separate closed schema and validator entry point with the labels above.

## 3. Case artifact shape

```yaml
schema: cps.pil-oracle-case
schema_version: 1.0.0
case_id: <^[a-z][a-z0-9_-]{0,39}$, unique across the suite>
coverage: [<non-empty unique subset of required_coverage>]
manifest: <PerceptualInterpretationManifest 1.0, complete incl. manifest_hash>
project: <ArrangementProject 1.2, complete and standalone-valid>
segmentation_policy: <null | complete SegmentationPolicy 1.0>
feature_spec: <null | complete ChordFeatureSpec 1.0>
vocabulary: <null | complete ChordVocabulary 1.0>
voice_matching_policy: <null | complete VoiceMatchingPolicy 1.0>
trajectory_template_set: <null | complete TrajectoryTemplateSet 1.0>
native_ji_report_hash: <null | sha256>   # correlation metadata only
expected:
  status: success | failure
  error: <null | PIL_[A-Z0-9_]+>
  report_hash: <null | sha256>   # null only when status == failure is raised
                                 # before a bound report can exist (binding /
                                 # schema stage); otherwise the full hash
  canonical_report_sha256: <sha256 of exact canonical report bytes>
execution:
  worker_counts: [1, 2, 4, 8]        # parity matrix for this case
  pythonhashseeds: [<seed strings>]  # cross-process parity seeds
case_hash: <artifact hash, self member excluded>
```

Rules:

- `expected` values are the owner-only golden surface. Placeholders above are
  normative types, not values.
- A `failure` case whose failure occurs at binding/schema stage records the
  stable raised code in `error` and `report_hash: null`; a computation-stage
  failure records the failed report's hash and bytes like a success case.
- `project` must recompute to its own artifact hash under spec section 17;
  PIL tests recompute it rather than trusting a stored copy.
- `manifest` must recompute to `manifest_hash` under the generic
  `cps-artifact-hash/v1` preimage rule adopted by the Phase 1 implementation;
  if the owner later standardizes a different PIL hash preimage, the Phase 1
  implementation and this suite change together in one commit.
- Payload presence is phase-exact: Phase 1 has all five nullable assets null;
  Phase 2 requires only `segmentation_policy`; Phase 3 requires its first three;
  Phase 4 requires all five.
  Every non-null asset self-hash and embedded raw-schema hash is recomputed,
  then compared with its manifest/upstream binding before execution.

## 4. Required cases (contract section 9 mapping)

| case_id (proposed) | contract item | phase | notes |
| --- | --- | --- | --- |
| `pil_soft_major_1_1_5_4_3_2` | 1 | 1 | high soft major similarity; exact ratios retained in `source_ratio` |
| `pil_seven_limit_multi_candidate` | 2 | 1 | every pitch row keeps multiple nonzero candidates |
| `pil_passing_tone_delta` | 3 | 2+ | similarity delta bound declared in the case, not by implementation |
| `pil_12tet_major_chord` | Phase 3 | 3 | exact 12-TET major template is the top candidate |
| `pil_ji_major_chord` | Phase 3 | 3 | `1/1,5/4,3/2` has the major template as top candidate |
| `pil_ambiguous_chord_margin` | Phase 3 | 3 | candidate list retained while `best_label` is null |
| `pil_missing_bass_component` | Phase 3 | 3 | bass weight is removed, never scored as zero |
| `pil_12et_ii_v_i` | 4 | 4+ | high trajectory similarity |
| `pil_exact_ratio_ii_v_i` | 5 | 4+ | JI analogue, high trajectory similarity |
| `pil_nonfunctional_two_reports` | 6 | 4+ | high Native JI coherence + low ii-V-I similarity as two separate reports |
| `pil_tritave_phase_split` | 7 | 1 | 3/1 equave: native phase != 2/1 interpretation phase |
| `pil_kernel_boundaries` | 8 | 1 | edge, tie, empty-support in one multi-event project or split cases |
| `pil_segment_boundary` | 8 | 2 | half-open interval rules |
| `pil_matching_tie` | 8 | 4+ | voice-matching tie |
| `pil_matching_unequal` | Phase 4 | 4 | both injection orientations and unmatched encoding |
| `pil_matching_identity` | Phase 4 | 4 | sustained event ID is forced to itself |
| `pil_trajectory_missing_bass` | Phase 4 | 4 | null bass component is omitted and weights renormalize |
| `pil_trajectory_overlap_windows` | Phase 4 | 4 | every consecutive window retained in canonical order |
| `pil_cache_parity` | 8 | 1 | cold/hit/corrupt byte identity |
| `pil_cross_process_workers` | 8 | 1 | PYTHONHASHSEED and 1/2/4/8-worker parity |

Phase 1/2 cases and the four Phase 3 chord cases are implementable once the
checked-in FeatureSpec and Vocabulary assets exist. Phase 4 cases additionally
require owner-approved matching policy and trajectory-template payloads.

## 5. Validation flow (read-only)

1. Resolve and authenticate the index and every case by raw bytes (existing
   fixture-suite closure pattern).
2. JSON-Schema-validate `manifest`, `project`, and `expected` against the
   bound schema bytes named by `case_schema_hash`.
3. Recompute `manifest_hash`, the Project artifact hash, and (for
   report-producing cases) the report hash and canonical bytes; compare to
   `expected` exactly — no tolerance.
4. Run the declared worker/PYTHONHASHSEED matrix; all executions must produce
   byte-identical reports.
5. Confirm the PIL run leaves the case `project` bytes and any cited Native
   JI report hash untouched.

## 6. Open decisions for the fixture owner

- Final `case_id` assignments and suite_version numbering.
- Whether binding-stage failure cases belong in this suite or in a separate
  negative-pack registry (analogous to `error_registry.json`).
- The owner-assigned FeatureSpec and Vocabulary payload values and hashes.
  Implementers may provide an independent generator, but may not approve or
  rewrite its checked-in expected report bytes.
- The owner-assigned VoiceMatchingPolicy weights/caps/kernel radius and
  TrajectoryTemplateSet templates/weights. Their expected bytes must be
  generated and approved independently from the production implementation.
