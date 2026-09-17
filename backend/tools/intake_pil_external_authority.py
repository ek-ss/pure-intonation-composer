"""Validate and atomically install an external PIL calibration authority bundle."""

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

from songprogram_conformance.pil_external_authority_validator import (  # noqa: E402
    validate_external_authority,
)

SCHEMAS = BACKEND / "songprogram_conformance" / "schemas"
FILES = (
    "listener_cohort",
    "registry",
    "policy",
    "fixture_set",
    "evidence_summary",
    "decision",
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _load_canonical(path: Path) -> tuple[dict, bytes]:
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


def _identity(name: str, value: dict) -> str:
    members = {
        "listener_cohort": "manifest_hash",
        "registry": "registry_hash",
        "policy": "policy_hash",
        "fixture_set": "fixture_set_hash",
        "evidence_summary": "summary_hash",
        "decision": "decision_hash",
    }
    return value[members[name]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument(
        "--expected-bindings",
        required=True,
        type=Path,
        help="Trusted bindings supplied independently of the untrusted bundle.",
    )
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        values: dict[str, dict] = {}
        raw: dict[str, bytes] = {}
        for name in FILES:
            values[name], raw[name] = _load_canonical(args.bundle / f"{name}.json")
        bindings, _ = _load_canonical(args.expected_bindings)
        decision = validate_external_authority(
            listener_cohort=values["listener_cohort"],
            registry=values["registry"],
            policy=values["policy"],
            fixture_set=values["fixture_set"],
            evidence_summary=values["evidence_summary"],
            decision=values["decision"],
            expected_bindings=bindings,
            schema_validator=_schema_validator(),
        )
        receipt = {
            "decision_hash": decision,
            "artifacts": [
                {"kind": name, "artifact_hash": _identity(name, values[name])} for name in FILES
            ],
        }
        receipt_bytes = _canonical(receipt)
        if not args.dry_run:
            target = args.store / "bundles" / "sha256" / decision[7:9] / decision[9:]
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if (target / "receipt.json").read_bytes() != receipt_bytes:
                    raise ValueError("authority bundle hash collision")
            else:
                temporary = Path(tempfile.mkdtemp(prefix=".pil-authority-", dir=target.parent))
                try:
                    for name in FILES:
                        (temporary / f"{name}.json").write_bytes(raw[name])
                    (temporary / "trusted_expected_bindings.json").write_bytes(
                        _canonical(bindings)
                    )
                    (temporary / "receipt.json").write_bytes(receipt_bytes)
                    os.replace(temporary, target)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
        sys.stdout.buffer.write(receipt_bytes + b"\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
