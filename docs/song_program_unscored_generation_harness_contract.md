# Evaluation-Free Generation Harness Contract

`cps.unscored-generation-receipt` 1.0 connects a complete SongProgram 0.1 to
the production compiler and GEN0-C reference renderer without invoking Native
JI evaluation, PIL, genre similarity, ranking, archive admission or an LLM.

The caller supplies a u64 seed as correlation metadata, a complete SongProgram,
CompilerIdentity, canonical Instrument Catalog bytes, content-addressed asset
resolver, RenderManifest digest and a new or empty output directory. The
CompilerIdentity catalog digest MUST equal the digest recomputed from catalog
bytes. No fallback catalog or instrument substitution is permitted.

Successful execution writes canonical `song_program.json`, `project.json`,
`render_report.json`, raw `preview.wav`, and canonical `receipt.json`. Existing
files are never overwritten. The receipt binds every relevant identity and has
`evaluation_performed:false`; adding any score or acceptance decision requires
a different versioned harness.

`receipt_hash` uses domain `cps.unscored-generation-receipt/v1` and the standard
canonical LF-framed artifact hash with only `receipt_hash` removed. The stable
harness errors are `UNSCORED_REQUEST_INVALID`, `UNSCORED_CATALOG_MISMATCH`, and
`UNSCORED_OUTPUT_EXISTS`; compiler, Project validator and renderer errors retain
their existing typed namespaces.

The reference CLI is `backend/tools/generate_unscored.py`. It requires explicit
Program, CompilerIdentity, catalog, asset directory, RenderManifest, seed and
output paths; it has no ambient defaults. The asset directory is resolved only
by the lowercase SHA-256 basename carried by `asset://sha256/<hex>` catalog
URIs.
