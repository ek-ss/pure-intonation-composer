from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from .pil_synthetic_bundle import (
    PILSyntheticBundleError,
    build_bundle_index,
    replay_bundle,
)
from .test_pil_synthetic_authority_validator import _chain


def _bundle(chain: dict) -> dict:
    arguments = {key: chain[key] for key in (
        "protocol", "agents", "cohort", "assignment_set", "responses",
        "judgment_set", "registry", "evidence_summary", "decision",
    )}
    return {"index": build_bundle_index(**arguments), **arguments}


def test_bundle_index_replays_complete_validated_chain() -> None:
    chain = _chain()
    bundle = _bundle(chain)
    assert replay_bundle(
        **bundle,
        expected_bindings=chain["expected_bindings"],
        schema_validator=chain["schema_validator"],
    ) == bundle["index"]["bundle_hash"]


def test_bundle_index_rejects_reordered_or_substituted_members() -> None:
    chain = _chain()
    bundle = _bundle(chain)
    bundle["index"] = copy.deepcopy(bundle["index"])
    bundle["index"]["agent_manifest_hashes"].reverse()
    with pytest.raises(PILSyntheticBundleError, match="PIL_SYNTHETIC_BUNDLE_INDEX_MISMATCH"):
        replay_bundle(
            **bundle,
            expected_bindings=chain["expected_bindings"],
            schema_validator=chain["schema_validator"],
        )


def test_bundle_hash_changes_when_decision_identity_changes() -> None:
    chain = _chain()
    original = _bundle(chain)["index"]["bundle_hash"]
    changed = copy.deepcopy(chain)
    changed["decision"]["decision_hash"] = "sha256:" + "f" * 64
    assert _bundle(changed)["index"]["bundle_hash"] != original


def test_cli_intake_is_canonical_atomic_and_idempotent(tmp_path: Path) -> None:
    chain = _chain()
    bundle = _bundle(chain)
    source = tmp_path / "bundle"
    source.mkdir()

    def write(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        )

    write(source / "index.json", bundle["index"])
    for name in (
        "protocol", "cohort", "assignment_set", "judgment_set", "registry",
        "evidence_summary", "decision",
    ):
        write(source / f"{name}.json", bundle[name])
    for agent in bundle["agents"]:
        write(source / "agents" / f"{agent['manifest_hash'][7:]}.json", agent)
    for response in bundle["responses"]:
        write(source / "responses" / f"{response['record_hash'][7:]}.json", response)
    bindings = tmp_path / "bindings.json"
    write(bindings, chain["expected_bindings"])
    store = tmp_path / "store"
    tool = Path(__file__).resolve().parents[1] / "tools" / "intake_pil_synthetic_authority.py"
    runtime = Path(sys.base_prefix) / "bin" / "python"
    command = [
        str(runtime), str(tool), "--bundle", str(source),
        "--expected-bindings", str(bindings), "--store", str(store),
    ]
    first = subprocess.run(command, check=True, capture_output=True)
    second = subprocess.run(command, check=True, capture_output=True)
    assert first.stdout == second.stdout
    receipt = json.loads(first.stdout)
    assert receipt["bundle_hash"] == bundle["index"]["bundle_hash"]
    assert len(list(store.rglob("receipt.json"))) == 1
