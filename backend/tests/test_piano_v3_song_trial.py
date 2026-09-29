"""The independent 5D trial must produce a real Program, Project and PCM."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from tools.generate_piano_v3_trial import build_trial_program, generate

SCHEMAS = Path(__file__).resolve().parents[1] / "songprogram_conformance/schemas"


def test_trial_program_owns_section_harmony_without_in_place_aliasing() -> None:
    first = build_trial_program(0, "sha256:" + "0" * 64)
    second = build_trial_program(1, "sha256:" + "0" * 64)
    for program in (first, second):
        assert len(program["lattice"]["generators"]) == 5
        assert len(program["form"]) == 4 and sum(row["bars"] for row in program["form"]) == 16
        cells = [row for row in program["materials"] if row["kind"] == "harmony_intent_cell"]
        assert len(cells) == 4 and len({row["id"] for row in cells}) == 4
        assert cells[0]["root_anchors"][0] == cells[3]["root_anchors"][0] == [0] * 5
        assert any(cell["root_anchors"][0][3] for cell in cells)
        assert any(cell["root_anchors"][0][4] for cell in cells)
        jsonschema.Draft202012Validator(
            json.loads((SCHEMAS / "song_program_0_2.schema.json").read_text())
        ).validate(program)
    assert first["materials"] != second["materials"]


def test_trial_sounds_5d_high_axes_and_checks_pcm() -> None:
    _, project, wav, report = generate(0)
    jsonschema.Draft202012Validator(
        json.loads((SCHEMAS / "arrangement_project_1_3_5d.schema.json").read_text())
    ).validate(project)
    roots = [chord["anchor_vector"] for chord in project["resolved_chords"]]
    assert any(vector[3] for vector in roots)
    assert any(vector[4] for vector in roots)
    assert report["pcm"]["status"] == "checked"
    assert report["pcm"]["nonzero_samples"] > 0 and wav[:4] == b"RIFF"
    assert len(report["section_root_reconciliation"]) == 4
    assert all(row["root_matched"] for row in report["section_root_reconciliation"])
    assert report["dictionary_variant_bound"] is False
