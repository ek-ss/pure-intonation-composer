"""Independent verification entry point for checked-in Mutation fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .mutation_oracle import artifact_hash, canonical_lf, evaluate


def verify(root: Path) -> None:
    raw = (root / "cases.json").read_bytes()
    if not raw.endswith(b"\n") or canonical_lf(json.loads(raw)) != raw:
        raise AssertionError("mutation cases are not canonical LF JSON")
    suite = json.loads(raw)
    seen: set[str] = set()
    for case in suite["cases"]:
        if case["case_id"] in seen:
            raise AssertionError("duplicate mutation case id")
        seen.add(case["case_id"])
        request = case["request"]
        if artifact_hash("cps.mutation-application-request/v1", request) != case["request_hash"]:
            raise AssertionError(f"request hash mismatch: {case['case_id']}")
        actual = evaluate(
            request["base_program"], request["mutations"][0], request["locked_roots"],
            request["mutation_choice_catalog"], request["instrument_catalog"], case["request_hash"],
        )
        if canonical_lf(actual) != canonical_lf(case["expected"]):
            raise AssertionError(f"oracle mismatch: {case['case_id']}")
    manifest = json.loads((root / "manifest.json").read_bytes())
    expected = "sha256:" + hashlib.sha256(raw).hexdigest()
    if manifest["files"] != [{"path": "cases.json", "sha256": expected}]:
        raise AssertionError("mutation fixture manifest mismatch")


if __name__ == "__main__":
    verify(Path(__file__).resolve().parent / "fixtures" / "mutation")
