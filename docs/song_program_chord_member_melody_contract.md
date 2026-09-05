# Chord-member Melody Binding Contract 1.0

Status: normative for SongProgram 0.1, GEN0-B, and Project 1.2.

Binding runs after all harmony paths and global chord indices are fixed, and
before direct-pitch lowering. Harmony backtracking is forbidden; this
supersedes the draft backtracking sentence in SongProgram section 9.2.

Expand MelodyIntent realizations with the ordinary section offset, repeat,
left-to-right rhythm rotations, gate, and velocity formulas. Mapping uses the
rotation-result canonical rhythm-step array ordinal: `zip` requires equal step
and point counts and uses the same ordinal; `cycle` uses ordinal modulo point
count. Start and duration are
`section_start + realization.at_tick + repeat*every_ticks + step.at_tick` and
`max(1,RHE(step.duration_ticks*gate_scale_q/10000))`. Section overflow fails
before binding. Bind raw records in `(start_tick,track_id UTF-8,section_id
UTF-8,realization_id UTF-8,repeat_ordinal,source_step_ordinal)` order.

For melody half-open interval M, an active candidate is a HarmonyOccurrence in
the same section whose half-open interval H completely contains M:
`H.start <= M.start && M.end <= H.end`. Equality at the right end succeeds;
`M.start == H.end` does not. Exactly one candidate across all harmony tracks
and runs is required. Zero, multiple, or boundary-crossing candidates fail
`MELODY_HARMONY_CONFLICT`; events are never split or shortened.

`member` is target ordinal, not array index. Find its unique index `j` in the
selected chord's `target_voice_ordinals`; absence fails conflict. Set:

- `source_vector = anchor_vector + voice_offsets[j]`;
- both delta vectors to the generator-dimension zero vector;
- `final_vector = source_vector`;
- exponent/ratio from `equave_exponents[j]`/`exact_ratios[j]`;
- active chord ID/index from the occurrence, target ordinal from `member`, and
  `next_resolved_chord_id=null`.

Event source uses the melody material instance, post-rotation step ordinal, and
`emitted_voice_ordinal=0`; event ratio equals the copied exact ratio. There is
no register shift, nearest member, retuning, or anticipation.

The melody track must have role melody and non-null ordered register bounds.
Copied ratio millicents must be within inclusive bounds. After binding and
direct-pitch lowering, sweep all pitched events per melody track as half-open intervals, processing ends
before starts at equal ticks; exceeding maximum polyphony fails conflict.
For consecutive distinct onset groups on a melody track, every Cartesian pitch
pair between groups must be within the inclusive
`maximum_melodic_jump_millicents`; simultaneous events create no jump pair.
Within an onset group, use Project event canonical order. Test jump pairs in
previous-group event order then current-group event order and report the
current event of the first violating pair. For polyphony, process all ends,
then starts one at a time in Project event order and report the first start
that makes the count exceed the ceiling.

Failure order is selected-chord integrity; melody symbols/role/rhythm; zip
length; temporal expansion/section bounds; raw sort; active cardinality;
member lookup; pitch equation; register; semantic/event ID collision; direct
lowering; jump; polyphony; final Project validation. Active/member/register/
jump/polyphony failures use `MELODY_HARMONY_CONFLICT`; structural failures keep
their existing typed codes.

Binding adds no child or new counter. Existing source-step structural charges
cover inspection; arithmetic is root `events`, emission is `emitted_events`,
validation and sorting use their existing counters, all with null child ID.
Semantic conflict has complete root receipt status under the GEN0-B contract:
the stream contains every successful charge through the failed semantic check,
no failed check adds a charge, and later actions are absent. CompileReport alone
has failure status; its counter/requested/used/ceiling fields are null.

The success-only `cps.chord-member-melody-report` sidecar binds source Program,
GEN0-B evidence, Project, and every binding. `gen0b_evidence_hash` is exactly
the `evidence_hash` of a schema-valid GEN0-B evidence artifact. Join each
binding by `project_chord_index` to the evidence's exactly-one selected record;
occurrence ID, track, core hash, and resolved chord ID must all agree.
`project_hash` is the Arrangement Project 1.2 artifact hash.

Report hash is `"sha256:" + hexlower(SHA256(UTF8(
"cps.chord-member-melody-report/v1\0") || canonical_json_with_final_LF(report
with report_hash omitted)))`. Bindings have consecutive ordinals and raw order;
their event IDs are unique and their UTF-8-sorted set equals the UTF-8-sorted
ID set of all Project resolved-melody events. Project event array order is
validated independently and never reorders bindings. Every point ordinal, join field, vector equation,
and event field is revalidated. Failure returns Project:null, GEN0-B
evidence:null, and melody report:null; the canonical CompileReport error is the
failure sidecar.

Selected-chord integrity checks evidence hash, query/result hashes, selected
core membership, occurrence-to-global-index bijection, resolved chord core/ID,
and Project occurrence chord ID, in that order. Failure is
`PROGRESSION_RESULT_INVALID`, stage `melody_selection`, pointing to the first
failed evidence field. Melody structural failures use `REFERENCE_NOT_FOUND`,
`MATERIAL_TRACK_ROLE_MISMATCH`, `MAPPING_LENGTH_MISMATCH`,
`EVENT_SECTION_OVERFLOW`, or `EVENT_ID_COLLISION` at the source SongProgram
pointer. Binding conflicts use `MELODY_HARMONY_CONFLICT`, stage
`melody_binding`. Active/member/register conflicts point to the owning
`/realizations/<index>`; step timing/mapping conflicts point to
`/materials/<rhythm_material_index>/steps/<post_rotation_step_ordinal>`.
Expanded coordinates never appear in a JSON Pointer. The CompileReport error
snapshot is exactly `{"binding_ordinal":n,"repeat_ordinal":r,
"source_step_ordinal":s}` for a raw binding; pre-binding and
selected-integrity failures use `{}`. Jump/polyphony point to the later-onset
Project event's source realization pointer. For a resolved-melody event the
snapshot uses the same three-key object; for a direct event it is exactly
`{"repeat_ordinal":r,"source_step_ordinal":s}`.

Structural pointers are exact: a missing reference points to its referencing
field, checking realization `section_id`, `track_id`, `material_id`, then melody
material `rhythm_id` in raw realization order. `MATERIAL_TRACK_ROLE_MISMATCH`
points to `/realizations/<index>/track_id`; `MAPPING_LENGTH_MISMATCH` points to
`/materials/<melody_material_index>/mapping`; `EVENT_SECTION_OVERFLOW` points
to `/realizations/<index>`; `EVENT_ID_COLLISION` points to the later raw
record's `/realizations/<index>`. Collection indices are pre-mutation canonical
SongProgram array indices.
