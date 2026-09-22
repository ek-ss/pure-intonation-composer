from __future__ import annotations

import importlib.util
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_composition_viability.py"
SPEC = importlib.util.spec_from_file_location("audit_composition_viability", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_candidate_audit_exposes_proxy_pass_failures() -> None:
    program = {
        "form": [
            {"id": "s0", "role": "outro"},
            {"id": "s1", "role": "build"},
        ]
    }
    project = {
        "clock": {"beats_per_bar": 4, "ticks_per_beat": 480},
        "form": [
            {"id": "s0", "role": "outro"},
            {"id": "s1", "role": "build"},
        ],
        "tracks": [
            {"id": "h", "role": "harmony"},
            {"id": "b", "role": "bass"},
        ],
        "events": [
            {
                "kind": "note",
                "track_id": "h",
                "section_id": "s0",
                "start_tick": 0,
                "ratio": "1/1",
            },
            {
                "kind": "note",
                "track_id": "h",
                "section_id": "s1",
                "start_tick": 1920,
                "ratio": "1/1",
            },
            {
                "kind": "note",
                "track_id": "b",
                "section_id": "s1",
                "start_tick": 2880,
                "ratio": "1/2",
            },
        ],
    }

    result = MODULE.audit_candidate(7, program, project, {"archive_eligible": True})

    assert result["current_archive_eligible"] is True
    assert result["form_transition_diagnostics"] == {
        "intro_after_first": 0,
        "outro_before_last": 1,
        "final_before_nonterminal_section": 0,
        "build_without_immediate_release": 1,
    }
    assert result["foreground_diagnostics"]["melody_event_count"] == 0
    assert result["harmony_diagnostics"]["static_section_pitch_set"] is True
    assert result["rhythm_diagnostics"]["second_half_of_bar_onset_basis_points"] == 3333


def test_form_diagnostics_accepts_basic_terminal_arc() -> None:
    assert MODULE._form_diagnostics(
        ["intro", "verse", "build", "drop", "final", "outro"]
    ) == {
        "intro_after_first": 0,
        "outro_before_last": 0,
        "final_before_nonterminal_section": 0,
        "build_without_immediate_release": 0,
    }
