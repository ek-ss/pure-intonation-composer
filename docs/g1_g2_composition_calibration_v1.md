# G1/G2 composition calibration cohort v1

This cohort calibrates composition viability without replacing Native JI or PIL. G1 is a
parallel, non-authoritative symbolic feature report. G2 is a blind perceptual assignment.
Neither result changes archive admission until a separately promoted calibration decision
binds thresholds and failure policy.

## Cohorts

- 24 legacy full-song generator candidates.
- 24 CompositionPlan 2.0 generator candidates.
- 48 destructive negatives: 8 each for foreground removal, groove removal, bass
  desynchronization, middle silence, ending truncation, and flattened dynamics.
- 24 rights-cleared ACE-Step reference clips as the G2 ceiling cohort.

The ceiling clips do not have a SongProgram or Project. They therefore deliberately have no
G1 symbolic report and are marked for G2 use only. Supplying invented symbolic features for
these clips is forbidden.

## Split and blinding

The split unit is a lineage, never an individual artifact. A generated source and all of its
destructive derivatives remain in one partition. Lineages are stratified by their complete
cohort-membership signature, ordered by a domain-separated SHA-256 key, and divided 70/30.
The blind manifests expose only an opaque ID, ordinal, audio path, and audio hash. Generator,
negative type, candidate ID, lineage ID, and G1 features remain hidden from the listener.

The checked local-authority result contains 87 calibration and 33 holdout assignments, with
zero lineage crossover. Each destructive-negative type contributes six calibration and two
holdout candidates.

## Known v1 limitation

`flatten_dynamics` is intentionally retained even though G1 v1 does not react to it. G1 v1
extracts symbolic structure but has no velocity/loudness-contour feature. The item is useful
for G2 and documents a measurable G1 blind spot. Adding a dynamic-arc metric requires a new
feature schema/version and regeneration of every report; it must not be silently inserted
into this frozen v1 cohort.

## Local artifacts

- `local_authority/g1_old_generator_24_v1/`
- `local_authority/g1_new_generator_24_v1/`
- `local_authority/g1_destructive_negatives_v1/`
- `local_authority/g1_g2_calibration_v1/candidates.json`
- `local_authority/g1_g2_calibration_v1/lineage_split.json`
- `local_authority/g1_g2_calibration_v1/blind_calibration.json`
- `local_authority/g1_g2_calibration_v1/blind_holdout.json`
- `local_authority/g1_g2_calibration_v1/ceiling_reference_manifest.json`
