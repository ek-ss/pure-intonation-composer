from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.songprogram.composition_generation import generate_composition_plan
from tools.build_g1_experiment_profiles import DESTINATION, SOURCE, build_profiles


def test_experiment_profiles_are_frozen_valid_and_change_same_seed_plans() -> None:
    base = json.loads(SOURCE.read_text(encoding="utf-8"))
    variants = build_profiles(base)
    assert set(variants) == {"contrast_arc", "motif_recall", "rhythm_dialogue"}
    plans = {"baseline": [generate_composition_plan(base, seed) for seed in range(8)]}
    for name, profile in variants.items():
        assert json.loads((DESTINATION / f"{name}.json").read_text(encoding="utf-8")) == profile
        plans[name] = [generate_composition_plan(profile, seed) for seed in range(8)]
        assert all(plan["profile_hash"] == profile["profile_hash"] for plan in plans[name])
        assert any(left["sections"] != right["sections"] or left["motif_plan"] != right["motif_plan"]
                   or left["part_coordination"] != right["part_coordination"]
                   for left, right in zip(plans["baseline"], plans[name], strict=True))
    assert len({rows[0]["plan_hash"] for rows in plans.values()}) == 4


def test_shell_dry_run_covers_four_isolated_profile_runs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "backend/tools/run_g1_profile_experiments.sh"
    completed = subprocess.run(
        ["bash", str(script), "--dry-run"], cwd=tmp_path, capture_output=True, text=True,
        check=True,
    )
    for name in ("baseline", "contrast_arc", "motif_recall", "rhythm_dialogue"):
        line = next(line for line in completed.stdout.splitlines()
                    if line.startswith(f"{name}: ") and " --output " in line)
        assert f"--output {root}/local_authority/g1_profile_experiments_v1/{name}" in line
        assert "--seed-offset 0 --rounds 1 --candidates-per-round 2 --piano-style none" in line
