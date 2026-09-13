# PIL Negative Case Pack — Draft Proposal

**Status:** non-normative design draft prepared by the implementation side.
This document is **not** a contract. The oracle suite fixture specification
(`song_program_pil_oracle_suite_fixture_spec.md` section 6) excludes
binding/schema-stage malformed cases from the PIL oracle suite and assigns
them to "a separately versioned negative pack". No such pack exists yet for
PIL; this draft proposes its shape and lists the owner decisions required
before promotion.

## 1. Current failure-code coverage (no pack required for these)

Runtime failure codes are already exercised by synthetic unit tests
(`backend/tests/test_perceptual_failure_codes.py` and the phase test files):

| code | coverage |
| --- | --- |
| `PIL_BINDING_MISMATCH` | phase tests (hash/binding mutations) |
| `PIL_SCHEMA_INVALID` | failure-code tests (non-canonical ratio, run-level raise) |
| `PIL_NUMERIC_OVERFLOW` | failure-code tests (sub-millihertz frequency) |
| `PIL_PITCH_SUPPORT_EMPTY` | phase 1 tests + precedence test |
| `PIL_SEGMENTATION_POLICY_INVALID` | phase 2 tests + precedence test |
| `PIL_SEGMENT_BOUNDARY_INVALID` | failure-code tests (odd `ticks_per_beat`) |
| `PIL_SEGMENT_EMPTY` | phase 2 tests |
| `PIL_FEATURE_EXTRACTION_FAILED` | phase 3 tests |
| `PIL_VOCABULARY_FAILED` | phase 3 tests |
| `PIL_VOICE_MATCHING_FAILED` | phase 4 tests |
| `PIL_TRAJECTORY_FAILED` | phase 4 tests |
| `PIL_RESULT_VALIDATION` | failure-code tests (corrupt report bounds) |
| `PIL_GENRE_FAILED` | **blocked** (G1–G7; Phase 5 does not exist) |

## 2. Proposed pack shape (draft, for owner review)

```yaml
schema: cps.pil-negative-case-pack        # proposed; N1
schema_version: 1.0.0
pack_version: <SemVer, owner-assigned>    # same rule as suite_version
cases:
  - case_id: ^pil_neg_[a-z0-9_]+$
    phase: pitch_projection|harmonic_segmentation|chord_similarity|functional_trajectory
    input: <full Project/manifest/asset payloads, like oracle case inputs>
    expected_error: <one of the 13 section 4.3 codes>
    expected_report: none|failure_report   # binding/schema => none
pack_hash: <generic artifact self hash>
```

- Binding/schema-stage cases (`PIL_BINDING_MISMATCH`, `PIL_SCHEMA_INVALID`)
  assert that **no report is created** (the error propagates); later-stage
  cases assert a normal failed report with the exact error code.
- Case inputs are mutated descendants of the promoted oracle case inputs, so
  the pack stays byte-closed over real bindings rather than synthetic
  shortcuts.
- Once promoted, the pack lives under the protected conformance area and
  follows the same readonly-guard and version-bump rules as the oracle suite.

## 3. Open owner decisions (N-blockers)

| # | decision |
| --- | --- |
| N1 | Pack schema name, versioning rule, and whether it needs its own JSON Schema or reuses an existing registry shape |
| N2 | Whether binding-stage negatives execute the reference implementation (expecting a raise) or only the validators |
| N3 | Required coverage: all 13 codes, or only the binding/schema codes the oracle suite excludes |
| N4 | Relationship to the project-level negative pack (`fixtures/negative/`, `cps.negative-mutation-cases`): separate PIL registry vs extension |
| N5 | `PIL_GENRE_FAILED` cases wait for Phase 5 (G1–G7) and are out of 1.0 scope |

## 4. Non-goals

This draft does not create the pack, its schema, or any fixture. Unit tests
already prevent regression of every 1.0 failure code; the pack is an
authoritative hardening layer whose shape the owner must fix first.
