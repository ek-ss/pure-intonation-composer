from __future__ import annotations

import json
from pathlib import Path

from .render_determinism_matrix_validator import validate


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures/render_determinism_matrix"
SCHEMAS = ROOT / "schemas"


def test_owner_fixture_is_readonly_valid() -> None:
    validate(FIXTURE)


def test_owner_fixture_declares_closed_schema_identities() -> None:
    manifest = json.loads((FIXTURE / "matrix_manifest.json").read_text())
    receipt = json.loads((FIXTURE / "matrix_receipt.json").read_text())
    fixture_set = json.loads((FIXTURE / "fixture_set.json").read_text())
    assert (manifest["schema"], manifest["schema_version"]) == (
        "cps.render-determinism-matrix-manifest",
        "1.0.0",
    )
    assert (receipt["schema"], receipt["schema_version"]) == (
        "cps.render-determinism-matrix-receipt",
        "1.0.0",
    )
    assert (fixture_set["schema"], fixture_set["schema_version"]) == (
        "cps.render-fixture-set",
        "1.0.0",
    )


def test_matrix_binds_one_hundred_invocations_and_all_coordinates() -> None:
    manifest = json.loads((FIXTURE / "matrix_manifest.json").read_text())
    receipt = json.loads((FIXTURE / "matrix_receipt.json").read_text())
    assert manifest["invocation_count"] == 100
    assert len(receipt["process_coordinates"]) == 16
    assert [row["block_size"] for row in receipt["block_coordinates"]] == [64, 256, 1024]
