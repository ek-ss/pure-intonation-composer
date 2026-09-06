"""Independent verifier for the checked-in GEN0-B/melody fixture bundle."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .gen0b_melody_oracle import artifact_hash, bind_chord_members, progression_result
from .identifiers import program_hash, project_artifact_hash

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures" / "compiler"
SCHEMAS = ROOT / "schemas"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> None:
    fixture_set=_load(FIXTURES/"gen0b_melody_fixture_set.json")
    assert set(fixture_set["files"])==set(fixture_set["file_sha256"])
    for name in fixture_set["files"]:
        assert fixture_set["file_sha256"][name]=="sha256:"+hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest()
    program = _load(FIXTURES / "gen0b_melody_song_program.json")
    query = _load(FIXTURES / "gen0b_progression_query.json")
    expected = _load(FIXTURES / "gen0b_progression_result.json")
    project = _load(FIXTURES / "gen0b_melody_project.json")
    bindings_expected = _load(FIXTURES / "chord_member_melody_bindings.json")
    assert (program["schema"], program["schema_version"]) == ("cps.song-program", "0.1.0")
    assert (query["schema"], query["schema_version"]) == ("cps.progression-query", "1.2.0")
    assert (expected["schema"], expected["schema_version"]) == ("cps.progression-result", "1.1.0")
    assert (project["schema"], project["schema_version"]) == ("cps.arrangement-project", "1.2.0")
    assert progression_result(query) == expected
    assert bindings_expected["source_program_hash"] == program_hash(program)
    assert bindings_expected["project_hash"] == project_artifact_hash(project)
    chords = {item["id"]: item for item in project["resolved_chords"]}
    raw = [{"section_id": b["section_id"], "start_tick": b["start_tick"], "duration_ticks": b["duration_ticks"], "member": b["member"]} for b in bindings_expected["bindings"]]
    occurrences = project["harmony_occurrences"]
    bound = bind_chord_members(raw, occurrences, chords)
    assert [item["shape_voice_ordinal"] for item in bound] == [item["shape_voice_ordinal"] for item in bindings_expected["bindings"]]
    failures = _load(FIXTURES / "chord_member_melody_failures.json")["cases"]
    assert {item["expected_error"] for item in failures} == {"MELODY_HARMONY_CONFLICT"}
    manifest=_load(FIXTURES/"gen0b_compiler_manifest.json")
    profile=_load(FIXTURES/"resolver_profile_gen0a_bnb.json")
    profile_core={k:v for k,v in profile.items() if k!="profile_hash"}
    assert profile["profile_hash"]==artifact_hash("cps.resolver-profile/v1",profile_core)
    assert manifest["resolver"]["profile_hash"]==profile["profile_hash"]
    assert manifest["resolver"]["build_id"]==profile["resolver_build_id"]
    assert manifest["instrument_catalog_digest"]==program["production"]["catalog_digest"]
    assert manifest["instrument_catalog_digest"] != "sha256:"+"0"*64
    catalog=_load(ROOT/"fixtures"/"render"/"catalog.json")
    assert manifest["instrument_catalog_digest"]==artifact_hash("cps.instrument-catalog/v1",catalog)
    streams={name:_load(FIXTURES/name) for name in ("gen0b_root_opcode_stream.json","gen0b_chord_opcode_stream.json","gen0b_progression_opcode_stream.json")}
    for stream in streams.values():
        core={k:v for k,v in stream.items() if k!="stream_hash"}
        assert stream["stream_hash"]==artifact_hash("cps.logical-opcode-stream/v1",core)
        assert [r["ordinal"] for r in stream["records"]]==list(range(len(stream["records"])))
    root=streams["gen0b_root_opcode_stream.json"]
    for child_name,prefix in (("gen0b_chord_opcode_stream.json","chord_"),("gen0b_progression_opcode_stream.json","progression_")):
        child=streams[child_name]; child_id=next(c["query_id"] for c in _load(FIXTURES/"gen0b_charge_receipt.json")["children"] if c["query_id"].startswith(prefix))
        projection=[]
        for record in root["records"]:
            if record["child_id"]==child_id: projection.append({**record,"ordinal":len(projection)})
        assert child["records"]==projection
    receipt=_load(FIXTURES/"gen0b_charge_receipt.json")
    evidence=_load(FIXTURES/"gen0b_compiler_evidence.json")
    evidence_core={k:v for k,v in evidence.items() if k!="evidence_hash"}
    assert evidence["root_receipt_digest"]==artifact_hash("cps.charge-receipt/v1.1",receipt)
    assert evidence["evidence_hash"]==artifact_hash("cps.gen0b-compiler-evidence/v1",evidence_core)
    report=_load(FIXTURES/"chord_member_melody_report.json")
    report_core={k:v for k,v in report.items() if k!="report_hash"}
    assert report["report_hash"]==artifact_hash("cps.chord-member-melody-report/v1",report_core)


if __name__ == "__main__":
    verify()
