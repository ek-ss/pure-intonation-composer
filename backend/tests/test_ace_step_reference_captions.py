from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


CAPTIONS = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "ace_step_kawaii_future_bass_reference_captions_v1.json"
)


def test_ace_step_reference_caption_cohort_is_closed_and_balanced() -> None:
    value = json.loads(CAPTIONS.read_text())
    assert set(value) == {
        "schema",
        "schema_version",
        "set_id",
        "target_generator",
        "task_type",
        "duration_seconds",
        "time_signature",
        "partition_policy",
        "reference_scope",
        "tracks",
    }
    assert value["schema"] == "cps.ace-step-reference-caption-set"
    assert value["schema_version"] == "1.0.0"
    assert value["reference_scope"] == "synthetic_generator_conditioned"
    assert value["duration_seconds"] == 90
    tracks = value["tracks"]
    assert len(tracks) == 48
    assert Counter(track["partition"] for track in tracks) == {
        "calibration": 24,
        "validation": 12,
        "holdout": 12,
    }
    assert len({track["id"] for track in tracks}) == 48
    assert len({track["seed"] for track in tracks}) == 48
    assert len({track["caption"] for track in tracks}) == 48
    for track in tracks:
        assert set(track) == {"id", "partition", "seed", "bpm", "keyscale", "lyrics", "caption"}
        assert 140 <= track["bpm"] <= 172
        assert track["lyrics"] == "[Instrumental]"
        assert "future bass" in track["caption"].lower()
