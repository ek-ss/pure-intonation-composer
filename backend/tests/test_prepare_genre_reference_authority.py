from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from app.songprogram.evaluation_harness import _artifact_hash


def _tool() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "tools" / "prepare_genre_reference_authority.py"
    spec = importlib.util.spec_from_file_location("prepare_genre_reference_authority", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _tool()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_prepare_binds_explicit_grant_and_sorts_partitions(tmp_path: Path) -> None:
    entries = []
    for identifier, partition in (
        ("hold", "holdout"),
        ("cal", "calibration"),
        ("val", "validation"),
    ):
        relative = f"clips/{partition}/{identifier}.wav"
        payload = identifier.encode()
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        entries.append(
            {
                "id": identifier,
                "partition": partition,
                "clip_relative_path": relative,
                "clip_wav_sha256": _sha(payload),
                "receipt_sha256": _sha(f"receipt:{identifier}".encode()),
            }
        )
    transfer = {"set_id": "test_set", "entries": entries}
    (tmp_path / "transfer_manifest.json").write_text(json.dumps(transfer))

    grant, policy, provenances, intake = TOOL.prepare(
        tmp_path, reference_set_id="test_set", issued_epoch_day=20_715
    )

    assert grant["rights_basis"] == "user_supplied_explicit_grant"
    assert grant["grant_hash"] == _artifact_hash(grant, "grant_hash")
    assert policy["allowed_rights_bases"] == ["user_supplied_explicit_grant"]
    assert policy["policy_hash"] == _artifact_hash(policy, "policy_hash")
    assert [row["reference_id"] for row in provenances] == ["cal", "val", "hold"]
    assert [row["partition"] for row in intake["sources"]] == [
        "calibration",
        "validation",
        "holdout",
    ]
    assert all(row["license_policy_hash"] == policy["policy_hash"] for row in provenances)
    assert all(
        row["provenance_hash"] == _artifact_hash(row, "provenance_hash") for row in provenances
    )
