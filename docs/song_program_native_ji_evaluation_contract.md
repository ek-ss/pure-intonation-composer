# Native JI Evaluation 1.0 — Minimal Parallel Authority

**Status:** normative for the `native_ji_separation` oracle prerequisite.
Schemas, implementation and fixtures are separate conformance deliverables;
their absence does not permit a substitute metric or a fabricated report hash.

## 1. Ownership and non-replacement

This contract creates the smallest versioned Native JI evidence artifact
needed to authenticate a PIL correlation. It does not replace or reinterpret
GEN0-B `ResolvedChord`, native voice-leading, comma drift, harmonicity,
roughness, or any existing Native JI evidence. A later richer Native JI report
may add separately named metrics but must not silently change this metric.

Native JI evaluation and PIL both consume the immutable ArrangementProject
1.2 independently. Neither consumes the other's report. PIL may copy only the
final Native JI report hash into nullable `native_ji_report_hash` correlation
metadata. It must not read the coherence value, manifest fields, or report
payload during pitch projection, segmentation, similarity, trajectory, cache
key construction, or failure handling.

## 2. NativeJIEvaluationManifest 1.0

The manifest is a closed canonical JSON artifact with exactly these members:

```yaml
schema: cps.native-ji-evaluation-manifest
schema_version: 1.0.0
algorithm: native-ji-lattice-coherence/v1
implementation_build_id: <non-empty versioned identifier>
project_schema_hash: <SHA-256 of exact ArrangementProject 1.2 schema bytes>
report_schema_hash: <SHA-256 of exact NativeJIEvaluationReport 1.0 schema bytes>
metric_id: native_ji.coherence
coordinate_order: [equave_exponent, final_vector]
distance: lattice-l1/v1
distance_cap: <integer 1..1048576>
within_group_weight_q: <integer 0..10000>
between_group_weight_q: <integer 0..10000>
manifest_hash: <self hash>
```

Both weights are required and their sum must be positive. There are no ambient
defaults, corpus assets, pitch-name tables, tunings, floating-point constants,
or PIL bindings. `implementation_build_id` identifies executable behavior but
does not enter the numerical operator. A different algorithm, bound schema,
cap, weight, or executable behavior requires a new manifest hash and build ID.

The manifest self-hash uses the generic artifact preimage with only
`manifest_hash` removed:

```text
UTF8("cps-artifact-hash/v1\0" || schema || "\0" || schema_version || "\0")
|| canonical_json(manifest_without_manifest_hash)
```

## 3. Authoritative input coordinates

Validate the complete Project against the manifest-bound ArrangementProject
1.2 schema and recompute its Project artifact hash before evaluation. Only
`kind == "note"` events participate; drum events are ignored.

For each note, define its native coordinate as the signed integer tuple:

```text
C(event) = [pitch_provenance.equave_exponent,
            *pitch_provenance.final_vector]
```

All participating tuples must have length `1 + len(project.lattice.generators)`.
The exact event `ratio` must agree with the lattice coordinate under the
existing ArrangementProject validator. This evaluator neither derives a
12-TET pitch class nor reads PIL pitch mappings.

Group notes by exact `start_tick`. Sort groups by ascending tick and events in
each group by UTF-8 event ID. This makes simultaneous harmony independent of
compiler emission order.

For coordinates `x,y`, native lattice distance is checked unsigned integer
L1 distance:

```text
D(x,y) = sum(abs(x[i] - y[i]))
```

Overflow is an evaluation failure; values are never saturated.

## 4. Integer `native_ji.coherence`

Define the capped distance score:

```text
S(d) = max(0, 10000 - RHE(10000 * d / distance_cap))
```

`RHE` is round-half-to-even integer division. All multiplication, addition and
absolute-value operations use checked u128/i128 intermediates.

### 4.1 Within-onset compactness

For every onset group containing at least two notes, enumerate all unordered
pairs by event-ID ordinal and evaluate `S(D(a,b))`. `within_q` is the RHE mean
of all such pair scores across the Project. If no onset group supplies a pair,
the component is unavailable rather than zero.

### 4.2 Between-onset continuity

For each adjacent nonempty onset-group pair `A,B`, compute both directed
nearest-neighbour score sets:

```text
A_to_B = [max(S(D(a,b)) for b in B) for a in A]
B_to_A = [max(S(D(a,b)) for a in A) for b in B]
```

The transition score is the RHE mean of the concatenation
`A_to_B || B_to_A`. `between_q` is the RHE mean of transition scores in tick
order. With fewer than two onset groups, the component is unavailable.

Nearest-neighbour scoring is deliberately many-to-one. It avoids importing
GEN0-B or PIL voice matching, and is invariant under unequal polyphony.

### 4.3 Final value

Remove the configured weight of each unavailable component. Then compute:

```text
native_ji.coherence =
  RHE(sum(available_component_q * configured_weight_q) /
      sum(available configured_weight_q))
```

At least one component must be available; otherwise evaluation fails with
`NATIVE_JI_INSUFFICIENT_NOTES`. The successful result is an integer in
`0..10000`, direction `maximize`. No threshold or qualitative word such as
"high" is part of this numerical report. An oracle case or CalibrationDecision
must bind its own explicit acceptance threshold.

## 5. NativeJIEvaluationReport 1.0

The report is a closed canonical JSON artifact with exactly these members:

```yaml
schema: cps.native-ji-evaluation-report
schema_version: 1.0.0
project_hash: <recomputed ArrangementProject artifact hash>
manifest_hash: <authenticated NativeJIEvaluationManifest hash>
implementation_build_id: <exact manifest value>
status: success
metrics:
  - metric_id: native_ji.coherence
    direction: maximize
    value_q: <integer 0..10000>
    within_q: <integer 0..10000 | null>
    between_q: <integer 0..10000 | null>
error: null
report_hash: <self hash>
```

`metrics` contains exactly the single row shown. Report self-hashing uses the
generic artifact preimage from section 2 with only `report_hash` removed.
Canonical JSON is NFC-normalized, key-sorted, integer-only UTF-8 with no
trailing LF. The report hash therefore authenticates the same Project hash,
evaluator manifest/build, component evidence, final metric, status and error.

The initial authority emits a report only after successful Project, manifest,
arithmetic and result validation. Failures produce a separately specified
execution failure receipt and must not be represented by a fabricated success
report. The `native_ji_separation` PIL oracle case requires a successful report.

## 6. Independent reproducibility and PIL binding

An authoritative fixture must contain the complete Project, complete manifest,
complete successful report, exact canonical report SHA-256, and independently
recomputed `report_hash`. Golden promotion requires an implementation not used
to produce the production evaluator, plus cold/cache-hit/cross-process equality
of canonical report bytes.

For `pil_nonfunctional_two_reports`, promotion additionally fixes an explicit
minimum `native_ji.coherence` threshold in the oracle case description and
checks the report value against it. The PIL report independently fixes its low
ii-V-I similarity assertion. The only link between the reports is:

```text
pil_report.native_ji_report_hash == native_ji_report.report_hash
pil_report.project_hash == native_ji_report.project_hash
```

Changing or removing either report cannot rewrite the other. A UI or later
decision must display them as `native_ji.coherence` and the separately named
`pil.*` metric; an unlabeled merged score is forbidden.
