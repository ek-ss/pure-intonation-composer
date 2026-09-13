import json
from pathlib import Path

from .search_loop13_fixture_oracle import action_id, artifact_hash, seal_event_payload, seal_record

ROOT = Path(__file__).parent / "schemas"
H = "sha256:" + "a" * 64


def _validate(name, value):
    schema = json.loads((ROOT / name).read_text())
    assert set(value) == set(schema["required"])
    for key, rule in schema["properties"].items():
        if "const" in rule:
            assert value[key] == rule["const"]


def test_minimal_cancellation_record_chain_is_schema_closed():
    run, context = H, "sha256:" + "b" * 64
    snapshot = {
        "schema": "cps.archive-heads-snapshot",
        "schema_version": "1.0.0",
        "run_hash": run,
        "context_hash": context,
        "round": 0,
        "stage": "round_before",
        "entries": [],
        "snapshot_hash": "",
    }
    snapshot["snapshot_hash"] = artifact_hash(snapshot, "snapshot_hash")
    _validate("archive_heads_snapshot.schema.json", snapshot)
    inbox = {
        "schema": "cps.cancellation-inbox-record",
        "schema_version": "1.1.0",
        "run_hash": run,
        "request_schema_hash": H,
        "raw_request_bytes_base64": "e30K",
        "raw_request_digest": H,
        "request_hash": H,
        "acceptance_sequence": 0,
        "inbox_hash": "",
    }
    inbox["inbox_hash"] = artifact_hash(inbox, "inbox_hash")
    _validate("cancellation_inbox_record_1_1.schema.json", inbox)
    c0 = (0, 0, 0, 0)
    p0 = seal_event_payload("cancellation_request", run, context, c0, inbox["inbox_hash"], H)
    r0 = seal_record(run, 0, "cancellation_request", c0, p0["payload_hash"], None)
    decision = {
        "schema": "cps.cancellation-decision",
        "schema_version": "1.1.0",
        "status": "accepted",
        "cancelled": True,
        "run_hash": run,
        "context_hash": context,
        "inbox_record_hash": inbox["inbox_hash"],
        "raw_request_digest": H,
        "request_hash": H,
        "effective_cutoff_action_id": action_id(run, 0, 0, 0, 2),
        "cutoff_coordinate": {
            "round": 0,
            "phase_ordinal": 0,
            "candidate_ordinal": 0,
            "event_ordinal": 2,
        },
        "last_committable_action_id": action_id(run, 0, 0, 0, 1),
        "champion_at_cutoff": None,
        "archive_heads_hash": snapshot["snapshot_hash"],
        "decision_hash": "",
    }
    decision["decision_hash"] = artifact_hash(decision, "decision_hash")
    _validate("cancellation_decision_1_1.schema.json", decision)
    c1 = (0, 0, 0, 1)
    p1 = seal_event_payload("cancellation_decision", run, context, c1, decision["decision_hash"], H)
    r1 = seal_record(run, 1, "cancellation_decision", c1, p1["payload_hash"], r0["record_hash"])
    checkpoint = {
        "schema": "cps.search-checkpoint",
        "schema_version": "1.1.0",
        "run_hash": run,
        "last_sequence": 1,
        "last_record_hash": r1["record_hash"],
        "next_action_id": action_id(run, 0, 13, 0, 3),
        "cursor": {"round": 0, "candidate_ordinal": 0, "phase_ordinal": 13, "event_ordinal": 3},
        "budget_usage": {"compile_logical_units": 0, "render_frames": 0, "planner_calls": 0},
        "planner_calls": 0,
        "patience_rounds": 0,
        "archive_heads": [],
        "champions": [],
        "accepted_champion": None,
        "termination": {
            "status": "terminated",
            "reason": "cancelled",
            "decision_hash": decision["decision_hash"],
        },
    }
    _validate("search_checkpoint_1_1.schema.json", checkpoint)
    c2 = (0, 13, 0, 2)
    p2 = seal_event_payload("checkpoint", run, context, c2, artifact_hash(checkpoint, "_none"), H)
    r2 = seal_record(run, 2, "checkpoint", c2, p2["payload_hash"], r1["record_hash"])
    for p in (p0, p1, p2):
        _validate("search_loop_13_event_payload.schema.json", p)
    for r in (r0, r1, r2):
        _validate("search_run_record_1_1.schema.json", r)
