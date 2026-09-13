"""PIL Phase 5 (genre/style interpretation) production tests.

The authoritative fixture bytes under ``songprogram_conformance/fixtures`` are
read-only inputs here; no fixture, oracle, or golden is created or modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from app.songprogram import perceptual_genre as pg
from app.songprogram.perceptual import PilError, report_hash, run_perceptual_interpretation

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "songprogram_conformance" / "fixtures" / "pil_genre_phase5"
TEMPLATES = BACKEND.parent / "docs" / "pil_oracle_case_templates"


def _success_case() -> dict:
    return json.loads((FIXTURES / "phase5_harmony_success.json").read_bytes())


def _set_path(value: dict, path: str, replacement: object) -> None:
    current: object = value
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    if isinstance(current, list):
        current[int(parts[-1])] = replacement
    else:
        current[parts[-1]] = replacement


def test_authoritative_success_parity() -> None:
    case = _success_case()
    results = pg.evaluate_genre(case["model"], case["feature_record"])
    assert results == case["expected"]["results"]
    digest = "sha256:" + hashlib.sha256(pg.canonical_results_bytes(results)).hexdigest()
    assert digest == case["expected"]["canonical_results_sha256"]


def test_authoritative_failure_parity() -> None:
    base = _success_case()
    sidecar = json.loads((FIXTURES / "failure_cases.json").read_bytes())
    for item in sidecar["cases"]:
        case = deepcopy(base)
        _set_path(case, item["mutation"], item["value"])
        if item["case_id"] in {"empty_progression", "numeric_overflow"}:
            case["feature_record"]["record_hash"] = pg.genre_feature_record_hash(
                case["feature_record"]
            )
        with pytest.raises(PilError) as caught:
            pg.evaluate_genre(case["model"], case["feature_record"])
        assert caught.value.code == item["expected_error"], item["case_id"]


def test_run_level_cache_cold_hit_corrupt_parity(tmp_path) -> None:
    case = _success_case()
    kwargs = {"cache_dir": tmp_path}
    cold = pg.run_genre_interpretation(case["model"], case["feature_record"], **kwargs)
    hit = pg.run_genre_interpretation(case["model"], case["feature_record"], **kwargs)
    for path in tmp_path.glob("*.json"):
        path.write_bytes(b"corrupt")
    corrupt = pg.run_genre_interpretation(case["model"], case["feature_record"], **kwargs)
    assert pg.canonical_results_bytes(cold) == pg.canonical_results_bytes(hit)
    assert pg.canonical_results_bytes(cold) == pg.canonical_results_bytes(corrupt)
    assert cold == pg.evaluate_genre(case["model"], case["feature_record"])


def test_model_schema_and_binding_failures() -> None:
    case = _success_case()
    model, record = case["model"], case["feature_record"]

    bad = deepcopy(model)
    bad["required_groups"] = ["harmony", "melody"]
    with pytest.raises(PilError) as caught:
        pg.evaluate_genre(bad, record)
    assert caught.value.code == "PIL_GENRE_FAILED"

    bad = deepcopy(model)
    bad["entries"][0]["detail_weights_q"] = [2000, 2000, 2000, 2000, 2001]
    bad["model_hash"] = pg.genre_model_hash(bad)
    with pytest.raises(PilError) as caught:
        pg.evaluate_genre(bad, record)
    assert caught.value.code == "PIL_GENRE_FAILED"

    bad = deepcopy(model)
    bad["model_hash"] = "sha256:" + "00" * 32
    with pytest.raises(PilError) as caught:
        pg.evaluate_genre(bad, record)
    assert caught.value.code == "PIL_GENRE_FAILED"

    manifest = {"genre_model_hash": "sha256:" + "11" * 32}
    with pytest.raises(PilError) as caught:
        pg.run_genre_interpretation(model, record, manifest=manifest)
    assert caught.value.code == "PIL_GENRE_FAILED"


def test_result_sorting_uses_ordinal_then_genre_id() -> None:
    case = _success_case()
    results = pg.evaluate_genre(case["model"], case["feature_record"])
    keys = [(-row["typicality_q"], row["model_ordinal"], row["genre_id"]) for row in results]
    assert keys == sorted(keys)


def test_cross_process_byte_parity() -> None:
    command = (
        "import json,sys;"
        "from app.songprogram.perceptual_genre import canonical_results_bytes,evaluate_genre;"
        "c=json.load(open(sys.argv[1]));"
        "sys.stdout.buffer.write(canonical_results_bytes("
        "evaluate_genre(c['model'],c['feature_record'])))"
    )
    case_path = FIXTURES / "phase5_harmony_success.json"
    payloads = []
    for seed in ("0", "1", "424242"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        payloads.append(
            subprocess.run(
                [sys.executable, "-c", command, str(case_path)],
                cwd=BACKEND,
                env=environment,
                check=True,
                capture_output=True,
            ).stdout
        )
    assert len(set(payloads)) == 1


def _phase4_report_from_template() -> tuple[dict, dict, dict, dict]:
    case = json.loads((TEMPLATES / "pil_12et_ii_v_i.json").read_bytes())
    report = run_perceptual_interpretation(
        case["project"],
        case["manifest"],
        segmentation_policy=case["segmentation_policy"],
        feature_spec=case["feature_spec"],
        chord_vocabulary=case["vocabulary"],
        voice_matching_policy=case["voice_matching_policy"],
        trajectory_template_set=case["trajectory_template_set"],
    )
    assert report["status"] == "success"
    assert report["completed_phase"] == "functional_trajectory"
    return case["project"], report, case["vocabulary"], case["trajectory_template_set"]


def test_feature_extraction_from_phase4_report() -> None:
    project, report, vocabulary, template_set = _phase4_report_from_template()
    record = pg.extract_genre_feature_record(project, report, vocabulary, template_set)
    pg.validate_genre_feature_record(record, phase4_report=report)
    assert record["source_phase4_report_hash"] == report["report_hash"]
    assert record["vocabulary_hash"] == vocabulary["vocabulary_hash"]
    assert record["trajectory_template_set_hash"] == template_set["template_set_hash"]
    for histogram in (
        record["chord_vocabulary_histogram_q31"],
        record["progression_histogram_q31"],
    ):
        assert sum(row["weight_q31"] for row in histogram) == pg.Q31_TOTAL
        ordinals = [row["ordinal"] for row in histogram]
        assert ordinals == sorted(ordinals)
    assert sum(record["harmonic_rhythm_profile_q"]) == 10_000
    # The ii-V-I template case has one vocabulary template and trajectory
    # results only for template ordinal 0.
    assert record["progression_histogram_q31"] == [
        {"ordinal": 0, "weight_q31": pg.Q31_TOTAL}
    ]


def test_extraction_rejects_non_phase4_report() -> None:
    project, report, vocabulary, template_set = _phase4_report_from_template()
    corrupt = deepcopy(report)
    corrupt["status"] = "failure"
    with pytest.raises(PilError) as caught:
        pg.extract_genre_feature_record(project, corrupt, vocabulary, template_set)
    assert caught.value.code == "PIL_GENRE_FAILED"


def test_extraction_rejects_unknown_candidate_id() -> None:
    project, report, vocabulary, template_set = _phase4_report_from_template()
    corrupt = deepcopy(report)
    corrupt["segment_interpretations"][0]["candidates"][0]["id"] = "unknown"
    corrupt["report_hash"] = report_hash(corrupt)
    with pytest.raises(PilError) as caught:
        pg.extract_genre_feature_record(project, corrupt, vocabulary, template_set)
    assert caught.value.code == "PIL_GENRE_FAILED"


def test_extracted_record_scores_against_synthetic_model() -> None:
    project, report, vocabulary, template_set = _phase4_report_from_template()
    record = pg.extract_genre_feature_record(project, report, vocabulary, template_set)
    model = {
        "schema": pg.GENRE_MODEL_SCHEMA,
        "schema_version": pg.GENRE_SCHEMA_VERSION,
        "algorithm": pg.GENRE_MODEL_ALGORITHM,
        "feature_record_schema_hash": pg.GENRE_FEATURE_RECORD_SCHEMA_HASH,
        "vocabulary_hash": vocabulary["vocabulary_hash"],
        "trajectory_template_set_hash": template_set["template_set_hash"],
        "required_groups": ["harmony"],
        "entries": [
            {
                "genre_id": "test.mirror",
                "ordinal": 0,
                "chord_vocabulary_target_q31": record["chord_vocabulary_histogram_q31"],
                "progression_target_q31": record["progression_histogram_q31"],
                "function_target_q": record["function_profile_q"],
                "voice_leading_target_q": record["voice_leading_profile_q"],
                "harmonic_rhythm_target_q": record["harmonic_rhythm_profile_q"],
                "detail_weights_q": [2000, 2000, 2000, 2000, 2000],
                "cliche_template_ordinals": [0],
                "novelty_exemplars_q31": [record["progression_histogram_q31"]],
            }
        ],
    }
    model["model_hash"] = pg.genre_model_hash(model)
    (result,) = pg.evaluate_genre(model, record)
    assert result["typicality_q"] == 10_000
    assert result["novelty_q"] == 0
    assert result["cliche_dependence_q"] == 10_000
    assert result["missing_groups"] == list(pg.MISSING_GROUPS)
