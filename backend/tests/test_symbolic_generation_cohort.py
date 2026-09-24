from __future__ import annotations

import json

from tools.run_composition_generation_cohort import _generate
from tools.generate_composition_song import DEFAULT_PROFILE, DEFAULT_REALIZATION_PROFILE
from tools.run_fixture_generation_cohort import DEFAULT_GENERATION_MANIFEST


def test_cached_symbolic_receipt_requires_same_mode_and_profiles(tmp_path) -> None:
    directory = tmp_path / "seed-0001"
    directory.mkdir()
    receipt = {
        "render_status": "skipped", "profile_hash": json.loads(DEFAULT_PROFILE.read_text())["profile_hash"],
        "realization_profile_hash": json.loads(DEFAULT_REALIZATION_PROFILE.read_text())["profile_hash"],
    }
    (directory / "receipt.json").write_text(json.dumps(receipt))
    args = (1, str(tmp_path), str(DEFAULT_PROFILE), str(DEFAULT_GENERATION_MANIFEST), "none",
            str(DEFAULT_REALIZATION_PROFILE))
    assert _generate(*args, skip_wav=True)["status"] == "success"
    assert _generate(*args, skip_wav=False)["error"] == "GENERATION_RECEIPT_MODE_MISMATCH"
    receipt["profile_hash"] = "sha256:" + "0" * 64
    (directory / "receipt.json").write_text(json.dumps(receipt))
    assert _generate(*args, skip_wav=True)["error"] == "GENERATION_RECEIPT_PROFILE_MISMATCH"
