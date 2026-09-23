# GEN0-B five-dimensional authority

CompilerManifest 2.0 binds SongProgram 0.2, ArrangementProject 1.3,
ProgressionQuery 2.0, GEN0-B evidence 2.0, and chord-member melody report 2.0.
CompilerManifest 1.1 remains immutable and accepts only SongProgram 0.1.
The compile report, logical opcode stream, and charge receipt retain their
existing 1.1 envelope because their field layout and accounting semantics do
not change. New program, manifest, query, evidence, and melody hashes use
version-separated domains. Project hashes include the Project schema version.

The manifest permits up to five dimensions, axis width seven, coordinate
cardinality 1,024, register width eight, and placed cardinality 4,096. These
are ceilings. Coordinate cardinality is the product of inclusive axis widths;
placed cardinality multiplies that product by inclusive register width.
All five checks precede resolver invocation. Exceeding a manifest limit fails
with `GEN0B_DOMAIN_LIMIT_EXCEEDED`. Program
`pitch_exploration.maximum_domain_points` remains a separate earlier bound.

The independent generator is
[`build_gen0b_5d_fixtures.py`](../backend/songprogram_conformance/build_gen0b_5d_fixtures.py).
It imports no production `app.songprogram` module. It writes the separate
[`compiler_v2_5d`](../backend/songprogram_conformance/fixtures/compiler_v2_5d)
suite without modifying legacy goldens. The suite index seals raw file and
schema byte hashes, semantic expected hashes, generator identity, worker
matrix, process hash seeds, and its own hash. The independent verifier checks
these bindings and progression result. Production tests compare Project,
evidence, melody report, and opcode hashes, execute dimension/cardinality
negative cases, and confirm 1/2/4/8 worker and cross-process parity.

The versioned fixture promotion is sealed in
[`connected_v2_5d`](../backend/songprogram_conformance/fixtures/connected_v2_5d).
Its independent [builder](../backend/songprogram_conformance/build_connected_v2_5d_fixtures.py)
and [read-only verifier](../backend/songprogram_conformance/verify_connected_v2_5d_fixtures.py)
bind a v2 executor manifest, connected request/output/cache entry, SearchRunManifest
1.3, and SearchLoop13 RunContext 2.0 to the five-dimensional compiler manifest.
Nine context schema bindings are promoted to v2; unchanged bindings retain
their previous raw bytes. Connected envelopes use version-separated hash
domains, while the cache-key, opcode-bundle, charge-receipt, and mutation-receipt
formats keep their existing domains. The identity rhythm mutation makes the
connected cold output's compiler artifacts byte-identical to the sealed 5D
goldens; production cold, cache hit, and corrupt-cache recomputation are tested
against the independent oracle. This closes the connected-cache and context
schema-hash promotion gate for the 5D authority suite.

The 5D-specific Project 1.3 schema accepts RFC 6901 paths such as
`/realizations/0`; the 5D-specific ChargeReceipt 1.1 schema binds the v2
budget profile ID. CompileReport 1.1 and connected logical output v2 refer
to those schemas. Their raw hashes are sealed in the 5D and connected suite
indexes, while the earlier schema bytes and legacy fixtures remain intact.
