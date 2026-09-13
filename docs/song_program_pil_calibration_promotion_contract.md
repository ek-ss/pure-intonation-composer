# PIL Calibration Promotion Contract 1.0

This contract closes C1-C6 for Perceptual Interpretation Layer (PIL) Phases
1-4. It does not promote a metric by itself. A conforming
`cps.pil-calibration-decision` artifact is the only promotion authority.
Genre Phase 5 and `pil.genre.*` metrics are outside this version and remain
blocked by G1-G7.

PIL remains parallel to Native JI. A promoted PIL metric neither removes,
renames, weakens nor substitutes a `native_ji.*` metric.

## Metric registry

Metric IDs use the dotted `pil.*` namespace. The bound registry is
`cps.pil-metric-registry` 1.0.0. Each row fixes one report JSON pointer,
integer aggregation, direction and missing policy. The decision fixes its
evidence-derived acceptance threshold and repeats the other registry fields.
Rows sort by UTF-8 metric ID and IDs are unique.

The initial integer aggregations are:

- `minimum`: minimum of every selected non-null Q0.10000 value;
- `maximum`: maximum of every selected non-null Q0.10000 value;
- `minimum-runner-up-margin`: for every successful chord interpretation,
  subtract the second candidate similarity from the first, then take the
  minimum. Candidate order is the canonical report order;
- `maximum-absolute`: absolute value of each selected signed value followed
  by maximum.

`source_selector` is RFC 6901 JSON Pointer extended only by `*`, which expands
every array element in ascending array order. No other wildcard exists.

No rounding is performed. An empty selected set, a null selected member, an
unlabelled chord, or fewer than two candidates for a runner-up margin yields
missing. The 1.0 missing policy is always `unavailable`: emit no numeric value,
never coerce to zero, and make a required promotion criterion fail.

`maximize` passes at `value >= acceptance_threshold_q`; `minimize` passes at
`value <= acceptance_threshold_q`. Threshold equality passes. Decision rows
repeat registry direction, aggregation, threshold and missing policy exactly;
a mismatch is `PIL_CALIBRATION_CONTEXT_MISMATCH`.

## Decision and evidence closure

A decision binds the exact PIL manifest, metric registry, oracle suite index,
oracle 1/2/4/8 matrix receipt, Phase 1-4 calibration fixture set, acceptance
policy and evidence summary hashes. `evidence_hash` on each promoted row binds
the metric-specific evidence object selected by the evidence summary.

`scope` is fixed to `phase_1_4`. Consequently `genre_intent_hash` and genre
reference/model bindings do not occur in this schema. They cannot be filled
with dummy digests. A future Phase 5 decision uses a new version after G1-G7.

A promoted decision has at least one metric, null failure code, and identical
sorted `metric_ids` and promoted-row IDs. A rejected decision has both arrays
empty and a non-null failure code. The decision hash is SHA-256 over
`"cps.pil-calibration-decision/v1\0" || canonical_json(decision without
decision_hash)`.

## Promotion state

The checked-in registry fixes interpretation but supplies no listener or
calibration evidence. Therefore it is authoritative specification data, not a
promotion decision. Until independently collected Phase 1-4 calibration
fixtures, policy and evidence are checked in, every PIL metric remains
audit-only.

The current non-decision status is recorded by
`cps.pil-calibration-promotion-readiness` 1.0. It binds available registry and
oracle authority while representing each unavailable external authority as
`status: missing_external_authority` and `artifact_hash: null`. This artifact
cannot be consumed as, converted implicitly to, or substituted for a
CalibrationDecision.
