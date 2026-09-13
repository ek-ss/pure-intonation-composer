# SearchLoop13 success/parallel fixture owner decisions

These values are authoritative fixture inputs selected by the maintainer on
2026-09-13. They apply only to the new success/parallel conformance group and
are not production defaults.

- `root_seed = 7`; one round, one candidate, population one; planner is null.
- Candidate source is `initial_sampler`; structural sampling accepts its first
  terminal attempt and broad-prior production succeeds.
- Fallback proposes exactly one non-identity typed mutation; mutation and
  compile succeed.
- Fingerprint is valid and distinct. Render is selected and succeeds.
  Evaluation succeeds. With no champion, challenger acceptance accepts;
  archive admission admits.
- Round termination is `maximum_rounds`; the terminal artifact is the normal
  phase-12 checkpoint.
- The base cache scenario is cold. Parallel variants have worker counts
  `1,2,4,8`, distinct physical completion permutations, and identical semantic
  parity projections and expected roots.
- Payload seeds are the checked-in minimal-direct SongProgram and its compiler,
  render catalog and render manifest fixtures. They are independently
  re-sealed under the fixture RunManifest 1.3, RunContext and source decision;
  their old hashes are not inherited as run authority.
- Every otherwise unspecified integer is the smallest schema-valid value that
  preserves the selected successful branch. Budget ceilings are the exact
  committed logical charge totals (the smallest non-rejecting ceilings).
  Every nullable operational deadline is null. Empty ordered collections are
  used only where the selected branch permits them.
- All 32 inline RunContext artifact bindings, four contract hashes and 73 raw
  schema hashes bind checked-in canonical bytes. Synthetic placeholder policy,
  schema, run or context hashes are forbidden.
- Exactly 27 inline artifact bindings are non-null. Only the five planner
  bindings (`planner_manifest`, prompt asset, invocation policy, tokenizer and
  tool catalog) are null. Genre and calibration bindings are non-null and use
  a promoted, fixture-only CalibrationDecision whose evidence is valid solely
  for this SearchLoop13 conformance authority. It is not a production default
  and MUST NOT be reused as real-world genre calibration.
- The listener cohort manifest is not an inline RunContext slot. It is a
  content-addressed CAS authority reachable from CalibrationDecision and
  CalibrationDataset evidence, registered in the fixture edge registry, and
  verified against the exact checked-in listener-cohort schema bytes.
- `fallback_sampler` and `broad_prior_production` bind the same exact raw bytes
  and SHA-256 of `docs/song_program_fallback_sampler_contract.md`, because that
  one versioned contract owns both named sections. Contract-binding field names
  identify semantic roles and do not imply four pairwise-distinct byte files.
- The independent builder and verifier must not import `app.songprogram`.
