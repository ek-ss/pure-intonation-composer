"""GEN0 production resolver differential tests.

The expected calculation deliberately comes from the independent conformance
oracle, never from production code.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.songprogram.resolver import resolve_joint_bnb
from songprogram_conformance.reference import resolve_exact


GOLDENS = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "goldens"


def test_joint_bnb_matches_independent_oracle_for_checked_in_queries() -> None:
    for name in ("major_query.json", "minor_query.json", "tritave_query.json"):
        query = json.loads((GOLDENS / name).read_text(encoding="utf-8"))
        assert resolve_joint_bnb(query, 1) == [resolve_exact(query)]


def test_joint_bnb_is_invariant_to_physical_placed_domain_order() -> None:
    query = json.loads((GOLDENS / "major_query.json").read_text(encoding="utf-8"))
    original = resolve_joint_bnb(query, 24)
    query["domain"]["coordinate_bounds"] = [list(item) for item in query["domain"]["coordinate_bounds"]]
    assert resolve_joint_bnb(query, 24) == original
