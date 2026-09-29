from __future__ import annotations

import pytest

from app.audio_reference.targets import (
    TARGETS,
    TargetError,
    require_executable,
    resolve_target,
)


def test_full_song_target_is_executable() -> None:
    target = resolve_target("full-song-generation-v1")
    assert target.executable is True
    assert target.dimensions == 3
    require_executable(target)  # must not raise


def test_piano_v1_is_historical_and_not_selectable() -> None:
    target = resolve_target("piano-solo-v1")
    assert target.executable is False
    assert target.dimensions == 2
    with pytest.raises(TargetError) as exc:
        require_executable(target)
    assert exc.value.code == "TARGET_NOT_EXECUTABLE"


def test_piano_v3_targets_are_registered_but_not_executable() -> None:
    for manifest_id in ("piano-solo-v3-octave", "piano-solo-v3-tritave"):
        target = resolve_target(manifest_id)
        assert target.executable is False
        assert target.dimensions == 5
        with pytest.raises(TargetError):
            require_executable(target)


def test_unknown_target_is_rejected() -> None:
    with pytest.raises(TargetError) as exc:
        resolve_target("does-not-exist")
    assert exc.value.code == "TARGET_UNKNOWN"
    # The error lists the known ids so a caller can self-correct.
    assert "full-song-generation-v1" in exc.value.detail


def test_registry_is_closed() -> None:
    assert set(TARGETS) == {
        "full-song-generation-v1",
        "piano-solo-v1",
        "piano-solo-v3-octave",
        "piano-solo-v3-tritave",
    }
