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
    for name in ("structural_song_program_1_0.schema.json", "structural_lowering_manifest.schema.json", "sampler_manifest_1_1.schema.json", "structural_rejection_evidence_1_1.schema.json"):
        schema = load(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://cps.local/schemas/")


def test_contract_fixes_attempt_stream_and_expansion():
    text = (ROOT.parent.parent / "docs" / "song_program_structural_sampler_1_1_contract.md").read_text()
    for required in ("raw32(attempt_seed_hash)", "{transform}", "counter zero", "SAMPLER_TOTAL_BARS_MISMATCH", "preregistered cohort gate"):
        assert required in text
