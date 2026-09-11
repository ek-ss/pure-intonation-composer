import pytest

from .search_loop13_extension_oracle import (
    ExtensionError, bootstrap_indices, calibrated_criterion, challenger_ni_imp,
    criterion_ratio, genre_similarity_q, material_improvement, rank_interval,
    validate_evaluation_rows, validate_event_schedule, validate_reference_members, validate_response_rows,
)


def test_genre_similarity_is_integer_lower_median() -> None:
    assert genre_similarity_q([0, 0], [[0, 0], [2**31 - 1, 2**31 - 1], [1, 1]]) == 10_000
    with pytest.raises(ExtensionError, match="DIMENSION"):
        genre_similarity_q([0], [[0, 0]])


def test_bootstrap_rank_and_zero_denominator_are_deterministic() -> None:
    assert bootstrap_indices(7, 2, "a", 4) == bootstrap_indices(7, 2, "a", 4)
    assert rank_interval([4, 1, 9, 2], 1, 4, 3, 4) == (1, 4)
    with pytest.raises(ExtensionError, match="RANK_INVALID"):
        rank_interval([1, 2], 5, 4, 1, 1)
    assert criterion_ratio(0, 0) is None
    assert not calibrated_criterion(None, minimum=1)


def test_reference_response_and_round_semantics_are_closed() -> None:
    validate_reference_members([
        {"reference_id": "a", "partition": "calibration"},
        {"reference_id": "b", "partition": "holdout"},
    ])
    with pytest.raises(ExtensionError, match="SPLIT"):
        validate_reference_members([{"reference_id":"a","partition":"calibration"}, {"reference_id":"a","partition":"holdout"}])
    validate_response_rows([{"participant_hash":"sha256:" + "a" * 64,"item_id":"a","presentation_ordinal":0,"stratum":"s"}], ["sha256:" + "a" * 64], ["s"])
    assert material_improvement([{"cell":[0, 0],"kind":"replacement","direction_normalized_delta":2,"meets_threshold":True}], 2)


def test_challenger_noninferiority_improvement_and_tie() -> None:
    metrics = [{"id":"a","ordinal":0,"direction":"maximize","noninferiority_margin_q":1,"improvement_margin_q":2}, {"id":"b","ordinal":1,"direction":"minimize","noninferiority_margin_q":1,"improvement_margin_q":2}]
    assert challenger_ni_imp(metrics, [12, 8], [10, 10], "a", "b", True)[:3] == ("challenger_dominates", "not_needed", True)


def test_row_and_schedule_validation() -> None:
    rows = [{"id":"a","ordinal":0}, {"id":"b","ordinal":1}]
    validate_evaluation_rows(rows, rows)
    validate_event_schedule([{"round":0,"phase_ordinal":8,"candidate_ordinal":0,"event_ordinal":2,"kind":"evaluation_request"}])
    with pytest.raises(ExtensionError, match="SCHEDULE"):
        validate_event_schedule([{"round":0,"phase_ordinal":8,"candidate_ordinal":0,"event_ordinal":2,"kind":"metric_report"}])
