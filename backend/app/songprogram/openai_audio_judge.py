"""OpenAI Chat Completions adapter for sealed synthetic PIL audio judgments."""

from __future__ import annotations

import base64
import os
import re
from collections.abc import Mapping
from typing import Any

import httpx

_SNAPSHOT = re.compile(r"^[a-z0-9][a-z0-9.-]*-20[0-9]{2}-[0-9]{2}-[0-9]{2}$")


class OpenAIAudioJudgeError(RuntimeError):
    pass


class OpenAIAudioJudge:
    """One-shot adapter. It never retries and never logs credentials or audio."""

    def __init__(
        self,
        *,
        model_snapshot: str,
        metric_ids: tuple[str, ...],
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not _SNAPSHOT.fullmatch(model_snapshot):
            raise OpenAIAudioJudgeError("OPENAI_AUDIO_MODEL_SNAPSHOT_REQUIRED")
        self.model_snapshot = model_snapshot
        if not metric_ids or tuple(sorted(set(metric_ids))) != metric_ids:
            raise OpenAIAudioJudgeError("OPENAI_AUDIO_METRIC_IDS_INVALID")
        self.metric_ids = metric_ids
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise OpenAIAudioJudgeError("OPENAI_API_KEY_MISSING")
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def __call__(self, request: Mapping[str, Any], opaque_id: str, pcm: bytes) -> bytes:
        rubric = (
            "Judge only the heard audio. Return one compact JSON object with schema "
            "cps.pil-synthetic-judge-response, schema_version 1.0.0, and sorted judgments. "
            "Each judgment has metric_id, ordinal_label, available. No prose or markdown."
            f" Required metric IDs: {','.join(self.metric_ids)}."
        )
        payload = {
            "model": self.model_snapshot,
            "temperature": 0,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{rubric}\nOpaque item: {opaque_id}"},
                    {"type": "input_audio", "input_audio": {
                        "data": base64.b64encode(pcm).decode("ascii"), "format": "wav"
                    }},
                ],
            }],
        }
        response = self.client.post("/chat/completions", json=payload)
        if response.status_code != 200:
            raise OpenAIAudioJudgeError(f"OPENAI_AUDIO_HTTP_{response.status_code}")
        body = response.json()
        if body.get("model") != self.model_snapshot:
            raise OpenAIAudioJudgeError("OPENAI_AUDIO_MODEL_IDENTITY_MISMATCH")
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise OpenAIAudioJudgeError("OPENAI_AUDIO_RESPONSE_INVALID") from error
        if not isinstance(content, str):
            raise OpenAIAudioJudgeError("OPENAI_AUDIO_RESPONSE_INVALID")
        return content.encode("utf-8")
