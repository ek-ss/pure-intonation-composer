"""Validate and atomically install a stored-response synthetic PIL bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from songprogram_conformance.pil_synthetic_bundle import replay_bundle  # noqa: E402

SCHEMAS = BACKEND / "songprogram_conformance" / "schemas"
SINGLES = (
    "protocol", "cohort", "assignment_set", "judgment_set", "registry",
    "evidence_summary", "decision",
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _load_canonical(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or raw != _canonical(value):
        raise ValueError(f"non-canonical JSON object: {path}")
    return value, raw


def _schema_validator() -> Callable[[str, dict[str, Any]], bool]:
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in SCHEMAS.glob("*.json")]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    validators = {
        Path(schema["$id"]).name: Draft202012Validator(schema, registry=registry)
        for schema in schemas
    }
    return lambda name, value: name in validators and validators[name].is_valid(value)


def _hash_path(root: Path, group: str, value: str) -> Path:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("invalid indexed hash")
    return root / group / f"{value[7:]}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--expected-bindings", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        index, index_raw = _load_canonical(args.bundle / "index.json")
        values: dict[str, dict[str, Any]] = {}
        raw: dict[str, bytes] = {"index": index_raw}
        for name in SINGLES:
            values[name], raw[name] = _load_canonical(args.bundle / f"{name}.json")
        agents_with_raw = [
            _load_canonical(_hash_path(args.bundle, "agents", digest))
            for digest in index["agent_manifest_hashes"]
        ]
        responses_with_raw = [
            _load_canonical(_hash_path(args.bundle, "responses", digest))
            for digest in index["response_record_hashes"]
        ]
        agents = [value for value, _ in agents_with_raw]
        responses = [value for value, _ in responses_with_raw]
        expected_bindings, _ = _load_canonical(args.expected_bindings)
        bundle_hash = replay_bundle(
            index=index, agents=agents, responses=responses,
            expected_bindings=expected_bindings, schema_validator=_schema_validator(), **values
        )
        receipt = {"bundle_hash": bundle_hash, "decision_hash": values["decision"]["decision_hash"]}
        receipt_bytes = _canonical(receipt)
        if not args.dry_run:
            target = args.store / "synthetic-audit" / "sha256" / bundle_hash[7:9] / bundle_hash[9:]
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if (target / "receipt.json").read_bytes() != receipt_bytes:
                    raise ValueError("synthetic bundle hash collision")
            else:
                temporary = Path(tempfile.mkdtemp(prefix=".pil-synthetic-", dir=target.parent))
                try:
                    for name, payload in raw.items():
                        (temporary / f"{name}.json").write_bytes(payload)
                    for group, rows in (("agents", agents_with_raw), ("responses", responses_with_raw)):
                        directory = temporary / group
                        directory.mkdir()
                        member = "manifest_hash" if group == "agents" else "record_hash"
                        for value, payload in rows:
                            (directory / f"{value[member][7:]}.json").write_bytes(payload)
                    (temporary / "trusted_expected_bindings.json").write_bytes(
                        _canonical(expected_bindings)
                    )
                    (temporary / "receipt.json").write_bytes(receipt_bytes)
                    os.replace(temporary, target)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
        sys.stdout.buffer.write(receipt_bytes + b"\n")
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
