from fractions import Fraction
from math import log2

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tuning.ratios import parse_interval
from app.tuning.snap import snap_ratio

client = TestClient(app)


def test_parse_interval_ratio() -> None:
    assert parse_interval("3/2") == Fraction(3, 2)


def test_parse_interval_cents() -> None:
    ratio = parse_interval("748.2")
    expected = 2 ** (748.2 / 1200)
    assert abs(float(ratio) - expected) < 1e-6


def test_parse_interval_edo_degree() -> None:
    ratio = parse_interval("5\\12")
    assert abs(float(ratio) - 2 ** (5 / 12)) < 1e-6


def test_parse_interval_decimal() -> None:
    assert parse_interval("1.33") == Fraction(133, 100)


def test_parse_interval_expression() -> None:
    ratio = parse_interval("=2**(6/12)")
    assert abs(float(ratio) - 2 ** 0.5) < 1e-6
    assert parse_interval("=3/2") == Fraction(3, 2)
    caret = parse_interval("=2^(7/12)")
    assert abs(float(caret) - 2 ** (7 / 12)) < 1e-6


@pytest.mark.parametrize("text", ["", "abc", "1/0", "-3/2", "=__import__('os')", "=0", "=1-2", "5\\0"])
def test_parse_interval_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_interval(text)


def test_snap_edo_fifth() -> None:
    snapped = snap_ratio(Fraction(3, 2), "edo", 12)
    assert abs(float(snapped) - 2 ** (7 / 12)) < 1e-6


def test_snap_prime_limit_recovers_fifth() -> None:
    tempered = Fraction(2 ** (7 / 12)).limit_denominator(1_000_000)
    assert snap_ratio(tempered, "prime_limit", 5) == Fraction(3, 2)


def test_snap_prime_limit_seven() -> None:
    assert snap_ratio(Fraction(8, 5), "prime_limit", 7) == Fraction(8, 5)


def test_snap_invalid_mode_and_value() -> None:
    with pytest.raises(ValueError):
        snap_ratio(Fraction(3, 2), "meantone", 12)
    with pytest.raises(ValueError):
        snap_ratio(Fraction(3, 2), "edo", 1)
    with pytest.raises(ValueError):
        snap_ratio(Fraction(3, 2), "prime_limit", 0)


def test_analyze_interval_endpoint() -> None:
    response = client.post("/api/analyze-interval", json={"value": "3/2"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ratio"] == "3/2"
    assert payload["cents"] == pytest.approx(701.955, abs=1e-3)
    assert payload["monzo"] == {"2": -1, "3": 1}


def test_analyze_interval_endpoint_expression() -> None:
    response = client.post("/api/analyze-interval", json={"value": "=2**(7/12)"})
    assert response.status_code == 200
    assert response.json()["cents"] == pytest.approx(700, abs=1e-2)


def test_analyze_interval_endpoint_invalid() -> None:
    response = client.post("/api/analyze-interval", json={"value": "=__import__('os')"})
    assert response.status_code == 422


def test_snap_endpoint_edo() -> None:
    response = client.post("/api/tuning/snap", json={"ratios": ["3/2"], "mode": "edo", "value": 12})
    assert response.status_code == 200
    [pitch] = response.json()["pitches"]
    assert pitch["original"] == "3/2"
    assert pitch["cents"] == pytest.approx(700, abs=1e-2)
    assert abs(1200 * log2(float(Fraction(pitch["ratio"]))) - 700) < 0.01


def test_snap_endpoint_prime_limit() -> None:
    tempered = str(Fraction(2 ** (7 / 12)).limit_denominator(1_000_000))
    response = client.post("/api/tuning/snap", json={"ratios": [tempered], "mode": "prime_limit", "value": 5})
    assert response.status_code == 200
    [pitch] = response.json()["pitches"]
    assert pitch["ratio"] == "3/2"


def test_snap_endpoint_invalid() -> None:
    assert client.post("/api/tuning/snap", json={"ratios": ["3/2"], "mode": "edo", "value": 1}).status_code == 422
    assert client.post("/api/tuning/snap", json={"ratios": ["3/2"], "mode": "nope", "value": 12}).status_code == 422
    assert client.post("/api/tuning/snap", json={"ratios": ["bad"], "mode": "edo", "value": 12}).status_code == 422
