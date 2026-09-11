import json
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMAS = ROOT / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text())


def test_v11_is_versioned_and_production_free():
    v1 = load("sampler_manifest.schema.json")
    v11 = load("sampler_manifest_1_1.schema.json")
    assert v1["properties"]["schema_version"]["const"] == "1.0.0"
    assert v11["properties"]["algorithm"]["const"] == "broad-prior-v1.1"
    assert v11["properties"]["stream_algorithm"]["const"] == "path-addressed-sha256-attempt/v1.1"
    table_names = set(v11["properties"]["tables"]["properties"])
    assert not {"track_instrument_by_role", "gain_q", "pan_q"} & table_names
    structural = load("structural_song_program_1_0.schema.json")
    assert not {"tracks", "production"} & set(structural["properties"])


def test_rejection_precedence_is_exact():
    schema = load("structural_rejection_evidence_1_1.schema.json")
    assert schema["properties"]["code"]["enum"] == [
        "SAMPLER_LOWERING_BINDING_INVALID", "SAMPLER_DECISION_PROGRAM_INVALID",
        "SAMPLER_WEIGHT_SUM_OVERFLOW", "SAMPLER_TABLE_EMPTY",
        "SAMPLER_PATH_EXPANSION_INVALID", "SAMPLER_TOTAL_BARS_MISMATCH",
        "SAMPLER_ID_COLLISION", "SAMPLER_SECTION_UNCOVERED",
        "SAMPLER_SOUNDING_ROLE_UNDERSHOOT", "SAMPLER_RECALL_MISSING",
        "SAMPLER_NON_IDENTITY_RECALL_MISSING", "SAMPLER_STRUCTURAL_SCHEMA_INVALID",
        "SAMPLER_STRUCTURAL_SEMANTIC_INVALID",
    ]


def test_new_schema_pack_resolves():
    for name in ("structural_song_program_1_0.schema.json", "structural_lowering_manifest.schema.json", "sampler_manifest_1_1.schema.json", "structural_rejection_evidence_1_1.schema.json", "structural_sampler_request_1_1.schema.json", "structural_sampler_trace_1_1.schema.json", "structural_sampler_result_1_1.schema.json", "broad_prior_production_result_1_1.schema.json"):
        schema = load(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://cps.local/schemas/")


def test_v11_envelopes_bind_lowering_and_evidence():
    request = load("structural_sampler_request_1_1.schema.json")
    trace = load("structural_sampler_trace_1_1.schema.json")
    result = load("structural_sampler_result_1_1.schema.json")
    required = {"sampler_manifest_hash", "structural_lowering_manifest_hash", "structural_program_schema_hash", "structural_rejection_evidence_schema_hash"}
    assert required <= set(request["required"])
    assert required <= set(trace["required"])
    assert required <= set(result["required"])
    attempts = trace["properties"]["attempts"]["items"]["oneOf"]
    assert [item["$ref"] for item in attempts] == ["#/$defs/accepted", "#/$defs/rejectedComplete", "#/$defs/rejectedIncomplete"]


def test_production_v11_result_repeats_request_causality():
    schema = load("broad_prior_production_result_1_1.schema.json")
    for field in ("run_hash", "context_hash", "source_decision_hash", "request_hash", "sampler_manifest_hash", "structural_lowering_manifest_hash", "production_lowering_manifest_hash", "instrument_catalog_digest", "structural_program_hash"):
        assert field in schema["required"]


def test_contract_fixes_attempt_stream_and_expansion():
    text = (ROOT.parent.parent / "docs" / "song_program_structural_sampler_1_1_contract.md").read_text()
    for required in ("raw32(attempt_seed_hash)", "{transform}", "counter zero", "SAMPLER_TOTAL_BARS_MISMATCH", "preregistered cohort gate"):
        assert required in text


def test_contract_closes_recall_realization_and_coverage_semantics():
    text = (ROOT.parent.parent / "docs" / "song_program_structural_sampler_1_1_contract.md").read_text()
    for required in (
        "complete Cartesian product",
        "sole exception to the selected-owner rule",
        "rhythm material maps only to `drums`",
        "direct-vector material maps to `bass` and `texture`",
        "SAMPLER_SECTION_UNCOVERED`: a selected section has zero realizations",
        "selected `rotate_amount` is nonzero",
        "cps.structural-song-program/1.0\\0",
        "explicit fourth argument or as a",
        "fallback lookup and process-local defaults are",
        "helper is also the primary material",
        "signed displacement in rhythm-derived quanta",
        "ticks = rotate_amount * quantum",
    ):
        assert required in text
