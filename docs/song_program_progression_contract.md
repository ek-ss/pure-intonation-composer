# GEN0-B Progression Resolver Contract

**Status:** normative and implementation-ready; execution remains gated by GEN0-A equality

## Input and output

Input is an ordered, gapless sequence of `HarmonyQueryOccurrence` records. Each
record contains occurrence ID/timing, ChordIntent hash, root anchor, and the
ordered exact top-K candidate cores returned by a GEN0-A-conforming resolver.
Candidates are immutable; progression search may select but never retune them.

Native GEN0-B output is exact only when all states and transitions in this
finite layered graph are evaluated. `beam_bounded` output remains a diagnostic
artifact and is forbidden from Project, viability, and QD inputs.

## Voice correspondence

For an edge from A to B, enumerate every injective matching from the smaller
voice set into the larger. Unmatched count is the voice-count difference.
Matched voices use absolute integer `ratio_mc`; exact common tone means equal
reduced ratio after applying the selected absolute registers.

For each matching compute:

```text
(
  unmatched_voice_count,
  lost_exact_common_tone_count,
  crossing_count,
  sum_absolute_motion_mc,
  maximum_absolute_motion_mc,
  bass_motion_mc,
  unintended_comma_drift_mc,
  sum_lattice_l1_motion,
  canonical_matching_key
)
```

`crossing_count` counts unordered matched voice pairs whose height order
reverses, with exact-height ties ordered by target ordinal, vector, exponent,
ratio. `bass_motion_mc` compares the lowest voices under the same order.
Unintended comma drift is zero for identical exact common tones; otherwise it
is the absolute difference between actual motion and equave-wrapped phase
motion for matched equal target ordinals. Lattice L1 uses generator-schema
coordinate order plus absolute equave-exponent change. Select the
lexicographically minimum matching; weighted sums are forbidden.

## Path score

Hard constraints reject candidate states before edge construction: Project
validity, track range/polyphony, forbidden crossing policy, and maximum voice
motion. The exact Viterbi path score is the lexicographic tuple:

```text
(
  total_unmatched_voices,
  total_lost_exact_common_tones,
  total_crossings,
  total_absolute_motion_mc,
  maximum_single_voice_motion_mc,
  total_bass_motion_mc,
  total_unintended_comma_drift_mc,
  total_lattice_l1_motion,
  sum_local_pair_rms_mc,
  sum_local_pair_max_mc,
  sum_local_complexity,
  canonical_path_key
)
```

Totals use checked u64; motion and complexity overflow is a typed failure.
`maximum_single_voice_motion_mc` is updated by max, not addition.
`canonical_path_key` lists occurrence ID, ResolvedChord core hash, and matching
key in timeline order. This is the only tie-break. Genre, roughness, openness,
and production costs do not participate in GEN0-B.

## Search and budget

Layer order is occurrence order; state order is candidate score/core hash.
Transitions enumerate predecessor state then canonical matching order. Exact
dynamic programming retains the best complete score for every state plus its
canonical predecessor. No beam pruning is allowed in native mode.

Ledger adds `progression_states` and `progression_edges` counters in a new
`gen0-progression-exact-v1` profile. Reserve one state before evaluation and one
edge before matching enumeration. Exhaustion returns no path or Project.
Cache keys include the ordered occurrence/candidate core hashes, algorithm,
NumericContract, and budget profile.

## Melody binding

After the harmony path is fixed, SP0 `chord_member` melody binds by active
occurrence and canonical target ordinal. Failure is `MELODY_HARMONY_CONFLICT`;
GEN0-B does not backtrack into another harmony path. Neighbor, approach,
cross-occurrence anticipation, and comma-movement provenance remain GEN0-B2.

## Acceptance

- exhaustive path enumeration and Viterbi produce identical path bytes for all
  graphs with <=6 layers and <=6 states/layer;
- permutation of physical input arrays leaves canonical output unchanged;
- common-tone, inversion, unequal-voice, crossing, comma-drift, and exact-tie
  goldens cover 2/1 and 3/1;
- 1/2/4/8-worker and cache parity tests are byte-identical;
- every selected chord and event revalidates independently in Project 1.2;
- `beam_bounded` is rejected by native Project validation.
