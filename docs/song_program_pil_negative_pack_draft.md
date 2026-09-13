# PIL Negative Case Pack — Promotion Record

**Status:** N1-N5 are resolved by the independent maintainer ruling below.
The oracle suite fixture specification
(`song_program_pil_oracle_suite_fixture_spec.md` section 6) excludes
binding/schema-stage malformed cases from the PIL oracle suite and assigns
them to "a separately versioned negative pack". That pack is now fixed below.

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

## 2. Normative 1.0 pack shape

```yaml
schema: cps.pil-negative-case-pack
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

The closed schema is
`backend/songprogram_conformance/schemas/pil_negative_case_pack.schema.json`.
Its authoritative pack is
`backend/songprogram_conformance/fixtures/pil_negative/pack.json`.

## 3. Maintainer rulings (N1-N5)

| # | ruling |
| --- | --- |
| N1 | A separate closed `cps.pil-negative-case-pack` 1.0 schema is used. `pack_version` follows SemVer and any changed case or expectation requires a version bump. |
| N2 | Cases execute the same reference entry point as normal PIL execution and require a raised `PilError`; validators alone are insufficient. No report may be emitted. |
| N3 | Version 1.0 covers exactly the two pre-report classes excluded from the oracle suite: `PIL_BINDING_MISMATCH` and `PIL_SCHEMA_INVALID`. Computation-stage failures remain in the oracle suite or unit conformance tests. |
| N4 | The pack is a separate PIL registry. It must not extend or reinterpret the Project mutation negative pack. |
| N5 | `PIL_GENRE_FAILED` is excluded. A Phase 5 negative-pack version is forbidden until G1-G7 are closed. |

## 4. Non-goals

The initial cases are mutated descendants of the authoritative
`pil_12et_ii_v_i` case and bind both its raw-file digest and the containing
suite digest and its completed 1/2/4/8 matrix receipt. JSON Pointer replacement is applied to an in-memory copy. Case
order is UTF-8 `case_id` order and IDs are unique. Pack hash uses the generic
artifact hash over the object without `pack_hash`.
