from __future__ import annotations

from pathlib import Path

from .search_loop13_component_authority_builder import (
    build_reusable_components,
    component_hashes,
    write_reusable_components,
)


FIXTURE = Path(__file__).with_name("fixtures") / "search_loop_13" / "shared_authority" / "artifacts"


def test_reusable_component_hashes_retain_producer_domains() -> None:
    components = build_reusable_components()
    hashes = component_hashes(components)
    assert hashes["render_manifest"] == components["render_manifest"]["render_manifest_digest"]
    assert hashes["instrument_catalog"] == components["render_manifest"]["catalog_digest"]
    assert len(set(hashes.values())) == len(hashes)


def test_checked_in_reusable_components_match_builder(tmp_path) -> None:
    write_reusable_components(tmp_path)
    expected = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    actual = {path.name: (FIXTURE / path.name).read_bytes() for path in tmp_path.iterdir()}
    assert actual == expected
