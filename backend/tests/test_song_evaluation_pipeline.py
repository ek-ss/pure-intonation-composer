from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.songprogram.composition_viability import extract_composition_viability
from app.songprogram.mutation import program_hash
from app.songprogram.perceptual import project_hash
from app.songprogram.search import canonical_bytes
from tests.test_composition_viability import _inputs
from tools.prepare_song_evaluation import _seal, _sha, prepare
from tools.summarize_song_g2 import summarize


def _write(path: Path, value: dict) -> None:
    path.write_bytes(canonical_bytes(value))


def _cohorts(repository: Path) -> dict[str, Path]:
    result = {}
    for label in ("first", "second"):
        root = repository / "local_authority" / label
        result[label] = root
        for seed in (0, 1):
            directory = root / f"seed-{seed:04d}"
            directory.mkdir(parents=True, exist_ok=True)
            program, project = _inputs()
            program["schema_version"] = "0.2.0"
            project["compiler"] = {"build_id": "fixture"}
            project["project_id"] = f"{label}-{seed}"
            g1 = extract_composition_viability(program, project)
            validity = {"assessment_hash": "sha256:" + "1" * 64,
                        "archive_eligible": True, "failure_codes": []}
            audio = directory / "reference.wav"
            audio.write_bytes(b"RIFF" + bytes([seed]))
            _write(directory / "program.json", program)
            _write(directory / "project.json", project)
            _write(directory / "g1_features.json", g1)
            _write(directory / "song_validity.json", validity)
            _write(directory / "receipt.json", {
                "seed": seed, "program_hash": program_hash(program),
                "project_hash": project_hash(project), "wav_hash": _sha(audio),
                "g1_feature_report_hash": g1["report_hash"],
                "song_validity_hash": validity["assessment_hash"],
                "archive_eligible": True,
            })
    return result


def test_prepares_blind_audio_and_aggregates_g2_by_candidate(tmp_path: Path) -> None:
    cohorts = _cohorts(tmp_path)
    output = tmp_path / "local_authority" / "evaluation"
    first = prepare(cohorts, output, seeds=2, repository=tmp_path)
    assert first == prepare(cohorts, output, seeds=2, repository=tmp_path)
    assert first["candidates"] == 4
    split = json.loads((output / "private_lineage_split.json").read_text())
    assert {row["partition"] for row in split["assignments"]} == {"calibration", "holdout"}
    for seed in (0, 1):
        assert len({row["partition"] for row in split["assignments"]
                    if row["lineage_id"] == f"generated-seed-{seed:04d}"}) == 1
    for partition in ("calibration", "holdout"):
        assignment = json.loads((output / f"blind_{partition}.json").read_text())
        assert len(assignment["assignments"]) == 2
        assert all(row["audio_path"].startswith("local_authority/evaluation/audio/")
                   for row in assignment["assignments"])
        assert all((tmp_path / row["audio_path"]).is_file() for row in assignment["assignments"])
        for listener in range(3):
            responses = [{
                "blind_id": row["blind_id"], "technical_failure": False,
                "answers": {question: "yes" for question in assignment["questions"]},
            } for row in assignment["assignments"]]
            if listener == 0:
                responses[0]["technical_failure"] = True
                responses[0]["answers"] = None
            submission = _seal({
                "schema": "cps.composition-blind-response", "partition": partition,
                "assignment_hash": assignment["assignment_hash"],
                "listener_id": f"listener_{listener}", "responses": responses,
            }, "cps.composition-blind-response/v1", "response_hash")
            destination = output / "responses" / partition
            destination.mkdir(parents=True, exist_ok=True)
            _write(destination / f"listener_{listener}.json", submission)
    result = summarize(output)
    assert result["listeners_by_partition"] == {"calibration": 3, "holdout": 3}
    assert sorted(row["valid_listeners"] for row in result["rows"]) == [2, 2, 3, 3]
    assert sum(row["technical_failures"] for row in result["rows"]) == 2
    assert sum(row["at_least_three_listeners"] for row in result["rows"]) == 2


def test_rejects_incomplete_input_and_assignment_changes(tmp_path: Path) -> None:
    cohorts = _cohorts(tmp_path)
    output = tmp_path / "local_authority" / "evaluation"
    (cohorts["second"] / "seed-0001" / "receipt.json").unlink()
    with pytest.raises(ValueError, match="incomplete cohort"):
        prepare(cohorts, output, seeds=2, repository=tmp_path)
    assert not output.exists()
    cohorts = _cohorts(tmp_path)
    prepare(cohorts, output, seeds=2, repository=tmp_path)
    with pytest.raises(ValueError, match="existing blind assignment differs"):
        prepare(cohorts, output, seeds=2, assignment_seed=7, repository=tmp_path)


def test_rejects_changed_audio_and_tampered_g2_response(tmp_path: Path) -> None:
    cohorts = _cohorts(tmp_path)
    output = tmp_path / "local_authority" / "evaluation"
    prepare(cohorts, output, seeds=2, repository=tmp_path)
    assignment = json.loads((output / "blind_calibration.json").read_text())
    response = _seal({
        "schema": "cps.composition-blind-response", "partition": "calibration",
        "assignment_hash": assignment["assignment_hash"], "listener_id": "one",
        "responses": [{"blind_id": item["blind_id"], "technical_failure": False,
                       "answers": {question: "yes" for question in assignment["questions"]}}
                      for item in assignment["assignments"]],
    }, "cps.composition-blind-response/v1", "response_hash")
    response["responses"][0]["answers"][assignment["questions"][0]] = "no"
    directory = output / "responses" / "calibration"
    directory.mkdir(parents=True)
    _write(directory / "one.json", response)
    with pytest.raises(ValueError, match="invalid G2 response"):
        summarize(output)
    (directory / "one.json").unlink()
    (cohorts["first"] / "seed-0000" / "reference.wav").write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact binding mismatch"):
        prepare(cohorts, output, seeds=2, repository=tmp_path)
