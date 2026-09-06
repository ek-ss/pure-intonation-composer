# Connected Cache and Parallel Runner Contract 1.0

Status: normative for Mutation application -> GEN0-B compile -> chord-member
melody -> LineageIndex as one connected candidate task.

## Identity and boundary

Only the whole connected task is a normative cache level. Resolver/internal
caches are unobservable optimizations and cannot change output or receipts.
`ConnectedExecutorManifest` binds exact contract/schema hashes for Mutation,
SongProgram, compiler, Project, GEN0-B evidence, melody report, CompileReport,
receipts, opcode streams, and LineageIndex, plus canonical JSON v1 and pipeline
order. Its digest domain is `cps.connected-executor-manifest/v1`.

`ConnectedRequest` contains the complete inline Program, ordered Mutations,
locks, action ID, RunManifest, choice/instrument catalogs, CompilerManifest,
and executor-manifest digest. Validate every intrinsic digest and cross-binding
before lookup. Its hash is the artifact hash under `cps.connected-request/v1`;
full Program bytes including `program_id` participate.

`ConnectedLogicalOutput` contains request hash, status, resulting Program,
Mutation impact/receipt, Project, GEN0-B evidence, melody report, CompileReport,
LineageIndex, and error. Its hash domain is
`cps.connected-logical-output/v1`, omitting its hash. Success has every artifact
and null error. Mutation failure has only its failure receipt. Compile failure
has resulting Program, Mutation artifacts, and failed CompileReport; Project,
both evidence reports, and LineageIndex are null. Operational failures are not
logical outputs and are never cached.

## Cache key and entry

The key core is exactly `{request_hash,executor_manifest_digest}` and key hash
uses `cps.connected-cache-key/v1`. CAS location is
`cas/connected-cache/sha256/<first-two-hex>/<remaining-62-hex>`.
`ConnectedCacheEntry` contains the complete key, logical output and hash,
Mutation/compile receipt hashes, root opcode stream, child opcode streams in
receipt-child order, and `entry_hash`. Entry hash uses
`cps.connected-cache-entry/v1` with itself omitted. Timestamp, host, worker,
cache source, and free-text producer fields are forbidden.

Validate a candidate hit privately in this order: framing/size; JSON/schema;
canonical bytes; path/key recomputation; requested-key equality; entry hash;
logical-output hash; receipt hashes; root/child opcode hashes and projections;
all artifact intrinsic hashes/cross-bindings; independent Project, evidence,
melody, and lineage validation. Any failure invalidates the entire entry;
partial artifact or child reuse is forbidden.

A valid hit dry-runs stored root opcodes in ordinal order against a private
ledger, then atomically commits all reservations before publishing artifacts.
Insufficient current budget returns the same canonical budget failure that
cold execution would reach; it is not corruption and does not cold-recompute.
Corrupt entries change no ledger state, increment nonsemantic telemetry, and
mandatorily cold-recompute. `CACHE_RECEIPT_INVALID` never replaces the semantic
outcome. Cold/hit/corrupt logical outputs and receipts are byte-identical.

## Runner wire protocol

The wire request contains fixture-set hash, case ID, pipeline, semantic input
hash, and execution `{worker_count,cache_mode}`. Pipelines are
`mutation_application`, `gen0b_compile`, `gen0b_melody_compile`, and
`connected_candidate`; workers are 1/2/4/8 and cache mode is cold/hit/corrupt.
Semantic request hash uses `cps.connected-runner-semantic-request/v1` over the
wire request with `execution` omitted. Worker/cache settings never enter a
semantic artifact.

Input is exactly one canonical JSON value plus one transport LF, no BOM or
trailing bytes. Output is exactly one canonical result plus one transport LF;
logs use stderr. Artifact hashes include their specified canonical LF;
`stdout_sha256` hashes the literal complete stdout including transport LF.
Valid semantic success or failure exits 0. Protocol/schema/canonical/fixture
binding failure exits 64 with a closed `cps.runner-protocol-error`; crash,
signal, timeout, or I/O failure is never an expected conformance outcome.

## Parallel semantics

Single-worker logical traversal assigns every work item ordinal 0..N-1.
Physical assignment is `ordinal mod worker_count`. Mutation steps remain
sequential; independent candidates and resolver work may run concurrently.
Only the coordinator commits budget reservations, cache publication, first
failure, reductions, and output in logical-ordinal order. Arrival order is
unobservable. Work after the earliest logical failure contributes no charge,
cache write, or output.

Concurrent same-key misses may compute redundantly. CAS publication is
same-directory temporary write, fsync, create-if-absent. A loser validates the
winner and discards identical bytes; unequal valid bytes cause operational
`DETERMINISM_VIOLATION`, publish neither as authority, and fail conformance.

Each matrix cell starts with an isolated cache namespace: cold is empty, hit is
fully preseeded with the valid fixture entry, corrupt is preseeded with the
fixture's exact corrupted bytes. Results are committed in request ordinal.

## Matrix

RunnerMatrix cases sort `(pipeline UTF-8,case_id UTF-8)`. Each has exactly 12
cells sorted by worker count then cache order cold/hit/corrupt. Every cell has
the same semantic result hash and stdout SHA-256; only exit code 0 is valid.
Execution telemetry `{hits,misses,corrupt_entries,recomputations,workers}` is a
separate nonauthoritative sidecar and never appears in CompileReport or logical
output. Environment/hash-seed/delay schedules may form an outer execution
matrix but cannot change expected semantic bytes.

