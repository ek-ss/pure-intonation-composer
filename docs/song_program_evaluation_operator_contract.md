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
