from __future__ import annotations

import pytest

from app.harmony_dictionary.calibration import calibrate_thresholds


def test_thresholds_fit_train_and_measure_independent_holdout() -> None:
    observations = [
        {"id": f"{split}-{label}", "split": split, "label": label,
         "stability_q": score, "label_source": "independent_listening"}
        for split, scores in (("train", (1000, 5000, 9000)), ("held_out", (2000, 6000, 8500)))
        for label, score in zip(("dominant", "subdominant", "tonic"), scores, strict=True)
    ]
    result = calibrate_thresholds(observations)
    assert result["held_out_count"] == 3
    assert result["held_out_accuracy_q"] == 10000
    assert result["status"] == "evaluated_not_sealed"
    observations[0]["label_source"] = "composition_plan_function"
    with pytest.raises(ValueError, match="CALIBRATION_LABEL_PROVENANCE_INVALID"):
        calibrate_thresholds(observations)
