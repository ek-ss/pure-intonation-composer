from __future__ import annotations

import json

from tools.cluster_section_seed_plans import DEFAULT_PROFILE, cluster, features, run
from app.songprogram.composition_generation import generate_composition_plan


def test_plan_clusters_cover_seed_cohort_and_represent_members(tmp_path) -> None:
    profile = json.loads(DEFAULT_PROFILE.read_text())
    rows = [{"seed": seed, "features": features(generate_composition_plan(profile, seed))}
            for seed in range(48)]
    groups = cluster(rows, 6)
    assert len(groups) == 6
    assert sorted(seed for group in groups for seed in group["member_seeds"]) == list(range(48))
    assert all(group["representative_seed"] in group["member_seeds"] for group in groups)
    path = tmp_path / "report.json"
    first = run(DEFAULT_PROFILE, path, seeds=48, clusters=6)
    assert first == run(DEFAULT_PROFILE, path, seeds=48, clusters=6)
    assert first["clusters"] == groups
    assert all(row["plan_hash"].startswith("sha256:") for row in first["rows"])
