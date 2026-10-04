"""Real CompositionPlan-to-Project v3 generation on both equaves."""

from __future__ import annotations

import json
import sys

import pytest

from tools.generate_piano_v3_cadence_trial import generate_one


@pytest.mark.parametrize(("equave", "seed"), [("2/1", 4), ("3/1", 0)])
def test_composition_cadence_program_project_reconciliation(equave: str, seed: int) -> None:
    artifacts, report = generate_one(equave, seed, skip_wav=True)
    assert report["status"] == "success"
    assert report["candidate_slots"] == report["matched_slots"]
    assert report["section_bars"]
    assert all(row["status"] == "matched" for row in report["slot_bindings"])
    assert all(row["source_dictionary_hash"] == report["dictionary_hash"]
               for row in report["slot_bindings"])
    assert all(row["program_variant_hashes"] for row in report["slot_bindings"])
    assert artifacts["composition_plan.json"]
    assert artifacts["cadence_plan.json"]
    assert artifacts["program.json"]
    assert artifacts["project.json"]
    assert report["pcm"] == {"status": "not_evaluated"}


def test_cadence_trial_repeats_identical_plan_program_and_project_hashes() -> None:
    first_artifacts, first = generate_one("3/1", 0, skip_wav=True)
    second_artifacts, second = generate_one("3/1", 0, skip_wav=True)
    for field in (
        "composition_plan_hash", "cadence_plan_hash", "program_hash", "project_hash"
    ):
        assert first[field] == second[field]
    assert first_artifacts == second_artifacts


def test_failing_seed_records_staged_failure_with_partial_artifacts() -> None:
    from tools.generate_piano_v3_cadence_trial import V3TrialFailure

    # Octave seed 0 has no progression path: the failure is staged at compile
    # and keeps every artifact produced before it (never a silent drop).
    with pytest.raises(V3TrialFailure) as excinfo:
        generate_one("2/1", 0, skip_wav=True)
    failure = excinfo.value
    assert failure.stage == "compile"
    assert failure.code == "PROGRESSION_NO_PATH"
    assert set(failure.artifacts) == {
        "composition_plan.json", "cadence_policy.json",
        "cadence_plan.json", "program.json",
    }


def test_successful_seed_report_carries_empty_mismatches() -> None:
    _, report = generate_one("3/1", 0, skip_wav=True)
    assert all(row["mismatches"] == [] for row in report["slot_bindings"])
    assert all(row["status"] == "matched" for row in report["slot_bindings"])


def test_crossing_policy_resolves_failing_seeds() -> None:
    from app.songprogram.sparse_variant import build_register_lift_policy

    # Octave seeds 0-3 have no exact progression path (PROGRESSION_NO_PATH)
    # under the canonical edge matching: the lowest-cost pairing crosses and
    # is dropped by crossing_policy="forbid" even when a non-crossing pairing
    # exists.  The versioned, 0.3-only crossing_match="non_crossing" query
    # policy makes the resolver rank only non-crossing pairings, so every seed
    # succeeds and every slot reconciles.  The register-lift policy is enabled
    # here as an independent 0.3 feature (register alternatives) but is NOT
    # what repairs the crossing: with canonical matching, lifts alone do not
    # resolve these seeds (see test_lifts_alone_do_not_resolve_crossing).
    policy = build_register_lift_policy(allow_lifts=True, max_lift=1, max_variants=8)
    for seed in (0, 1, 2, 3):
        _, report = generate_one(
            "2/1", seed, skip_wav=True,
            register_lift_policy=policy, crossing_match="non_crossing",
        )
        assert report["status"] == "success"
        assert report["register_lift_policy_hash"] == policy["policy_hash"]
        assert report["crossing_match"] == "non_crossing"
        assert report["candidate_slots"] == report["matched_slots"]
        assert all(row["status"] == "matched" for row in report["slot_bindings"])


