# PIL Oracle Case Templates — Maintainer Promotion Guide

This directory holds **input templates** for the Perceptual Interpretation
Layer oracle suite required by
`docs/song_program_perceptual_interpretation_layer_contract.md` section 9.
They are **not** authoritative fixtures:

- every `expected.*` field, `case_hash`, and every suite-index hash is `null`;
- the directory is outside the read-only conformance authority area
  (`backend/songprogram_conformance/fixtures|goldens|schemas`, oracle
  modules, and `docs/*contract*.md`), so ordinary implementation work may
  regenerate it;
- only the **oracle maintainer** may fill golden values and promote cases,
  through the documented authoritative-update workflow.

The generated `project` objects are standalone-valid ArrangementProject 1.2
inputs compiled from compact note descriptions. Their event provenance and
`project_hash` are real case inputs, but are not expected/golden values. The
oracle maintainer MUST revalidate them before promotion and must not rewrite
them while deriving expected report bytes.

Regenerate inputs after a deliberate spec/implementation change:

```bash
cd backend
python tools/build_pil_oracle_case_templates.py
```

The script writes concrete Project/manifest/asset payloads (with real
binding hashes — those are case *inputs*, not goldens) and leaves every
expected output null.

Pre-flight check (read-only; also enforced by
`tests/test_pil_contract_and_genre_draft_tools.py`):

```bash
cd backend
python tools/check_pil_oracle_case_templates.py
```

It revalidates every case binding with the same validator the maintainer
uses, and fails if any golden field became non-null, if coverage labels drift
from `PIL_REQUIRED_COVERAGE`, or if the suite index no longer mirrors the
case files.

## Promotion workflow (oracle maintainer only)

### 1. Fill golden values

For each `pil_*.json` case:

1. Revalidate the checked-in standalone Project 1.2 input, then execute the
   case with the reference implementation
   (`app.songprogram.perceptual.run_perceptual_interpretation`, passing the
   case's `project`, `manifest`, and the non-null entries of `assets`).
2. Independently review the result against the contract (section 9 mapping
   in `docs/song_program_pil_oracle_suite_fixture_spec.md`). Golden values
   must come from reviewed reference behavior, never copied from an
   implementation's self-report without audit.
3. Fill `expected.status`, `expected.error`, `expected.report_hash`, and
   `expected.canonical_report_sha256` (exact canonical report bytes hash).
   All promoted cases are binding-valid and therefore have report bytes;
   malformed/binding negatives are maintained in a separate negative pack.
4. Fill `native_ji_report_hash` only where the case documents correlation
   metadata (e.g. `pil_nonfunctional_two_reports`); it is never a
   computation input.
5. Compute `case_hash` with the generic artifact preimage
   (`cps-artifact-hash/v1`, only `case_hash` removed).

### 2. Fill the suite index

In `suite_index.json`:

1. Assign `suite_version`.
2. For every case row fill `raw_file_sha256` (raw case file bytes),
   `case_hash`, and `case_schema_hash` (raw bytes of the case JSON Schema
   once it is frozen under `backend/songprogram_conformance/schemas/`).
3. Confirm `coverage` labels still match each case and that
   `required_coverage` is fully covered.
4. Compute `suite_hash` (same generic preimage, only `suite_hash` removed).

### 3. Promote into the protected area

1. Move the completed cases and index to
   `backend/songprogram_conformance/fixtures/pil_oracle/` (create the
   directory; do not modify any existing fixture).
2. Add the case/suite JSON Schemas to
   `backend/songprogram_conformance/schemas/` if they are not already
   frozen, and update `schemas/README.md`.
3. Keep the original templates here unchanged as regeneration sources.

### 4. Verify with the readonly guard

The guard rejects protected worktree changes unless the maintainer flag is
passed. Run it explicitly during the promotion commit:

```bash
cd backend
python -m songprogram_conformance.verify_fixture_readonly --allow-authoritative-update
python -m pytest tests/test_fixture_readonly_guard.py \
    tests/test_songprogram_schema_pack.py -q
```

- The first command must exit 0 (protected changes are the intended
  promotion; production code must still not reference fixture builders).
- The pytest run must pass; note that
  `test_guard_passes_for_the_repository` fails while *any* protected change
  is uncommitted — this is expected mid-promotion and must pass again after
  the promotion commit lands.

### 5. Commit

Commit the promoted fixtures, schemas, and any contract updates as one
`spec:`/`test:` authoritative commit, separate from implementation commits
(see `b6c018b` / `4ebce52` for the split pattern). Afterwards:

```bash
python -m pytest tests/test_fixture_readonly_guard.py -q   # must pass
git status --short                                          # must be clean
```

### Rules that do not change during promotion

- Implementation work never creates or edits files under the protected
  prefixes, never edits goldens, and never imports
  `songprogram_conformance.build_*` / `generate_*` / oracle modules from
  `backend/app`.
- One asset byte change creates new content hashes; never silently
  overwrite an earlier suite — bump `suite_version` instead.
- Until this suite and a CalibrationDecision exist, all PIL metrics remain
  audit-only.
