# PIL Genre/Style Interpretation Phase 5 — Normative Contract 1.0

**Status:** normative. This contract closes G1–G7 for the deterministic,
harmony-only Phase 5 launch profile. It adds a parallel PIL interpretation and
MUST NOT replace, feed, normalize or suppress Native JI evaluation. All Phase 5
metrics remain audit-only unless an exact `CalibrationDecision` promotes them.

## 1. Authority and closed assets (G1, G6)

The build identity is `pil.phase5.1.0.0`; the completed phase is
`genre_interpretation`. An executable request binds complete canonical payloads
for `PerceptualGenreModel 1.0` and `PerceptualGenreFeatureRecord 1.0`; a hash
alone is insufficient. Their closed schemas are
`perceptual_genre_model.schema.json` and
`perceptual_genre_feature_record.schema.json`. Raw schema SHA-256 values are
recorded by the authoritative suite index. Self hashes remove only the named
`model_hash`, `record_hash`, or `result_hash` and use:

```text
UTF8("cps-artifact-hash/v1\0" || schema || "\0" || schema_version || "\0")
|| canonical_json(body)
```

Canonical JSON is NFC, sorted-key, UTF-8, integer-only, compact JSON with no
trailing LF. Every addition and multiplication is checked u64/i64. Overflow is
`PIL_NUMERIC_OVERFLOW`.

## 2. Harmony feature source and extraction (G2, G4)

The sole required group in 1.0 is `harmony`. Its source is one successful,
schema-valid Phase 4 `PerceptualInterpretationReport` whose
`completed_phase` is `functional_trajectory`. The feature record binds its
`report_hash`, vocabulary hash and trajectory-template-set hash. Native JI
values are never read; `native_ji_report_hash` remains correlation metadata.

Let `T=2147483647`. All histogram normalization uses floor division followed
by largest fractional remainder, smaller ordinal first, to total exactly T.

* Chord vocabulary raw bin `v` is the sum, over all segments and retained
  candidates with vocabulary ordinal `v`, of
  `segment_duration_ticks * candidate_similarity_q`. Unknown IDs fail.
* Progression raw bin `t` is the sum of `similarity_q` for every retained
  trajectory result with template ordinal `t`.
* Function profile is the ordered five-component RHE mean across transition
  records: bass-fifth likeness (omit null), bass-fourth likeness (omit null),
  step-up resolution, step-down resolution, and `10000-abs(directed_tension_change_q)`.
* Voice-leading profile is the ordered three-component RHE mean across voice
  matching records: `10000-total_cost_q`, common-tone, contrary-motion.
* Harmonic-rhythm profile has four bins. Each segment duration is classified by
  exact comparison with `ticks_per_beat`: `<1/2`, `[1/2,1)`, `[1,2)`, or
  `>=2` beats; raw bin mass is duration ticks and is normalized to Q0.10000
  using the same largest-remainder rule with total 10000.

An omitted mean component is null, never zero. Empty chord or progression raw
mass, an unknown ordinal, inconsistent binding, or invalid derived record is
`PIL_GENRE_FAILED`.

## 3. Integer scoring (G3, G4)

Sparse histograms are expanded with absent bins equal to zero. For equal-length
Q0.10000 profiles, `profile_sim = RHE(sum(10000-abs(a_i-b_i))/N)`.
For normalized Q31 histograms,
`hist_sim = 10000-RHE(10000*sum(abs(a_i-b_i))/(2*T))`.
Null observed/model components are unavailable.

The five harmonic-detail scores, in immutable order, are chord vocabulary,
progression, function, voice leading and harmonic rhythm. `typicality_q` is
the RHE weighted mean of available detail scores using the model entry's five
weights. `idiomaticity_q` is the RHE weighted mean of available function,
voice-leading and harmonic-rhythm scores using their same weights. In either
calculation, unavailable components remove their weight; a zero denominator
is `PIL_GENRE_FAILED`.

`cliche_dependence_q` is
`RHE(10000 * sum(observed progression Q31 mass at the entry's declared
cliche_template_ordinals) / T)`. The list may be empty, yielding zero.

`novelty_q` is the minimum normalized Q31 L1 distance from the observed
progression histogram to every declared exemplar progression histogram:
`RHE(10000*L1/(2*T))`. At least one exemplar is required. This is not an alias
of typicality.

Each result retains the five detail scores (nullable), the four public scores,
and the model ordinal. Rows sort by `(-typicality_q, model_ordinal,
genre_id UTF-8)`; no winner and no overall score exist. Subjective thresholds,
labels such as “close enough”, metric direction and archive/search authority
belong exclusively to a separately bound CalibrationDecision.

## 4. Missing groups (G5)

The Phase 5 launch model MUST declare `required_groups:["harmony"]`. Evaluation
continues and reports exactly
`["melody","rhythm","form","instrumentation","production"]` in that order.
If harmony is missing, evaluation fails. Future groups require a new schema and
build identity; they cannot be inferred from ambient audio or metadata.

## 5. Failure precedence, cache and parity

After a successful Phase 4 report, precedence is: model schema; model binding;
feature extraction/schema; numeric overflow; genre scoring/result validation.
All except overflow report `PIL_GENRE_FAILED`; overflow reports
`PIL_NUMERIC_OVERFLOW`. Earlier Phase 1–4 failures retain their existing
precedence and Phase 5 does not run.

The Phase 5 cache-key preimage is
`UTF8("cps.pil-phase5-cache-key/v1\0") || canonical_json({project_hash,
phase4_report_hash,pil_manifest_hash,genre_model_hash,feature_record_hash,
implementation_build_id,requested_phase})`. Cache entries contain canonical
result bytes and their SHA-256. A malformed key, byte length, content hash,
self hash or schema is a corrupt miss: discard and recompute; never repair in
place. Cold, hit, corrupt, separate-process, and 1/2/4/8-worker executions MUST
produce byte-identical ordered results. Cache telemetry is noncanonical.

## 6. LLM sealing (G7)

No LLM is executable in Phase 5 1.0. A later LLM judge MUST use a new contract
and bind complete canonical payloads and hashes for model/build identity,
tokenizer, prompt template, structured context, invocation parameters,
response and CalibrationDecision. Provider text and hidden state are never
authority. An LLM may interpret sealed results but may not compute or replace
pitch, segmentation, matching, trajectory, Phase 5 integers, or Native JI.

## 7. Authoritative oracle

`fixtures/pil_genre_phase5/suite_index.json` binds immutable independent-oracle
cases and raw schema hashes. Required coverage is success, missing optional
groups, score tie, distinct novelty, invalid binding, empty progression,
overflow, cache cold/hit/corrupt, cross-process and workers 1/2/4/8. The oracle
owner alone may change expected bytes/hashes. Production implementations and
their maintainers MUST treat them read-only.
