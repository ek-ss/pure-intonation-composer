# Exploration Cohort Profile v1

Status: non-authoritative development profile. It does not replace any GEN0
conformance authority or golden fixture.

## Authority construction

`backend/tools/run_fixture_generation_cohort.py` creates one sealed
`SamplerManifest` and `StructuralLoweringManifest` for every cohort seed. The
seed-addressed choices use SHA-256 domain
`cps.exploration-authority/v1` and are therefore independent of process order
and worker count. Every successful seed directory persists both manifests.

The sampler uses weighted 7-limit domains: `2/1` with generators (`3/1`,
`5/1`, `7/1`) and `3/1` with generators (`2/1`, `5/1`, `7/1`). In the latter,
the equave itself supplies prime 3, so both domains span primes 2, 3, 5, and 7.
Each coordinate axis is `[-4,4]`; equave placement is `[-8,8]`. The full raw
domain is 12,393 placed coordinates before odd-limit and duplicate filtering.

Navigation is not limited to adjacent lattice moves. The manifest declares
12-TET pitch-class targets, and `nearest-12tet-vector/v1` searches the centered
half-domain `[-2,2]` on every axis. It retains candidates within 50,000
millicents, then orders by absolute-register displacement, approximation error,
lattice L1, maximum coordinate magnitude, and vector lexicographic order. The
half-domain reserve guarantees that adding a selected tonal center to a walk or
root vector remains inside the full domain.

Tonal centers, six non-adjacent four-point walks, and harmony root anchors all
come from this derivation. Root anchors are no longer fixed at the origin. The
selected equave is fixed before structural sampling and only compatible chord
references remain eligible: 12-EDO for `2/1`, and 19-EDT (approximately one
12-TET semitone per step) for `3/1`.

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

## Musical-time exploration profiles

The sparse cohort authority remains the default and is not changed by the
musical-time profiles. `song-preview-exploration-v1` and
`full-song-exploration-v1` are separate, closed, self-hashed inputs selected by
the runner's `--profile` option. The preview layout is 3 sections of 4 bars.
The full-song layout is deterministically selected per seed from 28, 32, and
40 bars.

Profile lowering is the sole owner of realization timing. It removes cohort
rhythm rotations and assigns each material to one seeded weighted role. If
that global ownership would fall below the profile's minimum sounding-role
count, deterministic role-specialized copies are added; each resulting
material is still bound to exactly one role. It then derives `repeat` from the
containing section's bar count and applies role-specific entry, period,
duration, and gate values. The final repeat's remaining section time is a hard
duration bound. Harmony and texture are continuous-bed roles:
their duration equals their complete 2- or 4-bar period and their gate is
10000. This prevents the earlier one-bar-on/one-bar-off silent pattern.

After compilation, the runner measures symbolic coverage from event intervals
in section-relative time. Coverage rejection precedes audible-hash duplicate
rejection. Continuous section roles (`build`, `drop`, `final`) allow no empty
bar; other sections allow at most two consecutive empty bars; overall coverage
must be at least 8500 basis points and at least three roles must sound. This is
an exploration admission gate, not a Native JI or PIL score and does not
replace either evaluation path.

The profile schema is
`songprogram_conformance/schemas/song_preview_exploration_profile.schema.json`.
All reports and rendered previews produced by these profiles remain
non-authoritative measurement artifacts.

Example invocations from the repository root:

```console
backend/.venv/bin/python backend/tools/run_fixture_generation_cohort.py \
  --profile song-preview --seeds 4 --workers 4 --output /tmp/cps-preview-4
backend/.venv/bin/python backend/tools/run_fixture_generation_cohort.py \
  --profile song-preview --seeds 32 --workers 8 --output /tmp/cps-preview-32
backend/.venv/bin/python backend/tools/run_fixture_generation_cohort.py \
  --profile full-song --seeds 1 --workers 1 --output /tmp/cps-full-song-smoke
backend/.venv/bin/python backend/tools/run_fixture_generation_cohort.py \
  --profile full-song --seed-start 4 --seeds 1 --workers 1 \
  --output /tmp/cps-full-song-40-bars
```

## Section-aware arrangement v2

The runner's `song-preview` and `full-song` selectors bind the v2 profiles.

## Generation authority manifest

Musical-form and arrangement policy remain owned by the selected exploration
profile. The formerly hard-coded stochastic and rendering inputs are owned by
the closed `cps.exploration-generation-manifest` v1 payload. The checked-in
default is `backend/songprogram_conformance/profiles/full_song_generation_v1.json`;
another self-hashed manifest may be supplied with `--generation-manifest`.

