# Exploration Cohort Profile v1

Status: non-authoritative development profile. It does not replace any GEN0
conformance authority or golden fixture.

## Authority construction

`backend/tools/run_fixture_generation_cohort.py` creates one sealed
`SamplerManifest` and `StructuralLoweringManifest` for every cohort seed. The
seed-addressed choices use SHA-256 domain
`cps.exploration-authority/v1` and are therefore independent of process order
and worker count. Every successful seed directory persists both manifests.

The sampler uses weighted `2/1` (`3/1`, `5/1`) and `3/1` (`2/1`, `5/1`)
domains, their compatible 12-EDO or 13-EDT triad reference, two rhythm grids,
two density levels, and the existing broad structural role/material tables.
The lowering authority selects tempo, tonal center, a four-point signed vector
walk, note duration, and accent. A candidate is rejected before compilation
when its chord reference equave differs from its lattice equave, or when any
melody rhythm cannot be contained by the section's single harmony rhythm.

## Audible identity and admission

`audible_project_hash` is SHA-256 over domain
`cps.audible-project/v1`, followed by canonical bytes containing only:

- clock and lattice base frequency;
- role, instrument, polyphony, gain, and pan for each track;
- event kind, role, start, duration, velocity, exact ratio, and drum note.

IDs, provenance, receipts, and compiler diagnostics are excluded. Cohort
semantic admission is ordered by ascending seed. The first candidate for an
audible hash is accepted; later candidates with the same hash are retained in
the ledger and marked `rejected_duplicate`.

## Catalog

The profile constructs an immutable Q1.31 mono asset for each pitched role.
Bass, harmony, melody, and texture use different deterministic harmonic
partials. Drums use a separate impulse asset. The canonical catalog and its
content-addressed asset descriptors are saved with every cohort run.

## Report

The report records all requested seeds, including failures; compile survival;
failure counts; Program, Project, audible Project, and WAV duplicate rates;
semantic admission; role and material distributions; equave counts; and both
candidate-presence and event-frequency lattice-vector distributions.

Reports under `songprogram_conformance/reports/non_authoritative` are measured
evidence, not golden outputs. A filename or `measurement_note` identifies a
report produced before a subsequently documented fix.
