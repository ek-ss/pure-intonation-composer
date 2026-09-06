from __future__ import annotations

import json
from pathlib import Path

from songprogram_conformance.build_mutation_fixtures import build
from songprogram_conformance.mutation_oracle import canonical_lf, evaluate
from songprogram_conformance.verify_mutation_fixtures import verify


ROOT=Path(__file__).resolve().parents[1]
SCHEMAS=ROOT/"songprogram_conformance"/"schemas"
FIXTURES=ROOT/"songprogram_conformance"/"fixtures"/"mutation"


def test_mutation_suite_rebuilds_byte_identically(tmp_path: Path) -> None:
    build(tmp_path)
    assert (tmp_path/"cases.json").read_bytes()==(FIXTURES/"cases.json").read_bytes()
    assert (tmp_path/"manifest.json").read_bytes()==(FIXTURES/"manifest.json").read_bytes()


def test_mutation_suite_schema_and_coverage() -> None:
    suite=json.loads((FIXTURES/"cases.json").read_text())
    schema=json.loads((SCHEMAS/"mutation_fixture_suite.schema.json").read_text())
    assert schema["properties"]["schema"]["const"] == suite["schema"]
    assert set(suite) == {"schema", "schema_version", "cases"}
    assert len({case["case_id"] for case in suite["cases"]}) == len(suite["cases"])
    assert len(suite["cases"])==41
    assert {(x["operation"],x["coverage"]) for x in suite["cases"]}=={(op,cov) for op in {x["operation"] for x in suite["cases"]} for cov in {"success","negative","scope","lock","boundary"}}


def test_independent_oracle_reproduces_every_expected_sidecar() -> None:
    verify(FIXTURES)
    suite=json.loads((FIXTURES/"cases.json").read_text())
    for case in suite["cases"]:
        request=case["request"]
        actual=evaluate(request["base_program"],request["mutations"][0],request["locked_roots"],request["mutation_choice_catalog"],request["instrument_catalog"],case["request_hash"])
        assert canonical_lf(actual)==canonical_lf(case["expected"]),case["case_id"]


def test_choice_binding_and_catalog_swap_special_cases() -> None:
    suite=json.loads((FIXTURES/"cases.json").read_text())
    by_id={x["case_id"]:x for x in suite["cases"]}
    assert by_id["replace_distribution_choice_success"]["expected"]["program"]["materials"][1]["mapping"]=="zip"
    assert by_id["swap_track_catalog_entry_success"]["expected"]["program"]["tracks"][0]["instrument_id"]=="pitched_fixture_3_1"
    assert by_id["swap_track_catalog_entry_negative"]["expected"]["error"]["code"]=="MUTATION_PARAMETER_INVALID"
    assert by_id["swap_track_catalog_entry_boundary"]["expected"]["status"]=="success"
    assert by_id["swap_track_catalog_entry_note_map_missing"]["expected"]["error"]["code"]=="MUTATION_PARAMETER_INVALID"
    request=by_id["replace_distribution_choice_success"]["request"]
    assert request["run_manifest"]["mutation_choice_catalog_hash"]==request["mutation_choice_catalog_hash"]
