"""Milestone 6: sealed dictionary builder and the read-only API."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / "harmony_dictionary_data"

from app.harmony_dictionary.authority import OCTAVE  # noqa: E402
from app.harmony_dictionary.dictionary import build_axis_dictionary  # noqa: E402
from app.harmony_dictionary.storage import (  # noqa: E402
    StorageError,
    canonical_bytes,
    read_sealed,
    seal,
    write_sealed,
)


# ------------------------------------------------------------------ builder


def test_axis_dictionary_build_is_deterministic() -> None:
    first = build_axis_dictionary(OCTAVE, 13, 3)
    second = build_axis_dictionary(OCTAVE, 13, 3)
    assert canonical_bytes(first) == canonical_bytes(second)


def test_seal_roundtrip_and_fail_closed(tmp_path: Path) -> None:
    payload = {"equave": "2/1", "axes": [3, 5, 7, 11, 13]}
    sealed = seal(payload, "harmony-dictionary/2-1")
    path = tmp_path / "harmony_dictionary_2-1.json"
    write_sealed(path, sealed)

    loaded = read_sealed(path, "harmony-dictionary/2-1")
    assert loaded == sealed

    # A wrong domain fails the hash check.
    with pytest.raises(StorageError) as error:
        read_sealed(path, "harmony-dictionary/3-1")
    assert error.value.code == "DICTIONARY_HASH_MISMATCH"

    # A byte edit breaks the seal (and canonical form).
    data = path.read_bytes()
    edited = data.replace(b'"2/1"', b'"9/1"')
    path.write_bytes(edited)
    with pytest.raises(StorageError) as error:
        read_sealed(path, "harmony-dictionary/2-1")
    assert error.value.code in ("DICTIONARY_HASH_MISMATCH", "DICTIONARY_NOT_CANONICAL")

    # A missing file fails closed.
    with pytest.raises(StorageError) as error:
        read_sealed(tmp_path / "missing.json", "harmony-dictionary/2-1")
    assert error.value.code == "DICTIONARY_MISSING"


def test_committed_files_carry_the_required_fields() -> None:
    for name, equave in (("harmony_dictionary_2-1.json", "2/1"), ("harmony_dictionary_3-1.json", "3/1")):
        payload = json.loads((DATA_DIR / name).read_text())
        for field in (
            "schema_version",
            "equave",
            "axes",
            "loop_policy",
            "templates_version",
            "dictionary_version",
            "stability_profile",
            "stability_profile_hash",
            "thresholds",
            "policy",
            "axes_detail",
            "dictionaries",
            "hash",
        ):
            assert field in payload, f"{name} missing {field}"
        assert payload["equave"] == equave
        assert len(payload["axes"]) == 5
        assert len(payload["dictionaries"]) == 10  # 5 axes x {3, 4} voices
        assert payload["stability_profile_hash"].startswith("sha256:")


def test_builder_check_reports_byte_parity() -> None:
    result = subprocess.run(
        [sys.executable, str(BACKEND / "tools" / "build_5d_chord_dictionary.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=BACKEND,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK byte parity" in result.stdout


# --------------------------------------------------------------------- api


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_config_lists_both_equaves(client) -> None:
    response = client.get("/api/harmony-dictionary/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["equaves"] == ["2/1", "3/1"]
    assert payload["axes"]["2/1"] == [3, 5, 7, 11, 13]
    assert payload["axes"]["3/1"] == [2, 5, 7, 11, 13]
    assert len(payload["templates"]) == 13
    for equave in payload["equaves"]:
        file = payload["files"][equave]
        assert file["available"] is True
        assert file["hash"].startswith("sha256:")
        assert file["stability_profile_hash"].startswith("sha256:")


def test_axis_endpoint_returns_loop_and_points(client) -> None:
    response = client.post("/api/harmony-dictionary/axis", json={"equave": "2/1", "generator": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["loop"]["n"] == 53  # the plan's reference table
    assert payload["point_count"] == 53
    assert len(payload["points"]) == 53
    assert payload["points"][0]["reduced_ratio"] == "1/1"


def test_axis_endpoint_rejects_unknown_generator(client) -> None:
    response = client.post("/api/harmony-dictionary/axis", json={"equave": "2/1", "generator": 17})
    assert response.status_code == 422


def test_axis_endpoint_rejects_unknown_equave(client) -> None:
    response = client.post("/api/harmony-dictionary/axis", json={"equave": "5/1", "generator": 3})
    assert response.status_code == 422


def test_chords_endpoint_pages_and_scores(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/chords",
        json={"equave": "2/1", "generator": 3, "voice_count": 3, "template": "major_triad", "page_size": 4},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert len(payload["entries"]) <= 4
    variant = payload["entries"][0]["variants"][0]
    assert 0 <= variant["stability_q"] <= 10000
    assert payload["thresholds"]["D_low"] < payload["thresholds"]["T_high"]


def test_chords_endpoint_empty_filter_is_a_result_not_an_error(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/chords",
        json={"equave": "2/1", "generator": 3, "voice_count": 3, "key": "1,5,9"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_chords_endpoint_rejects_invalid_tonic(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/chords",
        json={"equave": "2/1", "generator": 3, "voice_count": 3, "tonic": "abc"},
    )
    assert response.status_code == 422


def test_evaluate_endpoint_returns_full_diagnostics(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/evaluate",
        json={
            "equave": "2/1",
            "tonic": "1/1",
            "vectors": [[0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 0, 0, 0]],
            "registers": [0, -1, -2],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "OK"
    assert len(payload["axes"]) == 5
    assert payload["exact"]["template"] == "major_triad"
    assert payload["exact"]["stability_q"] is not None


def test_evaluate_endpoint_reports_unreliable_projection(client) -> None:
    # Two identical tones collapse on every axis (voice loss), so no axis
    # passes the gate and the bounded exact fallback is reported.
    response = client.post(
        "/api/harmony-dictionary/evaluate",
        json={
            "equave": "2/1",
            "vectors": [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [1, 0, 0, 0, 0]],
            "registers": [0, 0, -1],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "PROJECTION_UNRELIABLE"
    assert payload["selected_axis"] is None
    # 1/1 + 1/1 + 3/2 matches no template within the versioned tolerance.
    assert payload["exact"]["template"] == "other"


def test_evaluate_endpoint_enforces_input_caps(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/evaluate",
        json={"equave": "2/1", "vectors": [[0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 0, 0, 0]]},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/harmony-dictionary/evaluate",
        json={"equave": "2/1", "vectors": [[100, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 0, 0, 0]]},
    )
    assert response.status_code == 422


def test_cadences_endpoint_generates_and_reports(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/cadences",
        json={"equave": "2/1", "tonic": "1/1", "kind": "authentic", "seed": 7, "count": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    cadence = payload["cadences"][0]
    assert cadence["code"] == "OK"
    assert [chord["function"] for chord in cadence["chords"]] == ["T", "D", "T"]
    assert len(payload["report"]["confusion_matrix"]) == 3
    assert 0.0 <= payload["report"]["coverage"] <= 1.0


def test_cadences_endpoint_rejects_unknown_kind(client) -> None:
    response = client.post(
        "/api/harmony-dictionary/cadences",
        json={"equave": "2/1", "tonic": "1/1", "kind": "deceptive"},
    )
    assert response.status_code == 422


def test_api_fails_closed_when_the_dictionary_is_missing(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import app.harmony_dictionary.api as api

    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api, "_cache", {})
    response = client.get("/api/harmony-dictionary/config")
    assert response.status_code == 200
    for equave in ("2/1", "3/1"):
        assert response.json()["files"][equave]["available"] is False
        assert response.json()["files"][equave]["code"] == "DICTIONARY_MISSING"
    response = client.post("/api/harmony-dictionary/axis", json={"equave": "2/1", "generator": 3})
    assert response.status_code == 503
    assert "DICTIONARY_MISSING" in response.json()["detail"]
