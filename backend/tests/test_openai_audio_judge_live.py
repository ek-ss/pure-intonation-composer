from __future__ import annotations

import io
import os
import wave

import pytest

from app.songprogram.openai_audio_judge import OpenAIAudioJudge


def _silent_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 8000)
    return output.getvalue()


@pytest.mark.live_api
def test_real_audio_multi_model_smoke() -> None:
    if os.environ.get("CPS_RUN_LIVE_AUDIO_JUDGE") != "1":
        pytest.skip("set CPS_RUN_LIVE_AUDIO_JUDGE=1 to permit billed external calls")
    models = tuple(filter(None, os.environ.get("CPS_OPENAI_AUDIO_MODEL_SNAPSHOTS", "").split(",")))
    if len(models) < 2:
        pytest.skip("set at least two exact snapshots in CPS_OPENAI_AUDIO_MODEL_SNAPSHOTS")
    for model in models:
        response = OpenAIAudioJudge(
            model_snapshot=model,
            metric_ids=("pil.genre.typicality",),
        )({}, "item_000000000000000000000000", _silent_wav())
        assert b"pil.genre.typicality" in response
