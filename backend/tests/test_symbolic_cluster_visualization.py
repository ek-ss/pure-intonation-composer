from __future__ import annotations

import copy
import json
from xml.etree import ElementTree

from app.songprogram.composition_generation import generate_composition_plan
from tools.cluster_section_seed_plans import DEFAULT_PROFILE, features as plan_features
from tools.cluster_symbolic_songs import G1_KEYS, ROLES
from tools.visualize_symbolic_clusters import visualize


def _feature(seed: int) -> dict:
    plan = generate_composition_plan(json.loads(DEFAULT_PROFILE.read_text()), seed)
    result = copy.deepcopy(plan_features(plan))
    result.update(sounded_roles_by_section=[["harmony"] for _ in plan["sections"]],
                  onset_share_by_role={role: [0] * 16 for role in ROLES},
                  events_per_bar_by_role_q={role: 0 for role in ROLES},
                  four_voice_share_q=seed * 1000, distinct_resolved_chords_q=100,
                  lattice_exposure_q=seed * 500, lattice_mean_gap_millicents=seed * 1000,
                  g1_metrics_q={key: 5000 for key in G1_KEYS})
    return result


def test_distribution_svg_contains_every_song_and_links_each_cluster_audio(tmp_path) -> None:
    rows = [{"seed": seed, "features": _feature(seed)} for seed in range(4)]
    groups = [{"representative_seed": seed, "member_seeds": [seed, seed + 1],
               "member_count": 2} for seed in (0, 2)]
    cluster_path = tmp_path / "clusters.json"
    cluster_path.write_text(json.dumps({"rows": rows, "clusters": groups,
                                        "compiled_count": 4, "report_hash": "sha256:fixture"}))
    listening_path = tmp_path / "listening.json"
    listening_path.write_text(json.dumps({"success_count": 2, "rows": [
        {"cluster_medoid_seed": seed, "seed": seed,
         "receipt": {"expanded_frequency_envelope": False}} for seed in (0, 2)
    ]}))
    output = tmp_path / "view"
    first = visualize(cluster_path, listening_path, output)
    assert first == visualize(cluster_path, listening_path, output)
    root = ElementTree.parse(output / "distribution.svg").getroot()
    assert len([row for row in root.iter() if row.attrib.get("class") == "data-point"]) == 4
    assert len([row for row in root.iter() if row.tag.endswith("a")]) == 2
    assert 'href="seed-0000/reference.wav"' in (output / "distribution.html").read_text()
