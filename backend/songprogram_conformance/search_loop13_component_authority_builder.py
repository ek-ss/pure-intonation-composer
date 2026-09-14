"""Bind reusable producer-owned components for the SearchLoop13 context."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "songprogram_conformance" / "fixtures"


def producer_digest(domain: str, value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(value) + b"\n").hexdigest()
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def build_reusable_components() -> dict[str, dict[str, Any]]:
    connected = _load(FIXTURES / "connected" / "gen0b_identity_request.json")
    catalog = _load(FIXTURES / "render" / "catalog.json")
    pitched_source = next(entry for entry in catalog["entries"] if entry["kind"] == "pitched")
    for role in ("bass", "melody", "texture"):
        entry = deepcopy(pitched_source)
        entry["instrument_id"] = f"pitched_fixture_{role}"
        entry["role"] = role
        catalog["entries"].append(entry)
    catalog["entries"].sort(key=lambda entry: entry["instrument_id"].encode())
    catalog_digest = producer_digest("cps.instrument-catalog/v1", catalog)
    render_manifest = _load(FIXTURES / "render" / "render_manifest.json")
    render_manifest["catalog_digest"] = catalog_digest
    render_manifest["renderer_build"] = {
        "implementation_id": "cps-search-loop13-fixture-renderer",
        "source_artifact": "backend/songprogram_conformance/search_loop13_component_authority_builder.py",
        "source_sha256": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dependency_lock_sha256": "sha256:"
        + hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest(),
    }
    render_core = dict(render_manifest)
    render_core.pop("render_manifest_digest")
    render_manifest["render_manifest_digest"] = producer_digest(
        "cps.render-manifest/v1", render_core
    )
    return {
        "compiler_manifest": _load(FIXTURES / "compiler" / "gen0b_compiler_manifest.json"),
        "mutation_choice_catalog": _load(FIXTURES / "search" / "mutation_choice_catalog.json"),
        "fingerprint_spec": _load(FIXTURES / "search" / "fingerprint_spec.json"),
        "instrument_catalog": catalog,
        "render_manifest": render_manifest,
        "executor_manifest": connected["executor_manifest"],
    }


def component_hashes(components: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        "compiler_manifest": producer_digest(
            "cps.compiler-manifest/v1.1", components["compiler_manifest"]
        ),
        "mutation_choice_catalog": producer_digest(
            "cps.mutation-choice-catalog/v1", components["mutation_choice_catalog"]
        ),
        "fingerprint_spec": producer_digest(
            "cps.fingerprint-spec/v1", components["fingerprint_spec"]
        ),
        "instrument_catalog": producer_digest(
            "cps.instrument-catalog/v1", components["instrument_catalog"]
        ),
        "render_manifest": components["render_manifest"]["render_manifest_digest"],
        "executor_manifest": producer_digest(
            "cps.connected-executor-manifest/v1", components["executor_manifest"]
        ),
    }


def write_reusable_components(root: Path) -> dict[str, str]:
    components = build_reusable_components()
    root.mkdir(parents=True, exist_ok=True)
    for name, document in components.items():
        (root / f"{name}.json").write_bytes(canonical_bytes(document) + b"\n")
    hashes = component_hashes(components)
    (root / "reusable_component_hashes.json").write_bytes(canonical_bytes(hashes) + b"\n")
    return hashes
