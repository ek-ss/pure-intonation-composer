from __future__ import annotations

import json

from tools.cluster_section_seed_plans import DEFAULT_PROFILE, cluster, features, run
from app.songprogram.composition_generation import generate_composition_plan
from app.songprogram.search import canonical_bytes


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


def test_identical_feature_vectors_do_not_crash_cluster() -> None:
    """Identical feature vectors with k > 1 must not crash the medoid.

    Centers with identical feature vectors shadow each other (every row,
    including a center's own, ties to the smaller-seed center); the dedup
    keeps only the smallest-seed center per feature identity, so the result
    carries fewer than ``count`` clusters, every remaining center owns its
    own row, and no cluster has empty membership.
    """
    profile = json.loads(DEFAULT_PROFILE.read_text())
    feature = features(generate_composition_plan(profile, 7))
    rows = [{"seed": seed, "features": dict(feature)} for seed in (7, 8, 9)]
    groups = cluster(rows, 2)
    assert len(groups) == 1
    assert groups[0]["representative_seed"] == 7
    assert groups[0]["member_seeds"] == [7, 8, 9]
    assert all(group["member_count"] > 0 for group in groups)
    assert all(group["mean_distance_milli"] == 0 for group in groups)


def test_cluster_dedups_identical_centers_and_keeps_distinct() -> None:
    """Duplicates collapse to one center; distinct features keep their own."""
    profile = json.loads(DEFAULT_PROFILE.read_text())
    feature_a = features(generate_composition_plan(profile, 7))
    feature_b = features(generate_composition_plan(profile, 8))
    assert canonical_bytes(feature_a) != canonical_bytes(feature_b)
    rows = [
        {"seed": 7, "features": dict(feature_a)},
        {"seed": 8, "features": dict(feature_b)},
        {"seed": 9, "features": dict(feature_a)},
        {"seed": 10, "features": dict(feature_b)},
    ]
    groups = cluster(rows, 3)
    assert len(groups) == 2
    assert sorted(seed for group in groups for seed in group["member_seeds"]) == [7, 8, 9, 10]
    assert all(group["member_count"] > 0 for group in groups)


def test_zero_distance_nonidentical_features_no_empty_groups() -> None:
    """Zero-distance nonidentical features (a pseudo-metric) must not yield empty groups.

    The dedup only collapses *identical* feature vectors; two distinct vectors
    that a custom metric scores at distance 0 both survive it.  The assignment
    therefore gives each center its own point on a distance tie, so every
    center owns its row and no cluster has empty membership.
    """
    feature_a = {"opening": [1], "closure": [1], "form": ["a"]}
    feature_b = {"opening": [2], "closure": [2], "form": ["b"]}
    assert canonical_bytes(feature_a) != canonical_bytes(feature_b)  # distinct

    def zero_metric(left: dict, right: dict) -> float:
        return 0.0  # a pseudo-metric: every pair is distance 0

    rows = [
        {"seed": 1, "features": feature_a},
        {"seed": 2, "features": feature_b},
        {"seed": 3, "features": feature_a},
    ]
    groups = cluster(rows, 2, metric=zero_metric)
    assert all(group["member_count"] > 0 for group in groups)
    assert sorted(seed for group in groups for seed in group["member_seeds"]) == [1, 2, 3]
