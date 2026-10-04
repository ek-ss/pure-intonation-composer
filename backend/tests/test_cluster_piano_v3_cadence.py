"""Tests for the piano v3 cadence clustering tool.

The module-scoped fixtures run the real generation path once per
(equave, crossing, seed) combination and write the artifacts to a shared
working directory; the individual tests then copy / tamper those artifacts and
exercise the fail-closed validation (including impact-report recomputation,
cross-equave binding, and forged-slot forgery), the graceful zero-success path,
the equave / crossing / register-lift separation, malformed-record tolerance,
identical-feature clamping, and the deterministic report.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from app.songprogram.search import canonical_bytes
from tools.cluster_piano_v3_cadence import (
    SCHEMA,
    clamp_clusters,
    distance_cadence,
    features,
    run,
    validate_success,
)
from tools.generate_piano_v3_cadence_trial import V3TrialFailure, generate_one


def _write_trial(
    equave: str, seed: int, directory, *, skip_wav: bool = True,
    register_lift_policy=None, crossing_match: str = "canonical",
    style_profile=None,
) -> None:
    """Run one seed and write its artifacts, mirroring the generation CLI."""
    from app.songprogram.style_profile import style_profile_hash

    directory.mkdir(parents=True, exist_ok=True)
    try:
        artifacts, _ = generate_one(
            equave, seed, skip_wav=skip_wav,
            register_lift_policy=register_lift_policy, crossing_match=crossing_match,
            style_profile=style_profile,
        )
        for name, payload in artifacts.items():
            (directory / name).write_bytes(payload)
    except V3TrialFailure as error:
        for name, payload in error.artifacts.items():
            (directory / name).write_bytes(payload)
        failure = {
            "schema": "cps.piano-v3-cadence-trial-failure",
            "schema_version": "1.2.0",
            "seed": seed,
            "equave": equave,
            "status": "failed",
            "stage": error.stage,
            "failure_code": getattr(error, "code", None) or type(error).__name__,
            "detail": str(error),
            "partial_artifacts": sorted(error.artifacts),
            "candidate_failures_counted": True,
            "style_profile": style_profile,
            "style_profile_hash": (
                style_profile_hash(style_profile) if style_profile is not None else None
            ),
        }
        (directory / "failure.json").write_bytes(canonical_bytes(failure))


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return tmp_path_factory.mktemp("v3cadence_cluster")


@pytest.fixture(scope="module")
def golden_cohort(workdir):
    """2/1 canonical: seed 0 fails at compile; seeds 4 and 5 succeed."""
    cohort = workdir / "golden"
    for seed in (0, 4, 5):
        _write_trial("2/1", seed, cohort / f"seed-{seed}")
    return cohort


@pytest.fixture(scope="module")
def tritave_success(workdir):
    """A single 3/1 canonical success (seed 0)."""
    directory = workdir / "tritave" / "seed-0"
    _write_trial("3/1", 0, directory)
    return directory


@pytest.fixture(scope="module")
def noncrossing_success(workdir):
    """A single 2/1 non_crossing success (seed 0)."""
    directory = workdir / "noncross" / "seed-0"
    _write_trial("2/1", 0, directory, crossing_match="non_crossing")
    return directory


@pytest.fixture(scope="module")
def lift_success(workdir):
    """A genuine 2/1 success generated with register lifts enabled (seed 4)."""
    from app.songprogram.sparse_variant import build_register_lift_policy

    directory = workdir / "lift" / "seed-4"
    _write_trial(
        "2/1", 4, directory,
        register_lift_policy=build_register_lift_policy(allow_lifts=True),
    )
    return directory


@pytest.fixture(scope="module")
def restrained_success(workdir):
    """A single 2/1 success generated with the restrained style (seed 4)."""
    from app.songprogram.style_profile import STYLE_PROFILES

    directory = workdir / "restrained" / "seed-4"
    _write_trial(
        "2/1", 4, directory, crossing_match="non_crossing",
        style_profile=STYLE_PROFILES["restrained"],
    )
    return directory


@pytest.fixture(scope="module")
def driving_success(workdir):
    """A single 2/1 success generated with the driving style (seed 5)."""
    from app.songprogram.style_profile import STYLE_PROFILES

    directory = workdir / "driving" / "seed-5"
    _write_trial(
        "2/1", 5, directory, crossing_match="non_crossing",
        style_profile=STYLE_PROFILES["driving"],
    )
    return directory


def _cohort(workdir, name: str, seed_dirs) -> Path:
    """Assemble a cohort directory from existing seed directories."""
    cohort = workdir / name
    cohort.mkdir(parents=True)
    for source in seed_dirs:
        shutil.copytree(source, cohort / source.name)
    return cohort


def _load_features(directory):
    plan = json.loads((directory / "composition_plan.json").read_text())
    cadence = json.loads((directory / "cadence_plan.json").read_text())
    project = json.loads((directory / "project.json").read_text())
    return features(plan, cadence, project)


def test_validates_real_successes_and_clusters(golden_cohort, workdir):
    report = run(golden_cohort, workdir / "golden_clusters.json", clusters=2)
    assert report["schema"] == SCHEMA
    assert report["non_authoritative"] is True
    assert report["equave"] == "2/1"
    assert report["crossing_match"] == "canonical"
    assert report["seed_denominator"] == 3
    # The failing seed stays in the denominator and is reported separately.
    assert report["generation_failure_count"] == 1
    assert report["generation_failures"][0]["seed"] == 0
    assert report["generation_failures"][0]["failure_code"] == "PROGRESSION_NO_PATH"
    assert report["validation_failure_count"] == 0
    assert report["validated_success_count"] == 2
    assert {row["seed"] for row in report["rows"]} == {4, 5}
    assert len(report["clusters"]) == 2
    for group in report["clusters"]:
        assert group["representative_seed"] in group["member_seeds"]
    assert sorted(seed for g in report["clusters"] for seed in g["member_seeds"]) == [4, 5]
    # skip-wav => PCM not_evaluated; no audio-quality claim is made.
    assert report["pcm_not_evaluated_count"] == 2
    assert report["pcm_checked_count"] == 0
    assert report["audio_quality_assessed"] is False
    assert all(row["pcm_status"] == "not_evaluated" for row in report["rows"])
    assert report["report_hash"].startswith("sha256:")


def test_report_is_deterministic(golden_cohort, workdir):
    output = workdir / "golden_det.json"
    first = run(golden_cohort, output, clusters=2)
    second = run(golden_cohort, output, clusters=2)
    assert first == second
    assert first["report_hash"] == second["report_hash"]


def test_zero_successes_is_graceful(golden_cohort, workdir):
    cohort = _cohort(workdir, "zero", [golden_cohort / "seed-0"])
    report = run(cohort, workdir / "zero.json", clusters=1)
    assert report["validated_success_count"] == 0
    assert report["rows"] == []
    assert report["clusters"] == []
    assert report["generation_failure_count"] == 1
    assert report["seed_denominator"] == 1


def test_mixed_equaves_fail_closed(golden_cohort, tritave_success, workdir):
    cohort = _cohort(workdir, "mixed_eq", [golden_cohort / "seed-4", tritave_success])
    with pytest.raises(ValueError, match="mixed equaves"):
        run(cohort, workdir / "mixed_eq.json", clusters=2)


def test_mixed_crossing_policies_fail_closed(golden_cohort, noncrossing_success, workdir):
    cohort = _cohort(workdir, "mixed_x", [golden_cohort / "seed-4", noncrossing_success])
    with pytest.raises(ValueError, match="mixed crossing"):
        run(cohort, workdir / "mixed_x.json", clusters=2)


def test_tampered_program_hash_is_a_validation_failure(golden_cohort, workdir):
    cohort = _cohort(workdir, "tamper_prog", [golden_cohort / "seed-4"])
    path = cohort / "seed-4" / "program.json"
    program = json.loads(path.read_text())
    program["limits"]["max_bars"] = 65
    path.write_text(json.dumps(program))
    report = run(cohort, workdir / "tamper_prog.json", clusters=1)
    assert report["validated_success_count"] == 0
    assert report["validation_failure_count"] == 1
    assert "program hash mismatch" in report["validation_failures"][0]["reason"]


def test_missing_midi_is_a_validation_failure(golden_cohort, workdir):
    cohort = _cohort(workdir, "tamper_midi", [golden_cohort / "seed-4"])
    (cohort / "seed-4" / "evaluation_reference.mid").unlink()
    report = run(cohort, workdir / "tamper_midi.json", clusters=1)
    assert report["validated_success_count"] == 0
    assert "missing artifact evaluation_reference.mid" in report["validation_failures"][0]["reason"]


def test_validate_success_returns_artifacts_and_raises_on_tamper(golden_cohort, workdir):
    directory = golden_cohort / "seed-4"
    plan, cadence, _program, _project, report = validate_success(directory, 4)
    assert plan["plan_hash"] == cadence["source_plan_hash"]
    assert report["seed"] == 4 and report["equave"] == "2/1"
    tampered = workdir / "tampered"
    shutil.copytree(directory, tampered)
    path = tampered / "project.json"
    project = json.loads(path.read_text())
    project["clock"]["tempo_milli_bpm"] += 1
    path.write_text(json.dumps(project))
    with pytest.raises(ValueError, match="project hash mismatch"):
        validate_success(tampered, 4)


def test_genuine_styled_success_validates(restrained_success):
    assert validate_success(restrained_success, 4)[-1]["style_profile"] is not None


def test_style_swap_is_rejected(restrained_success, workdir):
    from app.songprogram.style_profile import STYLE_PROFILES, style_profile_hash

    tampered = workdir / "style_swapped"
    shutil.copytree(restrained_success, tampered)
    report_path = tampered / "report.json"
    report = json.loads(report_path.read_text())
    report["style_profile"] = STYLE_PROFILES["driving"]
    report["style_profile_hash"] = style_profile_hash(report["style_profile"])
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="cadence policy does not match inputs"):
        validate_success(tampered, 4)


def test_clearing_style_fields_on_styled_success_is_rejected(restrained_success, workdir):
    tampered = workdir / "style_cleared"
    shutil.copytree(restrained_success, tampered)
    report_path = tampered / "report.json"
    report = json.loads(report_path.read_text())
    report["style_profile"] = None
    report["style_profile_hash"] = None
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="cadence policy does not match inputs"):
        validate_success(tampered, 4)


def test_features_are_realized_and_distance_is_zero_for_identical(golden_cohort):
    feature = _load_features(golden_cohort / "seed-4")
    for key in (
        "cadence_function_share", "cadence_expectation_share", "voice_count_share",
        "generator_share", "register_mean_mc_by_role", "register_spread_mc_by_role",
        "onset_share_by_role", "chord_span_mc", "form",
    ):
        assert key in feature
    # stability_q (a dictionary score) is not an independent auditory feature.
    assert "stability_q" not in feature
    # The register is absolute (log2 of the final ratios), not the equave exponent.
    assert "register_mean_exponent_by_role" not in feature
    assert distance_cadence(feature, feature) == 0


def test_distance_changes_when_realized_content_changes(golden_cohort):
    left = _load_features(golden_cohort / "seed-4")
    right = _load_features(golden_cohort / "seed-5")
    assert distance_cadence(left, right) > 0


def test_register_distance_is_normalized_in_millicents(golden_cohort):
    """The register term is normalized against millicent windows, not milli-octaves.

    Shifting one role's mean register by exactly one octave (1_200_000 millicents)
    contributes 1/4 for that role (the 4-octave mean window), i.e. 0.125 to the
    total distance — not ~150 as the old 1200x-inflated normalization would give.
    """
    import copy

    base = _load_features(golden_cohort / "seed-4")
    shifted = copy.deepcopy(base)
    shifted["register_mean_mc_by_role"]["melody"] += 1_200_000
    # Only the register term differs; it must stay small, not 1200x-inflated.
    assert distance_cadence(base, shifted) < 0.5


def test_empty_forged_impact_is_a_validation_failure(golden_cohort, workdir):
    """Empty slot_bindings / impact slots with zero counts must not pass."""
    cohort = _cohort(workdir, "forged_empty", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    report = json.loads((directory / "report.json").read_text())
    report["slot_bindings"] = []
    report["matched_slots"] = 0
    report["candidate_slots"] = 0
    (directory / "report.json").write_text(json.dumps(report))
    impact = json.loads((directory / "cadence_impact_report.json").read_text())
    impact["slots"] = []
    (directory / "cadence_impact_report.json").write_text(json.dumps(impact))
    result = run(cohort, workdir / "forged_empty.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert result["validation_failure_count"] == 1
    assert "impact report recomputation mismatch" in result["validation_failures"][0]["reason"]


def test_forged_slot_with_recomputed_hash_is_a_validation_failure(golden_cohort, workdir):
    """A forged slot that survives the cadence hash check fails on impact recompute."""
    from app.songprogram.piano_v3 import _cadence_plan_hash

    cohort = _cohort(workdir, "forged_slot", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    cadence = json.loads((directory / "cadence_plan.json").read_text())
    cadence["slots"][0]["generator"] = 999
    cadence["cadence_plan_hash"] = _cadence_plan_hash(cadence)  # forger recomputes
    (directory / "cadence_plan.json").write_text(json.dumps(cadence))
    report = json.loads((directory / "report.json").read_text())
    report["cadence_plan_hash"] = cadence["cadence_plan_hash"]  # and updates the report
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "forged_slot.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "impact report recomputation failed" in result["validation_failures"][0]["reason"]


def test_cross_equave_project_swap_is_a_validation_failure(golden_cohort, tritave_success, workdir):
    """A project from another equave (with a valid hash) fails the equave binding."""
    cohort = _cohort(workdir, "x_eq", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    (directory / "project.json").write_bytes((tritave_success / "project.json").read_bytes())
    result = run(cohort, workdir / "x_eq.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "project lattice equave mismatch" in result["validation_failures"][0]["reason"]


def test_mixed_lift_policies_fail_closed(golden_cohort, lift_success, workdir):
    """Different register-lift policy hashes must not be mixed among successes.

    A *partial* lift-policy forgery (report seed + policy + impact rewritten)
    is caught per-seed by the plan/program seed binding; a *fully consistent*
    one (a genuine success generated under the other policy) is caught by the
    cohort-level mixed-policy check.
    """
    from app.harmony_dictionary.storage import read_sealed
    from app.songprogram.piano_v3 import cadence_impact_report
    from app.songprogram.sparse_variant import build_register_lift_policy
    from tools.cluster_piano_v3_cadence import DICTIONARY_DIR

    # Partial forgery: the plan still records seed 4, so the seed binding
    # fails before the (consistently rewritten) policy and impact are reached.
    cohort = _cohort(workdir, "mixed_lift", [golden_cohort / "seed-4"])
    source = cohort / "seed-4"
    target = cohort / "seed-700"
    shutil.copytree(source, target)
    report = json.loads((target / "report.json").read_text())
    report["seed"] = 700
    enabled = build_register_lift_policy(allow_lifts=True)
    report["register_lift_policy"] = enabled
    report["register_lift_policy_hash"] = enabled["policy_hash"]
    (target / "report.json").write_text(json.dumps(report))
    # A consistent forger also rewrites the impact artifact with the new policy.
    cadence = json.loads((target / "cadence_plan.json").read_text())
    program = json.loads((target / "program.json").read_text())
    project = json.loads((target / "project.json").read_text())
    dictionary = read_sealed(
        DICTIONARY_DIR / "harmony_dictionary_2-1.json", "harmony-dictionary/2/1"
    )
    recomputed = cadence_impact_report(
        cadence, program, project, dictionary_file=dictionary,
        register_lift_policy=enabled,
    )
    (target / "cadence_impact_report.json").write_bytes(canonical_bytes(recomputed))
    result = run(cohort, workdir / "mixed_lift.json", clusters=1)
    assert result["validated_success_count"] == 1
    assert result["validation_failure_count"] == 1
    assert "seed mismatch" in result["validation_failures"][0]["reason"]

    # Fully consistent: a genuine success generated under the lifted policy,
    # mixed with a canonical one.  Both pass per-seed validation (each is a
    # valid trial); the cohort must refuse to cluster them together.
    mixed = _cohort(workdir, "mixed_lift_genuine", [golden_cohort / "seed-5", lift_success])
    with pytest.raises(ValueError, match="mixed register lift policies"):
        run(mixed, workdir / "mixed_lift_genuine.json", clusters=2)


def test_malformed_failure_record_does_not_abort(golden_cohort, workdir):
    """A malformed failure.json is a generation failure, not a cohort abort."""
    cohort = _cohort(
        workdir, "bad_fail", [golden_cohort / "seed-0", golden_cohort / "seed-4"]
    )
    (cohort / "seed-0" / "failure.json").write_text("not json")
    result = run(cohort, workdir / "bad_fail.json", clusters=1)
    assert result["seed_denominator"] == 2
    assert result["generation_failure_count"] == 1
    assert result["generation_failures"][0]["failure_code"] == "MALFORMED_FAILURE_RECORD"
    assert result["validated_success_count"] == 1


def test_list_equave_in_failure_does_not_abort(golden_cohort, workdir):
    """A failure record whose equave is a list must not abort the run.

    The unhashable equave would raise ``TypeError`` on ``set.add``; it is now
    skipped for the cohort-level equave check, while the seed stays in the
    denominator and is recorded as a generation failure.
    """
    cohort = _cohort(
        workdir, "list_eq", [golden_cohort / "seed-0", golden_cohort / "seed-4"]
    )
    failure = json.loads((cohort / "seed-0" / "failure.json").read_text())
    failure["equave"] = ["2/1"]  # unhashable: would abort the set.add()
    (cohort / "seed-0" / "failure.json").write_text(json.dumps(failure))
    result = run(cohort, workdir / "list_eq.json", clusters=1)
    assert result["seed_denominator"] == 2
    assert result["generation_failure_count"] == 1
    assert result["validated_success_count"] == 1


def test_malformed_report_is_a_validation_failure(golden_cohort, workdir):
    """A malformed report.json is a validation failure, not a cohort abort."""
    cohort = _cohort(workdir, "bad_rep", [golden_cohort / "seed-4"])
    (cohort / "seed-4" / "report.json").write_text("not json")
    result = run(cohort, workdir / "bad_rep.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert result["validation_failure_count"] == 1
    assert result["validation_failures"][0]["reason"] == "MALFORMED_JSON"


def _write_wav(directory, samples) -> bytes:
    """Write a small mono 16-bit WAV and return its bytes."""
    import struct as _struct
    import wave as _wave

    body = _struct.pack("<" + "h" * len(samples), *samples)
    path = directory / "reference.wav"
    with _wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(body)
    return path.read_bytes()


def test_non_object_report_is_a_validation_failure(golden_cohort, workdir):
    """A JSON array report is a validation failure, not an abort."""
    cohort = _cohort(workdir, "nonobj_rep", [golden_cohort / "seed-4"])
    (cohort / "seed-4" / "report.json").write_text("[1, 2, 3]")
    result = run(cohort, workdir / "nonobj_rep.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "report is not an object" in result["validation_failures"][0]["reason"]


def test_non_object_pcm_is_a_validation_failure(golden_cohort, workdir):
    """A string pcm field is a validation failure, not an AttributeError abort."""
    cohort = _cohort(workdir, "nonobj_pcm", [golden_cohort / "seed-4"])
    report = json.loads((cohort / "seed-4" / "report.json").read_text())
    report["pcm"] = "checked"
    (cohort / "seed-4" / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "nonobj_pcm.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "pcm is not an object" in result["validation_failures"][0]["reason"]


def test_non_object_failure_record_does_not_abort(golden_cohort, workdir):
    """A JSON array failure record is a malformed generation failure."""
    cohort = _cohort(
        workdir, "nonobj_fail", [golden_cohort / "seed-0", golden_cohort / "seed-4"]
    )
    (cohort / "seed-0" / "failure.json").write_text("[1, 2, 3]")
    result = run(cohort, workdir / "nonobj_fail.json", clusters=1)
    assert result["generation_failure_count"] == 1
    assert result["generation_failures"][0]["failure_code"] == "MALFORMED_FAILURE_RECORD"
    assert result["validated_success_count"] == 1


def test_forged_note_event_with_recomputed_hash_is_a_validation_failure(
    golden_cohort, workdir,
):
    """A forged sounding ratio with a recomputed project hash fails the recompile."""
    from app.songprogram.perceptual import project_hash

    cohort = _cohort(workdir, "forged_event", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    path = directory / "project.json"
    project = json.loads(path.read_text())
    note = next(event for event in project["events"] if event["kind"] == "note")
    note["ratio"] = "170/96"
    note["pitch_provenance"]["final_ratio"] = "170/96"
    note["pitch_provenance"]["equave_exponent"] += 1
    path.write_text(json.dumps(project))
    report = json.loads((directory / "report.json").read_text())
    report["project_hash"] = project_hash(project)  # forger recomputes the hash
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "forged_event.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "project recompile mismatch" in result["validation_failures"][0]["reason"]


def test_forged_midi_is_a_validation_failure(golden_cohort, workdir):
    """Another seed's consistent MIDI + manifest pair fails the re-export."""
    cohort = _cohort(workdir, "forged_midi", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    other = golden_cohort / "seed-5"
    (directory / "evaluation_reference.mid").write_bytes(
        (other / "evaluation_reference.mid").read_bytes()
    )
    (directory / "evaluation_reference_midi.json").write_bytes(
        (other / "evaluation_reference_midi.json").read_bytes()
    )
    result = run(cohort, workdir / "forged_midi.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "MIDI re-export mismatch" in result["validation_failures"][0]["reason"]


def test_forged_compiler_identity_is_a_validation_failure(golden_cohort, workdir):
    """A forged compiler identity in the report fails the re-derived binding."""
    cohort = _cohort(workdir, "forged_id", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    report = json.loads((directory / "report.json").read_text())
    report["compiler_identity"]["build_id"] = "forged/v9"
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "forged_id.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "compiler identity mismatch" in result["validation_failures"][0]["reason"]


def test_silent_wav_is_a_validation_failure(golden_cohort, workdir):
    """A silent WAV behind a checked PCM report is rejected by _pcm_check."""
    import hashlib

    cohort = _cohort(workdir, "silent_wav", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    wav_bytes = _write_wav(directory, [0] * 8000)
    report = json.loads((directory / "report.json").read_text())
    # A forged checked record: _pcm_check itself raises V3_PCM_SILENT.
    report["pcm"] = {
        "status": "checked",
        "sample_rate_hz": 8000,
        "channels": 1,
        "frames": 8000,
        "nonzero_samples": 0,
        "peak_integer": 0,
        "wav_sha256": "sha256:" + hashlib.sha256(wav_bytes).hexdigest(),
    }
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "silent_wav.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "V3_PCM_SILENT" in result["validation_failures"][0]["reason"]


def test_corrupt_wav_is_a_validation_failure(golden_cohort, workdir):
    """A non-WAV file behind a checked PCM report is rejected (no abort)."""
    import hashlib

    cohort = _cohort(workdir, "corrupt_wav", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    (directory / "reference.wav").write_bytes(b"not a wav at all")
    report = json.loads((directory / "report.json").read_text())
    report["pcm"] = {
        "status": "checked",
        "sample_rate_hz": 8000,
        "channels": 1,
        "frames": 8000,
        "nonzero_samples": 123,
        "peak_integer": 100,
        "wav_sha256": "sha256:" + hashlib.sha256(b"not a wav at all").hexdigest(),
    }
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "corrupt_wav.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "reference WAV check failed" in result["validation_failures"][0]["reason"]


def test_forged_pcm_dict_is_a_validation_failure(golden_cohort, workdir):
    """A checked PCM dict that does not equal _pcm_check of the WAV fails."""
    from tools.generate_piano_v3_cadence_trial import _pcm_check

    cohort = _cohort(workdir, "forged_pcm", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    wav_bytes = _write_wav(directory, [(i % 256) - 128 for i in range(8000)])
    report = json.loads((directory / "report.json").read_text())
    report["pcm"] = dict(_pcm_check(wav_bytes))
    report["pcm"]["peak_integer"] += 5  # forged measurement
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "forged_pcm.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "PCM report mismatch" in result["validation_failures"][0]["reason"]


def test_valid_checked_pcm_passes(golden_cohort, workdir):
    """A genuine checked PCM report (from _pcm_check of the WAV) passes."""
    from tools.generate_piano_v3_cadence_trial import _pcm_check

    cohort = _cohort(workdir, "good_pcm", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    wav_bytes = _write_wav(directory, [(i % 256) - 128 for i in range(8000)])
    report = json.loads((directory / "report.json").read_text())
    report["pcm"] = _pcm_check(wav_bytes)
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "good_pcm.json", clusters=1)
    assert result["validated_success_count"] == 1


def test_report_seed_must_match_plan_and_program(golden_cohort, workdir):
    """Editing only the report seed breaks the plan/program seed binding."""
    cohort = _cohort(workdir, "seed_forge", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    report = json.loads((directory / "report.json").read_text())
    report["seed"] = 100  # plan and program still record seed 4
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "seed_forge.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "seed mismatch" in result["validation_failures"][0]["reason"]


def test_slot_bindings_content_mismatch_is_a_validation_failure(
    golden_cohort, workdir
):
    """A tampered slot_bindings entry fails the full-content comparison."""
    cohort = _cohort(workdir, "binding_tamper", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    report = json.loads((directory / "report.json").read_text())
    report["slot_bindings"][0]["bar"] += 1
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "binding_tamper.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "slot bindings differ" in result["validation_failures"][0]["reason"]


def test_clamp_clusters_on_identical_feature_rows(golden_cohort):
    """Identical feature rows clamp the effective count (pure rows, no seed forgery).

    The seed is bound to the plan's and program's recorded seeds, so a cohort
    of identical songs cannot be assembled by copying one directory under new
    seed names; the clamping logic is therefore exercised on pure feature rows.
    """
    feature = _load_features(golden_cohort / "seed-4")
    rows = [{"seed": seed, "features": dict(feature)} for seed in (4, 100, 200)]
    assert clamp_clusters(rows, 2) == 1
    assert clamp_clusters(rows, 5) == 1
    assert clamp_clusters([], 3) == 0
    other = _load_features(golden_cohort / "seed-5")
    mixed = rows + [{"seed": 300, "features": other}]
    assert clamp_clusters(mixed, 2) == 2
    assert clamp_clusters(mixed, 5) == 2


def test_report_records_provenance_scoping(golden_cohort, workdir):
    result = run(golden_cohort, workdir / "prov.json", clusters=2)
    assert result["crossing_match_provenance"] == "trial_report_recorded_not_rederived"
    assert result["project_verification"] == "deterministic_recompile_byte_equal"
    assert result["register_lift_policy_hash"].startswith("sha256:")
    assert result["requested_clusters"] == 2
    # Seeds 4 and 5 have distinct feature vectors, so nothing is clamped.
    assert result["effective_clusters"] == 2


def test_main_rejects_paths_outside_local_authority(golden_cohort, monkeypatch):
    import tools.cluster_piano_v3_cadence as module

    monkeypatch.setattr(
        sys, "argv", [
            module.__name__, "--cohort", str(golden_cohort),
            "--output", "/tmp/not_local_authority.json", "--clusters", "2",
        ]
    )
    with pytest.raises(SystemExit):
        module.main()


def _write_cohort_report(
    cohort, *, equave: str = "2/1",
    schema: str = "cps.piano-v3-cadence-cohort-report",
    version: str = "1.0.0",
) -> dict:
    """Build a ``cohort_report.json`` consistent with the cohort's seed directories.

    Mirrors the generation CLI: one outcome per seed, a success outcome
    carrying its report path and PCM status, a failure outcome being the full
    failure record.
    """
    outcomes = []
    for directory in sorted(
        cohort.glob("seed-*"), key=lambda p: int(p.name.removeprefix("seed-"))
    ):
        seed = int(directory.name.removeprefix("seed-"))
        if (directory / "report.json").is_file():
            report = json.loads((directory / "report.json").read_text())
            outcomes.append({
                "seed": seed,
                "status": "success",
                "report": str(directory / "report.json"),
                "pcm_status": report["pcm"]["status"],
            })
        else:
            outcomes.append(json.loads((directory / "failure.json").read_text()))
    cohort_report = {
        "schema": schema,
        "schema_version": version,
        "equave": equave,
        "seed_denominator": len(outcomes),
        "successes": sum(1 for item in outcomes if item.get("status") == "success"),
        "failures": sum(1 for item in outcomes if item.get("status") == "failed"),
        "outcomes": outcomes,
        "classification_threshold_calibrated": False,
        "profile_status": "unsealed",
    }
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    return cohort_report


def test_cohort_report_consistency_passes_and_changes_nothing(golden_cohort, workdir):
    """A cohort_report matching the directories validates; the report is unchanged.

    The validation is a gate, not new report content: with and without the
    cohort report the written report body (and hash) must be identical.
    """
    sources = [golden_cohort / "seed-0", golden_cohort / "seed-4", golden_cohort / "seed-5"]
    with_report = _cohort(workdir, "cr_ok", sources)
    _write_cohort_report(with_report)
    report = run(with_report, workdir / "cr_ok.json", clusters=2)
    assert report["seed_denominator"] == 3
    assert report["generation_failure_count"] == 1
    assert report["validated_success_count"] == 2

    adhoc = _cohort(workdir, "cr_ok_adhoc", sources)
    baseline = run(adhoc, workdir / "cr_ok_adhoc.json", clusters=2)

    # source_cohort differs by construction (different paths); everything else
    # in the hashed body must be identical.
    def _body(result):
        return {key: value for key, value in result.items()
                if key not in ("source_cohort", "report_hash")}

    assert _body(report) == _body(baseline)


def test_cohort_report_missing_seed_dir_fails(golden_cohort, workdir):
    """An outcome whose seed directory is absent fails closed (not a lower count)."""
    cohort = _cohort(workdir, "cr_missing", [golden_cohort / "seed-0", golden_cohort / "seed-4"])
    cohort_report = _write_cohort_report(cohort)
    cohort_report["outcomes"].append({
        "seed": 5, "status": "success",
        "report": str(cohort / "seed-5" / "report.json"),
        "pcm_status": "not_evaluated",
    })
    cohort_report["seed_denominator"] = 3
    cohort_report["successes"] += 1
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    with pytest.raises(ValueError, match="seed mismatch"):
        run(cohort, workdir / "cr_missing.json", clusters=2)


def test_cohort_report_extra_seed_dir_fails(golden_cohort, workdir):
    """A seed directory with no outcome is extra and fails closed."""
    cohort = _cohort(
        workdir, "cr_extra",
        [golden_cohort / "seed-0", golden_cohort / "seed-4", golden_cohort / "seed-5"],
    )
    cohort_report = _write_cohort_report(cohort)
    cohort_report["outcomes"] = [item for item in cohort_report["outcomes"] if item.get("seed") != 5]
    cohort_report["seed_denominator"] = 2
    cohort_report["successes"] -= 1
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    with pytest.raises(ValueError, match="seed mismatch"):
        run(cohort, workdir / "cr_extra.json", clusters=2)


def test_cohort_report_duplicate_outcome_seeds_fails(golden_cohort, workdir):
    """Duplicate outcome seeds fail even when the directory set matches."""
    cohort = _cohort(workdir, "cr_dup", [golden_cohort / "seed-4"])
    cohort_report = _write_cohort_report(cohort)
    cohort_report["outcomes"].append(dict(cohort_report["outcomes"][0]))
    cohort_report["seed_denominator"] = 2
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    with pytest.raises(ValueError, match="duplicate seeds"):
        run(cohort, workdir / "cr_dup.json", clusters=1)


def test_cohort_report_status_contradiction_fails(golden_cohort, workdir):
    """A recorded success whose report.json is missing fails closed."""
    cohort = _cohort(workdir, "cr_status", [golden_cohort / "seed-0", golden_cohort / "seed-4"])
    cohort_report = _write_cohort_report(cohort)
    (cohort / "seed-4" / "report.json").unlink()
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    with pytest.raises(ValueError, match="missing report.json"):
        run(cohort, workdir / "cr_status.json", clusters=2)


def test_cohort_report_bad_schema_fails(golden_cohort, workdir):
    cohort = _cohort(workdir, "cr_schema", [golden_cohort / "seed-4"])
    _write_cohort_report(cohort, schema="cps.some-other-cohort-report")
    with pytest.raises(ValueError, match="schema mismatch"):
        run(cohort, workdir / "cr_schema.json", clusters=1)


def test_cohort_report_equave_mismatch_fails(golden_cohort, workdir):
    """A cohort_report equave contradicting the per-seed records fails closed."""
    cohort = _cohort(workdir, "cr_eq", [golden_cohort / "seed-4"])
    _write_cohort_report(cohort, equave="3/1")
    with pytest.raises(ValueError, match="does not match cohort"):
        run(cohort, workdir / "cr_eq.json", clusters=1)


def test_cohort_report_forged_report_path_fails(golden_cohort, workdir):
    """A success outcome whose report path is a suffix forgery fails closed.

    The recorded path must bind exactly (resolved) to this cohort's
    directory/report.json.  A suffix match would accept an unrelated cohort's
    ``notseed-4/report.json``, which ends with ``seed-4/report.json``.
    """
    cohort = _cohort(workdir, "cr_path", [golden_cohort / "seed-4"])
    cohort_report = _write_cohort_report(cohort)
    for outcome in cohort_report["outcomes"]:
        if outcome.get("status") == "success":
            outcome["report"] = str(workdir / "unrelated" / "notseed-4" / "report.json")
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    with pytest.raises(ValueError, match="report path"):
        run(cohort, workdir / "cr_path.json", clusters=1)


def test_cohort_report_relative_report_path_passes(golden_cohort, workdir):
    """A relative recorded path (the documented CLI convention) is accepted.

    The generation CLI records the output path as given on the command line
    (a relative ``local_authority/...`` path is the documented convention);
    it resolves against the working directory and must equal the actual
    directory/report.json.
    """
    import os

    cohort = _cohort(workdir, "cr_rel", [golden_cohort / "seed-4"])
    cohort_report = _write_cohort_report(cohort)
    for outcome in cohort_report["outcomes"]:
        if outcome.get("status") == "success":
            outcome["report"] = os.path.relpath(str(cohort / "seed-4" / "report.json"))
    (cohort / "cohort_report.json").write_bytes(canonical_bytes(cohort_report))
    result = run(cohort, workdir / "cr_rel.json", clusters=1)
    assert result["validated_success_count"] == 1


def test_alias_seed_dir_fails_without_cohort_report(golden_cohort, workdir):
    """seed-0 and seed-00 duplicate the same numeric seed: fail closed."""
    cohort = _cohort(workdir, "alias", [golden_cohort / "seed-4"])
    shutil.copytree(golden_cohort / "seed-4", cohort / "seed-0")
    shutil.copytree(golden_cohort / "seed-4", cohort / "seed-00")
    with pytest.raises(ValueError, match="alias"):
        run(cohort, workdir / "alias.json", clusters=2)


def test_nonnumeric_seed_dir_fails_without_cohort_report(golden_cohort, workdir):
    cohort = _cohort(workdir, "nonnum", [golden_cohort / "seed-4"])
    shutil.copytree(golden_cohort / "seed-4", cohort / "seed-abc")
    with pytest.raises(ValueError, match="malformed"):
        run(cohort, workdir / "nonnum.json", clusters=1)


# ---------------------------------------------------------------------------
# Experimental style-profile provenance (restrained / driving)
# ---------------------------------------------------------------------------

def test_mixed_style_profiles_fail_closed(restrained_success, driving_success, workdir):
    """Different style profiles must not be mixed among the clustered successes.

    A different style profile changes the realized tempo / dynamics / rhythm /
    progression, so a cohort mixing two styles (or a style and the baseline)
    would conflate distinct realizations and fails closed.
    """
    cohort = _cohort(workdir, "mixed_style", [restrained_success, driving_success])
    with pytest.raises(ValueError, match="mixed style"):
        run(cohort, workdir / "mixed_style.json", clusters=2)


def test_style_and_baseline_mix_fail_closed(restrained_success, noncrossing_success, workdir):
    """A cohort mixing a styled seed and a baseline seed fails closed.

    Both use the non_crossing crossing policy (so the crossing check passes);
    the style separation is what fails: a styled seed and a baseline (``None``)
    seed are two distinct styles.
    """
    cohort = _cohort(workdir, "style_base", [restrained_success, noncrossing_success])
    with pytest.raises(ValueError, match="mixed style"):
        run(cohort, workdir / "style_base.json", clusters=2)


def test_tampered_style_profile_is_a_validation_failure(driving_success, workdir):
    """A styled success whose profile body no longer matches its hash fails."""
    cohort = _cohort(workdir, "tamper_style", [driving_success])
    directory = cohort / "seed-5"
    report = json.loads((directory / "report.json").read_text())
    report["style_profile"]["tempo_milli_bpm"] += 1  # body changed, hash stale
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "tamper_style.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert result["validation_failure_count"] == 1
    assert "style profile" in result["validation_failures"][0]["reason"]


def test_style_hash_without_profile_is_a_validation_failure(driving_success, workdir):
    """A report carrying a style hash but no profile body is inconsistent."""
    cohort = _cohort(workdir, "style_no_body", [driving_success])
    directory = cohort / "seed-5"
    report = json.loads((directory / "report.json").read_text())
    report["style_profile"] = None  # keep the hash, drop the body
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "style_no_body.json", clusters=1)
    assert result["validated_success_count"] == 0
    assert "style profile hash without profile" in result["validation_failures"][0]["reason"]


def test_old_report_without_style_fields_validates_as_baseline(golden_cohort, workdir):
    """A pre-style 1.1.0 report (no style fields) validates as the baseline."""
    cohort = _cohort(workdir, "old_report", [golden_cohort / "seed-4"])
    directory = cohort / "seed-4"
    report = json.loads((directory / "report.json").read_text())
    del report["style_profile"]
    del report["style_profile_hash"]
    report["schema_version"] = "1.1.0"
    (directory / "report.json").write_text(json.dumps(report))
    result = run(cohort, workdir / "old_report.json", clusters=1)
    assert result["validated_success_count"] == 1


def test_all_baseline_cohort_omits_style_fields(golden_cohort, workdir):
    """An all-baseline cohort's report carries no style fields (top level or rows)."""
    cohort = _cohort(
        workdir, "baseline_only", [golden_cohort / "seed-4", golden_cohort / "seed-5"]
    )
    result = run(cohort, workdir / "baseline_only.json", clusters=2)
    assert result["validated_success_count"] == 2
    assert "style_profile_hash" not in result
    assert "style_profile_status" not in result
    assert all("style_profile_hash" not in row for row in result["rows"])


def test_styled_cohort_records_style_provenance(driving_success, workdir):
    """A styled cohort's report records the profile hash and unsealed status."""
    from app.songprogram.style_profile import STYLE_PROFILES, style_profile_hash

    cohort = _cohort(workdir, "styled_only", [driving_success])
    result = run(cohort, workdir / "styled_only.json", clusters=1)
    assert result["validated_success_count"] == 1
    expected_hash = style_profile_hash(STYLE_PROFILES["driving"])
    assert result["style_profile_hash"] == expected_hash
    assert result["style_profile_status"] == "experimental_unsealed"
    assert all(row["style_profile_hash"] == expected_hash for row in result["rows"])
