from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.test_song_evaluation_pipeline import _cohorts, _write
from tools import run_composition_g1_exploration as exploration
from tools.run_composition_g1_exploration import OBJECTIVES, explore, frontier


def _row(seed: int, values: tuple[int, ...], eligible: bool = True) -> dict:
    return {"candidate_id": f"candidate-{seed}", "seed": seed,
            "status": "g0_eligible" if eligible else "g0_ineligible",
            "g1_objectives_q": dict(zip(OBJECTIVES, values, strict=True))}


def test_frontier_requires_g0_and_keeps_tradeoffs_without_scalar_score() -> None:
    rows = [_row(0, (4, 4, 4, 4, 4)), _row(1, (5, 4, 4, 4, 4)),
            _row(2, (4, 5, 4, 4, 4)), _row(3, (9, 9, 9, 9, 9), False),
            _row(4, (5, 4, 4, 4, 4))]
    assert frontier(rows) == ["candidate-1", "candidate-2"]


def test_rounds_resume_existing_cohort_and_detect_changed_artifacts(tmp_path) -> None:
    cohorts = _cohorts(tmp_path)
    output = tmp_path / "local_authority" / "exploration"
    first = explore(output, rounds=1, candidates_per_round=1,
                    source_cohort=cohorts["first"], repository=tmp_path)
    assert len(first["rounds"]) == 1
    second = explore(output, rounds=2, candidates_per_round=1,
                     source_cohort=cohorts["first"], repository=tmp_path)
    assert second == explore(output, rounds=2, candidates_per_round=1,
                             source_cohort=cohorts["first"], repository=tmp_path)
    assert second["report_hash"] == json.loads((output / "g1_exploration.json").read_text())["report_hash"]
    assert all(row["g1_feature_report_hash"].startswith("sha256:")
               for round_result in second["rounds"] for row in round_result["candidates"])
    before = (output / "g1_exploration.json").read_bytes()
    with pytest.raises(ValueError, match="different configuration"):
        explore(output, rounds=2, candidates_per_round=1, seed_offset=1,
                source_cohort=cohorts["first"], repository=tmp_path)
    assert (output / "g1_exploration.json").read_bytes() == before
    directory = cohorts["first"] / "seed-0001"
    validity = json.loads((directory / "song_validity.json").read_text())
    receipt = json.loads((directory / "receipt.json").read_text())
    validity["archive_eligible"] = False
    validity["failure_codes"] = ["fixture_failure"]
    receipt["archive_eligible"] = False
    _write(directory / "song_validity.json", validity)
    _write(directory / "receipt.json", receipt)
    with pytest.raises(ValueError, match="existing exploration artifacts differ"):
        explore(output, rounds=2, candidates_per_round=1,
                source_cohort=cohorts["first"], repository=tmp_path)
    assert (output / "g1_exploration.json").read_bytes() == before


def test_generated_mode_uses_existing_receipts_on_resume(tmp_path, monkeypatch) -> None:
    cohorts = _cohorts(tmp_path)
    output = tmp_path / "local_authority" / "generated_exploration"
    calls = []

    def generate(seed, destination, profile, manifest, piano_style, realization_profile):
        calls.append(seed)
        directory = tmp_path / "local_authority" / "generated_exploration" / "candidates" / f"seed-{seed:04d}"
        if not (directory / "receipt.json").exists():
            shutil.copytree(cohorts["first"] / f"seed-{seed:04d}", directory)
            receipt = json.loads((directory / "receipt.json").read_text())
            receipt["profile_hash"] = json.loads(Path(profile).read_text())["profile_hash"]
            receipt["realization_profile_hash"] = json.loads(Path(realization_profile).read_text())["profile_hash"]
            receipt["piano_style"] = piano_style
            _write(directory / "receipt.json", receipt)
        return {"status": "success"}

    monkeypatch.setattr(exploration, "_generate", generate)
    explore(output, rounds=1, candidates_per_round=1, repository=tmp_path)
    explore(output, rounds=2, candidates_per_round=1, repository=tmp_path)
    assert calls == [0, 0, 1]
    assert json.loads((output / "g1_exploration.json").read_text())["rounds"][1]["index"] == 1
