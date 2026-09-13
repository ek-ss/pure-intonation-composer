# PIL Calibration Promotion — Draft Gap Analysis

**Status:** non-normative design draft prepared by the implementation side.
This document is **not** a contract. All PIL metrics remain audit-only until
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

## 3. Undefined points that block a PIL promotion (C-blockers)

| # | Undefined item | Why it blocks |
| --- | --- | --- |
| C1 | `metric_id` pattern is `^[a-z][a-z0-9_]{0,63}$` — dots are not expressible, so a literal `pil.*` ID cannot be spelled in the current schema | either PIL metric IDs use underscore spellings (e.g. `pil_chord_similarity_confidence_q`) by owner ruling, or the decision schema needs a versioned extension; guessing either way creates unreviewable canonical bytes |
| C2 | No decision field explicitly binds the PIL manifest hash; `evaluation_manifest_hash` is the evaluation-pipeline manifest | the contract demands the *exact PIL manifest hash* be promoted; the carrying field must be named by the owner |
| C3 | No PIL metric ID registry exists | the set of promotable PIL metrics (per-phase similarities, confidence, trajectory component scores, genre Q values once Phase 5 exists), their directions and thresholds must be enumerated before `promoted_metrics[]` rows can be written |
| C4 | Missing-value behavior has no decision field | the contract requires it to be explicit; the encoding channel (acceptance policy? evidence summary? new field?) is an owner decision |
| C5 | Evidence-chain mapping is unnamed | which existing assets carry the oracle suite hash, the cross-process matrix receipt, and the PIL calibration fixture set into the decision's hash bindings |
| C6 | Direction/threshold representation | `promotion` rows carry noninferiority/improvement margins but no explicit direction or threshold member; whether margins alone satisfy the contract's "directions, thresholds" requirement needs a ruling |

## 4. Non-goals

- No PIL metric may affect QD axes, rejection, archive quality, challenger
  acceptance or stopping before C1–C6 are closed and a decision is promoted.
- This draft does not propose to relax the oracle suite, the readonly guard,
  or the audit-only default, and it does not intersect the genre/style
  blockers G1–G7 (`song_program_pil_genre_interpretation_draft.md`), which
  remain independently open.

## 5. Suggested owner actions

1. Rule on C1 spelling (underscore IDs vs schema extension).
2. Name the PIL-manifest binding field (C2) and the missing-value channel
   (C4).
3. Approve a PIL metric ID registry draft (C3, C6) — the implementation side
   can prepare a candidate list from the Phase 1–4 report fields on request.
4. Map the evidence chain (C5) onto the oracle suite and matrix receipt
   assets that already exist.
