from time import sleep

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_render_job_reaches_completed_state_and_downloads_audio() -> None:
    response = client.post(
        "/api/render/jobs",
        json={"events": [{"ratio": "3/2", "start_seconds": 0, "duration_seconds": 0.01}], "sample_rate": 8000},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(20):
        status = client.get(f"/api/render/jobs/{job_id}").json()["status"]
        if status == "completed":
            break
        sleep(0.01)
    assert status == "completed"
    assert client.get(f"/api/render/jobs/{job_id}/audio").content[:4] == b"RIFF"


def test_websocket_transport_controls_and_improvises() -> None:
    with client.websocket_connect("/api/ws/transport") as websocket:
        websocket.send_json({"command": "play"})
        assert websocket.receive_json() == {"type": "transport", "state": "playing"}
        websocket.send_json({"command": "improvise", "seed": 8})
        assert websocket.receive_json()["type"] == "improvise"
