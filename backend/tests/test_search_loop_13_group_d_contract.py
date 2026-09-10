from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_group_d_raw_schema_bindings_exist() -> None:
    run = _load("search_run_manifest_1_3.schema.json")
    context_hashes = _load("search_loop_13_context.schema.json")["properties"]["schema_hashes"]
    for name in ("archive_heads_snapshot", "structural_sampler_trace", "planner_proposal_preimage"):
        assert f"{name}_schema_hash" in run["required"]
        assert f"{name}_schema_hash" in run["properties"]
        assert name in context_hashes["required"]
        assert name in context_hashes["properties"]


def test_archive_snapshot_has_all_parent_selection_evidence() -> None:
    entry = _load("archive_heads_snapshot.schema.json")["$defs"]["entry"]
    assert entry["required"] == [
        "cell", "program_hash", "project_hash", "evaluation_report_hash",
        "archive_update_record_hash", "archive_admission_decision_hash", "parent_program",
    ]
    contract = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "source_occurrence_ordinal mod entries.length" in contract
    assert "program_hash raw digest bytes" in contract


def test_sampler_trace_rows_bind_manifest_draw_inputs() -> None:
    decision = _load("structural_sampler_trace.schema.json")["$defs"]["decision"]
    assert decision["required"] == [
        "decision_ordinal", "path", "counter", "table", "table_hash",
        "selected_index", "selected_value_hash", "row_hash",
    ]
    assert decision["additionalProperties"] is False
    assert decision["properties"]["path"]["type"] == "array"
    assert decision["properties"]["table"]["type"] == "array"


def test_attempt_seed_and_attempt_bounds_are_normative() -> None:
    trace = _load("structural_sampler_trace.schema.json")
    assert trace["properties"]["attempts"]["maxItems"] == 256
    assert trace["$defs"]["attempt"]["properties"]["attempt_ordinal"] == {
        "type": "integer", "minimum": 0, "maximum": 255,
    }
    assert trace["properties"]["terminal_attempt_ordinal"] == {
        "type": "integer", "minimum": 0, "maximum": 255,
    }
    contract = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert 'UTF-8("cps.structural-sampler-attempt-seed/v1\\0")' in contract
    assert "u64be(root_seed) || u64be(cohort_index) || u64be(attempt_ordinal)" in contract


def test_planner_proposal_preimage_has_only_mutations() -> None:
    schema = _load("planner_proposal_preimage.schema.json")
    assert schema["required"] == ["mutations"]
    assert set(schema["properties"]) == {"mutations"}
    contract = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert 'UTF-8("cps.planner-mutation-proposal/v1\\0")' in contract
    assert 'canonical_json_with_final_LF({"mutations": ordered_mutation_array})' in contract


def test_planner_null_and_cancel_checkpoint_event_numbers_are_unambiguous() -> None:
    coordinator = (ROOT.parent / "docs" / "song_program_search_loop_1_3_contract.md").read_text(encoding="utf-8")
    assert "Planner-null omits those two events" in coordinator
    assert "PlannerRequest at event 2 and PlannerResponse at event 3" in coordinator
    assert "FallbackRequest at event 4" in coordinator
    assert "MutationApplicationRequest at event 5" in coordinator
    payload = (ROOT.parent / "docs" / "song_program_search_loop_13_payload_contract.md").read_text(encoding="utf-8")
    assert "`(round, phase=13, candidate=0, event=2)`" in payload
    assert "`status=terminated`, `reason=cancelled`" in payload
    assert "no ordinary event at or above its\ncutoff may exist" in payload
    assert "Phase 0..12 event 2\nalways retains its ordinary scheduled meaning" in payload


def test_normal_checkpoint_points_to_next_round_control_barrier() -> None:
    coordinator = (ROOT.parent / "docs" / "song_program_search_loop_1_3_contract.md").read_text(encoding="utf-8")
    assert "committed immediately before the checkpoint record" in coordinator
    assert "event_ordinal=0" in coordinator
    assert "cannot be inserted retroactively" in coordinator
