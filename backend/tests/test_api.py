from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_root_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Pure Intonation Workbench" in response.text
    assert 'id="composition-roll"' in response.text
    assert 'id="lattice-chord-generate"' in response.text
    assert 'id="lattice-progression"' in response.text
    assert 'id="lattice-walk-compose"' in response.text
    assert 'id="lattice-keyboard"' in response.text
    assert 'id="lattice-keyboard-target"' in response.text
    assert "Lattice Keyboard" in response.text
    assert 'id="lattice-circle"' in response.text
    assert 'id="phase-panel"' in response.text
    assert "/static/app.js?v=20260727-lattice-page-2" in response.text
    assert 'id="compose-rhythm-apply"' in response.text
    assert 'id="compose-rhythm-native"' in response.text
    assert 'data-generator-role="harmony"' in response.text
    assert 'data-generator-role="bass"' in response.text
    assert 'data-generator-role="melody"' in response.text
    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "renderHarmonyStackOnCircle" in script.text
    assert "selectCompositionNode" in script.text
    assert "/api/exponent-lattice/chord" in script.text
    assert "/api/exponent-lattice/progression" in script.text
    assert "renderLatticeCircle" in script.text
    assert "latticeKeyboardIsTarget" in script.text
    assert "/api/compose/rhythm/apply" in script.text
    assert "/api/compose/rhythm/generate" in script.text
    assert "sendLatticeToCompose" in script.text
    assert 'const LATTICE_KEYS = "ASDFGHJKL;QWERTY"' in script.text
    assert client.get("/favicon.ico").status_code == 204


def test_primary_pages_link_to_every_other_workbench() -> None:
    pages = {
        "/": "/",
        "/lattice": "/lattice",
        "/harmonic-pitch-circle": "/harmonic-pitch-circle",
        "/prime-limit-explorer": "/prime-limit-explorer",
        "/minimal-functional-composer": "/minimal-functional-composer",
        "/motif-development": "/motif-development",
        "/vital-pack-composer": "/vital-pack-composer",
    }
    for page, current in pages.items():
        response = client.get(page)
        assert response.status_code == 200
        for destination in set(pages.values()) - {current}:
            assert f'href="{destination}"' in response.text
        assert 'href="/docs"' in response.text


def test_lattice_lab_page() -> None:
    response = client.get("/lattice")
    assert response.status_code == 200
    assert "Lattice Lab" in response.text
    assert 'id="pitch-circle"' in response.text
    assert 'id="progression-generate"' in response.text
    assert 'id="progression-minimal"' in response.text
    assert 'id="walk-minimal"' in response.text
    assert 'src="/static/lattice.js?v=20260728-lattice-minimal-transfer-1"' in response.text
    script = client.get("/static/lattice.js")
    assert script.status_code == 200
    assert '"/api/exponent-lattice/chord"' in script.text
    assert '"/api/exponent-lattice/walk"' in script.text
    assert "lattice-compose-harmonies" in script.text
    assert "minimalProgression" in script.text
    assert "startAudio" in script.text


def test_harmonic_pitch_circle_page() -> None:
    response = client.get("/harmonic-pitch-circle")
    assert response.status_code == 200
    assert "Harmonic Pitch Circle" in response.text
    assert 'id="harmonic-circle"' in response.text
    assert 'id="chord-buttons"' in response.text
    assert 'id="root-buttons"' in response.text
    assert 'id="chord-audition"' in response.text
    assert 'src="/static/harmonic_pitch_circle.js?v=20260727-harmonic-circle-transpose-5"' in response.text
    script = client.get("/static/harmonic_pitch_circle.js")
    assert script.status_code == 200
    assert "fifthSteps" in script.text
    assert "describeTransition" in script.text
    assert "auditionCurrentChord" in script.text
    assert "rootFrequency" in script.text


