# Instrument Catalog and RenderManifest Contract v1

**Status:** normative for `sample-linear-q31/v1`

## 1. Canonical catalog and identity

The machine form is `cps.instrument-catalog` `1.0.0`, validated by
`instrument_catalog.schema.json`. It contains no digest of itself and no local
path. Canonical bytes are UTF-8 canonical JSON: NFC strings, object keys sorted
by UTF-8 bytes, arrays preserved, integers in shortest decimal form, no
insignificant whitespace, and one final LF byte. Entries are sorted by
`instrument_id`; drum mappings are sorted by `drum_note`. Duplicate IDs or
notes reject.

```text
instrument_catalog_digest = "sha256:" + hexlower(SHA256(
  UTF8("cps.instrument-catalog/v1\0") + canonical_catalog_bytes
))
```

Project `compiler.instrument_catalog_digest` must equal this value before any
event is examined. An implementation cannot merge catalogs or substitute an
entry with the same display role.

## 2. Asset resolver and canonical WAV

Every asset reference contains exactly `uri`, `sha256`, and `byte_length`.
`uri` is `asset://sha256/<64 lowercase hex>` and its suffix equals `sha256`
without the prefix. The resolver interface is:

```text
resolve(uri) -> exact immutable bytes | ASSET_NOT_FOUND
```

It is content-addressed and has no search order. Filesystem, package, database,
or network storage may back it, but returned bytes must match both length and
SHA-256 before WAV parsing. A fixture resolver maps the URI to
`fixtures/render/assets/<hex>.wav`; this mapping is test infrastructure and is
not part of catalog bytes.

Canonical source WAV is RIFF little-endian with exactly `RIFF`, `WAVE`, one
16-byte PCM `fmt ` chunk, then one `data` chunk and EOF. Audio format is 1,
sample width 32 signed bits, sample rate 48,000, channel count 1 or 2, and all
RIFF sizes/rates/alignments must recompute exactly. No LIST, JUNK, extensible,
fact, padding, compressed, floating, or trailing bytes are allowed. Samples are
interleaved signed little-endian Q1.31. Catalog `channels`, `frames`, and
`sample_rate` must equal the parsed asset.

## 3. Pitched entries and release

A pitched entry owns one asset, root frequency, inclusive allowed frequency
range, loop definition, polyphony, catalog gain Q0.14, and `release_frames` in
`0..480000`. Frame `event_end` is the first release frame. For release length
`R>0`, release frame ordinal `j=0..R-1` multiplies the interpolated sample by
the exact rational `(R-j)/R`, using the renderer Q1.31 round-half-even multiply;
frame `event_end+R` and later are zero. Thus `j=0` preserves full amplitude.
For `R=0`, `event_end` and later are immediately zero. Release multiplication
occurs after interpolation and before velocity, catalog gain, track gain, and
pan. A non-looping asset that ends earlier is already zero and is not extended
by release. Looping stops at event end and never wraps during release: the
phase continues through the loop while the release multiplier is applied.

## 4. Drum lookup

A drum track's `instrument_id` names exactly one `drum_kit` entry. For each
drum event, lookup is the exact pair `(instrument_id, drum_note)` in that kit's
sorted `note_map`. Missing notes fail `DRUM_NOTE_UNMAPPED`; duplicate notes are
invalid catalog data. A mapped asset is a one-shot from phase zero at its source
rate, ignores event ratio and duration, never loops, and plays through its full
asset frame count. Drum samples have no release field; the one-shot asset
contains its own tail. Track and kit polyphony limits both apply, with the
smaller limit authoritative.

## 5. RenderManifest identity

The machine form is `cps.render-manifest` `1.0.0`, validated by
`render_manifest.schema.json`. Its `contract` record identifies the exact raw
UTF-8 LF bytes of `song_program_renderer_evaluation_contract.md` and this
contract by SHA-256. `renderer_build` contains the fixed implementation ID,
repository-relative source artifact path, exact raw source SHA-256, and exact
raw dependency-lock SHA-256. `numeric_constants` is a closed integer/string object; decimals
or host constants are forbidden.

Canonical manifest-core bytes use the catalog canonicalization rules and omit
only `render_manifest_digest`. The digest is:

```text
"sha256:" + hexlower(SHA256(
  UTF8("cps.render-manifest/v1\0") + canonical_manifest_core_bytes
))
```

The required numeric constants are engine ID, output rate 48000, channels 2,
sample bits 32, Q fractional bits 31, phase fractional bits 32, block frames
256, trailing zero frames 256, multiplication rounding
`round-half-to-even`, accumulator bits 64, and final conversion `saturate-once`.
Contracts are sorted by ID. Changing renderer build identity, either contract byte, catalog digest, or any
constant changes the manifest digest. Asset bytes change catalog identity via
their catalog hash and therefore also change manifest identity.

## 6. Validation and failures

Validate catalog schema/order, catalog digest, entry selection, asset URI,
length/hash, canonical WAV, catalog/WAV agreement, event mapping/range, then
polyphony. Stable failures are `CATALOG_DIGEST_MISMATCH`,
`CATALOG_ENTRY_NOT_FOUND`, `CATALOG_ENTRY_INVALID`, `ASSET_NOT_FOUND`,
`ASSET_LENGTH_MISMATCH`, `ASSET_HASH_MISMATCH`, `ASSET_WAV_NONCANONICAL`,
`ASSET_METADATA_MISMATCH`, `DRUM_NOTE_UNMAPPED`, and
`RENDER_POLYPHONY_EXCEEDED`. No failure permits fallback.

For pitched entries, `loop_mode=none` requires both loop points zero;
`forward` requires `0 <= start_frame < end_frame <= asset.frames`. Frequency
bounds are ascending. For drums, gain order is velocity, mapped-sample gain,
kit gain, track gain, then pan, with rounding after each multiply.

## 7. Fixtures

`fixtures/render/catalog.json`, `render_manifest.json`, `cases.json`, and the
hash-named WAV assets are normative. `build_renderer_catalog_fixtures.py`
recreates them without floating point. Checked-in bytes must equal a clean
rebuild. Cases cover pitched playback in 2/1 and 3/1 Project domains and an
explicit drum-note mapping. The equave changes Project pitch provenance, not
catalog lookup or asset identity.
