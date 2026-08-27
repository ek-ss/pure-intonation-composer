from fractions import Fraction

from fastapi.testclient import TestClient

from app.composition.explorer import _nearest_scale_degree, _root_target_semitones
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
        "/fractional-pop-composer": "/fractional-pop-composer",
        "/jpop-composer": "/jpop-composer",
        "/kawaii-future-pop": "/kawaii-future-pop",
        "/composition-explorer": "/composition-explorer",
        "/compose/bohlen-pierce": "/compose/bohlen-pierce",
        "/compose/mixed-meter-drums": "/compose/mixed-meter-drums",
        "/midi-toolkit": "/midi-toolkit",
    }
    for page, current in pages.items():
        response = client.get(page)
        assert response.status_code == 200
        for destination in set(pages.values()) - {current}:
            assert f'href="{destination}"' in response.text
        assert 'href="/docs"' in response.text


def test_experimental_composition_workbench_pages() -> None:
    bp_page = client.get("/compose/bohlen-pierce")
    assert bp_page.status_code == 200
    for control in ("bp-scale-generate", "bp-pitch-canvas", "bp-chord-search", "bp-progression-generate", "bp-compose-generate", "bp-midi", "bp-wav", "bp-scala"):
        assert f'id="{control}"' in bp_page.text
    bp_script = client.get("/static/bohlen_pierce.js")
    assert bp_script.status_code == 200
    assert "/api/bp/chords/search" in bp_script.text
    assert "/api/bp/compose/generate" in bp_script.text

    mixed_page = client.get("/compose/mixed-meter-drums")
    assert mixed_page.status_code == 200
    for control in ("mm-pattern-grid", "mm-custom-meters", "mm-track-list", "mm-timeline-canvas", "mm-midi", "mm-wav", "mm-transfer", "mm-transfer-explorer"):
        assert f'id="{control}"' in mixed_page.text
    mixed_script = client.get("/static/mixed_meter_drums.js")
    assert mixed_script.status_code == 200
    assert "/api/rhythm/mixed-meter/generate" in mixed_script.text
    assert "mixed-meter-compose-timeline" in mixed_script.text
    assert "mixed-meter-composition-explorer-project" in mixed_script.text
    assert "mixed-meter-compose-timeline" in client.get("/static/app.js").text


def test_composition_explorer_page_and_profiles() -> None:
    page = client.get("/composition-explorer")
    assert page.status_code == 200
    assert "Composition Explorer" in page.text
    for control in (
        "explorer-style",
        "explorer-style-mix",
        "explorer-mix-pop",
        "explorer-mix-jpop",
        "explorer-mix-kawaii",
        "explorer-instrument-list",
        "explorer-candidates",
        "explorer-cluster-count",
        "explorer-generate",
        "explorer-cluster-grid",
        "explorer-form-canvas",
        "explorer-like",
        "explorer-dislike",
        "explorer-midi",
        "explorer-mixed-enabled",
        "explorer-mixed-source",
        "explorer-mixed-integration",
        "explorer-mixed-pattern",
        "explorer-mixed-import",
    ):
        assert f'id="{control}"' in page.text
    script = client.get("/static/composition_explorer.js")
    assert script.status_code == 200
    assert "/api/composition-explorer/explore" in script.text
    assert "/api/compose/vital-pack/midi" in script.text
    assert "style_mix" in script.text
    assert "mixed_meter" in script.text
    assert "mixed-meter-composition-explorer-project" in script.text
    assert "time_signatures" in script.text
    assert "pure-intonation.composition-explorer-feedback" in script.text
    profiles = client.get("/api/composition-explorer/profiles")
    assert profiles.status_code == 200
    payload = profiles.json()
    assert len(payload["instruments"]) == 22
    assert payload["style_defaults"]["kawaii_fractional_future_pop"][-1] == "PI21"
    assert payload["styles"]["mixed"] == "Mixed Fractional Style"
    assert "PI22" in payload["style_defaults"]["mixed"]
    piano = next(profile for profile in payload["instruments"] if profile["id"] == "PI22")
    assert piano["roles"][:2] == ["keys", "harmony"]
    assert piano["preset_file"] == "PI 22 Fractional Piano.vital"
    assert "PI22" in payload["style_defaults"]["fractional_pop"]


def test_midi_creator_toolkit_page_contract() -> None:
    page = client.get("/midi-toolkit")
    assert page.status_code == 200
    assert "MIDI Creator Toolkit" in page.text
    for control in (
        "midi-toolkit-connect",
        "midi-toolkit-input",
        "midi-toolkit-record",
        "midi-toolkit-keyboard",
        "midi-toolkit-roll",
        "midi-toolkit-process",
        "midi-toolkit-scale-library",
        "midi-toolkit-scale-generate",
        "midi-toolkit-prime-basis",
        "midi-toolkit-exponent-limit",
        "midi-toolkit-thru-tuning",
        "midi-toolkit-pitch-circle",
        "midi-toolkit-circle-mode",
        "midi-toolkit-circle-legend",
        "midi-toolkit-midi",
        "midi-toolkit-json",
        "midi-toolkit-send-motif",
        "midi-toolkit-send-vital",
    ):
        assert f'id="{control}"' in page.text
    script = client.get("/static/midi_toolkit.js")
    assert script.status_code == 200
    assert "requestMIDIAccess" in script.text
    assert "/api/midi-toolkit/process" in script.text
    assert "/api/export/midi" in script.text
    assert "/api/prime-limit/explore" in script.text
    assert "white_keys_scale" in script.text
    assert "midi-toolkit-motif-transfer" in script.text
    assert 'THIRD_HARMONIC_COLOR = "#f49ad1"' in script.text
    assert "circlePoint(note.ratio * 3" in script.text
    motif_script = client.get("/static/motif_development.js")
    assert "midi-toolkit-motif-transfer" in motif_script.text


