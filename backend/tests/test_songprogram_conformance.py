from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from songprogram_conformance.protocol import (
    FIXTURE_DIR,
    canonical_bytes,
    load_fixture,
    run_case,
    validate_opcode_fixture,
)


def test_minimal_opcode_receipt_is_self_consistent() -> None:
    validate_opcode_fixture(load_fixture("minimal_direct_note"))


def test_cold_hit_corrupt_cache_have_identical_logical_results() -> None:
    corpus = json.loads((FIXTURE_DIR / "cache_corpus.json").read_text(encoding="utf-8"))
    results = [run_case(case["fixture"], case["cache_mode"]) for case in corpus["cases"]]
    logical = [canonical_bytes(result["logical"]) for result in results]
    assert logical[0] == logical[1] == logical[2]
    observed = [result["execution_telemetry"]["cache_receipt_invalid"] for result in results]
    expected = [case["expected_cache_receipt_invalid"] for case in corpus["cases"]]
    assert observed == expected


def test_cross_process_runner_is_byte_identical_across_hash_seeds() -> None:
    backend = Path(__file__).resolve().parents[1]
    outputs: list[bytes] = []
    matrix = [
        (seed, timezone, locale, decimal_mode)
        for seed in ("0", "4294967295")
        for timezone in ("UTC", "Asia/Tokyo")
        for locale in ("C", "C.UTF-8")
        for decimal_mode in ("default", "low_floor")
    ]
    request = b'{"operation":"run_fixture","case":"minimal_direct_note","cache":"cold"}\n'
    for index in range(100):
        seed, timezone, locale, decimal_mode = matrix[index % len(matrix)]
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        environment["TZ"] = timezone
        environment["LC_ALL"] = locale
        environment["CPS_CALLER_DECIMAL"] = decimal_mode
        completed = subprocess.run(
            [sys.executable, "-m", "songprogram_conformance.runner"],
            cwd=backend,
            env=environment,
            input=request,
            check=True,
            capture_output=True,
        )
        assert completed.stderr == b""
        assert completed.stdout.endswith(b"\n")
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1
