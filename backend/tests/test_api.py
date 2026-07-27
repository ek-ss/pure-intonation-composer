from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_root_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Pure Intonation Workbench" in response.text
    assert 'id="composition-roll"' in response.text
    assert 'id="lattice-chord-generate"' in response.text
    assert 'id="lattice-progression"' in response.text
    assert 'id="lattice-walk-compose"' in response.text
    assert 'id="lattice-keyboard"' in response.text
    assert 'id="lattice-keyboard-target"' in response.text
    assert "Lattice Keyboard" in response.text
    assert 'id="lattice-circle"' in response.text
    assert 'id="phase-panel"' in response.text
    assert "/static/app.js?v=20260727-lattice-page-2" in response.text
    assert 'id="compose-rhythm-apply"' in response.text
    assert 'id="compose-rhythm-native"' in response.text
    assert 'data-generator-role="harmony"' in response.text
    assert 'data-generator-role="bass"' in response.text
    assert 'data-generator-role="melody"' in response.text
    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "renderHarmonyStackOnCircle" in script.text
    assert "selectCompositionNode" in script.text
    assert "/api/exponent-lattice/chord" in script.text
    assert "/api/exponent-lattice/progression" in script.text
    assert "renderLatticeCircle" in script.text
    assert "latticeKeyboardIsTarget" in script.text
    assert "/api/compose/rhythm/apply" in script.text
    assert "/api/compose/rhythm/generate" in script.text
    assert "sendLatticeToCompose" in script.text
    assert 'const LATTICE_KEYS = "ASDFGHJKL;QWERTY"' in script.text
    assert client.get("/favicon.ico").status_code == 204


def test_lattice_lab_page() -> None:
    response = client.get("/lattice")
    assert response.status_code == 200
    assert "Lattice Lab" in response.text
    assert 'id="pitch-circle"' in response.text
    assert 'id="progression-generate"' in response.text
    assert 'src="/static/lattice.js?v=20260727-lattice-audio-2"' in response.text
    script = client.get("/static/lattice.js")
    assert script.status_code == 200
    assert '"/api/exponent-lattice/chord"' in script.text
    assert '"/api/exponent-lattice/walk"' in script.text
    assert "lattice-compose-harmonies" in script.text
    assert "startAudio" in script.text


def test_harmonic_pitch_circle_page() -> None:
    response = client.get("/harmonic-pitch-circle")
    assert response.status_code == 200
    assert "Harmonic Pitch Circle" in response.text
    assert 'id="harmonic-circle"' in response.text
    assert 'id="chord-buttons"' in response.text
    assert 'id="root-buttons"' in response.text
    assert 'id="chord-audition"' in response.text
    assert 'src="/static/harmonic_pitch_circle.js?v=20260727-harmonic-circle-transpose-5"' in response.text
    script = client.get("/static/harmonic_pitch_circle.js")
    assert script.status_code == 200
    assert "fifthSteps" in script.text
    assert "describeTransition" in script.text
    assert "auditionCurrentChord" in script.text
    assert "rootFrequency" in script.text


def test_prime_limit_explorer_page_and_search() -> None:
    response = client.get("/prime-limit-explorer")
    assert response.status_code == 200
    assert "Prime-Limit Harmonic Explorer" in response.text
    assert 'id="prime-circle"' in response.text
    script = client.get("/static/prime_limit_explorer.js")
    assert script.status_code == 200
    assert "/api/prime-limit/explore" in script.text
    assert "/api/prime-limit/chords" in script.text
    assert "/api/prime-limit/progression" in script.text
    assert "prime_limit_worker.js" in script.text
    worker = client.get("/static/prime_limit_worker.js")
    assert worker.status_code == 200
    assert "/api/prime-limit/explore" in worker.text
    response = client.post(
        "/api/prime-limit/explore",
        json={"primes": [3, 5, 7], "exponent_limit": 1, "height_limit": 2, "tolerance_cents": 8, "target_count": 7},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == [3, 5, 7]
    assert data["point_count"] == 19
    assert len(data["scale"]) == 7
    assert data["metrics"]["min_gap_cents"] > 0


def test_prime_limit_chord_discovery_and_progression() -> None:
    response = client.post(
        "/api/prime-limit/chords",
        json={"primes": [3, 5, 7], "exponent_limit": 1, "height_limit": 2, "tolerance_cents": 8, "target_count": 7, "tone_count": 3},
    )
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert candidates
    assert len(candidates[0]["tones"]) == 3
    assert candidates[0]["metrics"]["algorithm_version"] == "g12-chord-v1"
    response = client.post(
        "/api/prime-limit/progression",
        json={"chords": [[0, 300, 700], [0, 400, 700]]},
    )
    assert response.status_code == 200
    assert response.json()["transitions"] == [{"common_tones": 2, "johnson_distance": 1, "voice_leading_cents": 100.0}]


def test_cps_is_octave_reduced() -> None:
    response = client.post("/api/cps", json={"factors": [1, 3, 5, 7], "choose": 2})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == ["35/32", "5/4", "21/16", "3/2", "7/4", "15/8"]


def test_euler_fokker_has_divisors() -> None:
    response = client.post("/api/euler-fokker", json={"factors": [3, 5]})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == ["1/1", "5/4", "3/2", "15/8"]


def test_ratio_analysis() -> None:
    response = client.post("/api/analyze-ratio", json={"ratio": "3/2"})
    assert response.status_code == 200
    assert response.json()["monzo"] == {"2": -1, "3": 1}
