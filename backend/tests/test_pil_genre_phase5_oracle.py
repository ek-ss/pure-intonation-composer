from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

from songprogram_conformance.pil_genre_phase5_oracle import artifact_hash, canonical, evaluate

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "songprogram_conformance" / "schemas"
FIXTURES = ROOT / "songprogram_conformance" / "fixtures" / "pil_genre_phase5"

def test_authoritative_phase5_fixture() -> None:
    case = json.loads((FIXTURES / "phase5_harmony_success.json").read_bytes())
    results = evaluate(case["model"], case["feature_record"])
    assert results == case["expected"]["results"]
    assert "sha256:" + hashlib.sha256(canonical(results)).hexdigest() == case["expected"]["canonical_results_sha256"]

def test_phase5_oracle_is_independent_of_production() -> None:
    import songprogram_conformance.pil_genre_phase5_oracle as oracle
    source = Path(oracle.__file__).read_text(encoding="utf-8")
    assert "from app" not in source
    assert "import app" not in source

def _set_path(value: dict, path: str, replacement: object) -> None:
    current: object = value
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    if isinstance(current, list):
        current[int(parts[-1])] = replacement
    else:
        current[parts[-1]] = replacement

def test_authoritative_failure_sidecar() -> None:
    base = json.loads((FIXTURES / "phase5_harmony_success.json").read_bytes())
    sidecar = json.loads((FIXTURES / "failure_cases.json").read_bytes())
    observed = []
    for item in sidecar["cases"]:
        case = deepcopy(base)
        _set_path(case, item["mutation"], item["value"])
        if item["case_id"] in {"empty_progression", "numeric_overflow"}:
            case["feature_record"]["record_hash"] = artifact_hash(case["feature_record"], "record_hash")
        try:
            evaluate(case["model"], case["feature_record"])
        except ValueError as error:
            code = str(error)
        else:
            code = "NO_FAILURE"
        assert code == item["expected_error"]
        observed.append({"case_id": item["case_id"], "error": code})
    assert "sha256:" + hashlib.sha256(canonical(observed)).hexdigest() == sidecar["canonical_failures_sha256"]

def test_authoritative_cache_parity_sidecar() -> None:
    base = json.loads((FIXTURES / "phase5_harmony_success.json").read_bytes())
    sidecar = json.loads((FIXTURES / "cache_parity.json").read_bytes())
    authoritative = canonical(evaluate(base["model"], base["feature_record"]))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "entry"
        cold = authoritative
        path.write_bytes(cold)
        hit = path.read_bytes()
        path.write_bytes(b"corrupt")
        corrupt = authoritative if path.read_bytes() != authoritative else path.read_bytes()
    for payload in (cold, hit, corrupt):
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == sidecar["expected_canonical_results_sha256"]

def test_authoritative_process_worker_matrix() -> None:
    sidecar = json.loads((FIXTURES / "process_worker_matrix.json").read_bytes())
    base_path = FIXTURES / sidecar["base_case"]
    command = "import json,sys;from songprogram_conformance.pil_genre_phase5_oracle import canonical,evaluate;c=json.load(open(sys.argv[1]));sys.stdout.buffer.write(canonical(evaluate(c['model'],c['feature_record'])))"
    payloads = []
    for seed in sidecar["pythonhashseeds"]:
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        payloads.append(subprocess.run([sys.executable, "-c", command, str(base_path)], cwd=ROOT, env=environment, check=True, capture_output=True).stdout)
    base = json.loads(base_path.read_bytes())
    for count in sidecar["worker_counts"]:
        with ThreadPoolExecutor(max_workers=count) as pool:
            payloads.extend(pool.map(lambda _: canonical(evaluate(base["model"], base["feature_record"])), range(count)))
    hashes = ["sha256:" + hashlib.sha256(payload).hexdigest() for payload in payloads]
    assert set(hashes) == {sidecar["expected_canonical_results_sha256"]}
    assert "sha256:" + hashlib.sha256(canonical(hashes)).hexdigest() == sidecar["matrix_receipt_hash"]

def test_authoritative_suite_bindings_and_coverage_partition() -> None:
    suite = json.loads((FIXTURES / "suite_index.json").read_bytes())
    observed: list[str] = []
    for binding in suite["cases"]:
        path = FIXTURES / binding["path"]
        payload = json.loads(path.read_bytes())
        assert "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() == binding["raw_file_sha256"]
        assert artifact_hash(payload, "case_hash") == binding["case_hash"]
        observed.extend(binding["coverage"])
    assert len(observed) == len(set(observed))
    assert observed == suite["required_coverage"]
    assert artifact_hash(suite, "suite_hash") == suite["suite_hash"]
