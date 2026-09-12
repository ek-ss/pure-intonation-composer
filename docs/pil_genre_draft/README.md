# PIL Genre/Style Interpretation — Draft Schemas (non-normative)

This directory holds **design drafts** accompanying
`docs/song_program_pil_genre_interpretation_draft.md`. Nothing here is a
contract. Genre evaluation remains a SPEC-BLOCKER (G1–G7) until the owner
closes the open decisions in
`docs/song_program_perceptual_interpretation_layer_contract.md` section 7.

| File | Drafts | Blocker |
| --- | --- | --- |
| `genre_model.draft.schema.json` | GenreModel 1.0 content-addressed asset (draft doc §3.1) | G1 |
| `genre_feature_record.draft.schema.json` | Harmony-group GenreFeatureRecord 1.0 (§3.2) | G2, G4 |
| `genre_interpretation.draft.schema.json` | Report row shape, mirroring the authoritative `perceptual_interpretation_report.schema.json` `$defs/genre` unchanged (§3.3) | G3 (formulas stay open) |

## Rules

- These files MUST NOT be copied into
  `backend/songprogram_conformance/schemas/` or otherwise promoted except by
  the owner through the authoritative-update workflow. File names and `$id`s
  deliberately avoid the word "contract" so the readonly guard never treats
  them as protected.
- The drafts fix **shapes only**. The four score formulas (G3), the G4
  aggregation layout, and the G5 harmony-only closure remain owner decisions;
  no implementation may compute canonical bytes from these drafts yet.
- The drafts reuse the authoritative vocabularies: group names equal the
  report schema's `missing_groups` enum, and Q values equal `$defs/q`
  (integer 0..10000). Hashes follow the `sha256:<64 lowercase hex>` form.

## Consistency check

`backend/tools/check_pil_genre_draft_consistency.py` verifies that the drafts
stay aligned with the authoritative report/manifest schemas (row shape, group
enum, Q range, nullable `genre_model_hash` binding point) and validates a
sample instance against each draft with a minimal built-in checker. It is
read-only and prints blocker status (e.g. whether G6 is still open).

Run from the backend directory:

```
python tools/check_pil_genre_draft_consistency.py
```

Exit code 0 means the drafts are internally consistent; blocker notes are
informational and never fail the check.
