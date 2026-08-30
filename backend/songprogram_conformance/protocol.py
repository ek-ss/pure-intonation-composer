from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes


DOMAIN_CACHE_KEY = b"cps.songprogram-cache-key/v1\0"
DOMAIN_RECEIPT = b"cps.charge-receipt/v1\0"
FIXTURE_DIR = Path(__file__).with_name("fixtures")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def receipt_digest(receipt: dict[str, Any]) -> str:
    return "sha256:" + sha256_hex(DOMAIN_RECEIPT + canonical_bytes(receipt))


def cache_key(program: dict[str, Any], manifest: dict[str, Any]) -> str:
    preimage = DOMAIN_CACHE_KEY + canonical_bytes(program) + b"\0" + canonical_bytes(manifest)
    return "sha256:" + sha256_hex(preimage)


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURE_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_receipt(receipt: dict[str, Any]) -> None:
    required = {"schema", "version", "profile_id", "counters", "children"}
    if set(receipt) != required:
        raise ValueError("receipt root fields do not match ChargeReceiptV1 requirements")
    if receipt["schema"] != "cps.charge-receipt" or receipt["version"] != "1.0.0":
        raise ValueError("unsupported receipt identity")
    counters = receipt["counters"]
    if not isinstance(counters, dict) or "total_logical_units" not in counters:
        raise ValueError("receipt counters require total_logical_units")
    leaf_total = 0
    for name, counter in counters.items():
        if set(counter) != {"used", "ceiling"}:
            raise ValueError(f"invalid counter shape: {name}")
        used, ceiling = counter["used"], counter["ceiling"]
        if not isinstance(used, int) or not isinstance(ceiling, int):
            raise ValueError(f"counter values must be integers: {name}")
        if used < 0 or ceiling < 0 or used > ceiling:
            raise ValueError(f"counter outside ceiling: {name}")
        if name != "total_logical_units":
            leaf_total += used
    if counters["total_logical_units"]["used"] != leaf_total:
        raise ValueError("total_logical_units must equal the leaf counter sum")


def validate_opcode_fixture(fixture: dict[str, Any]) -> None:
    if fixture["schema"] != "cps.opcode-receipt-fixture" or fixture["version"] != "1.0.0":
        raise ValueError("unsupported opcode fixture")
    receipt = fixture["receipt"]
    validate_receipt(receipt)
    observed: dict[str, int] = {}
    for ordinal, opcode in enumerate(fixture["opcodes"]):
        if opcode["ordinal"] != ordinal:
            raise ValueError("opcode ordinals must be gapless")
        charge = opcode["charge"]
        if not isinstance(charge, int) or charge < 0:
            raise ValueError("opcode charge must be a non-negative integer")
        counter = opcode["counter"]
        observed[counter] = observed.get(counter, 0) + charge
    for name, count in observed.items():
        if receipt["counters"][name]["used"] != count:
            raise ValueError(f"opcode/receipt mismatch: {name}")


def make_cache_entry(fixture: dict[str, Any]) -> dict[str, Any]:
    receipt = deepcopy(fixture["receipt"])
    return {
        "schema": "cps.compile-cache-entry",
        "version": "1.0.0",
        "key": cache_key(fixture["program"], fixture["compiler_manifest"]),
        "result": deepcopy(fixture["expected_result"]),
        "receipt": receipt,
        "receipt_digest": receipt_digest(receipt),
    }


def run_case(name: str, cache_mode: str) -> dict[str, Any]:
    fixture = load_fixture(name)
    validate_opcode_fixture(fixture)
    entry = make_cache_entry(fixture)
    telemetry = {"cache": cache_mode, "cache_receipt_invalid": False}

    if cache_mode == "cold":
        result = deepcopy(fixture["expected_result"])
        receipt = deepcopy(fixture["receipt"])
    elif cache_mode == "hit":
        if entry["receipt_digest"] != receipt_digest(entry["receipt"]):
            raise AssertionError("fixture produced an invalid cache receipt")
        validate_receipt(entry["receipt"])
        result, receipt = deepcopy(entry["result"]), deepcopy(entry["receipt"])
    elif cache_mode == "corrupt":
        entry["receipt_digest"] = "sha256:" + ("0" * 64)
        telemetry["cache_receipt_invalid"] = True
        # Cache corruption is non-authoritative: mandatory cold recomputation.
        result = deepcopy(fixture["expected_result"])
        receipt = deepcopy(fixture["receipt"])
    else:
        raise ValueError(f"unknown cache mode: {cache_mode}")

    logical = {
        "fixture_id": fixture["fixture_id"],
        "result": result,
        "receipt": receipt,
        "result_digest": "sha256:" + sha256_hex(canonical_bytes(result)),
    }
    return {"logical": logical, "execution_telemetry": telemetry}
