from __future__ import annotations

import json

import httpx
import pytest

from app.songprogram.openai_audio_judge import OpenAIAudioJudge, OpenAIAudioJudgeError


@pytest.mark.parametrize("model", ["gpt-audio", "gpt-audio-latest", "gpt_audio_2025"])
def test_adapter_rejects_aliases_and_non_snapshots(model: str) -> None:
    with pytest.raises(OpenAIAudioJudgeError, match="MODEL_SNAPSHOT_REQUIRED"):
        OpenAIAudioJudge(model_snapshot=model, metric_ids=("pil.genre.typicality",), api_key="test")


@pytest.mark.parametrize(
    "model", ["gpt-audio-2025-08-28", "gpt-4o-audio-preview-2024-12-17"]
)
def test_multi_model_audio_request_and_exact_returned_identity(model: str) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        content = json.dumps({
            "judgments": [{
                "available": True, "metric_id": "pil.genre.typicality",
                "ordinal_label": "above",
            }],
            "schema": "cps.pil-synthetic-judge-response", "schema_version": "1.0.0",
        }, separators=(",", ":"), sort_keys=True)
        return httpx.Response(200, json={
            "model": model, "choices": [{"message": {"content": content}}]
        })

    adapter = OpenAIAudioJudge(
        model_snapshot=model, metric_ids=("pil.genre.typicality",), api_key="test", base_url="https://unit.test/v1",
        transport=httpx.MockTransport(handler),
    )
    result = adapter({}, "item_deadbeefdeadbeefdeadbeef", b"RIFF audio")
    assert json.loads(result)["schema"] == "cps.pil-synthetic-judge-response"
    assert seen["model"] == model
    assert seen["messages"][0]["content"][1]["type"] == "input_audio"


def test_adapter_rejects_server_model_alias_or_substitution() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "model": "gpt-audio-newer", "choices": [{"message": {"content": "{}"}}]
    }))
    adapter = OpenAIAudioJudge(
        model_snapshot="gpt-audio-2025-08-28",
        metric_ids=("pil.genre.typicality",), api_key="test", transport=transport
    )
    with pytest.raises(OpenAIAudioJudgeError, match="MODEL_IDENTITY_MISMATCH"):
        adapter({}, "item_deadbeefdeadbeefdeadbeef", b"RIFF audio")
