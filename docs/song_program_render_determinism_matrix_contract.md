# GEN0-C Render Determinism Matrix Contract

**Status:** normative acceptance extension  
**Contract:** `gen0-c-render-determinism-matrix/v1`

This contract closes the GEN0-C renderer contract's acceptance shorthand
without changing the renderer algorithm, RenderManifest, PCM/report preimages,
or any existing golden identity.

## 1. One-hundred invocation schedule

A `RenderDeterminismMatrixManifest 1.0.0` contains a non-empty,
case-ID-unique ordered list supplied by the independent fixture owner. The list
order is ascending case-ID UTF-8 bytes. Invocation ordinal `i` in `0..99`
selects case `i mod case_count`. Rendering has no random seed; the ordinal
controls only the mandatory repetition schedule and cannot enter PCM
computation.

Each case binds canonical Project bytes by `project_hash`, the exact
InstrumentCatalog and RenderManifest through the matrix-level hashes, and
owner-provided expected `wav_hash`, `pcm_hash`, `report_hash`, plus the ordered
per-track `(track_id, pcm_hash)` array hash. Production implementation cannot
write or update those expected values.

## 2. Process and block coordinates

The fresh-process matrix is the Cartesian product, in this order:

```text
PYTHONHASHSEED = [0, 1, 7, 42]
workers        = [1, 2, 4, 8]
```

Within a coordinate, the 100 invocations may execute concurrently but are
restored to invocation-ordinal order before hashing. Every coordinate emits
the same `sequence_hash` as the serial `(PYTHONHASHSEED=0, workers=1)` baseline.
No ambient process count or seed is allowed.

The test-only block matrix uses `[64, 256, 1024]` in that order. It renders
every distinct fixture case once in case order, using the same state machine
with only the processing chunk boundary changed. For each block size, WAV,
PCM, report, and every track PCM hash must equal the authoritative 256-frame
result. Block size is test execution metadata and is excluded from
RenderManifest identity and PCM/report preimages.

## 3. Canonical identities

```text
case_track_set_hash = SHA256("cps.render-track-set/v1" || 0x00 ||
                             canonical(ordered [track_id,pcm_hash]) || LF)
sequence_hash       = SHA256("cps.render-determinism-sequence/v1" || 0x00 ||
                             canonical(ordered invocation results) || LF)
manifest_hash       = SHA256("cps.render-determinism-matrix-manifest/v1" || 0x00 ||
                             canonical(manifest without manifest_hash) || LF)
receipt_hash        = SHA256("cps.render-determinism-matrix-receipt/v1" || 0x00 ||
                             canonical(receipt without receipt_hash) || LF)
```

## 4. Validation failure precedence

Validation order is manifest schema, manifest hash, fixture order/uniqueness,
fixture binding, coordinate set/order, invocation set/order, expected case hash
mismatch, sequence mismatch, block-coordinate set/order, block parity mismatch,
then receipt hash. Stable codes are `RENDER_MATRIX_MANIFEST_INVALID`,
`RENDER_MATRIX_MANIFEST_HASH_MISMATCH`, `RENDER_MATRIX_CASE_ORDER_INVALID`,
`RENDER_MATRIX_FIXTURE_MISMATCH`, `RENDER_MATRIX_COORDINATE_INVALID`,
`RENDER_MATRIX_INVOCATION_INVALID`, `RENDER_MATRIX_CASE_HASH_MISMATCH`,
`RENDER_MATRIX_SEQUENCE_MISMATCH`, `RENDER_MATRIX_BLOCK_COORDINATE_INVALID`,
`RENDER_MATRIX_BLOCK_PARITY_MISMATCH`, and
`RENDER_MATRIX_RECEIPT_HASH_MISMATCH`.

The independent owner supplies the manifest cases and expected hashes.
Production may consume and validate them but cannot regenerate or promote them.
