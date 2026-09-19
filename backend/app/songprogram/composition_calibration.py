"""Deterministic lineage split and blind assignment for G1/G2 calibration."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable, Mapping

from .search import canonical_bytes


class CompositionCalibrationError(ValueError):
    pass


def _hash(domain: str, value: Mapping[str, Any], omit: str) -> str:
    payload = {key: item for key, item in value.items() if key != omit}
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(payload)).hexdigest()


def split_lineages(
    candidates: Iterable[Mapping[str, Any]], *, calibration_basis_points: int = 7000
) -> dict[str, Any]:
    """Split complete lineages; no candidate from one lineage can cross the boundary."""
    if not 1 <= calibration_basis_points <= 9999:
        raise CompositionCalibrationError("CALIBRATION_SPLIT_RATIO_INVALID")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for source in candidates:
        row = dict(source)
        candidate_id = row.get("candidate_id")
        lineage_id = row.get("lineage_id")
        if not isinstance(candidate_id, str) or not isinstance(lineage_id, str):
            raise CompositionCalibrationError("CALIBRATION_CANDIDATE_INVALID")
        if candidate_id in seen:
            raise CompositionCalibrationError("CALIBRATION_CANDIDATE_DUPLICATE")
        seen.add(candidate_id)
        groups[lineage_id].append(row)
    strata: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for lineage_id, rows in groups.items():
        strata[tuple(sorted({row.get("cohort", "") for row in rows}))].append(lineage_id)
    partitions: dict[str, str] = {}
    for signature in sorted(strata):
        ordered = sorted(
            strata[signature],
            key=lambda lineage_id: hashlib.sha256(
                b"cps.g1-lineage-split/v1\0" + lineage_id.encode()
            ).digest(),
        )
        calibration_count = max(
            1,
            min(
                len(ordered) - 1 if len(ordered) > 1 else 1,
                round(len(ordered) * calibration_basis_points / 10000),
            ),
        )
        for ordinal, lineage_id in enumerate(ordered):
            partitions[lineage_id] = (
                "calibration" if ordinal < calibration_count else "holdout"
            )
    assignments = []
    for lineage_id in sorted(groups):
        partition = partitions[lineage_id]
        for row in sorted(groups[lineage_id], key=lambda item: item["candidate_id"]):
            assignments.append({**row, "partition": partition})
    result = {
        "schema": "cps.composition-calibration-split",
        "schema_version": "1.0.0",
        "calibration_basis_points": calibration_basis_points,
        "assignments": assignments,
        "split_hash": "",
    }
    result["split_hash"] = _hash("cps.composition-calibration-split/v1", result, "split_hash")
    return result


def build_blind_assignment(
    split: Mapping[str, Any], *, partition: str, assignment_seed: int
) -> dict[str, Any]:
    """Return opaque, deterministically shuffled listening assignments without class labels."""
    if partition not in {"calibration", "holdout"} or not 0 <= assignment_seed < 2**64:
        raise CompositionCalibrationError("BLIND_ASSIGNMENT_REQUEST_INVALID")
    selected = [row for row in split.get("assignments", []) if row.get("partition") == partition]
    ordered = sorted(
        selected,
        key=lambda row: hashlib.sha256(
            b"cps.g2-blind-order/v1\0"
            + assignment_seed.to_bytes(8, "big")
            + row["candidate_id"].encode()
        ).digest(),
    )
    assignments = []
    for ordinal, row in enumerate(ordered):
        opaque_id = "blind_" + hashlib.sha256(
            b"cps.g2-blind-id/v1\0"
            + assignment_seed.to_bytes(8, "big")
            + row["candidate_id"].encode()
        ).hexdigest()[:16]
        assignments.append(
            {
                "ordinal": ordinal,
                "blind_id": opaque_id,
                "audio_path": row["audio_path"],
                "audio_hash": row["audio_hash"],
            }
        )
    result = {
        "schema": "cps.composition-blind-assignment",
        "schema_version": "1.0.0",
        "source_split_hash": split["split_hash"],
        "partition": partition,
        "assignment_seed": assignment_seed,
        "questions": [
            "formal_arc_is_coherent",
            "motif_recurs_and_develops",
            "harmony_has_directed_motion",
            "groove_and_parts_coordinate",
            "sections_contrast_without_discontinuity",
            "ending_feels_complete",
        ],
        "response_enum": ["yes", "uncertain", "no"],
        "assignments": assignments,
        "assignment_hash": "",
    }
    result["assignment_hash"] = _hash(
        "cps.composition-blind-assignment/v1", result, "assignment_hash"
    )
    return result
