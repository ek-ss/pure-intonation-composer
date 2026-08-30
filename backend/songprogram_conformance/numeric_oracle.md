# SP0 Numeric and Exhaustive-Oracle Conformance

`reference.py` is an independent standard-library interpretation of
`cps-numeric/decimal-log2-rhe-v1`. It exposes `ratio_mc`, `edo_phase_mc`,
`wrap_mc`, `pair_rms_mc`, `odd_limit`, `chord_complexity`, `validate_query`,
and `resolve_exact`.

## Oracle candidate universe

```text
canonical targets := unique EDO steps modulo D, sorted by (phase_mc, step)
anchor placed pitch := (anchor_vector, anchor_equave_exponent)
placed universe := vectors in lexicographic Cartesian-product order, then
                   exponent in inclusive ascending register bounds
retain pitches passing exact domain filters
deduplicate equal exact ratios by retaining the first (vector, exponent)
for every combination of N-1 non-anchor pitches:
  for every lexicographic permutation assigned to targets 1..N-1:
    assign anchor to canonical target ordinal 0
    evaluate all hard checks and the NumericContract score
choose the lexicographically smallest eligible score
```

Completeness is exact only for this finite universe. There is no branch
pruning, independent nearest-note snap, implicit repair, or fallback. Results
store voices in canonical target order. Portable interfaces are
`oracle_query.schema.json` and `oracle_result.schema.json`.

## Frozen numeric dataset

`goldens/numeric_seed_1592639710.jsonl` contains 1,000 canonical JSON records
generated with `random.Random(1592639710)`. It covers ratio, EDO, wrap, RMS,
odd-limit, and chord-complexity operations. The `.sha256` sidecar hashes the
exact JSONL bytes. `generate_numeric_goldens.py` must reproduce both
byte-for-byte; ordinary consumers compare checked-in expected integers rather
than rewriting them.
