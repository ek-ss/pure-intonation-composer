# Lattice dimension and generator policy

## Scope

Lattice dimension is the length of `lattice.generators`. Generators are an
ordered basis and are not inferred from the equave. `coordinate_bounds`, every
tonal center, direct vector, harmony root anchor, chord vector, offset vector,
and mutation vector delta must have exactly that length. Generator order is
semantic and participates in canonical bytes and hashes.

The supported forward range is one through five dimensions. SongProgram 0.1
and ArrangementProject 1.2 remain immutable legacy authorities with a ceiling
of three. SongProgram 0.2 and ArrangementProject 1.3 carry the one-through-five
dimensional envelope. A 0.2 compile always emits 1.3; a 0.1 compile continues
to emit 1.2.

## Variable generator rules

- The equave is independently selectable (`2/1`, `3/1`, or another positive
  reduced ratio allowed by the enclosing profile).
- A generator may share prime factors with the equave. It must not be silently
  removed, reordered, or normalized by the compiler.
- Musical profiles declare `required_prime_factors`; the current full-song
  exploration profile declares `[3, 5, 7]`. Coverage is the union of prime
  factors in the equave and all generator numerators and denominators.
- The core compiler does not impose the full-song profile's 7-limit choice.
  Other profiles may select different generator sets while retaining the same
  dimensional contract.

## Bounded exploration

Dimension alone is not a sufficient resource bound. Before resolution, the
compiler computes the Cartesian coordinate cardinality and rejects it when it
exceeds `pitch_exploration.maximum_domain_points`. Navigation derivation uses a
separate `maximum_navigation_points` ceiling and streams the Cartesian product
instead of materializing it. Thus a five-dimensional domain is valid only when
its per-axis widths keep the declared search bound.

## Compatibility boundary

The legacy exact GEN0-B compiler manifest and fallback/mutation conformance
fixtures remain frozen to their existing dimensional ceilings and hashes.
Their promotion to the 0.2/1.3 envelope requires new independent oracle
fixtures rather than rewriting old goldens. Direct-vector compilation,
Project validation, composition vector padding, exploration navigation,
ProgressionQuery 2.0 lowering, and Mutation 2.0 vector operations are
implemented for five dimensions now. The non-authoritative compiler path can
therefore generate harmony and apply mutations in five dimensions. GEN0-B
receipt/evidence now has a separately promoted five-dimensional suite; see
[the authority contract](gen0b_5d_authority_contract.md). Connected SearchLoop13
cache and RunContext promotion remain separate.
