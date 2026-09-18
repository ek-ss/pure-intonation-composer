# Parallel Evaluation Harness Contract 1.0

## Purpose

The parallel evaluation harness connects a compiled Project to three separate
evaluation branches: Native JI lattice coherence, PIL Phase 1–5 interpretation,
and calibrated genre-reference similarity. PIL is an additional interpretation
layer. It does not replace, recompute, gate, or provide fallback values for the
Native JI branch.

## Authority and hashing

`cps.parallel-evaluation-authority` is a closed, self-hashed payload containing
the Native JI and PIL manifests, every PIL Phase 3/4 policy, the Phase 5 genre
model, GenreIntent, ReferenceSetManifest, GenreSimilaritySpec,
CalibrationDecision, and the exact reference GenreFeatureRecords.

`authority_hash` and `report_hash` use `cps-artifact-hash/v1`: remove only the
self-hash member and hash
`"cps-artifact-hash/v1\0" || schema || "\0" || schema_version || "\0" ||
canonical_json(payload)`. There is no final line feed.

The harness rejects a broken GenreIntent binding, an unsealed authority,
missing calibration reference records, extractor substitution, dimensional
mismatch, and non-Q1.31 values before publishing a report. Labels such as
`kawaii_future_bass` remain metadata; scores come only from the bound feature
records and calibrated artifacts.

## Branch execution

Native JI computes `native_ji.coherence` directly from exact Project lattice
coordinates. Its report is completed before PIL starts. PIL receives only the
Native JI report hash as correlation metadata and is prohibited from reading
its metric value. A PIL failure cannot synthesize or alter Native JI evidence.

Genre similarity uses `normalized-l1-q31/v1`. For dimension `D`, each
calibration reference score is
`10000 - RHE(10000 * sum(abs(candidate_i-reference_i)) /
(4294967295*D))`. Scores sort ascending and index `(N-1)//2` is selected.

The SearchLoop quality tuple is ordered as genre similarity, Native JI
coherence, PIL genre typicality, PIL genre idiomaticity, and inverse PIL cliche
dependence. All five are integers from 0 through 10000. This fixed order is
recorded in every report and matches the existing SearchLoop requirement for a
five-component quality tuple.

## Interfaces

`evaluate_parallel(project, authority, candidate_feature)` returns the closed
parallel report. `SearchEvaluationAdapter(authority, feature_provider)` has the
exact callable shape required by `SearchLoopSeams.evaluate`. The provider is
responsible only for resolving the already-pinned audio feature extractor; the
harness authenticates its returned FeatureRecord and extractor binding.

For an already generated candidate:

```text
backend/.venv/bin/python backend/tools/evaluate_parallel.py \
  --project /path/to/project.json \
  --authority /path/to/parallel_evaluation_authority.json \
  --candidate-genre-feature /path/to/genre_feature_record.json \
  --cache-directory /path/to/cache \
  --output /path/to/evaluation
```

The command writes the aggregate report plus Native JI, PIL, and PIL genre
sidecars. It never modifies the Project or any reference authority.

## Fixed feature snapshot and reference intake

The checked `pcm32_genre_feature_extractor_v1.json` manifest pins the production
`cps.pcm32-temporal-energy-zcr` 1.0.0 provider by exact source hash. It accepts
48 kHz uncompressed PCM32 mono/stereo WAV, applies integer round-half-even mono
downmix, and emits 16 temporal mean-absolute-amplitude plus 16 zero-crossing
Q1.31 bins over the fixed ten-second window. Short input is rejected; it is
never padded or looped. The provider is intentionally a deterministic baseline,
not evidence that a genre calibration has succeeded.

`extract_genre_feature.py` creates a candidate FeatureRecord. For reference
audio, `build_genre_reference_set.py` consumes an operational intake JSON with
`reference_set_id`, `evaluation_epoch_day`, and `sources`. Each source contains
`partition`, `provenance`, and `wav` paths. It verifies the sealed license
policy and provenance, storage/extraction/evaluation rights, expiry,
revocation, and exact raw-audio hash. Calibration, validation, and holdout must
all be non-empty.

The intake tool emits the ReferenceSetManifest, one FeatureRecord per member,
and `calibration_readiness.json`. The readiness status remains
`awaiting_external_calibration` until a real listener cohort, blinded
assignments, response set, holdout evidence, and maintainer promotion decision
exist. Neither the tool nor the implementation tests may issue a promoted
CalibrationDecision from synthetic or missing evidence.
