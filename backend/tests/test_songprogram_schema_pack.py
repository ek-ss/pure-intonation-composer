from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "songprogram_conformance"


def test_every_schema_is_closed_and_has_identity() -> None:
    schemas = sorted((ROOT / "schemas").glob("*.schema.json")) + sorted(ROOT.glob("*.schema.json"))
    assert schemas
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://cps.local/schemas/")
        _assert_objects_are_closed(schema, path.name)


def _assert_objects_are_closed(node: object, location: str) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            additional = node.get("additionalProperties")
            assert additional is False or isinstance(additional, dict), location
        for key, value in node.items():
            _assert_objects_are_closed(value, f"{location}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _assert_objects_are_closed(value, f"{location}/{index}")


def test_all_local_schema_references_exist() -> None:
    schema_dir = ROOT / "schemas"
    for path in schema_dir.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        for reference in _references(schema):
            target = reference.split("#", 1)[0]
            if target and not target.startswith("https://"):
                assert (schema_dir / target).is_file(), f"{path.name}: {reference}"
    for path in ROOT.glob("*.schema.json"):
        json.loads(path.read_text(encoding="utf-8"))


def _references(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str):
            found.append(node["$ref"])
        for value in node.values():
            found.extend(_references(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_references(value))
    return found


def test_negative_cases_use_registered_exact_errors() -> None:
    pack = ROOT / "fixtures" / "pack"
    registry = json.loads((pack / "error_registry.json").read_text(encoding="utf-8"))
    cases = json.loads((pack / "project_negative_cases.json").read_text(encoding="utf-8"))
    registered = {(item["code"], item["stage"]) for item in registry["errors"]}
    assert len({case["id"] for case in cases["cases"]}) == len(cases["cases"])
    for case in cases["cases"]:
        assert (case["expected"]["code"], case["expected"]["stage"]) in registered
        assert case["mutation"]["pointer"] == case["expected"]["pointer"]


def test_fixture_manifest_paths_and_raw_digests_are_frozen() -> None:
    manifest = json.loads((ROOT / "fixtures" / "manifest.json").read_text(encoding="utf-8"))
    for fixture in manifest["fixtures"]:
        for path_key, hash_key in (("input_path", "input_sha256"), ("expected_path", "expected_sha256")):
            path = ROOT / fixture[path_key]
            assert path.is_file(), fixture["id"]
            observed = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            assert observed == fixture[hash_key], fixture["id"]
        assert (ROOT / fixture["schema_path"]).is_file(), fixture["id"]
