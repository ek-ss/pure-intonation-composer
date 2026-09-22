# Affective Interpretation Layer 1.0

## Purpose and authority boundary

The Affective Interpretation Layer is the third parallel interpretation branch beside Native JI and PIL. It never replaces, normalizes, gates, repairs, or feeds either branch. All three consume the immutable ArrangementProject independently. Affective metrics are audit-only in version 1.0 and are not members of the SearchLoop quality tuple.

Version 1.0 separates five perceptual concepts instead of publishing a binary bright/dark label:

- `perceived_valence_q`: negative/dark to positive/bright, `[-10000,10000]`;
- `arousal_q`: calm to active, `[0,10000]`;
- `harmonic_majorness_q`: minor-like to major-like, `[-10000,10000]`;
- `tonal_tension_q`: stable to tense, `[0,10000]`;
- `timbral_brightness_q`: dark to bright spectrum, nullable in the symbolic profile.

`confidence_q` describes available symbolic evidence, not correctness. It MUST NOT be interpreted as a calibrated probability.

## Symbolic profile

`symbolic-affect-five-axis/v1` reads exact Project ratios. It does not quantize or rewrite them. Interval phases are compared continuously with the 300,000 millicent minor-third and 400,000 millicent major-third templates by a triangular kernel of manifest-bound radius. Majorness is major support minus minor support. Tonal tension is the complement of proximity to the fixed unison, minor/major third, fourth, fifth, minor/major sixth consonance set.

Valence is the fixed integer combination `60% majorness + 20% mean register + 20% melodic pitch direction`. Arousal is `40% tempo + 30% onset rate + 30% velocity`. Every division uses round-half-even integer arithmetic. The report contains whole-song values and the same extraction independently for each non-empty form section.

These formulas are deterministic baseline hypotheses. They require listener calibration before becoming search objectives or acceptance gates.

## Audio boundary

Symbolic profile 1.0 sets `timbral_brightness_q=null` and `audio_feature_status=not_evaluated`. A future audio profile must bind an exact PCM artifact, extractor manifest, segmentation rule, and calibration decision. It may use spectral centroid, rolloff and high-frequency energy, but cannot retroactively fill or reinterpret a symbolic report.

## Parallel harness

ParallelEvaluationAuthority and ParallelEvaluationReport 1.1 add respectively `affective_manifest` and `affective_report`. Version 1.0 remains valid and unchanged for fixture and cache compatibility. The existing five-component quality tuple is unchanged in 1.1. Report and manifest hashes use the common `cps-artifact-hash/v1` preimage.

Standalone execution:

```text
backend/.venv/bin/python backend/tools/evaluate_affective.py \
  --project /path/to/project.json \
  --output /path/to/affective_report.json
```

## Failure codes

- `AFFECTIVE_MANIFEST_INVALID`
- `AFFECTIVE_PROJECT_INVALID`
- `AFFECTIVE_INSUFFICIENT_NOTES`

No failed report is synthesized. A branch failure cannot alter Native JI or PIL evidence.
