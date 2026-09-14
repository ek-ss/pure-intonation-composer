from __future__ import annotations

from pathlib import Path

from .search_loop13_genre_evaluation_builder import (
    build_genre_evaluation_authority,
    write_genre_evaluation_authority,
)
from .search_loop13_fixture_oracle import artifact_hash


FIXTURE = Path(__file__).with_name("fixtures") / "search_loop_13" / "shared_authority" / "artifacts"


def test_genre_evaluation_chain_is_noncyclic_and_closed() -> None:
    authority = build_genre_evaluation_authority()
    fields = {
        "genre_similarity_spec": "spec_hash",
        "genre_intent": "intent_hash",
        "evaluation_manifest": "manifest_hash",
        "challenger_acceptance_policy": "policy_hash",
    }
    for name, field in fields.items():
        assert authority[name][field] == artifact_hash(authority[name], field)
    intent = authority["genre_intent"]
    evaluation = authority["evaluation_manifest"]
    challenger = authority["challenger_acceptance_policy"]
    assert evaluation["genre_intent_hash"] == intent["intent_hash"]
    assert challenger["genre_intent_hash"] == intent["intent_hash"]
    assert challenger["evaluation_manifest_hash"] == evaluation["manifest_hash"]
    evaluation_ids = {row["id"] for row in evaluation["metrics"]}
    assert [row["id"] for row in challenger["metrics"]] == [
        "genre_similarity",
        "native_ji_quality",
    ]
    assert set(row["id"] for row in challenger["metrics"]) <= evaluation_ids


def test_native_ji_and_perceptual_metrics_are_parallel() -> None:
    metrics = build_genre_evaluation_authority()["genre_intent"]["metrics"]
    assert [(row["id"], row["kind"]) for row in metrics] == [
        ("genre_similarity", "genre_similarity_q"),
        ("native_ji_quality", "symbolic_integer"),
    ]


def test_checked_in_genre_evaluation_authority_matches_builder(tmp_path) -> None:
    write_genre_evaluation_authority(tmp_path)
    expected = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    actual = {path.name: path.read_bytes() for path in FIXTURE.iterdir() if path.name in expected}
    assert actual == expected
