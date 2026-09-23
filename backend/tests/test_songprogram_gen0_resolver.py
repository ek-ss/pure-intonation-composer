"""GEN0 production resolver differential tests.

The expected calculation deliberately comes from the independent conformance
oracle, never from production code.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from app.songprogram.resolver import _mc, resolve_joint_bnb
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


def test_millicent_conversion_reuses_exact_ratio_result() -> None:
    _mc.cache_clear()
    assert _mc(Fraction(3, 2)) == _mc(Fraction(3, 2))
    info = _mc.cache_info()
    assert info.misses == 1
    assert info.hits == 1


def test_joint_bnb_matches_oracle_for_exact_ratio_collection() -> None:
    query = {
        "schema": "cps.sp0-oracle-query/v1",
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "domain": {
            "equave": "2/1",
            "generators": ["3/1", "5/1", "7/1"],
            "coordinate_bounds": [[-1, 1], [-1, 1], [-1, 1]],
            "register_bounds": [-2, 2],
            "maximum_odd_limit": 63,
            "maximum_reduced_complexity_bits": 12,
        },
        "intent": {
            "reference_equave": "2/1",
            "bass_policy": "preserve_target",
            "bass_target_ordinal": 0,
            "minimum_spacing_millicents": 50000,
            "maximum_span_millicents": 2400000,
            "maximum_pair_error_millicents": 60000,
            "maximum_pair_rms_millicents": 40000,
            "complexity_budget": 24,
        },
        "anchor": {"vector": [0, 0, 0], "equave_exponent": 0},
    }
    query["intent"]["ratios"] = ["1/1", "5/4", "3/2"]
    assert resolve_joint_bnb(query, 1) == [resolve_exact(query)]
