"""Independent integer/hash oracle for GEN0-D search artifact fixtures."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import unicodedata
from typing import Any


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def manifest_digest(domain: str, value: object) -> str:
    return sha(domain.encode() + b"\0" + canonical_bytes(value))


def stream_key(root_seed: int, cohort_index: int, path: list[str]) -> bytes:
    encoded = b""
    for segment in path:
        raw = unicodedata.normalize("NFC", segment).encode()
        encoded += struct.pack(">I", len(raw)) + raw
    return hashlib.sha256(b"cps.broad-prior/stream/v1\0" + struct.pack(">QQ", root_seed, cohort_index) + encoded).digest()


def draw(key: bytes, counter: int) -> int:
    return struct.unpack(">Q", hashlib.sha256(key + struct.pack(">Q", counter)).digest()[:8])[0]


def choose(table: list[dict[str, Any]], value: int) -> tuple[int, Any]:
    total = sum(int(item["weight"]) for item in table)
    point = value % total
    cumulative = 0
    for index, item in enumerate(table):
        cumulative += int(item["weight"])
        if point < cumulative:
            return index, item["value"]
    raise AssertionError("positive checked table must select")


def action_id(run_hash: str, round_index: int, phase: int, candidate: int) -> str:
    raw_hash = bytes.fromhex(run_hash.removeprefix("sha256:"))
    payload = b"cps.search-action/v1\0" + raw_hash + struct.pack(">QIQ", round_index, phase, candidate)
    encoded = base64.b32encode(hashlib.sha256(payload).digest()).decode().lower().rstrip("=")
    return "act_" + encoded[:26]


def seal_record(record: dict[str, Any]) -> dict[str, Any]:
    core = dict(record)
    core.pop("record_hash", None)
    result = dict(core)
    result["record_hash"] = manifest_digest("cps.search-run-record/v1", core)
    return result
