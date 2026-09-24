from __future__ import annotations

import copy
import json

from app.songprogram.composition_generation import generate_composition_plan
from app.songprogram.composition_viability import extract_composition_viability
from app.songprogram.lattice_pitch_diagnostic import lattice_pitch_diagnostic
from tests.test_composition_viability import _inputs
from tools.cluster_section_seed_plans import DEFAULT_PROFILE
from tools.cluster_symbolic_songs import distance_symbolic, features


def test_sounded_arrangement_changes_project_distance_without_changing_plan() -> None:
    plan = generate_composition_plan(json.loads(DEFAULT_PROFILE.read_text()), 1)
    program, project = _inputs()
    project["resolved_chords"] = [{"id": "ch", "voice_offsets": [[0], [1], [2]]}]
    for row in project["harmony_occurrences"]:
        row["resolved_chord_id"] = "ch"

    def measure(value):
        return features(plan, value, extract_composition_viability(program, value),
                        lattice_pitch_diagnostic(value))

    original = measure(project)
    changed = copy.deepcopy(project)
    changed["events"] = [event for event in changed["events"] if event["track_id"] != "trk_bass"]
    alternative = measure(changed)
    assert distance_symbolic(original, original) == 0
    assert distance_symbolic(original, alternative) > 0
    assert original["opening"] == alternative["opening"]
