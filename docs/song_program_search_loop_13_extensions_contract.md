# SearchLoop13 Evaluation, Calibration, and Challenger v1.1 extension

This extension adds authority versions without changing EvaluationManifest or
EvaluationReport v1.0, or Challenger policy/decision v1.0. A RunManifest 1.3
that selects these artifacts binds their raw schemas and inline RunContext
artifacts; a v1.0 artifact cannot be substituted for its v1.1 counterpart.
All self hashes use the Search Decision Contract `cps-artifact-hash/v1` preimage
with only the named self-hash member removed.

## Evaluation and genre similarity

EvaluationManifest 1.1 adds the `genre_feature_record` source kind and the
metric operator `{kind:"genre_similarity_q",genre_similarity_spec_hash}`.
Its sources are the candidate FeatureRecord followed by the selected reference
FeatureRecords in UTF-8 `reference_id` order. EvaluationReport 1.1 adds
`uncalibrated` to missing reasons. A GenreIntent metric requiring similarity is
`uncalibrated` unless its bound CalibrationDecision is promoted for that metric;
it is then ineligible for challenger/Pareto, never zero or a planner score.

`normalized-l1-q31/v1` checks equal nonempty vector dimensions. For each
reference, it sums `abs(candidate_q31-reference_q31)` in checked signed128,
then calculates `distance_q = RHE(10000*sum/(dimension*(2^32-1)))` and
`score_q=10000-distance_q`. `lower-median-reference-score/v1` sorts scores
ascending and takes index `(n-1)//2`. Bad Q31 input, dimension mismatch,
signed128 overflow, and out-of-range result fail in that order after source and
schema binding checks. Genre labels/tags do not enter this arithmetic.

Genre evidence never accepts precomputed scalar inputs. Its first
`feature_record_hashes` item is the candidate and the remainder are exactly the
reference source bindings in manifest order; every hash resolves to the bound
GenreFeatureRecord. Scalar operators use ScalarEvidence, while
`genre_similarity_q` uses GenreEvidence. Mixing the two shapes is
`EVALUATION_OPERATOR_INVALID` before arithmetic.

## Calibration

Reference members are UTF-8 `reference_id` sorted and unique globally, so a
reference cannot enter multiple partitions. Response rows sort by
`(participant_hash raw bytes,item_id UTF-8,presentation_ordinal)` and the tuple
is unique; participant and stratum must belong to the bound cohort/policy.

For deterministic stratified bootstrap replicate `r`, draw index `i` from a
stratum of size `n` as `uint64be(SHA256("cps.calibration-bootstrap/v1\\0" ||
u64be(seed) || u64be(r) || UTF8(stratum) || u64be(i))[0:8]) mod n`. Ranks use
sorted `n` values at `floor((n-1)*numerator/denominator)`; lower fraction must
not exceed upper fraction. A zero denominator yields no ratio and its criterion
fails. All ratio rounding is nonnegative RHE. Calibration decision promotion
requires its promoted metric set and every margin to equal the corresponding
ChallengerAcceptancePolicy 1.1 row.

## Challenger and stopping

ChallengerPolicy/Decision 1.1 restore typed EvaluationReport source
`artifact_kind/schema_hash/json_pointer`, the GenreIntent, EvaluationManifest,
CalibrationDecision, candidate evaluation-report hashes, and a tie result.
Rows have contiguous ordinals. A candidate is noninferior when it is within its
`noninferiority_margin_q` in every directed metric, and improves when it exceeds
`improvement_margin_q` in one; non-dominated ties use the directed metric tuple
then program hash.

RoundImprovementEvidence rows are unique by cell. A new cell is material; a
replacement is material exactly when its direction-normalized first difference
is at least StoppingPolicy's threshold. The evidence boolean must equal this
calculation before patience is updated. `search_loop13_extension_oracle.py` is
the independent reference for this extension.