The manifest is the authority for the equave/generator domains, chord-reference
tables, rhythm grid and density, tempo, 12-TET-derived tonal centres, vector walks,
duration/accent choices, lattice/chord budgets, production range/polyphony, and
the role-specific deterministic trial timbres. Choices use
`seed-domain-sha256-mod/v1`; worker count and scheduling never enter a choice
preimage. Every equave must have at least one chord reference and vice versa.
Every domain must include primes 3, 5, and 7 across its equave plus generator
list and must satisfy the manifest's 12-TET approximation error ceiling.

The manifest hash is:

```text
sha256("cps.exploration-generation-manifest/v1" || 0x00 || canonical_json(payload_without_manifest_hash))
```

This runner is deliberately evaluation-free. Its only valid evaluation payload
is `{"mode":"none"}`. Native JI, PIL, genre calibration, mutation rounds, and
archive admission are connected through their existing Evaluation and
SearchLoop contracts. Supplying another evaluation mode here fails with
`GENERATION_EVALUATION_UNAVAILABLE`; it must never be silently ignored.

`workers=1` executes in the calling process. Larger worker counts use the
process pool, while consuming identical seed-addressed authority. The report
records both `generation_manifest_id` and `generation_manifest_hash`, and the
exact canonical manifest is copied into the output directory.
The checked v1 profiles and their measured reports remain immutable historical
evidence. V2 adds the closed `arrangement_policy` payload and emits one
`cps.section-arrangement-plan` sidecar per successful seed.

`section-role-mask-and-recall/v1.1` first completes global single-role material
ownership, then makes one deterministic representative for each sounding role
available in every section. It selects the active role mask and velocity from
the section role (`intro`, `verse`, `build`, `drop`, `break`, `final`, or
`outro`). Lower-intensity roles prefer harmony/texture; build, drop, and final
prefer harmony/bass/drums before melodic decoration. The planner repairs the
mask set deterministically when necessary so that:

- the union across the song meets `minimum_sounding_roles`;
- a multi-section song has at least `minimum_distinct_role_masks`;
- the priority-leading bed role cannot be removed by mask-diversity repair;
- every emitted material remains bound to exactly one role;
- propagated realizations preserve their source material and therefore encode
  recall rather than creating an unrelated pitch object.

The plan sidecar binds the profile hash, source structural program ID, ordered
section plans, active roles, development stage, velocity, distinct-mask count,
and a domain-separated canonical plan hash. It is diagnostic input for later
search and evaluation; it does not replace Native JI or PIL evaluation.
Before compilation, the closed plan validator checks canonical role ordering,
form section ID/role/stage correspondence, section-role velocity membership,
mask and sounding-role counts, status, profile binding, and plan hash.

V2 also closes the gap between bar-level symbolic coverage and audible
continuity. `maximum_fully_silent_one_second_windows` is evaluated from the
rendered PCM32 payload. Arrangement rejection has first precedence, followed
by PCM-silence rejection, symbolic-coverage rejection, and semantic duplicate
rejection.

V1.1 also defines the effective realization period as
`gcd(configured_period_bars, section_bars - entry_bar)`. This keeps the period
divisible into the remaining section span. In particular, harmony and texture
in a five-bar section become one-bar bed periods instead of shortening every
two- or four-bar event to the final one-bar tail and leaving uncovered gaps.
`--seed-start` selects an explicit contiguous uint64 seed range so 28-, 32-,
and 40-bar boundary coordinates can be rerun independently.

When a profile seals `recall_transform_policy`
(`seeded-nonidentity-rotate-recall/v1`), the profile lowering replaces the
structural rotate transforms with its own recall transform: for every material
realized in two or more sections, exactly one later recall (seed-selected)
carries a single non-identity `{"op":"rotate","ticks":...}` transform whose
amount is seed-selected from `length_ticks // k` over the sealed denominators
`k`; every other realization keeps an empty transform list. Rotation is applied
to non-pad materials (drums/bass/melody) only: pad beds (harmony/texture) tile
their sections continuously, and rotating one would open a silent gap that PIL
harmonic segmentation rejects as `PIL_SEGMENT_EMPTY`. Because structural rhythm
cells are exactly one bar long while both the effective period and the final
tail span at least one bar, a rotated event cannot leave its section; step
durations are bounded by the maximum effective offset across all realizations
of that helper. `full_song_exploration_v2.json` seals denominators `[2, 3, 4]`;
the v1 profiles and `song_preview_exploration_v2.json` omit the policy and keep
transform-free lowering. This satisfies the GEN0 hard check
`non_identity_transformed_recall_across_sections` without loosening any
evaluation threshold.

The normative payload schemas are
`songprogram_conformance/schemas/song_exploration_profile_1_1.schema.json` and
`songprogram_conformance/schemas/section_arrangement_plan.schema.json`.
