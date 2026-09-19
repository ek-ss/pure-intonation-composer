from __future__ import annotations

from app.songprogram.composition_calibration import build_blind_assignment, split_lineages


def _candidates() -> list[dict]:
    return [
        {
            "candidate_id": f"candidate_{index}",
            "lineage_id": f"lineage_{index // 2}",
            "cohort": "new" if index % 2 else "old",
            "audio_path": f"audio/{index}.wav",
            "audio_hash": "sha256:" + f"{index:064x}",
            "g1_feature_report_hash": "sha256:" + f"{index + 10:064x}",
        }
        for index in range(12)
    ]


def test_split_is_deterministic_and_keeps_lineages_together() -> None:
    first = split_lineages(_candidates(), calibration_basis_points=5000)
    assert first == split_lineages(reversed(_candidates()), calibration_basis_points=5000)
    by_lineage = {}
    for row in first["assignments"]:
        by_lineage.setdefault(row["lineage_id"], set()).add(row["partition"])
    assert all(len(partitions) == 1 for partitions in by_lineage.values())


def test_blind_assignment_omits_candidate_identity_and_labels() -> None:
    split = split_lineages(_candidates(), calibration_basis_points=5000)
    blind = build_blind_assignment(split, partition="calibration", assignment_seed=42)
    assert blind == build_blind_assignment(split, partition="calibration", assignment_seed=42)
    assert all(set(row) == {"ordinal", "blind_id", "audio_path", "audio_hash"} for row in blind["assignments"])
    assert not any("cohort" in row or "candidate_id" in row for row in blind["assignments"])


def test_split_stratifies_by_lineage_cohort_signature() -> None:
    candidates = _candidates()
    for row in candidates[:8]:
        if row["candidate_id"].endswith("0") or row["candidate_id"].endswith("2"):
            row["cohort"] = "negative"
    split = split_lineages(candidates, calibration_basis_points=5000)
    signatures = {}
    for row in candidates:
        signatures.setdefault(row["lineage_id"], set()).add(row["cohort"])
    partitions = {row["lineage_id"]: row["partition"] for row in split["assignments"]}
    for signature in set(map(tuple, map(sorted, signatures.values()))):
        selected = [
            partitions[lineage]
            for lineage, cohorts in signatures.items()
            if tuple(sorted(cohorts)) == signature
        ]
        if len(selected) > 1:
            assert "calibration" in selected and "holdout" in selected