def test_lifts_alone_do_not_resolve_crossing() -> None:
    from app.songprogram.sparse_variant import build_register_lift_policy
    from tools.generate_piano_v3_cadence_trial import V3TrialFailure

    # With the canonical edge matching (the historical 0.1/0.2/default-0.3
    # semantics), the bounded register-lift policy alone does NOT repair the
    # crossing: the resolver still drops the lowest-cost (crossing) pairing,
    # so seeds 0-3 fail with PROGRESSION_NO_PATH.  This documents the measured
    # blocker and prevents claiming lift-only recovery.
    policy = build_register_lift_policy(allow_lifts=True, max_lift=1, max_variants=8)
    for seed in (0, 1, 2, 3):
        with pytest.raises(V3TrialFailure) as error:
            generate_one(
                "2/1", seed, skip_wav=True,
                register_lift_policy=policy, crossing_match="canonical",
            )
        assert error.value.code == "PROGRESSION_NO_PATH"


def test_disabled_policy_reproduces_documented_hashes() -> None:
    from app.songprogram.sparse_variant import build_register_lift_policy

    # The disabled policy reproduces the exact sparse path byte for byte: the
    # documented seed 4 (octave) and tritave 0 program/project hashes hold.
    policy = build_register_lift_policy(allow_lifts=False)
    expected = {
        ("2/1", 4): (
            "sha256:ebd5f9e1fc6bd1b89c17449a6c204de723c775fb3041efa3f4cb47ed215e06c8",
            "sha256:c734f6aa8ee852eac982aa30d5e7c31ac99243b11738bbce0a6a129cd002e054",
        ),
        ("3/1", 0): (
            "sha256:98a237f354201948d677a1cfb99deeafebe6f75cbcae87e03614b0afa91c171e",
            "sha256:b641579ad5166c2a4497dbae603b38220d734cc132154fb2aacd54fff879a625",
        ),
    }
    for (equave, seed), (program_hash, project_hash) in expected.items():
        _, report = generate_one(equave, seed, skip_wav=True, register_lift_policy=policy)
        assert report["program_hash"] == program_hash
        assert report["project_hash"] == project_hash


def test_artifact_write_error_records_failure_without_aborting(tmp_path, monkeypatch) -> None:
    """An OSError while writing success artifacts must not abort the run.

    The seed directory is already created when the write fails, so the
    handler's mkdir must use ``exist_ok`` (a second ``mkdir()`` would raise
    ``FileExistsError`` and abort the whole run).  The seed is recorded as a
    failure in the cohort report (denominator maintained, no false success)
    and the partially written artifacts are preserved on disk.
    """
    import tools.generate_piano_v3_cadence_trial as module

    real_write = module._write_artifact

    def flaky(path, payload):
        if path.name == "project.json":
            raise OSError("injected artifact write failure")
        real_write(path, payload)

    monkeypatch.setattr(module, "_write_artifact", flaky)
    output = tmp_path / "cohort"
    monkeypatch.setattr(
        sys, "argv", [
            module.__name__, "--equave", "2/1", "--seeds", "4", "5",
            "--output", str(output), "--skip-wav",
        ]
    )
    module.main()  # must complete, not abort

    cohort = json.loads((output / "cohort_report.json").read_text())
    assert cohort["seed_denominator"] == 2
    assert cohort["successes"] == 0
    assert cohort["failures"] == 2
    for seed in (4, 5):
        outcome = next(item for item in cohort["outcomes"] if item["seed"] == seed)
        assert outcome["status"] == "failed"
        assert outcome["stage"] == "unknown"
        directory = output / f"seed-{seed}"
        # The artifacts written before the injected failure are preserved...
        assert (directory / "composition_plan.json").is_file()
        assert (directory / "cadence_policy.json").is_file()
        assert (directory / "cadence_plan.json").is_file()
        assert (directory / "program.json").is_file()
        # ...the failed artifact and the success record are absent...
        assert not (directory / "project.json").exists()
        assert not (directory / "report.json").exists()
        # ...and the failure is recorded, listing exactly what was written.
        assert (directory / "failure.json").is_file()
        assert outcome["partial_artifacts"] == [
            "cadence_plan.json", "cadence_policy.json",
            "composition_plan.json", "program.json",
        ]


