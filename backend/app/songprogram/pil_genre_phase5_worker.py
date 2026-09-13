"""Fresh-process worker for one PIL Phase 5 matrix case.

The worker executes the cache cold, hit and corrupt coordinates inside the
subprocess (contract section 5) and emits the canonical result bytes only
when all three runs agree byte-for-byte.  Any failure exits non-zero so the
parent matrix runner raises ``PIL_GENRE_FAILED``.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from .perceptual_genre import (
    canonical_results_bytes,
    phase5_cache_key,
    run_genre_interpretation,
)


def main() -> None:
    case = json.loads(sys.stdin.buffer.read())
    model = case["model"]
    record = case["feature_record"]
    with tempfile.TemporaryDirectory(prefix="pil-genre-matrix-") as temporary:
        cache_dir = Path(temporary)
        cold = run_genre_interpretation(model, record, cache_dir=cache_dir)
        hit = run_genre_interpretation(model, record, cache_dir=cache_dir)
        key = phase5_cache_key(
            project_hash="",
            phase4_report_hash=record["source_phase4_report_hash"],
            pil_manifest_hash="",
            genre_model_hash_value=model["model_hash"],
            feature_record_hash=record["record_hash"],
        )
        entry = cache_dir / f"{key[len('sha256:'):]}.json"
        entry.write_bytes(b'{"corrupt": true}')
        repaired = run_genre_interpretation(model, record, cache_dir=cache_dir)
    canonical = canonical_results_bytes(cold)
    if (
        canonical_results_bytes(hit) != canonical
        or canonical_results_bytes(repaired) != canonical
    ):
        raise SystemExit(1)
    sys.stdout.buffer.write(canonical)


if __name__ == "__main__":
    main()
