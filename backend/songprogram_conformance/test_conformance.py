from __future__ import annotations

import json
import hashlib
from decimal import ROUND_FLOOR, getcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

from .reference import (
    chord_complexity,
    edo_phase_mc,
    odd_limit,
    pair_rms_mc,
    ratio_mc,
    resolve_exact,
    wrap_mc,
)

HERE = Path(__file__).parent


def test_search_decision_schemas_are_closed_draft_2020_12() -> None:
    schema_names = (
        "archive_admission_policy.schema.json",
        "archive_admission_decision.schema.json",
        "challenger_acceptance_policy.schema.json",
        "challenger_acceptance_decision.schema.json",
        "near_duplicate_decision.schema.json",
        "stopping_policy.schema.json",
        "round_decision.schema.json",
        "cancellation_request.schema.json",
        "cancellation_decision.schema.json",
        "render_selection_policy.schema.json",
        "render_request.schema.json",
        "render_charge.schema.json",
        "render_result.schema.json",
        "search_run_manifest_1_3.schema.json",
        "search_checkpoint_1_1.schema.json",
        "search_run_record_1_1.schema.json",
    )
    for name in schema_names:
        schema = json.loads((HERE / "schemas" / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


def test_search_manifest_1_3_binds_every_decision_policy() -> None:
    schema = json.loads(
        (HERE / "schemas" / "search_run_manifest_1_3.schema.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(schema["required"])
    assert {
        "genre_intent_hash",
        "fingerprint_spec_hash",
        "archive_admission_policy_hash",
        "challenger_acceptance_policy_hash",
        "stopping_policy_hash",
        "render_selection_policy_hash",
        "fallback_manifest_hash",
        "broad_prior_production_manifest_hash",
    } <= required


def test_challenger_policy_has_no_absolute_acceptance_gate() -> None:
    schema = json.loads(
        (HERE / "schemas" / "challenger_acceptance_policy.schema.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = json.dumps(schema, sort_keys=True)
    assert "minimum_score" not in serialized
    assert "required_consecutive" not in serialized


def _load(name: str) -> dict[str, Any]:
    return json.loads((HERE / "goldens" / name).read_text())


def test_numeric_goldens_and_context_isolation() -> None:
    context = getcontext()
    old_precision, old_rounding = context.prec, context.rounding
    try:
        context.prec, context.rounding = 6, ROUND_FLOOR
        assert ratio_mc(Fraction(1)) == 0
        assert ratio_mc(Fraction(2)) == 1_200_000
        assert ratio_mc(Fraction(5, 4)) == 386_314
        assert ratio_mc(Fraction(3, 2)) == 701_955
        assert ratio_mc(Fraction(6, 5)) == 315_641
        assert ratio_mc(Fraction(7, 4)) == 968_826
        assert ratio_mc(Fraction(3)) == 1_901_955
        assert ratio_mc(Fraction(4, 5)) == -386_314
    finally:
        context.prec, context.rounding = old_precision, old_rounding


def test_edo_wrap_rms_complexity_and_odd_limit_goldens() -> None:
    assert [edo_phase_mc(Fraction(2), 12, step) for step in (0, 3, 4, 7, 11)] == [0, 300_000, 400_000, 700_000, 1_100_000]
    assert [edo_phase_mc(Fraction(3), 13, step) for step in (0, 1, 3, 4, 7, 12)] == [0, 146_304, 438_913, 585_217, 1_024_130, 1_755_651]
    assert [wrap_mc(value, 1_200_000) for value in (599_999, 600_000, 600_001, -600_000, -600_001)] == [599_999, -600_000, -599_999, -600_000, 599_999]
    assert pair_rms_mc((1, 0, 0, 0)) == 0
    assert pair_rms_mc((3, 0, 0, 0)) == 2
    assert pair_rms_mc((3, 4)) == 4
    assert chord_complexity((Fraction(1), Fraction(5, 4), Fraction(3, 2)), Fraction(2)) == 10
    assert chord_complexity((Fraction(1), Fraction(5, 3), Fraction(7, 3)), Fraction(3)) == 10
    assert odd_limit(Fraction(5, 4), Fraction(2)) == 5
    assert odd_limit(Fraction(5, 2), Fraction(2)) == 5
    assert odd_limit(Fraction(64, 63), Fraction(2)) == 63
    assert odd_limit(Fraction(64, 65), Fraction(2)) == 65
    assert odd_limit(Fraction(5, 3), Fraction(3)) == 5
    assert odd_limit(Fraction(5), Fraction(3)) == 5


def test_major_and_minor_exact_oracle_goldens() -> None:
    major = resolve_exact(_load("major_query.json"))
    minor = resolve_exact(_load("minor_query.json"))
    assert major == _load("major_result.json")
    assert minor == _load("minor_result.json")
    assert major["exact_ratios"] == ["1/1", "5/4", "3/2"]
    assert major["vectors"] == [[0, 0], [0, 1], [1, 0]]
    assert major["equave_exponents"] == [0, -2, -1]
    assert major["pair_errors_millicents"] == [-13_686, 1_955, 15_641]
    assert major["score_prefix"] == [12_052, 15_641, 10]
    assert minor["exact_ratios"] == ["1/1", "6/5", "3/2"]
    assert minor["vectors"] == [[0, 0], [1, -1], [1, 0]]
    assert minor["equave_exponents"] == [0, 1, -1]
    assert minor["pair_errors_millicents"] == [15_641, 1_955, -13_686]
    assert minor["score_prefix"] == [12_052, 15_641, 10]


def test_threshold_boundaries_and_no_solution() -> None:
    query = _load("major_query.json")
    query["intent"]["maximum_pair_error_millicents"] = 15_640
    try:
        resolve_exact(query)
    except ValueError as error:
        assert str(error) == "NO_JOINT_CHORD_SOLUTION"
    else:
        raise AssertionError("maximum error boundary must reject")


def test_oracle_is_deterministic_and_reports_real_work() -> None:
    query = _load("major_query.json")
    first = resolve_exact(query)
    second = resolve_exact(query)
    assert first == second
    assert first["search_completeness"] == "exact"
    assert first["examined_assignments"] > 0


def test_tritave_and_independent_nearest_adversary() -> None:
    assert resolve_exact(_load("tritave_query.json")) == _load("tritave_result.json")
    adversary = _load("adversarial_independent_nearest_query.json")
    try:
        resolve_exact(adversary)
    except ValueError as error:
        assert str(error) == _load("adversarial_independent_nearest_expected.json")["error"]
    else:
        raise AssertionError("full pair matrix must reject independent-nearest witness")


def test_frozen_thousand_record_numeric_dataset() -> None:
    dataset = HERE / "goldens" / "numeric_seed_1592639710.jsonl"
    expected_digest = (dataset.with_suffix(".sha256")).read_text(encoding="ascii").strip()
    payload = dataset.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == expected_digest
    records = [json.loads(line) for line in payload.splitlines()]
    assert len(records) == 1000
    assert [record["i"] for record in records] == list(range(1000))