def test_staged_partial_write_error_records_only_persisted(tmp_path, monkeypatch) -> None:
    """A write failure on one staged partial artifact must not prevent the rest.

    Each staged artifact is attempted independently: only the ones actually
    persisted are listed in ``partial_artifacts``, and the failure record is
    written regardless (denominator maintained, no false success).
    """
    import tools.generate_piano_v3_cadence_trial as module

    real_write = module._write_artifact

    def flaky(path, payload):
        if path.name == "program.json":
            raise OSError("injected staged artifact write failure")
        real_write(path, payload)

    monkeypatch.setattr(module, "_write_artifact", flaky)
    output = tmp_path / "cohort"
    monkeypatch.setattr(
        sys, "argv", [
            module.__name__, "--equave", "2/1", "--seeds", "0",
            "--output", str(output), "--skip-wav",
        ]
    )
    module.main()  # must complete, not abort

    cohort = json.loads((output / "cohort_report.json").read_text())
    assert cohort["seed_denominator"] == 1
    assert cohort["successes"] == 0
    assert cohort["failures"] == 1
    outcome = cohort["outcomes"][0]
    assert outcome["status"] == "failed"
    assert outcome["stage"] == "compile"
    assert outcome["failure_code"] == "PROGRESSION_NO_PATH"
    # Only the artifacts that actually persisted are listed...
    assert outcome["partial_artifacts"] == [
        "cadence_plan.json", "cadence_policy.json", "composition_plan.json",
    ]
    directory = output / "seed-0"
    assert (directory / "composition_plan.json").is_file()
    assert (directory / "cadence_policy.json").is_file()
    assert (directory / "cadence_plan.json").is_file()
    assert not (directory / "program.json").exists()
    # ...and the failure record was written regardless.
    assert (directory / "failure.json").is_file()


def test_failure_record_write_error_still_records_outcome(tmp_path, monkeypatch) -> None:
    """If failure.json itself cannot be written, the outcome is still recorded.

    The cohort denominator is maintained and the seed is not a false success;
    the detail notes that the record could not be persisted, and the staged
    partial artifacts are still written for inspection.
    """
    import tools.generate_piano_v3_cadence_trial as module

    real_write = module._write_artifact

    def flaky(path, payload):
        if path.name == "failure.json":
            raise OSError("injected failure record write failure")
        real_write(path, payload)

    monkeypatch.setattr(module, "_write_artifact", flaky)
    output = tmp_path / "cohort"
    monkeypatch.setattr(
        sys, "argv", [
            module.__name__, "--equave", "2/1", "--seeds", "0",
            "--output", str(output), "--skip-wav",
        ]
    )
    module.main()  # must complete, not abort

    cohort = json.loads((output / "cohort_report.json").read_text())
    assert cohort["seed_denominator"] == 1
    assert cohort["successes"] == 0
    assert cohort["failures"] == 1
    outcome = cohort["outcomes"][0]
    assert outcome["status"] == "failed"
    assert outcome["stage"] == "compile"
    assert "record not persisted" in outcome["detail"]
    directory = output / "seed-0"
    assert not (directory / "failure.json").exists()
    # The staged partial artifacts were still persisted for inspection.
    assert (directory / "program.json").is_file()
    assert outcome["partial_artifacts"] == [
        "cadence_plan.json", "cadence_policy.json",
        "composition_plan.json", "program.json",
    ]


# ---------------------------------------------------------------------------
# Experimental style profiles (restrained / driving)
# ---------------------------------------------------------------------------