def test_composition_explorer_style_targets_are_12_tet_intervals() -> None:
    twelve_tet = tuple(
        Fraction(2 ** (step / 12)).limit_denominator(1_000_000)
        for step in range(12)
    )
    twenty_four_tet = tuple(
        Fraction(2 ** (step / 24)).limit_denominator(1_000_000)
        for step in range(24)
    )

    target_semitones = _root_target_semitones("fractional_pop", "verse", 2)
    target_ratio = 2 ** (target_semitones / 12)

    assert target_semitones == 5
    assert _nearest_scale_degree(twelve_tet, target_ratio) == 5
    assert _nearest_scale_degree(twenty_four_tet, target_ratio) == 10


def test_composition_explorer_mixes_styles_by_normalized_weight() -> None:
    weights = {
        "fractional_pop": 0.25,
        "fractional_jpop": 0.25,
        "kawaii_fractional_future_pop": 0.5,
    }
    assert _root_target_semitones("mixed", "drop", 1, weights) == 4.5

    request = {
        "style": "mixed",
        "style_mix": {
            "fractional_pop": 0.5,
            "fractional_jpop": 0.5,
            "kawaii_fractional_future_pop": 1,
        },
        "seed": 4812,
        "candidate_count": 4,
        "cluster_count": 2,
        "length_bars": 24,
        "instrument_palette": [],
    }
    first = client.post("/api/composition-explorer/explore", json=request)
    second = client.post("/api/composition-explorer/explore", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    assert result["style_mix"] == weights
    assert "PI01" in {profile["id"] for profile in result["instrument_profiles"]}
    assert "PI17" in {profile["id"] for profile in result["instrument_profiles"]}
    for song in result["representatives"]:
        assert song["genome"]["style_mix"] == weights
        assert song["metadata"]["form_style"] in weights
        assert {
            section["form_style"] for section in song["sections"]
        } == {song["metadata"]["form_style"]}
        assert all("style_target_ratio" in chord for chord in song["harmony"])

    invalid = client.post(
        "/api/composition-explorer/explore",
        json={
            "style": "mixed",
            "style_mix": {
                "fractional_pop": 0,
                "fractional_jpop": 0,
                "kawaii_fractional_future_pop": 0,
            },
        },
    )
    assert invalid.status_code == 422


def test_instrument_first_composition_exploration_is_clustered_and_deterministic() -> None:
    request = {
        "style": "kawaii_fractional_future_pop",
        "seed": 42810,
        "candidate_count": 8,
        "cluster_count": 3,
        "tempo_bpm": 150,
        "length_bars": 32,
        "base_frequency": 220,
        "scale_ratios": ["1/1", "9/8", "6/5", "5/4", "4/3", "3/2", "13/8", "5/3", "7/4"],
        "instrument_palette": [
            {"id": instrument_id}
            for instrument_id in (
                "PI21",
                "PI20",
                "PI19",
                "PI18",
                "PI17",
                "PI12",
                "PI11",
                "PI10",
                "PI09",
                "PI06",
            )
        ],
        "missing_role_policy": "warn",
        "form_temperature": 0.8,
        "harmony_temperature": 0.8,
        "part_temperature": 0.7,
        "rhythm_temperature": 0.7,
    }
    first = client.post("/api/composition-explorer/explore", json=request)
    second = client.post("/api/composition-explorer/explore", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    assert result["candidate_count"] == 8
    assert result["cluster_count"] == 3
    assert len(result["representatives"]) == 3
    assert sum(cluster["size"] for cluster in result["clusters"]) == 8
    assert "No bass preset" in result["warnings"][0]
    assert len(
        {
            tuple((section["role"], section["bars"]) for section in candidate["sections"])
            for candidate in result["candidates"]
        }
    ) >= 2
    assert len(
        {
            tuple(slot["root_degree"] for slot in song["harmony"])
            for song in result["representatives"]
        }
    ) == 3
    selected = {item["id"] for item in request["instrument_palette"]}
    for song in result["representatives"]:
        assert song["events"]
        assert {event["instrument_id"] for event in song["events"]} <= selected
        assert 0 <= song["scores"]["overall"] <= 1
        assert song["genome"]["component_seeds"]["form"]
        assert any(item["instrument_id"] == "PI18" for item in song["assignments"])
    representative = result["representatives"][0]
    midi = client.post(
        "/api/compose/vital-pack/midi",
        json={
            "events": representative["events"],
            "tempo_bpm": representative["metadata"]["tempo_bpm"],
            "base_frequency": representative["metadata"]["base_frequency"],
        },
    )
    assert midi.status_code == 200
    assert midi.headers["content-type"] == "audio/midi"
    assert midi.content.startswith(b"MThd")


def test_composition_explorer_component_locks_and_bass_substitution() -> None:
    response = client.post(
        "/api/composition-explorer/explore",
        json={
            "style": "fractional_pop",
            "seed": 711,
            "candidate_count": 6,
            "cluster_count": 2,
            "length_bars": 32,
            "instrument_palette": [{"id": "PI18"}, {"id": "PI19"}, {"id": "PI09"}],
            "missing_role_policy": "substitute",
            "locked_components": ["form"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    form_seeds = {candidate["genome"]["component_seeds"]["form"] for candidate in result["candidates"]}
    assert len(form_seeds) == 1
    forms = {tuple(candidate["section_roles"]) for candidate in result["candidates"]}
    assert len(forms) == 1
    assert any("root support" in warning for warning in result["warnings"])
    assert any(
        item["part_role"] == "bass" and item["instrument_id"] == "PI18"
        for song in result["representatives"]
        for item in song["assignments"]
    )


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
    assert (
        'src="/static/harmonic_pitch_circle.js?v=20260727-harmonic-circle-transpose-5"'
        in response.text
    )
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
    assert (
        len(
            {
                event["time_delta_beats"]
                for event in composition["events"]
                if "time_delta_beats" in event
            }
        )
        > 2
    )
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
            "prime_progression": [
                {
                    "id": "chord-21",
                    "tones": [
                        {"representative": {"normalized_ratio": "1/1"}},
                        {"representative": {"normalized_ratio": "7/6"}},
                        {"representative": {"normalized_ratio": "3/2"}},
                    ],
                },
                {
                    "id": "chord-22",
                    "tones": [
                        {"representative": {"normalized_ratio": "1/1"}},
                        {"representative": {"normalized_ratio": "5/4"}},
                        {"representative": {"normalized_ratio": "3/2"}},
                    ],
                },
            ],
            "function_chord_ids": {
                "T": ["chord-21", "chord-22"],
                "S": ["chord-21", "chord-22"],
                "D": ["chord-21", "chord-22"],
            },
        },
    )
    assert imported.status_code == 200
    assert {chord["id"] for chord in imported.json()["chords"]} <= {"chord-21", "chord-22"}
    midi = client.post(
        "/api/minimal-functional/midi",
        json={
            "notes": [{"ratio": "3/2", "start_beats": 0, "duration_beats": 1}],
            "drums": [{"note": 36, "start_beat": 0, "velocity": 100}],
        },
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
    assert 'id="vital-tonal-character"' in page.text
    assert 'id="vital-mode-strength"' in page.text
    assert 'id="vital-progression-contrast"' in page.text
    assert 'id="vital-piano-enabled"' in page.text
    assert 'id="vital-piano-mode"' in page.text
    assert 'id="vital-piano-activity"' in page.text
    assert 'id="vital-piano-density"' in page.text
    assert 'id="vital-piano-pack"' in page.text
    assert 'id="vital-drum-pack"' in page.text
    profiles = client.get("/api/instruments/vital-pack")
    assert profiles.status_code == 200
    assert len(profiles.json()["instruments"]) == 13
    assert any(
        profile["id"] == "PI22" and profile["role"] == "piano_material"
        for profile in profiles.json()["instruments"]
    )
    piano_preset = client.get("/static/vital_presets/PI%2022%20Fractional%20Piano.vital")
    assert piano_preset.status_code == 200
    piano_payload = piano_preset.json()
    assert piano_payload["preset_name"] == "PI 22 Fractional Piano"
    assert piano_payload["preset_style"] == "Keys"
    assert piano_payload["settings"]["osc_1_unison_voices"] == 1
    assert piano_payload["settings"]["osc_2_transpose"] == 12
    assert piano_payload["settings"]["velocity_track"] > 0
    piano_pack = client.get("/static/vital_presets/PI%20Fractional%20Piano.zip")
    assert piano_pack.status_code == 200
    assert piano_pack.content.startswith(b"PK")
    drum_profiles = {
        profile["id"]: profile
        for profile in profiles.json()["instruments"]
        if profile["id"] in {"PI09", "PI10", "PI11", "PI12"}
    }
    assert set(drum_profiles) == {"PI09", "PI10", "PI11", "PI12"}
    assert all(profile["tuning_policy"] == "fixed_drum_note" for profile in drum_profiles.values())
    for filename in (
        "PI%2009%20Pop%20Kick.vital",
        "PI%2010%20Pop%20Snare.vital",
        "PI%2011%20Pop%20Closed%20Hat.vital",
        "PI%2012%20Pop%20Perc.vital",
    ):
        preset = client.get(f"/static/vital_presets/{filename}")
        assert preset.status_code == 200
        assert preset.json()["preset_style"] == "Drums"
    drum_pack = client.get("/static/vital_presets/PI%20Vital%20Pop%20Drums.zip")
    assert drum_pack.status_code == 200
    assert drum_pack.content.startswith(b"PK")
    response = client.post(
        "/api/compose/vital-pack",
        json={"seed": 9, "length_bars": 16, "preset_mode": "adaptive"},
    )
    assert response.status_code == 200
    plan = response.json()
    assert sum(section["bars"] for section in plan["sections"]) == 16
    assert any(event["instrument_id"] == "PI05" for event in plan["events"])
    assert {"PI09", "PI10", "PI11", "PI12"} <= {event["instrument_id"] for event in plan["events"]}
    piano_events = [event for event in plan["events"] if event["instrument_id"] == "PI22"]
    assert piano_events
    assert all(event["articulation"] == "piano_scale_run" for event in piano_events)
    assert plan["quality"]["piano_run_notes"] == len(piano_events)
    assert plan["reaper_manifest"]["tuning_control_track"] == 15
    assert all(
        track["preset_file"].endswith(".vital")
        for track in plan["reaper_manifest"]["tracks"]
        if track["instrument_id"] in {"PI09", "PI10", "PI11", "PI12"}
    )
    assert plan["mts_timeline"]
    assert plan["sidechain_envelope"]
    assert plan["quality"]["bass_mono_ok"]
    assert all(4 <= len(section["active_instruments"]) <= 7 for section in plan["sections"])
    major = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 32,
            "tonal_character": "major",
            "mode_strength": 1,
            "progression_contrast": 1,
        },
    ).json()
    minor = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 32,
            "tonal_character": "minor",
            "mode_strength": 1,
            "progression_contrast": 1,
        },
    ).json()
    assert major["metadata"]["tonal_character"] == "major"
    assert minor["metadata"]["tonal_character"] == "minor"
    assert major["quality"]["harmony_major_ratio"] == 1
    assert minor["quality"]["harmony_minor_ratio"] == 1
    assert any(chord["degree"] == "I" and "5/4" in chord["tones"] for chord in major["harmony"])
    assert any(chord["degree"] == "i" and "6/5" in chord["tones"] for chord in minor["harmony"])
    assert [item["tones"] for item in major["harmony"]] != [
        item["tones"] for item in minor["harmony"]
    ]
    low_contrast = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 32,
            "tonal_character": "major",
            "mode_strength": 1,
            "progression_contrast": 0,
        },
    ).json()
    assert (
        major["quality"]["harmony_variety_score"] > low_contrast["quality"]["harmony_variety_score"]
    )
    piano_off = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 16,
            "piano_run_enabled": False,
        },
    ).json()
    assert not any(event["instrument_id"] == "PI22" for event in piano_off["events"])
    dense_piano = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 16,
            "piano_run_activity": 1,
            "piano_run_density": 1,
        },
    ).json()
    sparse_piano = client.post(
        "/api/compose/vital-pack",
        json={
            "seed": 9,
            "length_bars": 16,
            "piano_run_activity": 1,
            "piano_run_density": 0,
        },
    ).json()
    assert dense_piano["quality"]["piano_run_notes"] > sparse_piano["quality"]["piano_run_notes"]
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
    assert rhythm.json()["replace_instruments"] == ["PI09", "PI10", "PI11", "PI12"]
    midi = client.post(
        "/api/compose/vital-pack/midi", json={"tempo_bpm": 150, "events": plan["events"]}
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_fractional_pop_composer_page() -> None:
    page = client.get("/fractional-pop-composer")
    assert page.status_code == 200
    assert "Fractional Pop Composer" in page.text
    for control_id in (
        "fractional-pop-scale",
        "fractional-pop-color",
        "fractional-pop-performance",
        "fractional-pop-generate",
        "fractional-pop-circle",
        "fractional-pop-root-variety",
        "fractional-pop-progression",
        "fractional-pop-parts",
        "fractional-pop-midi",
        "fractional-pop-wav",
        "fractional-pop-json",
        "fractional-pop-drum-pack",
    ):
        assert f'id="{control_id}"' in page.text
    script = client.get("/static/fractional_pop_composer.js")
    assert script.status_code == 200
    assert 'genre_profile: "pop"' in script.text
    assert '"/api/arrange/generate"' in script.text
    assert '"/api/arrange/midi"' in script.text
    assert '"/api/arrange/render"' in script.text
    assert "PI09 Pop Kick" in script.text
    assert "PI12 Pop Perc" in script.text
    assert "Download .vital" in script.text


def test_fractional_jpop_composer_generation_and_assets() -> None:
    page = client.get("/jpop-composer")
    assert page.status_code == 200
    assert "Fractional J-Pop Composer" in page.text
    for control_id in (
        "jpop-cycles",
        "jpop-vocal",
        "jpop-shift",
        "jpop-form",
        "jpop-progression",
        "jpop-vocal-roll",
        "jpop-midi",
        "jpop-json",
    ):
        assert f'id="{control_id}"' in page.text
    script = client.get("/static/jpop_composer.js")
    assert script.status_code == 200
    assert 'fetch("/api/compose/jpop"' in script.text
    assert 'fetch("/api/compose/vital-pack/midi"' in script.text
    assert "PI16 Vocal Guide" in script.text

    request = {
        "seed": 81301,
        "tempo_bpm": 118,
        "cycles": 2,
        "base_frequency": 220,
        "vocal_activity": 0.78,
        "chorus_shift_depth": 1,
    }
    response = client.post("/api/compose/jpop", json=request)
    assert response.status_code == 200
    plan = response.json()
    assert plan["metadata"]["length_bars"] == 60
    assert {section["role"] for section in plan["sections"]} >= {
        "a_melody",
        "b_melody",
        "chorus",
    }

    def reduced(value: Fraction) -> Fraction:
        while value < 1:
            value *= 2
        while value >= 2:
            value /= 2
        return value

    for chord in plan["harmony"]:
        root = Fraction(chord["root_ratio"])
        second = Fraction(chord["tones"][1])
        if chord["section_role"] == "a_melody":
            assert chord["rule"] == "pure-fifth-stack"
            assert reduced(second / root) == Fraction(3, 2)
        elif chord["section_role"] == "b_melody":
            assert chord["rule"] == "pure-minor-third"
            assert reduced(second / root) == Fraction(6, 5)
        elif chord["section_role"] == "chorus":
            assert chord["rule"] == "13-limit-fifth-shift"
            assert reduced(second / root) == Fraction(3, 2)
    chorus = [item for item in plan["harmony"] if item["section_role"] == "chorus"]
    assert any(item["lattice_vector"]["13"] for item in chorus)
    assert plan["quality"]["a_melody_pure_fifth_bars"] == 16
    assert plan["quality"]["vocal_rest_bars"] > 0
    vocal = [event for event in plan["events"] if event["instrument_id"] == "PI16"]
    assert vocal
    assert all(event["ratio"] and event["lyric"] for event in vocal)
    assert client.post("/api/compose/jpop", json=request).json() == plan

    midi = client.post(
        "/api/compose/vital-pack/midi",
        json={
            "events": plan["events"],
            "tempo_bpm": plan["metadata"]["tempo_bpm"],
            "base_frequency": plan["metadata"]["base_frequency"],
        },
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")
    for number, style in ((13, "Keys"), (14, "Pluck"), (15, "Lead"), (16, "Lead")):
        filename = {
            13: "Fifth%20Keys",
            14: "Minor%20Third%20Pluck",
            15: "13-Limit%20Chorus%20Lead",
            16: "Vocal%20Guide",
        }[number]
        preset = client.get(f"/static/vital_presets/PI%20{number}%20{filename}.vital")
        assert preset.status_code == 200
        assert preset.json()["preset_style"] == style
    pack = client.get("/static/vital_presets/PI%20JPop%20Vital%20Instruments.zip")
    assert pack.status_code == 200
    assert pack.content.startswith(b"PK")
    assert client.post("/api/compose/jpop", json={"chorus_shift_depth": 3}).status_code == 422


def test_kawaii_fractional_future_pop_generation_and_assets() -> None:
    page = client.get("/kawaii-future-pop")
    assert page.status_code == 200
    assert "Kawaii Fractional Future Pop" in page.text
    for control_id in (
        "kfp-scale",
        "kfp-minimal",
        "kfp-drop",
        "kfp-vocal",
        "kfp-phase",
        "kfp-vocal-style",
        "kfp-form",
        "kfp-circle",
        "kfp-roll",
        "kfp-midi",
        "kfp-json",
    ):
        assert f'id="{control_id}"' in page.text
    script = client.get("/static/kawaii_future_pop.js")
    assert script.status_code == 200
    assert 'fetch("/api/compose/kawaii-future-pop"' in script.text
    assert 'fetch("/api/compose/vital-pack/midi"' in script.text
    assert "PI21 Sparkle Bell" in script.text

    request = {
        "seed": 260801,
        "tempo_bpm": 154,
        "cycles": 1,
        "base_frequency": 220,
        "scale_ratios": [
            "1/1",
            "9/8",
            "6/5",
            "5/4",
            "4/3",
            "3/2",
            "13/8",
            "5/3",
            "7/4",
        ],
        "minimalism": 0.68,
        "drop_intensity": 0.86,
        "vocal_activity": 0.72,
        "phase_shift_steps": 1,
        "vocal_style": "hooky",
    }
    response = client.post("/api/compose/kawaii-future-pop", json=request)
    assert response.status_code == 200
    plan = response.json()
    assert plan["metadata"]["length_bars"] == 44
    assert [section["role"] for section in plan["sections"]] == [
        "intro",
        "verse",
        "pre",
        "drop",
        "minimal",
        "drop",
        "outro",
    ]
    assert plan["scale"]["prime_limit"] == 13
    assert plan["quality"]["minimal_bars"] == 8
    assert plan["quality"]["drop_bars"] == 16
    assert plan["quality"]["drop_three_voice_bars"] == 8
    assert plan["quality"]["maximum_drop_tension"] == 0.68
    assert plan["quality"]["sidechain_triggers"] > 0
    assert plan["quality"]["vocal_rest_bars"] > 0
    assert plan["minimal_process"]["phase_shift_beats"] == 0.25
    minimal_events = [event for event in plan["events"] if event["instrument_id"] == "PI20"]
    assert {event["phase_lane"] for event in minimal_events} == {"A", "B"}
    assert any(event["instrument_id"] == "PI19" for event in plan["events"])
    assert any(event["instrument_id"] == "PI18" for event in plan["events"])
    assert any(event["instrument_id"] == "PI21" for event in plan["events"])
    for section in (item for item in plan["sections"] if item["role"] == "drop"):
        chords = [chord for chord in plan["harmony"] if chord["section_id"] == section["id"]]
        assert [chord["voice_count"] for chord in chords] == [3, 3, 3, 3, 4, 4, 4, 4]
        assert [chord["voicing_stage"] for chord in chords] == [
            "triad-entry",
            "triad-entry",
            "triad-open",
            "triad-open",
            "four-voice-open",
            "four-voice-open",
            "four-voice-color",
            "four-voice-color",
        ]
        tensions = [chord["tension"] for chord in chords]
        assert tensions == sorted(tensions)

    def pitch_class(value: str) -> Fraction:
        ratio = Fraction(value)
        while ratio < 1:
            ratio *= 2
        while ratio >= 2:
            ratio /= 2
        return ratio

    scale = {pitch_class(value) for value in plan["scale"]["ratios"]}
    assert all(pitch_class(event["ratio"]) in scale for event in plan["events"] if "ratio" in event)
    assert client.post("/api/compose/kawaii-future-pop", json=request).json() == plan

    midi = client.post(
        "/api/compose/vital-pack/midi",
        json={
            "events": plan["events"],
            "tempo_bpm": plan["metadata"]["tempo_bpm"],
            "base_frequency": plan["metadata"]["base_frequency"],
        },
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")
    presets = {
        17: ("Candy%20Pluck", "Pluck"),
        18: ("Future%20Chord%20Stack", "Synth"),
        19: ("Fractional%20Vocal%20Guide", "Lead"),
        20: ("Minimal%20Pulse", "Sequence"),
        21: ("Sparkle%20Bell", "Bell"),
    }
    for number, (filename, style) in presets.items():
        preset = client.get(f"/static/vital_presets/PI%20{number}%20{filename}.vital")
        assert preset.status_code == 200
        assert preset.json()["preset_style"] == style
    pack = client.get("/static/vital_presets/PI%20Kawaii%20Future%20Pop%20Vital%20Pack.zip")
    assert pack.status_code == 200
    assert pack.content.startswith(b"PK")
    invalid = client.post(
        "/api/compose/kawaii-future-pop",
        json={"scale_ratios": ["1/1", "2/1", "3/2", "5/4", "7/4", "9/8", "13/8"]},
    )
    assert invalid.status_code == 422


def test_motif_development_tree_can_arrange_vital_pack_song() -> None:
    motif_request = {
        "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
        "note_count": 6,
        "length_beats": 2,
        "max_polyphony": 3,
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
            "motif_activity": 0.7,
            "motif_rest_style": "breathing",
            "tonal_character": "minor",
            "mode_strength": 1,
            "progression_contrast": 0.9,
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
    motif_scale = set(plan["motif_arrangement"]["motif_scale"]["ratios"])
    assert len(motif_scale) >= 3
    assert set(plan["base_scale"]["ratios"]) == motif_scale
    assert all(set(chord["tones"]) <= motif_scale for chord in plan["harmony"])
    assert plan["quality"]["harmony_unique_chords"] >= 3
    assert plan["metadata"]["tonal_character"] == "minor"
    assert plan["quality"]["harmony_minor_ratio"] == 1
    assert "harmony_modal_third_error_mean_cents" in plan["quality"]
    assert plan["quality"]["motif_scale_harmony_coverage"] > 0.5
    assert plan["quality"]["motif_scale_event_conformance"] == 1
    assert plan["quality"]["piano_run_notes"] > 0
    assert plan["quality"]["piano_run_scale_conformance"] == 1

    def octave_class(value: str) -> Fraction:
        ratio = Fraction(value)
        while ratio < 1:
            ratio *= 2
        while ratio >= 2:
            ratio /= 2
        return ratio

    assert {
        octave_class(event["ratio"])
        for event in plan["events"]
        if event["instrument_id"] == "PI22"
    } <= {Fraction(value) for value in motif_scale}

    motif_piano_response = client.post(
        "/api/compose/motif-vital-pack",
        json={
            "seed": 37,
            "length_bars": 18,
            "section_count": 9,
            "anchor_chord": motif_request["anchor_chord"],
            "nodes": [*nodes, second_motif],
            "development_amount": 0.85,
            "motif_activity": 0.7,
            "motif_rest_style": "breathing",
            "piano_part_mode": "motif",
            "piano_run_activity": 1,
            "piano_run_density": 0.65,
        },
    )
    assert motif_piano_response.status_code == 200
    motif_piano_plan = motif_piano_response.json()
    motif_piano_events = [
        event for event in motif_piano_plan["events"] if event["instrument_id"] == "PI22"
    ]
    assert motif_piano_events
    assert motif_piano_plan["metadata"]["piano_part_mode"] == "motif"
    assert all(
        event["articulation"] == "piano_motif"
        and event["piano_material"] == "motif"
        and event.get("motif_id")
        for event in motif_piano_events
    )
    assert motif_piano_plan["quality"]["piano_motif_notes"] == len(motif_piano_events)
    assert motif_piano_plan["quality"]["piano_scale_run_notes"] == 0
    assert motif_piano_plan["quality"]["piano_run_scale_conformance"] == 1
    pitched_parts = [
        event for event in plan["events"] if event.get("ratio") and event["instrument_id"] != "PI04"
    ]

    def octave_class(value: str) -> str:
        ratio = Fraction(value)
        while ratio < 1:
            ratio *= 2
        while ratio >= 2:
            ratio /= 2
        return f"{ratio.numerator}/{ratio.denominator}"

    assert all(octave_class(event["ratio"]) in motif_scale for event in pitched_parts)
    assert plan["motif_arrangement"]["phase_shift"]["mode"] == "progressive"
    assert plan["motif_arrangement"]["phase_shift"]["schedule"]
    activity = plan["motif_arrangement"]["activity"]
    assert activity["style"] == "breathing"
    assert activity["full_rest_bars"] > 0
    assert any(not item["lane_a_active"] for item in activity["schedule"])
    assert plan["quality"]["motif_lead_max_consecutive_bars"] <= 3
    assert plan["quality"]["motif_breathing_ok"]
    lead_bars = {
        int(event["start_beat"]) // 4 + 1
        for event in plan["events"]
        if event["instrument_id"] == "PI04"
    }
    assert any(
        not item["lane_a_active"] and item["bar"] not in lead_bars for item in activity["schedule"]
    )
    assert any(
        event["instrument_id"] == "PI04" and event["articulation"] == "lead_motif"
        for event in plan["events"]
    )
    assert any(
        event["instrument_id"] == "PI04" and event.get("stack_voice", 0) > 0
        for event in plan["events"]
    )
    assert any(
        event["instrument_id"] == "PI05" and event["articulation"] == "bass_root"
        for event in plan["events"]
    )
    assert any(event.get("phase_lane") == "a" for event in plan["events"])
    assert any(event.get("phase_lane") == "b" for event in plan["events"])
    assert any(event.get("development_operations") for event in plan["events"])
    assert any(
        event["instrument_id"] in {"PI09", "PI10", "PI11", "PI12"} and event.get("motif_id")
        for event in plan["events"]
    )
    midi = client.post(
        "/api/compose/vital-pack/midi", json={"tempo_bpm": 150, "events": plan["events"]}
    )
    assert midi.status_code == 200
    assert midi.content.startswith(b"MThd")


def test_motif_generation_comparison_and_variation() -> None:
    page = client.get("/motif-development")
    assert page.status_code == 200
    assert "Motif Development" in page.text
    assert 'id="motif-circle"' in page.text
    assert 'id="motif-random-play"' in page.text
    assert 'id="motif-rest"' in page.text
    assert 'id="motif-polyphony"' in page.text
    assert 'id="motif-send-vital"' in page.text
    assert 'id="motif-select-visible"' in page.text
    script = client.get("/static/motif_development.js")
    assert script.status_code == 200
    assert "/api/motif/develop" in script.text
    assert "randomPlay" in script.text
    assert "renderCandidates" in script.text
    assert "await play()" in script.text
    assert "sendToVital" in script.text
    assert "compatibleHarmony" in script.text
    assert "Development harmony adapted to Prime basis" in script.text
    request = {
        "anchor_chord": ["1/1", "5/4", "3/2", "7/4"],
        "note_count": 6,
        "length_beats": 2,
        "register": [60, 84],
        "seed": 9,
        "rest_density": 0.28,
        "max_polyphony": 3,
    }
    first = client.post("/api/motif/generate", json=request)
    second = client.post("/api/motif/generate", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    motif = first.json()
    assert len(motif["notes"]) == 6
    assert motif["interval_signature"]
    assert motif["notes"][-1]["chord_relation"] == "exact"
    assert motif["polyphony_signature"]["maximum"] == 3
    assert all(
        1 + len(note["harmony_tones"]) <= request["max_polyphony"] for note in motif["notes"]
    )
    assert any(len(note["harmony_tones"]) == 2 for note in motif["notes"])
    monophonic = client.post(
        "/api/motif/generate",
        json={**request, "max_polyphony": 1, "candidate_count": 1},
    )
    assert monophonic.status_code == 200
    assert monophonic.json()["polyphony_signature"]["maximum"] == 1
    assert all(not note["harmony_tones"] for note in monophonic.json()["notes"])
    assert motif["rests"]
    assert motif["rhythm_signature"]["rest_ratio"] > 0
    assert motif["identity_features"]["terminal_role"] == "root"
    stable = client.post(
        "/api/motif/generate", json={**request, "terminal_policy": "stable", "candidate_count": 1}
    )
    assert stable.status_code == 200
    assert stable.json()["identity_features"]["terminal_role"] in {"root", "fifth"}
    colour = client.post(
        "/api/motif/generate", json={**request, "terminal_policy": "colour", "candidate_count": 1}
    )
    assert colour.status_code == 200
    assert colour.json()["identity_features"]["terminal_role"] in {"third", "colour"}
    for policy in ("nearest_anchor", "weighted", "random"):
        terminal = client.post(
            "/api/motif/generate", json={**request, "terminal_policy": policy, "candidate_count": 1}
        )
        assert terminal.status_code == 200
        assert terminal.json()["identity_features"]["terminal_role"] in {
            "root",
            "third",
            "fifth",
            "colour",
        }
    free = client.post(
        "/api/motif/generate", json={**request, "terminal_policy": "free", "candidate_count": 1}
    )
    assert free.status_code == 200
    assert free.json()["identity_features"]["terminal_role"] == "free"
    exploration = client.post(
        "/api/motif/generate",
        json={
            **request,
            "candidate_count": 8,
            "evaluation_profile": "rhythmic",
            "rhythm_profile": "random_exploration",
        },
    )
    assert exploration.status_code == 200
    candidates = exploration.json()["candidates"]
    assert len(candidates) == 8
    assert exploration.json()["exploration"]["profile"] == "rhythmic"
    accepted = exploration.json()["exploration"]["accepted"]
    assert all(candidate["evaluation"]["passed_filters"] for candidate in candidates[:accepted])
    assert not any(candidate["evaluation"]["passed_filters"] for candidate in candidates[accepted:])
    assert candidates[:accepted] == sorted(
        candidates[:accepted], key=lambda item: item["evaluation"]["total"], reverse=True
    )
    assert {"harmony", "melody", "rhythm", "identity", "novelty", "complexity"} <= set(
        candidates[0]["evaluation"]["components"]
    )
    assert all("passed_filters" in candidate["evaluation"] for candidate in candidates)
    random_rhythm = client.post(
        "/api/motif/generate",
        json={**request, "rhythm_profile": "random_exploration"},
    )
    assert random_rhythm.status_code == 200
    random_notes = random_rhythm.json()["notes"]
    assert len({note["duration_beats"] for note in random_notes}) > 1
    assert sum(note["duration_beats"] for note in random_notes) < request["length_beats"]
    assert random_rhythm.json()["rhythm_signature"]["rests"]
    compare = client.post(
        "/api/motif/compare",
        json={
            "anchor_chord": request["anchor_chord"],
            "source_notes": motif["notes"],
            "target_notes": motif["notes"],
        },
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
    assert variation.json()["transformation_chain"] == [
        "lattice_transpose",
        "neighbour_substitution",
    ]
    assert variation.json()["distance_vector"]["absolute_monzo"] > 0
    development = client.post(
        "/api/motif/develop",
        json={
            "anchor_chord": request["anchor_chord"],
            "source_notes": motif["notes"],
            "harmony": [
                request["anchor_chord"],
                ["3/2", "15/8", "9/4"],
                request["anchor_chord"],
                request["anchor_chord"],
            ],
            "seed": 11,
        },
    )
    assert development.status_code == 200
    assert len(development.json()["motif_tree"]["nodes"]) == 4
    assert development.json()["events"]
    assert any(event["stack_voice"] > 0 for event in development.json()["events"])


def test_motif_generation_supports_selected_prime_basis() -> None:
    anchor = ["1/1", "3/2", "7/4", "13/8"]
    request = {
        "anchor_chord": anchor,
        "prime_basis": [3, 7, 13],
        "note_count": 6,
        "max_polyphony": 3,
        "length_beats": 2,
        "register": [60, 84],
        "max_lattice_radius": 2,
        "candidate_count": 4,
        "seed": 1313,
    }
    response = client.post("/api/motif/generate", json=request)
    assert response.status_code == 200
    motif = response.json()
    assert motif["prime_basis"] == [3, 7, 13]
    assert motif["monzo_basis"] == [2, 3, 7, 13]
    assert all(len(note["monzo"]) == 4 for note in motif["notes"])
    assert all(
        len(note["exponent_delta"]) == 3
        and sum(abs(value) for value in note["exponent_delta"]) <= 2
        for note in motif["notes"]
    )

    def uses_only_selected_primes(value: str) -> bool:
        ratio = Fraction(value)
        numerator, denominator = ratio.numerator, ratio.denominator
        for prime in (2, 3, 7, 13):
            while numerator % prime == 0:
                numerator //= prime
            while denominator % prime == 0:
                denominator //= prime
        return numerator == denominator == 1

    generated_ratios = [
        ratio for note in motif["notes"] for ratio in [note["ratio"], *note["harmony_tones"]]
    ]
    assert all(uses_only_selected_primes(ratio) for ratio in generated_ratios)
    development = client.post(
        "/api/motif/develop",
        json={
            "anchor_chord": anchor,
            "prime_basis": [3, 7, 13],
            "source_notes": motif["notes"],
            "harmony": [
                anchor,
                ["3/2", "7/4", "13/8"],
                ["1/1", "7/4", "13/8"],
                anchor,
            ],
            "section_roles": ["theme", "development", "climax", "recapitulation"],
            "seed": 1314,
        },
    )
    assert development.status_code == 200
    tree = development.json()
    assert tree["prime_basis"] == [3, 7, 13]
    assert all(uses_only_selected_primes(event["ratio"]) for event in tree["events"])
    vital = client.post(
        "/api/compose/motif-vital-pack",
        json={
            "seed": 1315,
            "length_bars": 8,
            "section_count": 3,
            "anchor_chord": anchor,
            "prime_basis": [3, 7, 13],
            "nodes": tree["motif_tree"]["nodes"],
        },
    )
    assert vital.status_code == 200
    vital_plan = vital.json()
    assert vital_plan["metadata"]["prime_basis"] == [3, 7, 13]
    assert vital_plan["motif_arrangement"]["prime_basis"] == [3, 7, 13]
    assert all(
        uses_only_selected_primes(event["ratio"])
        for event in vital_plan["events"]
        if event.get("ratio")
    )
    invalid_basis = client.post(
        "/api/motif/generate",
        json={**request, "prime_basis": [3, 9, 13]},
    )
    assert invalid_basis.status_code == 422
    outside_basis = client.post(
        "/api/motif/generate",
        json={**request, "anchor_chord": ["1/1", "3/2", "5/4"]},
    )
    assert outside_basis.status_code == 422
    incompatible_harmony = client.post(
        "/api/motif/develop",
        json={
            "anchor_chord": anchor,
            "prime_basis": [3, 7, 13],
            "source_notes": motif["notes"],
            "harmony": [
                ["1/1", "5/4", "3/2"],
                ["1/1", "5/4", "3/2"],
                ["1/1", "5/4", "3/2"],
                ["1/1", "5/4", "3/2"],
            ],
        },
    )
    assert incompatible_harmony.status_code == 422
    assert "outside prime_basis: 5" in incompatible_harmony.json()["detail"]


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
        json={
            "primes": [3, 5, 7],
            "exponent_limit": 1,
            "height_limit": 2,
            "tolerance_cents": 8,
            "target_count": 7,
        },
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
        json={
            "primes": [3, 5, 7],
            "exponent_limit": 1,
            "height_limit": 2,
            "tolerance_cents": 8,
            "target_count": 7,
            "tone_count": 3,
            "ranking_mode": "balanced",
            "root_vector": [1, 0, 0],
        },
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
    assert response.json()["transitions"] == [
        {"common_tones": 2, "johnson_distance": 1, "voice_leading_cents": 100.0}
    ]


def test_cps_is_octave_reduced() -> None:
    response = client.post("/api/cps", json={"factors": [1, 3, 5, 7], "choose": 2})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == [
        "35/32",
        "5/4",
        "21/16",
        "3/2",
        "7/4",
        "15/8",
    ]


def test_euler_fokker_has_divisors() -> None:
    response = client.post("/api/euler-fokker", json={"factors": [3, 5]})
    assert response.status_code == 200
    assert [pitch["ratio"] for pitch in response.json()["pitches"]] == ["1/1", "5/4", "3/2", "15/8"]


def test_ratio_analysis() -> None:
    response = client.post("/api/analyze-ratio", json={"ratio": "3/2"})
    assert response.status_code == 200
    assert response.json()["monzo"] == {"2": -1, "3": 1}
