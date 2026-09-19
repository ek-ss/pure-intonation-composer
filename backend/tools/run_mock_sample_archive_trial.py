"""Evaluate a generated seed cohort with failed-calibration mock authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.evaluation_harness import _artifact_hash, evaluate_parallel_mock  # noqa: E402
from app.songprogram.perceptual import manifest_hash  # noqa: E402
from app.songprogram.perceptual_genre import genre_model_hash  # noqa: E402
from app.songprogram.song_validity import assess_completed_song  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _authority(local_authority: Path) -> dict:
    case = _load(
        BACKEND
        / "songprogram_conformance/fixtures/pil_oracle/pil_nonfunctional_two_reports.json"
    )
    phase5 = _load(
        BACKEND
        / "songprogram_conformance/fixtures/pil_genre_phase5/phase5_harmony_success.json"
    )
    model = phase5["model"]
    model["vocabulary_hash"] = case["vocabulary"]["vocabulary_hash"]
    model["trajectory_template_set_hash"] = case["trajectory_template_set"][
        "template_set_hash"
    ]
    model["entries"] = model["entries"][:1]
    model["entries"][0]["genre_id"] = "mock.kawaii_future_bass"
    model["entries"][0]["ordinal"] = 0
    model["model_hash"] = genre_model_hash(model)
    pil_manifest = case["manifest"]
    pil_manifest["genre_model_hash"] = model["model_hash"]
    pil_manifest["manifest_hash"] = manifest_hash(pil_manifest)

    positive = local_authority / "kawaii_future_bass_synthetic_v1"
    reference_dir = positive / "authority/reference_set"
    reference_set = _load(reference_dir / "genre_reference_set_manifest.json")
    records = [
        _load(reference_dir / f"{member['reference_id']}.feature.json")
        for member in reference_set["members"]
    ]
    discrimination = _load(
        local_authority
        / "kawaii_future_bass_negative_synthetic_v1/generated/discrimination_report.json"
    )
    similarity = {
        "schema": "cps.genre-similarity-spec",
        "schema_version": "1.0.0",
        "algorithm": "normalized-l1-q31/v1",
        "reference_partition": "calibration",
        "aggregation": "lower-median-reference-score/v1",
        "output_min": 0,
        "output_max": 10000,
        "feature_record_schema_hash": "sha256:" + "12" * 32,
        "spec_hash": "",
    }
    similarity["spec_hash"] = _artifact_hash(similarity, "spec_hash")
    calibration = {
        "schema": "cps.calibration-decision",
        "schema_version": "1.1.0",
        "status": "rejected",
        "reference_set_manifest_hash": reference_set["manifest_hash"],
        "feature_extractor_manifest_hash": reference_set["feature_extractor_manifest_hash"],
        "renderer_manifest_hash": "sha256:" + "13" * 32,
        "listener_cohort_manifest_hash": discrimination["report_hash"],
        "calibration_fixture_set_hash": discrimination["report_hash"],
        "acceptance_policy_hash": "sha256:" + "14" * 32,
        "evidence_summary_hash": discrimination["report_hash"],
        "promoted_metrics": [],
        "metric_ids": [],
        "failure_code": "CALIBRATION_THRESHOLD_NOT_MET",
        "decision_hash": "",
    }
    calibration["decision_hash"] = _artifact_hash(calibration, "decision_hash")
    intent = {
        "schema": "cps.genre-intent",
        "schema_version": "1.0.0",
        "intent_id": "mock.kawaii_future_bass",
        "display_label": "Kawaii Future Bass mock plumbing",
        "requested_tags": ["kawaii future bass"],
        "metrics": [{"id": "genre_similarity", "evaluation_metric_id": "genre_similarity", "kind": "genre_similarity_q", "usage": "acceptance", "missing_policy": "ineligible"}],
        "reference_set_manifest_hash": reference_set["manifest_hash"],
        "feature_extractor_manifest_hash": reference_set["feature_extractor_manifest_hash"],
        "genre_similarity_spec_hash": similarity["spec_hash"],
        "calibration_decision_hash": calibration["decision_hash"],
        "intent_hash": "",
    }
    intent["intent_hash"] = _artifact_hash(intent, "intent_hash")
    authority = {
        "schema": "cps.mock-parallel-evaluation-authority", "schema_version": "1.0.0",
        "native_ji_manifest": _load(BACKEND / "songprogram_conformance/fixtures/native_ji/pil_nonfunctional_manifest.json"),
        "pil_manifest": pil_manifest, "segmentation_policy": case["segmentation_policy"],
        "feature_spec": case["feature_spec"], "chord_vocabulary": case["vocabulary"],
        "voice_matching_policy": case["voice_matching_policy"],
        "trajectory_template_set": case["trajectory_template_set"], "genre_model": model,
        "genre_intent": intent, "genre_reference_set_manifest": reference_set,
        "genre_similarity_spec": similarity, "calibration_decision": calibration,
        "genre_reference_feature_records": records,
        "mock_policy": {"purpose": "whole_loop_plumbing_only", "genre_similarity_authoritative": False, "production_decisions_allowed": False, "archive_behavior": "allow_mock_ranking", "feature_extractor_upgrade_status": "deferred"},
        "genre_discrimination_report": discrimination, "authority_hash": "",
    }
    authority["authority_hash"] = _artifact_hash(authority, "authority_hash")
    return authority


def _song_validity(program: dict, project: dict, cohort_row: dict) -> dict:
    result = assess_completed_song(
        program,
        project,
        symbolic_coverage=cohort_row["symbolic_coverage"],
        arrangement=cohort_row["arrangement"],
        pcm_continuity=cohort_row["pcm_continuity"],
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--local-authority", type=Path, default=ROOT / "local_authority")
    arguments = parser.parse_args()
    authority = _authority(arguments.local_authority)
    cohort_report = _load(arguments.cohort / "cohort_report.json")
    cohort_rows = {row["seed"]: row for row in cohort_report["rows"]}
    (arguments.cohort / "mock_evaluation_authority.json").write_bytes(canonical_lf(authority))
    rows = []
    for directory in sorted(arguments.cohort.glob("seed-*")):
        seed = int(directory.name.removeprefix("seed-"))
        try:
            program = _load(directory / "program.json")
            project = _load(directory / "project.json")
            report = evaluate_parallel_mock(
                project, authority,
                _load(directory / "candidate_genre_feature.json"),
                cache_dir=str(arguments.cohort / "evaluation-cache"),
            )
            (directory / "mock_evaluation_report.json").write_bytes(canonical_lf(report))
            validity = _song_validity(program, project, cohort_rows[seed])
            (directory / "mock_song_validity.json").write_bytes(canonical_lf(validity))
            rows.append({"seed": seed, "status": "preview_archived", "song_validity": validity, "quality": report["quality"], "evaluation_report_hash": report["report_hash"]})
        except Exception as error:
            rows.append({"seed": seed, "status": "evaluation_failed", "error": getattr(error, "code", type(error).__name__)})
    admitted = sorted((row for row in rows if row["status"] == "preview_archived"), key=lambda row: (row["quality"], -row["seed"]), reverse=True)
    gen0_admitted = [row for row in admitted if row["song_validity"]["archive_eligible"]]
    output = {"schema": "cps.mock-sample-archive-trial-report", "schema_version": "1.0.0", "non_authoritative": True, "production_decisions_allowed": False, "authority_hash": authority["authority_hash"], "quality_metric_ids": ["genre_similarity_q", "native_ji.coherence", "pil_genre.typicality_q", "pil_genre.idiomaticity_q", "pil_genre.inverse_cliche_q"], "seed_count": len(rows), "archive_scope": "preview_only", "archive_count": len(admitted), "preview_archive_count": len(admitted), "gen0_song_archive_count": len(gen0_admitted), "archive": admitted, "gen0_song_archive": gen0_admitted, "rows": rows, "report_hash": ""}
    output["report_hash"] = _artifact_hash(output, "report_hash")
    (arguments.cohort / "mock_sample_archive_report.json").write_bytes(canonical_lf(output))
    sys.stdout.buffer.write(canonical_lf(output))


if __name__ == "__main__":
    main()
