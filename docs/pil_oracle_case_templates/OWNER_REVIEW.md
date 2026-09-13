# PIL Oracle Owner Acceptance Assertions

This file records semantic checks that precede authoritative promotion.  It is
not a golden artifact.  Passing hashes alone is insufficient: the independent
owner must establish every assertion below from the promoted input and report.

## Corrected case inputs

- `pil_12et_ii_v_i`: every named pitch uses the checked-in finite 5-limit
  approximation whose interpretation phase is within 2,250 millicents of its
  12-TET target.  Its `project_hash` and canonical report bytes must differ
  from `pil_exact_ratio_ii_v_i`.  The retained top trajectory must have
  `template_id == "ii_v_i"`, `canonical_alignment_key == [0,0]`, and a
  non-null similarity.
- `pil_exact_ratio_ii_v_i`: source ratios remain the simple-ratio JI spelling
  in the template.  Its retained top trajectory must have
  `template_id == "ii_v_i"` and `canonical_alignment_key == [0,0]`.
- `pil_seven_limit_multi_candidate`: the input contains a ratio with prime 7,
  and every pitch record must contain at least two strictly positive candidates
  whose weights sum to `2147483647`.
- `pil_kernel_boundaries`: the Numeric Contract must project
  `2158603/2097152` to exactly 50,000 millicents and
  `8887423/8388608` to exactly 100,000 millicents.  At 50,000 the two weights
  differ by one Q31 unit and the remainder goes to lower ordinal 0.  At 100,000
  class 0 has zero weight and is omitted, while class 1 receives all
  `2147483647` units.
- `pil_passing_tone_delta`: compare its two ordered segment interpretations.
  Both must retain `major` first, and
  `baseline_major_similarity_q - passing_major_similarity_q >= 700`.  The
  exact values remain protected by the full canonical-report golden.

## Native JI separation blocker

`pil_nonfunctional_two_reports` cannot yet be promoted.  The repository has
EvaluationReport schemas and hash-bearing search payloads, but no executable,
version-bound Native JI evaluator or authoritative Native JI report fixture
for this Project.  A syntactically valid invented SHA-256 value would prove
only correlation-field transport, not high Native JI coherence.

Promotion requires a separately produced Native JI report that:

1. binds the exact `project_hash` of `pil_nonfunctional_two_reports`;
2. identifies the Native JI evaluator manifest/build and metric definitions;
3. carries an independently checked native-coherence metric and an
   owner-declared acceptance threshold;
4. has canonical bytes and a recomputable report hash; and
5. is not consumed by PIL computation—its hash appears only as
   `native_ji_report_hash` correlation metadata.

The template intentionally keeps `native_ji_report_hash: null`; owner promotion
binds the independently authenticated report hash only in the protected copy.
