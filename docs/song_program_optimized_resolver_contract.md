# GEN0-A Optimized Resolver Contract

**Status:** normative and implementation-ready

## 1. Boundary

GEN0-A replaces exhaustive enumeration speed, not musical semantics. For every
query accepted by both implementations it must return the same ordered top-K
`OracleResult` cores as `sp0-exhaustive-joint/v1`. Project 1.2 contains only the
selected exact `ResolvedChord`; optimization statistics and certificates live
in an external ResolverReport.

The optimized algorithm identifier is `sp0-joint-bnb/v1`. Its cache and budget
profile differ from the exhaustive oracle, but NumericContract, candidate
universe, eligibility order, score tuple, and tie-break bytes are identical.
Approximate, truncated, timed-out, or beam results may not be lowered to a
native Project 1.2 exact chord.

## 2. Query and candidate universe

The wire input is exactly `OracleQuery v1` from the SP0 Conformance Pack. The
anchor, placed-pitch enumeration, exact-ratio deduplication, canonical target
order, and candidate-to-target bijections are those in `numeric_oracle.md`.
An implementation may index or reorder physical work internally, but logical
node identity is the canonical tuple:

```text
(query_hash, assigned_target_count,
 target-ordered (vector, equave_exponent, reduced_ratio) prefix)
```

Top-K means the first `K` distinct complete candidates under the full frozen
NumericContract score. `K` is `1..24`. Distinctness is canonical resolved core
before ID assignment. Duplicate paths to one core are discarded without
changing its rank.

## 3. Permitted pruning proofs

Every pruned node records exactly one proof code. No unlisted heuristic may
remove a candidate.

Hard proofs:

- `DUPLICATE_EXACT_RATIO`: two assigned voices have the same exact ratio;
- `SPACING_VIOLATION`: an assigned adjacent absolute-pitch pair is already
  below the inclusive minimum;
- `SPAN_VIOLATION`: assigned maximum minus minimum exceeds maximum span;
- `BASS_VIOLATION`: a selected assigned pitch is below the required preserved
  bass, including the frozen exact-height tie order;
- `PAIR_MAX_VIOLATION`: a known pair exceeds the inclusive maximum;
- `PAIR_RMS_LOWER_BOUND`: with final pair count `M`,
  `RHE(sqrt(known_squared_error_sum/M))` exceeds the RMS limit;
- `COMPLEXITY_VIOLATION`: known non-negative pair complexity exceeds budget;
- `DOMAIN_OR_REGISTER_VIOLATION`: an assigned placed pitch violates an exact
  frozen domain predicate.

Ranking proof `WORSE_THAN_TOP_K` is permitted only after K eligible incumbents
exist. For a partial node compute:

```text
lower_prefix = (
  RHE(sqrt(known_squared_error_sum / final_pair_count)),
  maximum_known_absolute_pair_error,
  known_pair_complexity
)
```

Prune only when `lower_prefix` is lexicographically strictly greater than the
worst incumbent's first three score components. Equality never prunes because
unknown assignment/shape tie-break fields may win. All calculations use the
NumericContract; binary float bounds are forbidden.

## 4. Traversal and determinism

Logical children are generated in canonical placed-pitch then target-assignment
order. A priority queue may change physical evaluation order, but its key is
`(lower_prefix, logical_node_identity)`. Parallel workers publish completed
nodes through this total order. Thread count, hash seed, cache state, and queue
implementation cannot change result bytes, report counts, first failure, or
budget receipt.

Budget is reserved before node expansion and pair evaluation using
OperationBudgetLedger v1. Budget exhaustion returns no Project and no partial
top-K. Cache hits replay their receipt. Algorithm/profile digests are included
in cache keys and CompilerManifest.

## 5. Completeness certificate

ResolverReport contains:

- canonical query hash and candidate-universe digest;
- algorithm/build/profile/NumericContract identities;
- requested K and ordered result core hashes;
- placed count, logical partial/complete node counts, eligible count;
- counts per pruning proof code;
- root/child charge-receipt digest;
- `completion=exact` or a stable failure;
- exhaustive comparison fields when run in differential mode.

The universe digest hashes the canonical ordered list of retained placed pitches
and canonical target phases. A report claiming `exact` is invalid unless every
logical node is either evaluated or covered by one permitted proof. The report
is diagnostic and excluded from Project identity.

## 6. Differential acceptance gate

Before `sp0-joint-bnb/v1` may become a compiler capability:

1. exact ordered top-K core equality for all checked-in 2/1 and 3/1 oracle
   fixtures, K=1 and maximum available K;
2. equality over every domain with dimensions <=2, axis width <=3, register
   width <=3, voices 2..4, and the preregistered target set;
3. 10,000 deterministic generated queries covering negative/oversized steps,
   inversions, threshold equality, kernel-equivalent spellings, and no-solution;
4. identical results for 1, 2, 4, and 8 workers, cold/hit cache, and the
   Conformance Pack process matrix;
5. certificate accounting identity:
   `complete_nodes + hard_pruned_nodes + ranking_pruned_nodes` equals the
   canonical logical frontier partition defined by the reference enumerator;
6. every optimized winner is revalidated from scratch by the independent
   Project validator before lowering.

Performance is a release gate, not a semantic rule: on the frozen benchmark,
median logical complete-node evaluations must improve by at least 5x and p95
wall time by at least 2x versus exhaustive single-thread reference. Failure
keeps exhaustive resolution; it never weakens equality requirements.

## 7. Deferred to GEN0-B

Progression Viterbi/beam search, cross-chord voice-leading cost, candidate
retention across occurrences, melody backtracking, and approximate large-domain
search are outside GEN0-A. This contract returns independently exact top-K chord
candidates so GEN0-B can consume a stable vocabulary.