def test_minimal_functional_composer_page_and_generation() -> None:
    response = client.get("/minimal-functional-composer")
    assert response.status_code == 200
    assert "Minimal Functional Composer" in response.text
    assert 'id="minimal-form"' in response.text
    assert 'id="minimal-voice-lanes"' in response.text
    script = client.get("/static/minimal_functional_composer.js")
    assert script.status_code == 200
    assert "/api/minimal-functional/generate" in script.text
    response = client.post(
        "/api/minimal-functional/generate",
        json={
            "duration_bars": 16,
            "tempo_bpm": 96,
            "voice_count": 4,
            "seed": 9,
            "tuning": "7-limit",
            "climax_start": 0.60,
            "resolution_start": 0.76,
        },
    )
    assert response.status_code == 200
    composition = response.json()
    assert composition["metadata"]["tuning"] == "7-limit"
    assert len(composition["analysis"]) == 16
    assert composition["events"]
    assert any(event["time_delta_beats"] != 0 for event in composition["events"])
    assert len({event["time_delta_beats"] for event in composition["events"] if "time_delta_beats" in event}) > 2
    assert {chord["function"] for chord in composition["chords"]} <= {"T", "S", "D"}
    assert composition["analysis"][-1]["section"] == "coda"
    assert composition["analysis"][-1]["stability"] > composition["analysis"][-1]["tension"]
    assert {layer["id"] for layer in composition["drum_layers"]} == {"kick", "snare", "hat", "perc"}
    assert composition["drum_events"]
    invalid = client.post(
        "/api/minimal-functional/generate",
        json={"climax_start": 0.80, "resolution_start": 0.70},
    )
    assert invalid.status_code == 422
    twelve_tet = client.post(
        "/api/minimal-functional/generate",
        json={"duration_bars": 8, "tuning": "12-tet"},
    )
    assert twelve_tet.status_code == 200
    assert twelve_tet.json()["metadata"]["tuning"] == "12-tet"
    imported = client.post(
        "/api/minimal-functional/generate",
        json={
            "duration_bars": 8,
            "prime_progression": [{"id": "chord-21", "tones": [{"representative": {"normalized_ratio": "1/1"}}, {"representative": {"normalized_ratio": "7/6"}}, {"representative": {"normalized_ratio": "3/2"}}]}, {"id": "chord-22", "tones": [{"representative": {"normalized_ratio": "1/1"}}, {"representative": {"normalized_ratio": "5/4"}}, {"representative": {"normalized_ratio": "3/2"}}]}],
            "function_chord_ids": {"T": ["chord-21", "chord-22"], "S": ["chord-21", "chord-22"], "D": ["chord-21", "chord-22"]},
        },
    )
    assert imported.status_code == 200
    assert {chord["id"] for chord in imported.json()["chords"]} <= {"chord-21", "chord-22"}
    midi = client.post(
        "/api/minimal-functional/midi",
        json={"notes": [{"ratio": "3/2", "start_beats": 0, "duration_beats": 1}], "drums": [{"note": 36, "start_beat": 0, "velocity": 100}]},
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_vital_pack_composer_profiles_and_generation() -> None:
    page = client.get("/vital-pack-composer")
    assert page.status_code == 200
    assert "Vital Pack Composer" in page.text
    assert 'id="vital-tracks"' in page.text
    assert 'id="vital-use-motif"' in page.text
    assert 'id="vital-sections"' in page.text
    assert 'id="vital-development"' in page.text
    assert 'id="vital-phase-mode"' in page.text
    profiles = client.get("/api/instruments/vital-pack")
    assert profiles.status_code == 200
    assert len(profiles.json()["instruments"]) == 8
    response = client.post(
        "/api/compose/vital-pack",
        json={"seed": 9, "length_bars": 16, "preset_mode": "adaptive"},
    )
    assert response.status_code == 200
    plan = response.json()
    assert sum(section["bars"] for section in plan["sections"]) == 16
    assert any(event["instrument_id"] == "PI05" for event in plan["events"])
    assert any(event["instrument_id"] == "DRUMS" for event in plan["events"])
    assert plan["reaper_manifest"]["tuning_control_track"] == 11
    assert plan["mts_timeline"]
    assert plan["sidechain_envelope"]
    assert plan["quality"]["bass_mono_ok"]
    assert all(4 <= len(section["active_instruments"]) <= 7 for section in plan["sections"])
    compact_form = client.post(
        "/api/compose/vital-pack",
        json={"seed": 9, "length_bars": 16, "section_count": 5},
    )
    assert compact_form.status_code == 200
    assert len(compact_form.json()["sections"]) == 5
    assert sum(section["bars"] for section in compact_form.json()["sections"]) == 16
    invalid_section = client.post(
        "/api/compose/vital-pack/section",
        json={"seed": 9, "length_bars": 16, "section_count": 5, "section_index": 5},
    )
    assert invalid_section.status_code == 422
    section = client.post(
        "/api/compose/vital-pack/section",
        json={"seed": 9, "length_bars": 16, "section_index": 3, "scope": "harmony"},
    )
    assert section.status_code == 200
    assert section.json()["scope"] == "harmony"
    assert section.json()["tuning_timeline"]
    rhythm = client.post(
        "/api/compose/vital-pack/section",
        json={"seed": 9, "length_bars": 16, "section_index": 3, "scope": "rhythm"},
    )
    assert rhythm.status_code == 200
    assert rhythm.json()["replace_instruments"] == ["DRUMS"]
    midi = client.post("/api/compose/vital-pack/midi", json={"tempo_bpm": 150, "events": plan["events"]})
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_motif_development_tree_can_arrange_vital_pack_song() -> None:
    motif_request = {
        "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
        "note_count": 6,
        "length_beats": 2,
        "register": [60, 84],
        "seed": 29,
    }
    motif = client.post("/api/motif/generate", json=motif_request).json()
    development = client.post(
        "/api/motif/develop",
        json={
            "anchor_chord": motif_request["anchor_chord"],
            "source_notes": motif["notes"],
            "harmony": [
                ["1/1", "5/4", "3/2"],
                ["3/2", "15/8", "9/4"],
                ["4/3", "5/3", "2/1"],
                ["1/1", "5/4", "3/2"],
            ],
            "section_roles": ["theme", "build", "climax", "recapitulation", "coda"],
            "seed": 31,
        },
    )
    assert development.status_code == 200
    nodes = development.json()["motif_tree"]["nodes"]
    for node in nodes:
        node["source_motif_id"] = "motif-primary"
    second_motif = {
        **nodes[0],
        "id": "motif-secondary-theme",
        "source_motif_id": "motif-secondary",
    }
    response = client.post(
        "/api/compose/motif-vital-pack",
        json={
            "seed": 37,
            "length_bars": 18,
            "section_count": 9,
            "anchor_chord": motif_request["anchor_chord"],
            "nodes": [*nodes, second_motif],
            "development_amount": 0.85,
            "phase_shift_mode": "progressive",
            "phase_shift_beats": 0.5,
            "phase_shift_increment": 0.125,
        },
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["metadata"]["composition_source"] == "motif-development-tree"
    assert len(plan["motif_arrangement"]["section_assignments"]) == 9
    assert plan["quality"]["motif_provenance_ok"]
    assert plan["quality"]["source_motif_count"] == 2
    assert plan["quality"]["development_operation_count"] >= 3
    assert plan["motif_arrangement"]["phase_shift"]["mode"] == "progressive"
    assert plan["motif_arrangement"]["phase_shift"]["schedule"]
    assert any(event["instrument_id"] == "PI04" and event["articulation"] == "lead_motif" for event in plan["events"])
    assert any(event["instrument_id"] == "PI05" and event["articulation"] == "bass_root" for event in plan["events"])
    assert any(event.get("phase_lane") == "a" for event in plan["events"])
    assert any(event.get("phase_lane") == "b" for event in plan["events"])
    assert any(event.get("development_operations") for event in plan["events"])
    assert any(event["instrument_id"] == "DRUMS" and event.get("motif_id") for event in plan["events"])
    midi = client.post("/api/compose/vital-pack/midi", json={"tempo_bpm": 150, "events": plan["events"]})
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_motif_generation_comparison_and_variation() -> None:
    page = client.get("/motif-development")
    assert page.status_code == 200
    assert "Motif Development" in page.text
    assert 'id="motif-circle"' in page.text
    assert 'id="motif-random-play"' in page.text
    assert 'id="motif-send-vital"' in page.text
    assert 'id="motif-select-visible"' in page.text
    script = client.get("/static/motif_development.js")
    assert script.status_code == 200
    assert "/api/motif/develop" in script.text
    assert "randomPlay" in script.text
    assert "renderCandidates" in script.text
    assert "await play()" in script.text
    assert "sendToVital" in script.text
    request = {
        "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
        "note_count": 6,
        "length_beats": 2,
        "register": [60, 84],
        "seed": 9,
    }
    first = client.post("/api/motif/generate", json=request)
    second = client.post("/api/motif/generate", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    motif = first.json()
    assert len(motif["notes"]) == 6
    assert motif["interval_signature"]
    assert motif["notes"][-1]["chord_relation"] == "exact"
    assert motif["identity_features"]["terminal_role"] == "root"
    stable = client.post("/api/motif/generate", json={**request, "terminal_policy": "stable", "candidate_count": 1})
    assert stable.status_code == 200
    assert stable.json()["identity_features"]["terminal_role"] in {"root", "fifth"}
    colour = client.post("/api/motif/generate", json={**request, "terminal_policy": "colour", "candidate_count": 1})
    assert colour.status_code == 200
    assert colour.json()["identity_features"]["terminal_role"] in {"third", "colour"}
    for policy in ("nearest_anchor", "weighted", "random"):
        terminal = client.post("/api/motif/generate", json={**request, "terminal_policy": policy, "candidate_count": 1})
        assert terminal.status_code == 200
        assert terminal.json()["identity_features"]["terminal_role"] in {"root", "third", "fifth", "colour"}
    free = client.post("/api/motif/generate", json={**request, "terminal_policy": "free", "candidate_count": 1})
    assert free.status_code == 200
    assert free.json()["identity_features"]["terminal_role"] == "free"
    exploration = client.post(
        "/api/motif/generate",
        json={**request, "candidate_count": 8, "evaluation_profile": "rhythmic", "rhythm_profile": "random_exploration"},
    )
    assert exploration.status_code == 200
    candidates = exploration.json()["candidates"]
    assert len(candidates) == 8
    assert exploration.json()["exploration"]["profile"] == "rhythmic"
    accepted = exploration.json()["exploration"]["accepted"]
    assert all(candidate["evaluation"]["passed_filters"] for candidate in candidates[:accepted])
    assert not any(candidate["evaluation"]["passed_filters"] for candidate in candidates[accepted:])
    assert candidates[:accepted] == sorted(candidates[:accepted], key=lambda item: item["evaluation"]["total"], reverse=True)
    assert {"harmony", "melody", "rhythm", "identity", "novelty", "complexity"} <= set(candidates[0]["evaluation"]["components"])
    assert all("passed_filters" in candidate["evaluation"] for candidate in candidates)
    random_rhythm = client.post(
        "/api/motif/generate",
        json={**request, "rhythm_profile": "random_exploration"},
    )
    assert random_rhythm.status_code == 200
    random_notes = random_rhythm.json()["notes"]
    assert len({note["duration_beats"] for note in random_notes}) > 1
    assert sum(note["duration_beats"] for note in random_notes) == request["length_beats"]
    compare = client.post(
        "/api/motif/compare",
        json={"anchor_chord": request["anchor_chord"], "source_notes": motif["notes"], "target_notes": motif["notes"]},
    )
    assert compare.status_code == 200
    assert compare.json()["identity_retention"] == 1
    assert compare.json()["distance_vector"]["pitch_circle"] == 0
    variation = client.post(
        "/api/motif/variation",
        json={
            "anchor_chord": request["anchor_chord"],
            "source_notes": motif["notes"],
            "target_chord": ["3/2", "15/8", "9/4"],
            "formal_role": "development",
            "allowed_transformations": ["lattice_transpose", "neighbour_substitution"],
            "seed": 10,
        },
    )
    assert variation.status_code == 200
    assert variation.json()["transformation_chain"] == ["lattice_transpose", "neighbour_substitution"]
    assert variation.json()["distance_vector"]["absolute_monzo"] > 0
    development = client.post(
        "/api/motif/develop",
        json={
            "anchor_chord": request["anchor_chord"],
            "source_notes": motif["notes"],
            "harmony": [request["anchor_chord"], ["3/2", "15/8", "9/4"], request["anchor_chord"], request["anchor_chord"]],
            "seed": 11,
        },
    )
    assert development.status_code == 200
    assert len(development.json()["motif_tree"]["nodes"]) == 4
    assert development.json()["events"]


def test_prime_limit_explorer_page_and_search() -> None:
    response = client.get("/prime-limit-explorer")
    assert response.status_code == 200
    assert "Prime-Limit Harmonic Explorer" in response.text
    assert 'id="prime-circle"' in response.text
    script = client.get("/static/prime_limit_explorer.js")
    assert script.status_code == 200
    assert "/api/prime-limit/explore" in script.text
    assert "/api/prime-limit/chords" in script.text
    assert "/api/prime-limit/progression" in script.text
    assert "prime_limit_worker.js" in script.text
    assert "prime-lattice-circle" in response.text
    assert 'id="prime-candidate-limit"' in response.text
    assert 'id="prime-ranking-mode"' in response.text
    assert "syncPrimeAxes();" in script.text
    worker = client.get("/static/prime_limit_worker.js")
    assert worker.status_code == 200
    assert "/api/prime-limit/explore" in worker.text
    response = client.post(
        "/api/prime-limit/explore",
        json={"primes": [3, 5, 7], "exponent_limit": 1, "height_limit": 2, "tolerance_cents": 8, "target_count": 7},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == [3, 5, 7]
    assert data["point_count"] == 19
    assert len(data["scale"]) == 7
    assert data["metrics"]["min_gap_cents"] > 0


def test_prime_limit_chord_discovery_and_progression() -> None:
    response = client.post(
        "/api/prime-limit/chords",
        json={"primes": [3, 5, 7], "exponent_limit": 1, "height_limit": 2, "tolerance_cents": 8, "target_count": 7, "tone_count": 3, "ranking_mode": "balanced", "root_vector": [1, 0, 0]},
    )
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert candidates
    assert len(candidates[0]["tones"]) == 3
    assert candidates[0]["metrics"]["algorithm_version"] == "g12-chord-v1"
    assert candidates[0]["metrics"]["ranking_mode"] == "balanced"
    assert 0 <= candidates[0]["metrics"]["balanced_score"] <= 1
    assert candidates[0]["tones"][0]["representative"]["vector"] == [1, 0, 0]
    assert candidates[0]["tones"][0]["cents"] == 701.955
    response = client.post(
        "/api/prime-limit/progression",
        json={"chords": [[0, 300, 700], [0, 400, 700]]},
    )
    assert response.status_code == 200
    assert response.json()["transitions"] == [{"common_tones": 2, "johnson_distance": 1, "voice_leading_cents": 100.0}]


def test_cps_is_octave_reduced() -> None:
    response = client.post("/api/cps", json={"factors": [1, 3, 5, 7], "choose": 2})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == ["35/32", "5/4", "21/16", "3/2", "7/4", "15/8"]


def test_euler_fokker_has_divisors() -> None:
    response = client.post("/api/euler-fokker", json={"factors": [3, 5]})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == ["1/1", "5/4", "3/2", "15/8"]


def test_ratio_analysis() -> None:
    response = client.post("/api/analyze-ratio", json={"ratio": "3/2"})
    assert response.status_code == 200
    assert response.json()["monzo"] == {"2": -1, "3": 1}