Required cases cover success and semantic failure for all four pipelines,
exact/+1 budget, earliest parallel failure, no-path, melody conflict, Mutation
failure, wrong key, truncated entry, artifact/receipt/root/child-stream
corruption, valid-hit budget shortage, and same-key writer race.

## V1 closure corrections

This section supersedes conflicting earlier wording. Runner v1 supports only
`connected_candidate`: Mutation -> GEN0-B -> chord-member melody. Mutation-aware
LineageIndex lowering is outside v1, so `lineage_index` is always null and its
contract/schema hash is not executor authority.

The wire request is one ordered batch: fixture-set hash, unique case IDs,
`semantic_input_hash`, global compile ceiling, and execution
`{worker_count,cache_mode,corruption_id}`. Case order defines task ordinals.
Every case manifest record supplies exactly one ConnectedRequest hash and has
pipeline `connected_candidate`. `corruption_id` is null for cold/hit and names
one exact corruption record for corrupt. Semantic input hash is the artifact
hash under `cps.connected-runner-input/v1` of
`{cases:[{case_id,connected_request_hash}],global_compile_logical_ceiling}`.

Success has all artifacts non-null except LineageIndex and top-level error.
Mutation failure has only Mutation receipt non-null and top-level error equal
to its `{code,stage,pointer}` projection. Compile failure has resulting Program,
Mutation impact/receipt, and CompileReport non-null; Project/evidence/melody/
Lineage are null and top-level error equals the CompileReport projection.
Mutation/compile semantic failures are published cacheable logical outputs and
do not stop the batch. Only runner-level global-budget, worker, protocol, or
determinism failure stops before publishing its task.

Parallel work items are top-level tasks only. Resolver parallelism follows its
own contracts. Same-key workers compute privately; the coordinator compares all
valid bytes before performing one create-if-absent publication. Unequal bytes
are `DETERMINISM_VIOLATION` before any authority is published. Connected-cache
replay uses the compile request's profile ledger; runner global ceiling is a
separate ordinal-commit check and produces RunnerResult failure, never a
ConnectedLogicalOutput.

Every new connected artifact hash is `"sha256:" + hexlower(SHA256(UTF8(
domain+"\0") || canonical_json_with_final_LF(value)))`, omitting its own hash
field. Domains are `cps.connected-runner-result/v1`,
`cps.connected-runner-matrix/v1`, `cps.connected-fixture-manifest/v1`, and
`cps.opcode-stream-bundle/v1` as applicable. Bundle inner/outer hashes equal;
children exactly equal receipt children in kind/query/order/input/stream hash.
`stdout_sha256` hashes literal stdout including its transport LF.

ExecutorManifest exact contract keys are `mutation_application`,
`gen0b_compiler_lowering`, `chord_member_melody`, and `connected_execution`.
Exact schema keys are `song_program`, `mutation`, `mutation_request`,
`mutation_impact`, `mutation_receipt`, `compiler_manifest`, `project`,
`gen0b_evidence`, `melody_report`, `compile_report`, `charge_receipt`,
`opcode_stream`, `opcode_bundle`, `connected_request`, `connected_output`, and
`connected_cache_entry`. No extra key is allowed.

Fixture cases and matrix cases sort by case ID UTF-8. Matrix cells are the exact
unique Cartesian product in worker numeric order and cache order
cold/hit/corrupt. Fixture SHA-256 hashes raw checked-in bytes. Paths are NFC
relative POSIX paths below the fixture root; absolute paths, backslash, empty,
`.` and `..` segments reject. Cold logical output and opcode bundle are separate
authorities; hit/corrupt reference their hashes. Execution telemetry is
nonauthoritative and excluded from expected semantic stdout.

`fixture_set_hash` is exactly the ConnectedFixtureManifest artifact hash
(`cps.connected-fixture-manifest/v1`, omitting `manifest_hash`). Each case has
exactly one corruption; variants use distinct case IDs. That corruption is
either one canonical JSON replacement or exact raw corrupted entry bytes named
by relative path/raw SHA-256. Each case also names the independent cold opcode
bundle file/raw hash; a cache entry is never its source authority.

For every fixture case, `opcode_stream_bundle` is non-null exactly when its
cold logical output has a non-null CompileReport. It is null for Mutation
failure; no `null` file, empty stream, or synthetic root stream is created.
The cache entry uses the same nullability rule.

Before publishing any semantic success or failure, runner global charge is
`compile_report.receipt.usage.total_logical_units`, or zero when CompileReport
is null. Atomically require `used+charge<=ceiling`. Failure does not publish or
charge and is exactly `RUN_COMPILE_BUDGET_EXCEEDED`, stage `publish_budget`,
counter `total_logical_units`, requested=charge, used=current used, and the
configured ceiling.

Every RunnerMatrix case names its own semantic request-core file/raw hash
containing that case's ordered case IDs and global ceiling; every cell names
its full wire request file/raw hash. A cell request MUST equal that case's
request core plus exactly its cell's `execution` object. Request bytes are
recovered from those files, never inferred from hashes. The matrix
fixture-set hash MUST equal the manifest hash above.
