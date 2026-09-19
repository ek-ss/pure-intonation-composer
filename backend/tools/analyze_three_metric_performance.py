"""Summarize Native JI and PIL metrics, excluding mock genre and cliche values."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402


METRICS = (
    (1, "native_ji.coherence"),
    (2, "pil_genre.typicality_q"),
    (3, "pil_genre.idiomaticity_q"),
)


def _preview_viable(row: dict) -> bool:
    checks = row["song_validity"]["hard_checks"]
    return all(
        checks[key]
        for key in (
            "every_section_realized",
            "minimum_three_core_sounding_roles",
            "symbolic_coverage_at_least_8500_bp",
            "no_fully_silent_one_second_window",
            "arrangement_development_passed",
            "polyphony_within_track_limits",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    source = json.loads(arguments.report.read_text(encoding="utf-8"))
    rows = source["rows"]
    summaries = []
    for index, metric_id in METRICS:
        values = [row["quality"][index] for row in rows]
        ranking = sorted(
            ({"seed": row["seed"], "value_q": row["quality"][index]} for row in rows),
            key=lambda item: (-item["value_q"], item["seed"]),
        )
        summaries.append(
            {
                "metric_id": metric_id,
                "minimum_q": min(values),
                "median_q": round(statistics.median(values)),
                "maximum_q": max(values),
                "mean_q": round(statistics.mean(values)),
                "population_standard_deviation_q": round(statistics.pstdev(values)),
                "range_q": max(values) - min(values),
                "distinct_value_count": len(set(values)),
                "ranking": ranking,
            }
        )
    failed_checks: dict[str, int] = {}
    for row in rows:
        for check, passed in row["song_validity"]["hard_checks"].items():
            if not passed:
                failed_checks[check] = failed_checks.get(check, 0) + 1
    output = {
        "schema": "cps.mock-three-metric-performance-report",
        "schema_version": "1.0.0",
        "non_authoritative": True,
        "source_report_hash": source["report_hash"],
        "excluded_metric_ids": ["genre_similarity_q", "pil_genre.inverse_cliche_q"],
        "seed_count": len(rows),
        "preview_viable_count": sum(
            _preview_viable(row) for row in rows
        ),
        "gen0_song_viable_count": sum(
            row["song_validity"]["archive_eligible"] for row in rows
        ),
        "failed_hard_check_count": dict(sorted(failed_checks.items())),
        "metric_summaries": summaries,
        "performance_conclusion": (
            "distribution_only_no_viable_song_discrimination"
            if not any(row["song_validity"]["archive_eligible"] for row in rows)
            else "viable_song_comparison_available"
        ),
        "report_hash": "",
    }
    body = {key: value for key, value in output.items() if key != "report_hash"}
    prefix = (
        b"cps-artifact-hash/v1\0"
        b"cps.mock-three-metric-performance-report\0"
        b"1.0.0\0"
    )
    output["report_hash"] = "sha256:" + hashlib.sha256(prefix + canonical_bytes(body)).hexdigest()
    arguments.output.write_bytes(canonical_bytes(output))


if __name__ == "__main__":
    main()
