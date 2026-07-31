from fastapi.testclient import TestClient

from app.exporters.scala_import import parse_scala
from app.main import app

client = TestClient(app)


def test_scale_save_list_get_delete_roundtrip() -> None:
    response = client.post("/api/scales", json={"name": "roundtrip-test", "ratios": ["1/1", "5/4", "3/2"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "roundtrip-test"
    assert payload["count"] == 3
    assert [pitch["ratio"] for pitch in payload["pitches"]] == ["1/1", "5/4", "3/2"]
    assert payload["pitches"][1]["monzo"] == {"2": -2, "5": 1}

    listing = client.get("/api/scales")
    assert listing.status_code == 200
    assert {"name": "roundtrip-test", "count": 3} in listing.json()

    fetched = client.get("/api/scales/roundtrip-test")
    assert fetched.status_code == 200
    assert fetched.json()["count"] == 3

    deleted = client.delete("/api/scales/roundtrip-test")
    assert deleted.status_code == 200
    assert deleted.json() == {"name": "roundtrip-test", "deleted": True}
    assert client.get("/api/scales/roundtrip-test").status_code == 404


def test_scale_save_overwrites_existing() -> None:
    client.post("/api/scales", json={"name": "overwrite-test", "ratios": ["1/1", "3/2"]})
    response = client.post("/api/scales", json={"name": "overwrite-test", "ratios": ["1/1", "5/4", "3/2", "7/4"]})
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert client.get("/api/scales/overwrite-test").json()["count"] == 4
    client.delete("/api/scales/overwrite-test")


def test_scale_get_and_delete_missing_return_404() -> None:
    assert client.get("/api/scales/does-not-exist").status_code == 404
    assert client.delete("/api/scales/does-not-exist").status_code == 404


def test_scale_save_rejects_invalid_ratio() -> None:
    response = client.post("/api/scales", json={"name": "bad-ratio-test", "ratios": ["1/1", "nope"]})
    assert response.status_code == 422
    assert client.get("/api/scales/bad-ratio-test").status_code == 404


def test_scale_save_rejects_invalid_name() -> None:
    assert client.post("/api/scales", json={"name": "", "ratios": ["1/1"]}).status_code == 422
    assert client.post("/api/scales", json={"name": "x" * 81, "ratios": ["1/1"]}).status_code == 422


def test_parse_scala_skips_comments_description_and_count() -> None:
    content = "! a comment\n! another comment\ndiatonic test scale\n 3\n! more comments\n100.0\n5/4\n2/1\n"
    ratios = parse_scala(content)
    assert len(ratios) == 4
    assert ratios[0] == 1
    assert abs(float(ratios[1]) - 2 ** (100 / 1200)) < 1e-6
    assert ratios[2] == 5 / 4
    assert ratios[3] == 2


def test_parse_scala_cents_entry() -> None:
    ratios = parse_scala("desc\n1\n1200.0\n")
    assert ratios[0] == 1
    assert abs(float(ratios[1]) - 2.0) < 1e-6


def test_parse_scala_rejects_bad_content() -> None:
    for content in ("", "only a description\n", "desc\nnot-a-count\n1/1\n", "desc\n1\nbogus\n", "desc\n1\n-3/2\n"):
        try:
            parse_scala(content)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {content!r}")


def test_scala_import_endpoint_saves_scale() -> None:
    content = "! comment\nimported scale\n2\n701.955\n3/2\n"
    response = client.post("/api/scales/import", json={"name": "import-test", "content": content})
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "import-test"
    assert payload["count"] == 3
    assert payload["pitches"][0]["ratio"] == "1/1"
    assert abs(payload["pitches"][1]["cents"] - 701.955) < 0.01
    assert payload["pitches"][2]["ratio"] == "3/2"

    fetched = client.get("/api/scales/import-test")
    assert fetched.status_code == 200
    assert fetched.json()["count"] == 3
    client.delete("/api/scales/import-test")


def test_scala_import_rejects_invalid_content() -> None:
    response = client.post("/api/scales/import", json={"name": "bad-import-test", "content": "desc\n1\nbogus\n"})
    assert response.status_code == 422
    assert client.get("/api/scales/bad-import-test").status_code == 404
