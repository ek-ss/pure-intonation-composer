"""Direct resolver and schema tests for the versioned non-crossing query.

The independent legacy oracle (``gen0b_melody_oracle.progression_result``)
implements the historical canonical edge matching and is deliberately not
modified.  These tests verify that:

* the resolver's canonical (1.2/2.0) result still matches the oracle for a
  non-crossing case (where both compute crossing=0),
* the resolver rejects ``crossing_match`` on 1.2/2.0 (the schemas forbid it),
* the resolver accepts ``crossing_match`` only on 2.1 with the non-crossing
  algorithm, and produces a usable non-crossing path for a two-layer crossing
  case that has no canonical path under ``crossing_policy="forbid"``,
* the dedicated 2.1 schema requires ``crossing_match`` const ``non_crossing``
  while the 2.0 schema forbids the field entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.songprogram.resolver import resolve_progression
from songprogram_conformance.gen0b_melody_oracle import progression_result

SCHEMAS = Path(__file__).resolve().parents[1] / "songprogram_conformance" / "schemas"

_SHA = "sha256:" + "0" * 64


def _voice(ratio_mc: int, exact_ratio: str, ordinal: int, vector: list[int]) -> dict:
    return {
        "target_ordinal": ordinal,
        "absolute_vector": vector,
        "equave_exponent": 0,
        "exact_ratio": exact_ratio,
        "ratio_millicents": ratio_mc,
    }


def _resolved_chord() -> dict:
    return {
        "id": "rc_" + "2" * 26,
        "domain_hash": _SHA,
        "intent_hash": _SHA,
        "resolver_build_id": "test",
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "search_completeness": "exact",
        "reference_equave": "2/1",
        "reference_divisions": 12,
        "canonical_steps": [0, 4],
        "eligibility_contract": {
            "kind": "absolute-pair-error",
            "maximum_pair_error_millicents": 120_000,
        },
        "anchor_vector": [0, 0],
        "voice_offsets": [[0, 0], [1, 0]],
        "equave_exponents": [0, 0],
        "exact_ratios": ["2/1", "3/1"],
        "target_voice_ordinals": [0, 1],
        "pair_errors_millicents": [0],
        "maximum_pair_error_millicents": 120_000,
        "pair_rms_error_millicents": 0,
        "complexity_score": 0,
    }


def _core(voices: list[dict], core_hash: str) -> dict:
    return {
        "core_hash": core_hash,
        "resolved_chord": _resolved_chord(),
        "domain_hash": _SHA,
        "intent_hash": _SHA,
        "anchor_vector": [0, 0],
        "voices": voices,
        "local_pair_rms_millicents": 0,
        "local_pair_max_millicents": 0,
        "local_complexity": 0,
    }


def _occurrence(occ_id: str, cores: list[dict]) -> dict:
    return {
        "id": occ_id,
        "start_tick": 0,
        "duration_ticks": 1,
        "track_id": "t",
        "register_millicents": [0, 10_000_000],
        "maximum_polyphony": 8,
        "overlapping_nonprogression_pitched_events": 0,
        "intent_hash": _SHA,
        "root_anchor": [0, 0],
        "candidate_cores": cores,
    }


def _non_crossing_case() -> tuple[dict, dict]:
    """Two layers whose lowest-cost pairing does NOT cross.

    Both the resolver and the oracle compute crossing=0 here (the voices are
    in the same order by ratio_millicents and ordinal), so the canonical
    result is identical in both.
    """
    left = _core(
        [_voice(100, "2/1", 0, [0, 0]), _voice(200, "3/1", 1, [1, 0])],
        "sha256:" + "a" * 64,
    )
    right = _core(
        [_voice(110, "2/1", 0, [0, 0]), _voice(190, "3/1", 1, [1, 0])],
        "sha256:" + "b" * 64,
    )
    return left, right


def _crossing_case() -> tuple[dict, dict]:
    """Two layers whose lowest-cost pairing crosses.

    Layer 0 voices: [100 (2/1), 200 (3/1)]  -> left[0] < left[1].
    Layer 1 voices: [190 (2/1), 110 (3/1)]  -> right[0] > right[1].

    The crossing pairing (0->0, 1->1) keeps both exact ratios (lost=0) and is
    therefore the canonical lowest-cost edge, but it crosses.  The non-crossing
    pairing (0->1, 1->0) swaps the ratios (lost=2) and does not cross.
    """
    left = _core(
        [_voice(100, "2/1", 0, [0, 0]), _voice(200, "3/1", 1, [1, 0])],
        "sha256:" + "a" * 64,
    )
    right = _core(
        [_voice(190, "2/1", 0, [0, 0]), _voice(110, "3/1", 1, [1, 0])],
        "sha256:" + "b" * 64,
    )
    return left, right


def _query(
    schema_version: str,
    algorithm: str,
    *,
    case: tuple[dict, dict] | None = None,
    crossing_match: str | None = None,
    crossing_policy: str = "forbid",
) -> dict:
    if case is None:
        case = _crossing_case()
    left, right = case
    query: dict = {
        "schema": "cps.progression-query",
        "schema_version": schema_version,
        "algorithm": algorithm,
        "numeric_contract": "cps-numeric/decimal-log2-rhe-v1",
        "budget_profile": "gen0-progression-exact-v1",
        "domain_hash": _SHA,
        "domain_equave": "2/1",
        "maximum_voice_motion_millicents": 2_400_000,
        "crossing_policy": crossing_policy,
        "occurrences": [
            _occurrence("a", [left]),
            _occurrence("b", [right]),
        ],
    }
    if crossing_match is not None:
        query["crossing_match"] = crossing_match
    return query


# ---------------------------------------------------------------------------
# Resolver: canonical (1.2/2.0) result matches the independent legacy oracle.
# ---------------------------------------------------------------------------


def test_canonical_2_0_matches_independent_oracle() -> None:
    query = _query(
        "2.0.0", "gen0-progression-exact/v1",
        case=_non_crossing_case(), crossing_policy="allow",
    )
    assert resolve_progression(query) == progression_result(query)


def test_canonical_1_2_matches_independent_oracle() -> None:
    query = _query(
        "1.2.0", "gen0-progression-exact/v1",
        case=_non_crossing_case(), crossing_policy="allow",
    )
    assert resolve_progression(query) == progression_result(query)


# ---------------------------------------------------------------------------
# Resolver: the non-crossing (2.1) path produces a usable edge under forbid.
# ---------------------------------------------------------------------------


def test_non_crossing_2_1_resolves_crossing_case() -> None:
    query = _query(
        "2.1.0", "gen0-progression-noncrossing/v1", crossing_match="non_crossing"
    )
    result = resolve_progression(query)
    # The selected edge must be the non-crossing pairing (0->1, 1->0).
    assert result["selected_core_hashes"] == [
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
    ]
    # The canonical (2.0) result for the same cores picks the crossing pairing,
    # so the non-crossing result must differ from it.  (crossing_policy="allow"
    # so the canonical path succeeds and can be compared.)
    canonical = _query("2.0.0", "gen0-progression-exact/v1", crossing_policy="allow")
    assert resolve_progression(canonical)["edge_matching_keys"] != result[
        "edge_matching_keys"
    ]


def test_canonical_2_0_forbid_has_no_path() -> None:
    # With canonical matching the lowest-cost edge crosses and is dropped by
    # crossing_policy="forbid", so no path survives.
    query = _query("2.0.0", "gen0-progression-exact/v1")
    with pytest.raises(ValueError, match="PROGRESSION_NO_PATH"):
        resolve_progression(query)


# ---------------------------------------------------------------------------
# Resolver: negative field / algorithm / version validation.
# ---------------------------------------------------------------------------


def test_rejects_crossing_match_on_2_0() -> None:
    query = _query(
        "2.0.0", "gen0-progression-exact/v1", crossing_match="non_crossing"
    )
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


def test_rejects_crossing_match_on_1_2() -> None:
    query = _query(
        "1.2.0", "gen0-progression-exact/v1", crossing_match="non_crossing"
    )
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


def test_rejects_old_algorithm_on_2_1() -> None:
    query = _query(
        "2.1.0", "gen0-progression-exact/v1", crossing_match="non_crossing"
    )
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


def test_rejects_missing_crossing_match_on_2_1() -> None:
    query = _query("2.1.0", "gen0-progression-noncrossing/v1")
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


def test_rejects_wrong_crossing_match_value_on_2_1() -> None:
    query = _query(
        "2.1.0", "gen0-progression-noncrossing/v1", crossing_match="canonical"
    )
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


def test_rejects_unknown_schema_version() -> None:
    query = _query("9.9.9", "gen0-progression-exact/v1")
    with pytest.raises(ValueError, match="PROGRESSION_QUERY_CONTEXT_INVALID"):
        resolve_progression(query)


# ---------------------------------------------------------------------------
# Schema: the dedicated 2.1 schema requires crossing_match; 2.0 forbids it.
# ---------------------------------------------------------------------------


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_2_0_schema_forbids_crossing_match() -> None:
    schema = _load_schema("progression_query_2_0.schema.json")
    assert schema["additionalProperties"] is False
    assert "crossing_match" not in schema["properties"]
    assert "crossing_match" not in schema["required"]


def test_2_1_schema_requires_non_crossing() -> None:
    schema = _load_schema("progression_query_2_1.schema.json")
    assert schema["additionalProperties"] is False
    assert schema["properties"]["crossing_match"] == {"const": "non_crossing"}
    assert "crossing_match" in schema["required"]
    assert schema["properties"]["algorithm"] == {
        "const": "gen0-progression-noncrossing/v1"
    }
    assert schema["properties"]["schema_version"] == {"const": "2.1.0"}
    # The 2.1 schema matches the actual compiler contract: the v1 budget
    # profile (what compile_sp0 emits) and polyphony up to 64 (the piano
    # track limit), unlike the 2.0 schema (v2 profile, polyphony <= 8).
    assert schema["properties"]["budget_profile"] == {
        "const": "gen0-progression-exact-v1"
    }
    assert schema["$defs"]["occurrence"]["properties"]["maximum_polyphony"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 64,
    }


# ---------------------------------------------------------------------------
# Full Draft202012 validation of a genuinely compiler-emitted 2.1 query,
# plus negative schema tests on the dedicated 2.1 schema.
# ---------------------------------------------------------------------------


def _validator():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    resources = [
        (schema["$id"], Resource.from_contents(schema))
        for path in SCHEMAS.glob("*.schema.json")
        if (schema := json.loads(path.read_text(encoding="utf-8")))
    ]
    registry = Registry().with_resources(resources)
    return Draft202012Validator(
        _load_schema("progression_query_2_1.schema.json"), registry=registry
    )


def _capture_compiler_query(
    monkeypatch: pytest.MonkeyPatch, equave: str, seed: int
) -> dict:
    """Capture the 2.1 progression query the compiler actually emits."""
    import app.songprogram.compiler as compiler

    captured: list[dict] = []
    original = compiler.resolve_progression

    def _capture(query: dict, diagnostics: dict | None = None) -> dict:
        captured.append(query)
        return original(query, diagnostics) if diagnostics is not None else original(query)

    monkeypatch.setattr(compiler, "resolve_progression", _capture)
    from tools.generate_piano_v3_cadence_trial import generate_one

    try:
        generate_one(equave, seed, skip_wav=True, crossing_match="non_crossing")
    except Exception:
        pass  # The query is captured before any downstream failure.
    assert captured, "no progression query was captured"
    return captured[0]


def test_compiler_emitted_2_1_query_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    assert query["schema_version"] == "2.1.0"
    errors = list(_validator().iter_errors(query))
    assert not errors, [
        (list(error.path), error.message) for error in errors
    ]


def test_2_1_schema_rejects_wrong_budget_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    query["budget_profile"] = "gen0-progression-exact-v2"
    errors = list(_validator().iter_errors(query))
    assert any("budget_profile" in list(error.path) for error in errors)


def test_2_1_schema_rejects_polyphony_over_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    query["occurrences"][0]["maximum_polyphony"] = 65
    errors = list(_validator().iter_errors(query))
    assert any(
        "maximum_polyphony" in list(error.path) for error in errors
    )


def test_2_1_schema_rejects_missing_crossing_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    del query["crossing_match"]
    errors = list(_validator().iter_errors(query))
    # A missing required field reports on the parent (path=[]) with the
    # "required" validator naming the missing property.
    assert any(
        error.validator == "required" and "crossing_match" in error.message
        for error in errors
    )


def test_2_1_schema_rejects_wrong_crossing_match_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    query["crossing_match"] = "canonical"
    errors = list(_validator().iter_errors(query))
    assert any("crossing_match" in list(error.path) for error in errors)


def test_2_1_schema_rejects_old_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _capture_compiler_query(monkeypatch, "2/1", 0)
    query["algorithm"] = "gen0-progression-exact/v1"
    errors = list(_validator().iter_errors(query))
    assert any("algorithm" in list(error.path) for error in errors)
