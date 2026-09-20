from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import blind_evaluation


def _client(tmp_path: Path, monkeypatch) -> tuple[TestClient, str]:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFtest")
    assignment_hash = "sha256:" + "12" * 32
    assignment = {
        "schema": "cps.composition-blind-assignment",
        "schema_version": "1.0.0",
        "assignment_hash": assignment_hash,
        "partition": "calibration",
        "questions": list(blind_evaluation.BlindAnswers.model_fields),
        "response_enum": ["yes", "uncertain", "no"],
        "assignments": [
            {
                "ordinal": 0,
                "blind_id": "blind_0123456789abcdef",
                "audio_path": str(audio),
                "audio_hash": "sha256:" + "34" * 32,
            }
        ],
    }
    (tmp_path / "blind_calibration.json").write_text(json.dumps(assignment))
    monkeypatch.setenv("CPS_BLIND_EVALUATION_ROOT", str(tmp_path))
    monkeypatch.setattr(blind_evaluation, "AUTHORITY_ROOT", tmp_path)
    app = FastAPI()
    app.include_router(blind_evaluation.router)
    return TestClient(app), assignment_hash


def test_assignment_hides_source_path_and_serves_registered_audio(tmp_path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/api/blind-evaluation/assignment/calibration")
    assert response.status_code == 200
    item = response.json()["assignments"][0]
    assert set(item) == {"ordinal", "blind_id", "audio_url"}
    assert client.get(item["audio_url"]).content == b"RIFFtest"


def test_complete_response_is_saved_once(tmp_path, monkeypatch) -> None:
    client, assignment_hash = _client(tmp_path, monkeypatch)
    answers = {name: "yes" for name in blind_evaluation.BlindAnswers.model_fields}
    payload = {
        "assignment_hash": assignment_hash,
        "listener_id": "listener_001",
        "session_id": "session_001",
        "started_at": "2026-09-20T10:00:00+09:00",
        "responses": [
            {
                "blind_id": "blind_0123456789abcdef",
                "answers": answers,
                "technical_failure": False,
                "confidence_q": 7500,
                "listening_count": 1,
                "comment": "",
            }
        ],
    }
    response = client.post("/api/blind-evaluation/responses/calibration", json=payload)
    assert response.status_code == 200
    saved = tmp_path / "responses/calibration/listener_001--session_001.json"
    assert saved.is_file()
    assert json.loads(saved.read_text())["response_hash"] == response.json()["response_hash"]
    assert client.post("/api/blind-evaluation/responses/calibration", json=payload).status_code == 409


def test_response_must_cover_every_blind_item(tmp_path, monkeypatch) -> None:
    client, assignment_hash = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/blind-evaluation/responses/calibration",
        json={
            "assignment_hash": assignment_hash,
            "listener_id": "listener_001",
            "session_id": "session_001",
            "started_at": "2026-09-20T10:00:00+09:00",
            "responses": [],
        },
    )
    assert response.status_code == 422
