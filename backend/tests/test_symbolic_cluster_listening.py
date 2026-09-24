from __future__ import annotations

import json

from tools.render_symbolic_cluster_representatives import _renderable, _select_renderable
from tools.cluster_section_seed_plans import DEFAULT_PROFILE, features
from tools.cluster_symbolic_songs import G1_KEYS, ROLES
from app.songprogram.composition_generation import generate_composition_plan


def test_renderable_selection_stays_within_cluster_then_keeps_unrenderable_medoid(
    tmp_path, monkeypatch,
) -> None:
    import tools.render_symbolic_cluster_representatives as listening

    catalog = {"entries": [{"instrument_id": "synth", "allowed_frequency_millihz": [20000, 4000000]}]}
    monkeypatch.setattr(listening, "_trial_catalog", lambda manifest: (catalog, b"", "", {}))
    plan = generate_composition_plan(json.loads(DEFAULT_PROFILE.read_text()), 0)
    base = features(plan)
    base.update(sounded_roles_by_section=[[] for _ in plan["sections"]],
                onset_share_by_role={role: [0] * 16 for role in ROLES},
                events_per_bar_by_role_q={role: 0 for role in ROLES},
                four_voice_share_q=0, distinct_resolved_chords_q=0,
                lattice_exposure_q=0, lattice_mean_gap_millicents=0,
                g1_metrics_q={key: 0 for key in G1_KEYS})
    clusters = {"rows": [{"seed": seed, "features": base} for seed in (1, 2, 3)],
                "clusters": [{"representative_seed": 1, "member_seeds": [1, 2]},
                             {"representative_seed": 3, "member_seeds": [3]}]}
    (tmp_path / "manifest.json").write_text("{}")
    for seed, ratio in ((1, "10/1"), (2, "1/1"), (3, "10/1")):
        directory = tmp_path / f"seed-{seed:04d}"
        directory.mkdir()
        (directory / "project.json").write_text(json.dumps({
            "tracks": [{"id": "t", "instrument_id": "synth"}],
            "lattice": {"base_frequency_millihz": 440000},
            "events": [{"kind": "note", "track_id": "t", "ratio": ratio}],
        }))
    assert not _renderable(json.loads((tmp_path / "seed-0001/project.json").read_text()), catalog)
    assert _select_renderable(clusters, tmp_path, tmp_path / "manifest.json", None) == [
        (1, 2), (3, 3),
    ]
