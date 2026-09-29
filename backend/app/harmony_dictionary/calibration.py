"""Calibrate T/D/S thresholds only against independently labeled examples.

No CompositionPlan function, generator slot, or model prediction is a label.
The caller supplies train and held-out *human* observations explicitly; the
held-out partition is never used to select thresholds.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .stability import ClassificationThresholds, classify_threshold

LABELS = ("dominant", "subdominant", "tonic")


def calibrate_thresholds(observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations or len({row.get("id") for row in observations}) != len(observations):
        raise ValueError("CALIBRATION_OBSERVATIONS_INVALID")
    for row in observations:
        if (set(row) != {"id", "split", "label", "stability_q", "label_source"}
                or not isinstance(row["id"], str) or not row["id"]
                or row["split"] not in ("train", "held_out")
                or row["label"] not in LABELS
                or type(row["stability_q"]) is not int or not 0 <= row["stability_q"] <= 10000
                or row["label_source"] != "independent_listening"):
            raise ValueError("CALIBRATION_LABEL_PROVENANCE_INVALID")
    partitions = {split: [row for row in observations if row["split"] == split]
                  for split in ("train", "held_out")}
    if any(Counter(row["label"] for row in rows).keys() != set(LABELS)
           for rows in partitions.values()):
        raise ValueError("CALIBRATION_CLASSES_INCOMPLETE")
    observed = sorted({row["stability_q"] for row in partitions["train"]})
    scores = sorted({0, 10000, *observed,
                     *((left + right) // 2 for left, right in zip(observed, observed[1:]))})
    best: tuple[tuple[int, int, int, int], ClassificationThresholds] | None = None
    for low in scores:
        for high in scores:
            if low >= high:
                continue
            thresholds = ClassificationThresholds(version="held-out-evaluation/v1", T_high=high, D_low=low, margin=0)
            correct = sum(classify_threshold(row["stability_q"], thresholds) == row["label"]
                          for row in partitions["train"])
            # Among equally accurate fits prefer a wider S interval, with
            # thresholds between rather than on labeled observations.
            on_example = sum(row["stability_q"] in (low, high) for row in partitions["train"])
            key = (-correct, on_example, -(high - low), low)
            if best is None or key < best[0]:
                best = (key, thresholds)
    assert best is not None
    thresholds = best[1]
    held_out = partitions["held_out"]
    confusion = {label: {predicted: 0 for predicted in LABELS} for label in LABELS}
    for row in held_out:
        confusion[row["label"]][classify_threshold(row["stability_q"], thresholds)] += 1
    return {"schema": "cps.harmony-threshold-calibration", "schema_version": "1.0.0",
            "thresholds": thresholds.as_dict(), "train_count": len(partitions["train"]),
            "held_out_count": len(held_out), "held_out_confusion": confusion,
            "held_out_accuracy_q": 10000 * sum(confusion[label][label] for label in LABELS) // len(held_out),
            "label_source": "independent_listening", "status": "evaluated_not_sealed"}
