# GEN0-B Progression Resolver Contract

**Status:** normative and implementation-ready; execution remains gated by GEN0-A equality

## Input and output

Input is a self-contained `cps.progression-query` `1.1.0` containing an ordered,
gapless sequence of `HarmonyQueryOccurrence` records. Each record contains
occurrence ID/timing, ChordIntent hash, root anchor, and the ordered exact top-K
canonical candidate-core payloads returned by a GEN0-A-conforming resolver.
Hash-only `1.0.0` queries are non-conforming: no filesystem, database, process
cache, or implementation-private lookup may supply missing core data.
Candidates are immutable; progression search may select but never retune them.

Each candidate payload contains the complete Project 1.2 `resolved_chord`, its
full SHA-256 `core_hash`, a normalized matching projection containing
domain/intent hashes, anchor, local RMS/max/complexity, and 2..8 voices. A voice contains canonical target
ordinal, absolute lattice vector, absolute equave exponent, positive reduced
exact ratio, and signed `ratio_millicents`. Voice order is
`(ratio_millicents,target_ordinal,absolute_vector,equave_exponent,exact_ratio)`.
Target ordinals are unique. Vector dimensions equal the query domain and root
anchor; candidate domain/intent hashes equal their enclosing query/occurrence.
The candidate anchor equals the occurrence root anchor, and each absolute
vector is that anchor plus the corresponding `resolved_chord.voice_offsets`
entry. Every projected field must equal its `resolved_chord` authority.

`ratio_millicents` must equal NumericContract RHE conversion of `exact_ratio`.
`core_hash` is the complete SHA-256 used by the Project 1.2 ResolvedChord ID
preimage, before base32 truncation; the stored `resolved_chord.id` must be its
specified `rc_` derivation. Schema validation, reduced-ratio validation, dimensional
and enclosing-hash validation, ratio conversion, voice-order/ordinal checks,
and finally core-hash validation occur in that order. First failure returns no
result. Candidate array order must equal GEN0-A score order
`(local RMS,local max,local complexity,core_hash)` and hashes are unique.

Native GEN0-B output is exact only when all states and transitions in this
finite layered graph are evaluated. `beam_bounded` output remains a diagnostic
artifact and is forbidden from Project, viability, and QD inputs.

## Voice correspondence

For an edge from A to B, enumerate every injective matching from the smaller
voice set into the larger. Unmatched count is the voice-count difference.
Matched voices use signed integer `ratio_millicents`; exact common tone means
byte-equal reduced `exact_ratio`. Thus neither fact is inferred from the other.

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

The normative `gen0-progression-exact-v1` Budget Contract profile adds
`progression_states` and `progression_edges`. Reserve one state before its hard
constraint evaluation. For layers after the first, reserve one edge for every
Cartesian predecessor/current candidate pair before enumerating any matching;
an invalid or unreachable endpoint does not refund it. Matching permutations
carry no separate counter. Reservation atomically updates the progression
child, root leaf counter, and root `total_logical_units`. Exhaustion returns no
path or Project.

The cache key hashes the complete canonical query bytes, including all
candidate payloads, plus algorithm, NumericContract, and budget-profile
digests. A cache hit replays the full progression child receipt atomically;
there is no core lookup during replay.

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
