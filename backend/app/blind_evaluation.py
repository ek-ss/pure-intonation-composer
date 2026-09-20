"""Local-only blind listening assignment and response collection API."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from app.songprogram.search import canonical_bytes

router = APIRouter(prefix="/api/blind-evaluation", tags=["blind-evaluation"])
REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "local_authority"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class BlindAnswers(BaseModel):
    formal_arc_is_coherent: Literal["yes", "uncertain", "no"]
    motif_recurs_and_develops: Literal["yes", "uncertain", "no"]
    harmony_has_directed_motion: Literal["yes", "uncertain", "no"]
    groove_and_parts_coordinate: Literal["yes", "uncertain", "no"]
    sections_contrast_without_discontinuity: Literal["yes", "uncertain", "no"]
    ending_feels_complete: Literal["yes", "uncertain", "no"]


class BlindItemResponse(BaseModel):
    blind_id: str
    answers: BlindAnswers | None
    technical_failure: bool = False
    confidence_q: int | None = Field(default=None, ge=0, le=10000)
    listening_count: int = Field(ge=1, le=100)
    comment: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_answers_unless_technical_failure(self) -> BlindItemResponse:
        if not self.technical_failure and self.answers is None:
            raise ValueError("answers are required unless technical_failure is true")
        return self


class BlindSubmission(BaseModel):
    assignment_hash: str
    listener_id: str
    session_id: str
    started_at: str
    responses: list[BlindItemResponse]


def evaluation_root() -> Path:
    configured = os.environ.get("CPS_BLIND_EVALUATION_ROOT")
    return Path(configured).resolve() if configured else (AUTHORITY_ROOT / "g1_g2_calibration_v1")


def _assignment(partition: str) -> dict:
    if partition not in {"calibration", "holdout"}:
        raise HTTPException(status_code=404, detail="unknown assignment partition")
    path = evaluation_root() / f"blind_{partition}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=503, detail="blind assignment is unavailable") from error
    if value.get("schema") != "cps.composition-blind-assignment":
        raise HTTPException(status_code=503, detail="blind assignment is invalid")
    return value


def _audio_path(partition: str, blind_id: str) -> Path:
    assignment = _assignment(partition)
    row = next(
        (item for item in assignment["assignments"] if item["blind_id"] == blind_id), None
    )
    if row is None:
        raise HTTPException(status_code=404, detail="unknown blind item")
    source = Path(row["audio_path"])
    resolved = (source if source.is_absolute() else REPO_ROOT / source).resolve()
    authority = AUTHORITY_ROOT.resolve()
    if not resolved.is_relative_to(authority) or not resolved.is_file():
        raise HTTPException(status_code=404, detail="audio is unavailable")
    return resolved


@router.get("/assignment/{partition}")
def get_assignment(partition: str) -> dict:
    assignment = _assignment(partition)
    return {
        "schema": assignment["schema"],
        "schema_version": assignment["schema_version"],
        "assignment_hash": assignment["assignment_hash"],
        "partition": partition,
        "questions": assignment["questions"],
        "response_enum": assignment["response_enum"],
        "assignments": [
            {
                "ordinal": row["ordinal"],
                "blind_id": row["blind_id"],
                "audio_url": f"/api/blind-evaluation/audio/{partition}/{row['blind_id']}",
            }
            for row in assignment["assignments"]
        ],
    }


@router.get("/audio/{partition}/{blind_id}")
def get_audio(partition: str, blind_id: str) -> FileResponse:
    return FileResponse(_audio_path(partition, blind_id), media_type="audio/wav")


@router.post("/responses/{partition}")
def save_responses(partition: str, submission: BlindSubmission) -> dict[str, object]:
    assignment = _assignment(partition)
    if submission.assignment_hash != assignment["assignment_hash"]:
        raise HTTPException(status_code=409, detail="assignment hash mismatch")
    if not IDENTIFIER.fullmatch(submission.listener_id) or not IDENTIFIER.fullmatch(
        submission.session_id
    ):
        raise HTTPException(status_code=422, detail="listener_id or session_id is invalid")
    expected = {row["blind_id"] for row in assignment["assignments"]}
    received = [row.blind_id for row in submission.responses]
    if len(received) != len(set(received)) or set(received) != expected:
        raise HTTPException(status_code=422, detail="responses must cover the assignment exactly once")
    payload = {
        "schema": "cps.composition-blind-response",
        "schema_version": "1.0.0",
        "partition": partition,
        "assignment_hash": submission.assignment_hash,
        "listener_id": submission.listener_id,
        "session_id": submission.session_id,
        "started_at": submission.started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "responses": [row.model_dump() for row in submission.responses],
        "response_hash": "",
    }
    payload["response_hash"] = "sha256:" + hashlib.sha256(
        b"cps.composition-blind-response/v1\0"
        + canonical_bytes({key: value for key, value in payload.items() if key != "response_hash"})
    ).hexdigest()
    destination = evaluation_root() / "responses" / partition
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{submission.listener_id}--{submission.session_id}.json"
    if path.exists():
        raise HTTPException(status_code=409, detail="this response session already exists")
    path.write_bytes(canonical_bytes(payload))
    return {"saved": True, "response_hash": payload["response_hash"]}
