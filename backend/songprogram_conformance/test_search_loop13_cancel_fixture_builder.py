import hashlib
import json
from .search_loop13_cancel_fixture_builder import FIXTURE_ROOT, SCHEMAS, build, raw_hash
from .search_loop13_fixture_oracle import artifact_hash, canonical_json, manifest_hash


def test_checked_in_cancel_fixture_is_exact_oracle_output():
    generated = build()
    assert generated
    for relative, expected in generated.items():
        assert (FIXTURE_ROOT / relative).read_bytes() == expected


def test_cancel_fixture_cas_and_transcript_are_closed():
    case = json.loads((FIXTURE_ROOT / "cancel_phase0.json").read_bytes())
    index = json.loads((FIXTURE_ROOT / "cas_index.json").read_bytes())
    by_hash = {}
    schema_files = {
        ("cps.archive-heads-snapshot", "1.0.0"): "archive_heads_snapshot.schema.json",
        ("cps.cache-publication-index", "1.0.0"): "cache_publication_index.schema.json",
        ("cps.cancellation-decision", "1.1.0"): "cancellation_decision_1_1.schema.json",
        ("cps.cancellation-inbox-record", "1.1.0"): "cancellation_inbox_record_1_1.schema.json",
        ("cps.cancellation-request", "1.0.0"): "cancellation_request.schema.json",
        ("cps.search-checkpoint", "1.1.0"): "search_checkpoint_1_1.schema.json",
        ("cps.search-loop-13-event-payload", "1.0.0"): "search_loop_13_event_payload.schema.json",
        ("cps.search-run-record", "1.1.0"): "search_run_record_1_1.schema.json",
    }
    for row in index["entries"]:
        path = FIXTURE_ROOT / row["locator"]["path"]
        raw = path.read_bytes()
        assert len(raw) == row["byte_length"]
        value = json.loads(raw)
        assert value["schema"]
        schema_file = schema_files[(value["schema"], value["schema_version"])]
        assert row["schema_hash"] == raw_hash((SCHEMAS / schema_file).read_bytes())
        self_fields = {
            "cps.archive-heads-snapshot": "snapshot_hash",
            "cps.cache-publication-index": "index_hash",
            "cps.cancellation-decision": "decision_hash",
            "cps.cancellation-inbox-record": "inbox_hash",
            "cps.cancellation-request": "request_hash",
            "cps.search-loop-13-event-payload": "payload_hash",
        }
        if value["schema"] in self_fields:
            assert row["artifact_hash"] == artifact_hash(value, self_fields[value["schema"]])
        by_hash[row["artifact_hash"]] = value

    records = []
    cursor = case["expected"]["transcript_root_hash"]
    while cursor is not None:
        record = by_hash[cursor]
        body = dict(record)
        del body["record_hash"]
        assert cursor == manifest_hash("cps.search-run-record/v1", body)
        records.append(record)
        cursor = record["previous_record_hash"]
    records.reverse()
    assert [row["sequence"] for row in records] == [0, 1, 2]
    for record in records:
        payload = by_hash[record["payload_hash"]]
        assert payload["action_id"] == record["action_id"]
        assert payload["kind"] == record["kind"]
        assert by_hash[payload["artifact_hash"]]
    framed = b"".join(len(raw := canonical_json(row)).to_bytes(8, "big") + raw for row in records)
    assert hashlib.sha256(framed).digest()

    assert case["expected"]["cas_index_hash"] == index["index_hash"]
    assert case["cache_scenario"] == {
        "mode": "not_reached",
        "initial_entries": [],
        "expected_lookup": "not_performed",
        "expected_corruption_receipt_hash": None,
        "expected_publication_entry_hash": None,
    }
    assert case["parallel_scenario"]["scheduled_action_ids"] == []
    assert case["parallel_scenario"]["completion_permutation"] == []
    assert (
        raw_hash((FIXTURE_ROOT / "cas/inbox.json").read_bytes())
        == case["inputs"][0]["raw_file_sha256"]
    )


def test_cancel_case_is_not_prematurely_promoted_as_complete_suite():
    assert not (FIXTURE_ROOT / "suite_index.json").exists()
