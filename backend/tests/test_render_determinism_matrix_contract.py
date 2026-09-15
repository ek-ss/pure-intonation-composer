from __future__ import annotations

import json
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SCHEMAS = BACKEND / "songprogram_conformance" / "schemas"
CONTRACT = BACKEND.parent / "docs" / "song_program_render_determinism_matrix_contract.md"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_render_matrix_coordinates_are_closed() -> None:
    properties = _load("render_determinism_matrix_manifest.schema.json")["properties"]
    assert properties["invocation_count"] == {"const": 100}
    assert [row["const"] for row in properties["python_hash_seeds"]["prefixItems"]] == [
        0, 1, 7, 42
    ]
    assert [row["const"] for row in properties["worker_counts"]["prefixItems"]] == [
        1, 2, 4, 8
    ]
    assert [row["const"] for row in properties["test_block_sizes"]["prefixItems"]] == [
        64, 256, 1024
    ]


def test_render_receipt_requires_complete_matrix_and_true_parity() -> None:
    properties = _load("render_determinism_matrix_receipt.schema.json")["properties"]
    assert properties["process_coordinates"]["minItems"] == 16
    assert properties["process_coordinates"]["maxItems"] == 16
    assert properties["all_process_equal"] == {"const": True}
    assert properties["all_blocks_equal"] == {"const": True}


def test_render_contract_fixes_schedule_hashes_and_failure_precedence() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "`i mod case_count`",
        "`[64, 256, 1024]`",
        "`RENDER_MATRIX_CASE_ORDER_INVALID`",
        "Production implementation cannot\nwrite or update those expected values",
        "The fixture set is inputs-only and non-cyclic",
        "must exclude `fixture_set.json` itself",
    ):
        assert required in text
