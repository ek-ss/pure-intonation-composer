# Evaluation operator registry

EvaluationManifest rows resolve only verified source values whose producer
schema hash matches. Hard checks use `bool_identity` (one boolean) or
`integer_compare` (`ge`, `le`, `eq`, one integer and threshold). Metrics use
`integer_identity` (one integer), `absolute_difference` (two integers), or
`weighted_sum_q` (integer inputs, signed integer weights, positive divisor).

Every weighted product and every sequential addition uses checked signed128 in
the inclusive range `-2^127..2^127-1`; divide uses round-half-even for both
signs; the final value must fit signed64 `-2^63..2^63-1`. Source type, arity, accumulator, rounding or
output overflow fails in precedence after source binding and before result
validation. Missing required render evidence yields the report missing reason,
never zero. Each row evidence hash is SHA-256 over
`cps.evaluation-evidence/v1\0` plus CPS conformance canonical JSON followed by
exactly one LF, of closed
`{source_bindings,operator,inputs,result}`.

Report evidence is one such object, never an array of partially repeated
records. Each source binding is closed and includes artifact kind, artifact
hash, producer schema hash, and JSON pointer. A metric with an integer value has
non-null evidence, null missing reason, and an empty
`available_source_bindings`. A metric with null value has null evidence, an
explicit missing reason, and may preserve already verified sources only in the
separate closed `available_source_bindings` field.

## Row binding, missing values, and failure precedence

For every non-missing row, `source_bindings`, `inputs`, and the manifest row's
`sources` have identical non-zero length and identical order. At index *i*, the
binding's `artifact_kind`, `schema_hash`, and `json_pointer` equal the manifest
source at *i*; its `artifact_hash` equals the verified corresponding artifact
in `EvaluationRequest`. A source kind is never used as a map key, so repeated
kinds cannot reorder or substitute inputs. The operator equals the manifest
operator exactly. A hard-check `passed` equals its boolean evidence result; a
metric `value` equals its integer evidence result. The independent conformance
oracle `verify_evidence` is the reference for these checks.

If a metric cannot be evaluated, it has `value:null`, `evidence:null`, and its
`available_source_bindings` is the ordered subsequence of manifest sources
whose producer artifact has already been verified. It carries no input or
invented result. For `required_render:true`, EvaluationRequest render status
`not_selected` maps to `render_not_selected` and `failed` maps to
`render_failed`; other unavailable declared sources map to
`source_unavailable`. `not_applicable` may be used only when the bound
manifest row itself declares that the metric has no applicable domain; v1 has
no such row attribute, so a v1 coordinator must not emit it.

A required-render hard check cannot be represented as a missing boolean. A
missing required render for it terminates the report with
`EVALUATION_RENDER_EVIDENCE_MISMATCH`. For a non-missing row, error precedence
after request/context/manifest/GenreIntent/source and project/fingerprint/render
binding checks is source type, operator shape, operator arity, signed128
accumulator overflow, signed64 output overflow, then evidence/result/hash
validation. The corresponding fixed report failure codes are
`EVALUATION_SOURCE_TYPE_INVALID`, `EVALUATION_OPERATOR_INVALID`,
`EVALUATION_OPERATOR_ARITY_INVALID`, `EVALUATION_ACCUMULATOR_OVERFLOW`,
`EVALUATION_RESULT_OVERFLOW`, and `EVALUATION_RESULT_INVALID`.
