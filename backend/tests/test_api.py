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
    assert "/static/app.js?v=20260726-role-rhythms" in response.text
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
    assert "/api/compose/rhythm/apply" in script.text
    assert "/api/compose/rhythm/generate" in script.text
    assert "sendLatticeToCompose" in script.text
    assert 'const LATTICE_KEYS = "ASDFGHJKL;QWERTY"' in script.text
    assert client.get("/favicon.ico").status_code == 204


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
