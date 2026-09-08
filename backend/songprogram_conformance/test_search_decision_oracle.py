from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from .search_decision_oracle import (
    DecisionContractError, action_id, archive_admission, challenger_acceptance,
    comparison_set_hash, near_duplicate, reserve_render, resolve_component,
    round_decision, select_render_candidates, validate_action, validate_charge,
    validate_components,
)

ROOT = Path(__file__).parent
FIX = ROOT / "fixtures" / "search_decisions"


def load(path: str):
    return json.loads((FIX / path).read_text())


def test_oracle_has_no_production_imports() -> None:
    tree = ast.parse((ROOT / "search_decision_oracle.py").read_text())
    names = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name == "app" or name.startswith("app.") for name in names)


def test_authoritative_success_sidecar() -> None:
    cases, expected = load("success/cases.json"), load("success/expected.json")
    assert list(archive_admission(**cases["archive"])) == expected["archive"]
    assert list(challenger_acceptance(**cases["challenger"])) == expected["challenger"]
    got = near_duplicate(**cases["near_duplicate"])
    assert json.loads(json.dumps(got)) == expected["near_duplicate"]
    assert comparison_set_hash(["sha256:"+"1"*64,"sha256:"+"2"*64]) == expected["comparison_set_hash"]
    assert list(round_decision(**cases["stopping"])) == expected["stopping"]
    c = cases["cancellation"]
    assert action_id(c["run_hash"], 2, 7, 3) == expected["cancellation_action_id"]
    assert list(reserve_render(**cases["render"])) == expected["render"]


def test_authoritative_boundaries() -> None:
    cases, expected = load("boundary/cases.json"), load("boundary/expected.json")
    for name in ("archive_empty", "archive_hash_tie"):
        assert list(archive_admission(**cases[name])) == expected[name]
    assert list(challenger_acceptance(**cases["challenger_exact_margins"])) == expected["challenger_exact_margins"]
    for name in ("near_exact_threshold", "near_threshold_plus_one"):
        assert json.loads(json.dumps(near_duplicate(**cases[name]))) == expected[name]
    for name in ("render_exact", "render_plus_one"):
        assert list(reserve_render(**cases[name])) == expected[name]
    for name in ("stop_precedence", "patience_exact"):
        assert list(round_decision(**cases[name])) == expected[name]
    assert expected["near_exact_threshold"][0] == "near_duplicate"
    assert expected["near_threshold_plus_one"][0] == "distinct"
    assert expected["render_exact"] == ["reserved", 1000]
    assert expected["render_plus_one"] == ["rejected", 600]
    assert expected["stop_precedence"][1] == "cancelled"


def test_authoritative_negative_sidecars() -> None:
    funcs = {
        "validate_action": lambda x: validate_action(x),
        "validate_charge": lambda x: validate_charge(x),
        "comparison_set_hash": comparison_set_hash,
        "validate_components": validate_components,
        "reserve_render": lambda x: reserve_render(**x),
    }
    expected = load("negative/expected.json")
    for case in load("negative/cases.json"):
        with pytest.raises(DecisionContractError) as caught:
            funcs[case["call"]](case["input"])
        assert {"code":caught.value.code,"pointer":caught.value.pointer} == expected[case["id"]]


def test_component_source_and_render_selection_semantics() -> None:
    h = "sha256:" + "a" * 64
    source = {"artifact_kind":"evaluation_report","schema_hash":h,"json_pointer":"/metrics/genre"}
    assert resolve_component(source, {"evaluation_report":{"schema_hash":h,"document":{"metrics":{"genre":91}}}}) == 91
    candidates = [
        {"program_hash":"sha256:"+"2"*64,"compile_valid":True,"distinct":True,"components":[10,4]},
        {"program_hash":"sha256:"+"1"*64,"compile_valid":True,"distinct":True,"components":[10,3]},
        {"program_hash":"sha256:"+"0"*64,"compile_valid":False,"distinct":True,"components":[99,0]},
    ]
    assert select_render_candidates(candidates,["maximize","minimize"],1) == ["sha256:"+"1"*64]
