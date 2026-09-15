# PIL External Calibration Authority Intake Contract 1.0

This contract defines the read-only intake boundary for external PIL
calibration. It never creates listener evidence or promotes a metric. PIL is
parallel to Native JI; neither decision version may replace or alter a
`native_ji.*` result.

## Canonical bytes and hashes

Every artifact is closed-schema, NFC, sorted-key, compact UTF-8 canonical JSON
with integers only and no trailing LF. Unless stated otherwise its self hash is
SHA-256 over
`UTF8("cps-artifact-hash/v1\0" || schema || "\0" || schema_version || "\0")`
followed by canonical JSON with only its named self-hash member removed.
Metric evidence rows use the same rule with synthetic schema identity
`cps.pil-calibration-metric-evidence` version `1.0.0`, removing only
`evidence_hash`. Decisions retain their version-specific domain prefix.

## Phase 1–4 dependency order

The external owner supplies, in this order: the existing closed
`ListenerCohortManifest`; `cps.pil-calibration-acceptance-policy` 1.0;
`cps.pil-calibration-fixture-set` 1.0; and
`cps.pil-calibration-metric-evidence-summary` 1.0. The fixture set binds raw
interpretation-report evidence and the policy but not the derived summary,
preventing a hash cycle. The summary binds the fixture set. The final
`cps.pil-calibration-decision` 1.0 binds both.

Policy and summary metric rows MUST be unique and sorted by metric ID and MUST
equal a non-empty subset of the bound Phase 1–4 registry. Aggregation,
direction and missing policy repeat the registry exactly. Summary thresholds
repeat the policy. `observed_q:null` means unavailable and MUST have
`passed:false`. Otherwise maximize passes iff observed is at least threshold;
minimize passes iff it is at most threshold. `all_required_metrics_passed` is
the conjunction of metric results and the two policy count minima. A promoted
decision repeats exactly the passing summary rows, including threshold and
margins, and each `evidence_hash`; a rejected decision contains no metrics.

Intake validation precedence is: schema/canonical failure; self-hash failure;
unresolved hash; PIL manifest/registry/oracle binding mismatch; policy/fixture
binding mismatch; partition leakage or cohort membership failure; metric
recomputation mismatch; count or threshold failure; summary mismatch; decision
hash/status mismatch. These map respectively to the existing Phase 1–4
`PIL_CALIBRATION_INPUT_INVALID`, `PIL_CALIBRATION_CONTEXT_MISMATCH`,
`PIL_CALIBRATION_THRESHOLD_NOT_MET`, and
`PIL_CALIBRATION_RESULT_INVALID` categories. SearchLoop13 fixture-only
artifacts are forbidden inputs regardless of byte similarity.

## Phase 5 genre decision

Genre uses `cps.pil-calibration-decision` 2.0 with scope `genre_phase_5`; it is
not compatible with Phase 1–4 v1 or SearchLoop CalibrationDecision 1.x. It
binds the exact PIL manifest, `pil.phase5.1.0.0` build, GenreIntent,
PerceptualGenreModel, genre reference-set manifest, genre metric registry,
oracle suite, external fixture set, policy and evidence summary.

The authoritative registry selects only result rows whose `genre_id` occurs
in the bound GenreIntent target IDs. Missing target rows are unavailable.
Across all selected targets: typicality, idiomaticity and novelty use minimum
and maximize; cliche dependence uses maximum and minimizes. This conservative
aggregation prevents one strong target from masking another weak target.
Threshold equality passes. All rows and IDs sort by UTF-8 metric ID.

The v2 decision hash is SHA-256 over
`"cps.pil-calibration-decision/v2\0" || canonical_json(decision without
decision_hash)`. Promoted status requires one or more identical sorted metric
and promotion ID lists and null failure code. Rejected status requires both
lists empty and a non-null genre calibration failure code. Actual threshold,
margin, cohort and evidence values remain exclusively owner-supplied.

## Read-only acceptance

An intake implementation may validate and copy content-addressed bytes into
CAS, but MUST NOT synthesize missing artifacts, repair hashes, select a newer
decision implicitly, generate expected outputs, or convert a readiness record
into a decision. Promotion requires an explicit exact decision hash in the run
context; absent or rejected decisions leave the affected metrics audit-only.
