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

Connected executor cache keys and SearchLoop13 RunContext still bind older
schema hashes. They require a separate versioned fixture promotion before
this five-dimensional suite can authorize connected-search runs.
