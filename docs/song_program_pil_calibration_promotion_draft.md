# PIL Calibration Promotion — Maintainer Resolution

**Status:** C1-C6 are closed by
`song_program_pil_calibration_promotion_contract.md`. All PIL metrics remain
audit-only until
a versioned CalibrationDecision promotes them
(`song_program_perceptual_interpretation_layer_contract.md` section 2). This
draft enumerates what that promotion requires and which points are undefined,
so the owner can close them deliberately. Nothing here permits implementation
work on QD/archive/challenger/stopping integration.

## 1. What contract section 2 already fixes

- Promotion happens only through a versioned CalibrationDecision that
  explicitly promotes the **exact PIL manifest hash**, **metric IDs**,
  **directions**, **thresholds** and **missing-value behavior**.
- Promotion adds PIL evidence; it never removes or aliases a Native JI
  criterion.
- Metric namespaces are disjoint: `native_ji.*` and `pil.*`.
- Contract section 9 additionally requires the authoritative oracle suite to
  exist before any promotion; that suite is now promoted
  (`backend/songprogram_conformance/fixtures/pil_oracle/`, commit `0a39ba9`).

## 2. Existing CalibrationDecision 1.0 shape (authoritative schema)

`calibration_decision.schema.json` requires: `status`
(`promoted`/`rejected`), hash bindings for genre intent, evaluation manifest,
reference set, feature extractor, renderer, listener cohort, calibration
fixture set, acceptance policy and evidence summary, plus
`promoted_metrics[]` (max 16; each `metric_id`,
`noninferiority_margin_q` 0..9999, `improvement_margin_q` 1..10000,
`evidence_hash`) and `metric_ids[]` (max 16).

## 3. Resolved points

| # | ruling | encoding |
| --- | --- | --- |
| C1 | dotted namespace | new PIL-specific schema accepts only `pil.*`; Genre CalibrationDecision 1.0 is unchanged |
| C2 | exact manifest binding | `pil_manifest_hash` |
| C3 | closed registry | `cps.pil-metric-registry` 1.0 |
| C4 | no zero coercion | each row repeats `missing_policy: unavailable` |
| C5 | explicit evidence chain | decision fields bind oracle suite index, matrix receipt, calibration fixture set, policy and evidence summary |
| C6 | explicit semantics | each row repeats aggregation, direction and inclusive `acceptance_threshold_q`; NI/IMP margins remain distinct |

## 4. Non-goals

- No PIL metric may affect QD axes, rejection, archive quality, challenger
  acceptance or stopping before C1–C6 are closed and a decision is promoted.
- This draft does not propose to relax the oracle suite, the readonly guard,
  or the audit-only default, and it does not intersect the genre/style
  blockers G1–G7 (`song_program_pil_genre_interpretation_draft.md`), which
  remain independently open.

## 5. Remaining promotion authority

No Phase 1-4 `CalibrationDecision` is fabricated by this resolution. A real
promotion remains blocked on independently collected calibration fixtures,
acceptance policy and evidence summary. Genre Phase 5 remains separately
blocked on G1-G7.
