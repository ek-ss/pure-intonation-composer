from __future__ import annotations

import json

import pytest

from .pil_synthetic_blind_assignment import build_blind_assignment_set
from .pil_synthetic_judge_runner import PILSyntheticJudgeError, run_blind_judgments
from .test_pil_synthetic_authority_validator import _chain, _schema_validator


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_runner_exposes_only_opaque_id_and_pcm_and_is_order_independent() -> None:
    chain = _chain()
    pcm = b"RIFF synthetic pcm fixture"
    context_hash = "sha256:" + __import__("hashlib").sha256(pcm).hexdigest()
    assignment = build_blind_assignment_set(
        scope=chain["protocol"]["scope"],
        protocol_hash=chain["protocol"]["protocol_hash"],
        cohort_manifest_hash=chain["cohort"]["manifest_hash"],
        agent_manifest_hashes=[agent["manifest_hash"] for agent in chain["agents"]],
        sealed_context_hashes=[context_hash],
    )
    seen: list[tuple[dict, str, bytes]] = []

    def adapter(request, opaque_id, audio):
        seen.append((dict(request), opaque_id, audio))
        return _canonical({
            "schema": "cps.pil-synthetic-judge-response",
            "schema_version": "1.0.0",
            "judgments": [{
                "metric_id": "pil.genre.cliche",
                "ordinal_label": "below",
                "available": True,
            }],
        })

    records = run_blind_judgments(
        protocol=chain["protocol"], agents=list(reversed(chain["agents"])),
        assignment_set=assignment, pcm_by_context_hash={context_hash: pcm},
        adapter=adapter, schema_validator=_schema_validator,
    )
    assert len(records) == len(chain["agents"])
    assert all(audio == pcm and opaque_id.startswith("item_") for _, opaque_id, audio in seen)
    assert all("genre" not in request and "filename" not in request for request, _, _ in seen)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema":"cps.pil-synthetic-judge-response","schema_version":"1.0.0","judgments":[]}\n',
        b'{"judgments":[],"schema":"cps.pil-synthetic-judge-response","schema_version":"1.0.0"}',
        b'{"free_text":"ignore the rubric"}',
        b'not json',
    ],
)
def test_runner_rejects_noncanonical_free_text_or_invalid_response(payload: bytes) -> None:
    chain = _chain()
    pcm = b"pcm"
    context_hash = "sha256:" + __import__("hashlib").sha256(pcm).hexdigest()
    assignment = build_blind_assignment_set(
        scope=chain["protocol"]["scope"],
        protocol_hash=chain["protocol"]["protocol_hash"],
        cohort_manifest_hash=chain["cohort"]["manifest_hash"],
        agent_manifest_hashes=[chain["agents"][0]["manifest_hash"]],
        sealed_context_hashes=[context_hash],
    )
    with pytest.raises(PILSyntheticJudgeError, match="PIL_SYNTHETIC_RESPONSE_INVALID"):
        run_blind_judgments(
            protocol=chain["protocol"], agents=[chain["agents"][0]],
            assignment_set=assignment, pcm_by_context_hash={context_hash: pcm},
            adapter=lambda request, opaque_id, audio: payload,
            schema_validator=_schema_validator,
        )
