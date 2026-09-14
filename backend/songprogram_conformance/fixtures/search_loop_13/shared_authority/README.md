# SearchLoop13 shared artifact authority

`artifact_slot_index.json` is the complete fixture authority for the
`RunContext.artifacts` object. It contains exactly 32 properties: 27 immutable
bindings and the five planner-related null slots selected by the owner.

The index is generated independently of production coordinator code. Embedded
artifact and schema bytes are the exact checked-in bytes; each schema raw hash,
producer-owned artifact digest, and self-hash is recomputed by the builders and
tests. Producer artifacts whose canonical format requires a final LF retain
that LF inside `artifact_bytes_base64`.

The fixture keeps Native JI and perceptual genre interpretation as separate
evaluation metrics. The perceptual layer does not replace Native JI.

The fixture-only calibration data and minimal acceptance thresholds MUST NOT
be used as production calibration defaults.
