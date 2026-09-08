from __future__ import annotations
import json
from pathlib import Path
import pytest
from .fallback_sampler_oracle import SemanticError, lower_production, register_endpoint_mc, select_fallback, validate_fallback_manifest, weighted_choice

ROOT=Path(__file__).parent/"fixtures"/"fallback_sampler"
def load(name): return json.loads((ROOT/name).read_text())

def test_fallback_manifest_and_negative_boundaries():
    validate_fallback_manifest(load("fallback_manifest_semantic.json"),2)
    for case in load("fallback_negative_cases.json"):
        with pytest.raises(SemanticError,match=case["expected_error"]): validate_fallback_manifest(case["manifest"],2)

def test_weighted_modulo_boundaries():
    data=load("weighted_boundaries.json")
    assert [weighted_choice(data["table"],c["draw"]) for c in data["cases"]]==[c["expected"] for c in data["cases"]]

def test_production_success_is_byte_stable():
    assert lower_production(load("production_request.json"),load("production_manifest.json"),load("production_catalog.json"))==load("production_expected.json")

def test_production_negative_precedence():
    req=load("production_request.json"); manifest=load("production_manifest.json"); catalog=load("production_catalog.json")
    bad=dict(req, sampler_manifest_hash="sha256:"+"0"*64, instrument_catalog_digest="sha256:"+"0"*64)
    with pytest.raises(SemanticError,match="SAMPLER_PRODUCTION_MANIFEST_INVALID"): lower_production(bad,manifest,catalog)
    bad=dict(req, active_roles=["harmony","drums"])
    with pytest.raises(SemanticError,match="SAMPLER_ACTIVE_ROLE_INVALID"): lower_production(bad,manifest,catalog)

def test_fallback_success_retry_lock_and_exhaustion_goldens():
    manifest=load("fallback_manifest_semantic.json")
    cases=[("fallback_request_core.json","fallback_eligible_rows.json","fallback_success_expected.json"),("fallback_retry_request_core.json","fallback_retry_rows.json","fallback_retry_expected.json"),("fallback_lock_request_core.json","fallback_lock_rows.json","fallback_lock_expected.json")]
    for request,rows,expected in cases:
        assert select_fallback(load(request),manifest,load(rows))==load(expected)
    with pytest.raises(SemanticError,match=load("fallback_exhaustion_expected.json")["expected_error"]):
        request=load("fallback_request_core.json"); rows=load("fallback_eligible_rows.json"); rows=[dict(rows[0],identity=True)]
        select_fallback(request,manifest,rows)

def test_fallback_uses_one_batch_request_and_receipt():
    batch=load("fallback_batch_expected.json")
    assert batch["mutation_application_request_schema_version"]=="1.1.0"
    assert batch["expected_application_request_count"]==1
    assert batch["expected_application_receipt_count"]==1
    assert batch["mutations"]==load("fallback_success_expected.json")["mutations"]

def test_register_inclusive_and_plus_minus_one_boundaries():
    data=load("register_boundary_cases.json")
    lo,hi=[register_endpoint_mc(x,data["base_frequency_millihz"]) for x in data["catalog_frequency_millihz"]]
    assert [lo,hi]==data["catalog_endpoint_mc"]
    assert lo <= data["cases"][0]["register"][0] <= data["cases"][0]["register"][1] <= hi
    assert data["cases"][1]["register"][0] < lo
    assert data["cases"][2]["register"][1] > hi
    request=load("production_request.json"); manifest=load("production_manifest.json"); catalog=load("production_catalog.json")
    lower_production(request,manifest,catalog)
    for register in ([-1200001,1200000],[-1200000,1200001]):
        bad=json.loads(json.dumps(manifest))
        for role in ("bass","harmony","melody","texture"):
            bad["register_presets_by_role"][role][0]["value"]=register
        with pytest.raises(SemanticError,match="SAMPLER_NO_COMPATIBLE_REGISTER"):
            lower_production(request,bad,catalog)
