import json
from pathlib import Path

from .search_loop13_bound_component_builder import build_bound_components, write_bound_components
from .search_loop13_component_authority_builder import producer_digest
from .search_decision_oracle import artifact_hash


FIXTURE = Path(__file__).with_name("fixtures") / "search_loop_13" / "shared_authority" / "artifacts"


def test_all_eight_bound_slots_have_hashes_and_exact_dependencies() -> None:
    values = build_bound_components()
    hashes = values["component_hashes"]
    assert len(hashes) == 8
    assert (
        values["broad_prior_production_manifest"]["sampler_manifest_hash"]
        == hashes["sampler_manifest"]
    )
    assert (
        values["candidate_source_policy"]["archive_parent"]["qd_manifest_hash"]
        == hashes["qd_manifest"]
    )
    assert all(value.startswith("sha256:") for value in hashes.values())
    assert hashes["fallback_manifest"] == producer_digest(
        "cps.fallback-manifest/v1", values["fallback_manifest"]
    )
    assert hashes["broad_prior_production_manifest"] == producer_digest(
        "cps.production-lowering-manifest/v1", values["broad_prior_production_manifest"]
    )
    for name in (
        "archive_admission_policy",
        "stopping_policy",
        "render_selection_policy",
        "candidate_source_policy",
    ):
        assert hashes[name] == artifact_hash(values[name])


def test_production_tables_only_name_role_compatible_catalog_entries() -> None:
    production = build_bound_components()["broad_prior_production_manifest"]
    catalog = {
        entry["instrument_id"]: entry["role"]
        for entry in json.loads((FIXTURE / "instrument_catalog.json").read_bytes())["entries"]
    }
    for role, table in production["instrument_entries_by_role"].items():
        assert all(catalog[row["value"]] == role for row in table)


def test_render_selection_has_no_future_evaluation_dependency() -> None:
    policy = build_bound_components()["render_selection_policy"]
    assert all(
        row["source"]["artifact_kind"] in {"compile_report", "fingerprint_record"}
        for row in policy["order_components"]
    )


def test_checked_in_bound_components_match_builder(tmp_path) -> None:
    write_bound_components(tmp_path)
    for path in tmp_path.iterdir():
        assert (FIXTURE / path.name).read_bytes() == path.read_bytes()
