# SongProgram NumericContract v1

Status: normative for SP0. Identifier: `cps-numeric/decimal-log2-rhe-v1`.

## Arithmetic environment

Inputs are positive reduced rational numbers with arbitrary-precision integer
components. Published pitch values are signed integer millicents. Binary float
is forbidden. Each evaluation uses a fresh local decimal context, half-even
rounding, exponent range at least +/-999999, and traps invalid, division by zero,
and overflow. Evaluate independently at 80 and 112 decimal digits. If the final
integers disagree, retry from scratch at 144, 176, 208, 240, and 256. Return
after two consecutive precisions agree; otherwise `NUMERIC_INDETERMINATE`.
Caller context and intermediate values are never reused.

`RHE(x)` rounds to an integer, ties to even.

## Pitch functions

For reduced `r=n/d`:

```text
ratio_mc(r) = RHE(1_200_000 * (ln(n) - ln(d)) / ln(2))
```

Do not first form a Decimal quotient. Goldens:
`1/1=0`, `2/1=1200000`, `5/4=386314`, `3/2=701955`, `6/5=315641`,
`7/4=968826`, `3/1=1901955`. Reciprocal results must be exact negatives.

For ChordIntent reference equave `E`, divisions `D>=1`, step `s`:

```text
k = s mod D, in 0..D-1
edo_phase_mc(E,D,s) = RHE(1_200_000 * log2(E) * k / D)
```

Use unrounded `log2(E)`; duplicate canonical phases in one intent reject.
Goldens: 2/1 12-EDO steps 0,3,4,7,11 give
0,300000,400000,700000,1100000. 3/1 13-EDO steps 0,1,3,4,7,12 give
0,146304,438913,585217,1024130,1755651.

## Joint chord error

Recognition wraps by the ChordIntent reference equave, never the lattice-domain
equave. Let `P=ratio_mc(E)`:

```text
wrap(x,P) = ((x + floor(P/2)) mod P) - floor(P/2)
T(i,j) = wrap(target_phase[j] - target_phase[i], P)
A(i,j) = wrap(ratio_mc(actual[j] / actual[i]), P)
error(i,j) = wrap(A(i,j) - T(i,j), P)
```

Modulo is non-negative. Evaluate all unordered `i<j` pairs for every complete
candidate-to-target bijection; independent nearest-note snapping is invalid.
For `P=1200000`, wrap(600000)=-600000 and wrap(-600001)=599999.

For `M=N(N-1)/2`, `N>=2`:

```text
pair_max_mc = max(abs(error))
pair_rms_mc = RHE(sqrt(sum(error^2) / M))
```

Thresholds compare these quantized integers inclusively. RMS goldens:
`[1,0,0,0]->0`, `[3,0,0,0]->2`, `[3,4]->4`.

## Exact relation complexity

For each unordered sounding pair, set `q=max(ri,rj)/min(ri,rj)` and reduce by
exact powers of reference equave `E` until `1<=q<E`:

```text
pair_complexity = bit_length(numerator) + bit_length(denominator) - 2
chord_complexity = sum(pair_complexity)
```

The budget is inclusive. This is invariant under common frequency translation,
voice permutation, and alternate lattice spellings with identical ratios.
`[1,5/4,3/2]` under 2/1 and `[1,5/3,7/3]` under 3/1 both score 10.

For domain `maximum_odd_limit`, first equave-reduce a positive ratio exactly to
the unique `1<=q<E`, write reduced `q=n/d`, and define
`odd_part(x)=x/2^v2(x)` and `odd_limit=max(odd_part(n),odd_part(d))`. The hard
test is inclusive. Goldens: under 2/1, 5/4 and its equave shift 5/2 have limit
5; 64/63 has 63 and 64/65 has 65. Under 3/1, 5/3 and its equave shift 5/1
both have 5. Only powers of two are stripped; the equave reduction already
accounts for a 3/1 equave.

## Eligibility and total ordering

Define `absolute_voice_mc=ratio_mc(final_ratio)` and
`sounding_phase_mc=absolute_voice_mc mod P` using non-negative modulo. Sort
voices by `(absolute_voice_mc, reduced_ratio_n, reduced_ratio_d, vector,
equave_exponent)`. Minimum spacing is the minimum adjacent integer difference;
span is last minus first. Spacing requires `>=minimum_spacing_mc`; span requires
`<=maximum_span_mc`, both inclusive. With `bass_policy=preserve_target`,
`bass_target_ordinal` requires the first sorted voice to be assigned to that canonical target ordinal;
the remaining tuple fields resolve exact-height ties.

Reject in order: voice/phase invalidity; domain/register/ratio invalidity; exact
duplicate ratios; spacing/span/bass violation; maximum error; RMS error;
complexity budget. Near-class clustering is audit-only in SP0.

Eligible candidates use this lexicographic key; weighted sums are forbidden:

```text
(pair_rms_mc, pair_max_mc, chord_complexity,
 assignment_key, canonical_shape_key)
```

Targets sort by `(edo_phase_mc, canonical_step)` and every bijection is tested.
`assignment_key` lists, in target order, `(sounding_phase_mc, ratio_n, ratio_d,
offset_vector, equave_exponent)`. `canonical_shape_key` subtracts the first
target-ordered voice's vector and exponent from all voices, then flattens
`(relative_vector, relative_exponent, ratio_n, ratio_d)`. Generator order is
semantic. Enumeration, map, cache, and thread order cannot affect the winner.

## Required golden chord and tests

Major target `[0,4,7]`, ratios `[1,5/4,3/2]`: errors
`[-13686,+1955,+15641]`, maximum 15641, RMS 12052, complexity 10. Minor target
`[0,3,7]`, ratios `[1,6/5,3/2]`: `[+15641,+1955,-13686]`, same aggregates.
Equal limits pass; lowering the relevant limit by one fails.

Independent implementations test caller-context isolation, target/candidate
permutations, common transposition, kernel-equivalent spelling, 2/1 versus 3/1
wrap, precision escalation, and an adversarial independent-nearest rejection.