def test_styles_produce_different_rendering_features() -> None:
    """The two built-in styles realize clearly different, contrasting content.

    Each style alters the *realized* sound (tempo, per-role velocity / gate,
    per-role rhythm, and the cadence policy's voice-leading cap / candidate
    budget).  The realized feature vectors therefore differ between the two
    styles and from the baseline, and the realized projects carry distinct
    hashes.  No auditory T/D/S claim is made; this only asserts the realizations
    differ.
    """
    from app.songprogram.style_profile import STYLE_PROFILES
    from tools.cluster_piano_v3_cadence import features

    def _load(style_profile):
        artifacts, report = generate_one(
            "2/1", 4, skip_wav=True, crossing_match="non_crossing",
            style_profile=style_profile,
        )
        plan = json.loads(artifacts["composition_plan.json"])
        cadence = json.loads(artifacts["cadence_plan.json"])
        project = json.loads(artifacts["project.json"])
        return features(plan, cadence, project), report

    baseline_features, baseline_report = _load(None)
    restrained_features, restrained_report = _load(STYLE_PROFILES["restrained"])
    driving_features, driving_report = _load(STYLE_PROFILES["driving"])

    # The two styles are clearly contrasting in their realized content, and each
    # differs from the baseline (the realized sound changed).
    assert restrained_features != driving_features
    assert restrained_features != baseline_features
    assert driving_features != baseline_features

    # The realized projects carry three distinct hashes.
    assert len({
        baseline_report["project_hash"],
        restrained_report["project_hash"],
        driving_report["project_hash"],
    }) == 3


def test_no_style_records_null_provenance_and_baseline_hashes() -> None:
    """With no style selected the report records null provenance and the
    baseline Program/Project hashes are unchanged (byte-identical)."""
    _, report = generate_one("2/1", 4, skip_wav=True)
    assert report["style_profile"] is None
    assert report["style_profile_hash"] is None
    assert report["program_hash"] == (
        "sha256:ebd5f9e1fc6bd1b89c17449a6c204de723c775fb3041efa3f4cb47ed215e06c8"
    )
    assert report["project_hash"] == (
        "sha256:c734f6aa8ee852eac982aa30d5e7c31ac99243b11738bbce0a6a129cd002e054"
    )


def test_styled_run_records_style_provenance_and_reconciles() -> None:
    """A styled run records the full profile body and hash, stays unsealed, and
    still reconciles every cadence slot (the dictionary binding is intact)."""
    from app.songprogram.style_profile import STYLE_PROFILES, style_profile_hash

    profile = STYLE_PROFILES["driving"]
    _, report = generate_one(
        "2/1", 4, skip_wav=True, crossing_match="non_crossing",
        style_profile=profile,
    )
    assert report["status"] == "success"
    assert report["style_profile"] == profile
    assert report["style_profile_hash"] == style_profile_hash(profile)
    assert report["profile_status"] == "unsealed"
    # The cadence plan's dictionary binding is intact: every slot reconciles.
    assert report["candidate_slots"] == report["matched_slots"]
    assert all(row["status"] == "matched" for row in report["slot_bindings"])
    assert all(row["source_dictionary_hash"] == report["dictionary_hash"]
               for row in report["slot_bindings"])


def test_styled_run_rejects_a_tampered_profile() -> None:
    """A style profile whose body no longer matches its hash fails closed."""
    import copy

    from app.songprogram.style_profile import STYLE_PROFILES, StyleProfileError
    from tools.generate_piano_v3_cadence_trial import V3TrialFailure

    profile = copy.deepcopy(STYLE_PROFILES["driving"])
    profile["tempo_milli_bpm"] += 1  # body changed, hash stale
    with pytest.raises((V3TrialFailure, StyleProfileError)):
        generate_one(
            "2/1", 4, skip_wav=True, crossing_match="non_crossing",
            style_profile=profile,
        )
