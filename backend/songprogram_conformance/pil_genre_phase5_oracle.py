"""Independent integer-only oracle for normative PIL Phase 5 fixtures.

This module deliberately does not import ``app.songprogram``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

T = 2147483647
MISSING = ["melody", "rhythm", "form", "instrumentation", "production"]

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def artifact_hash(value: dict[str, Any], field: str) -> str:
    body = {k: v for k, v in value.items() if k != field}
    prefix = f"cps-artifact-hash/v1\0{value['schema']}\0{value['schema_version']}\0".encode()
    return "sha256:" + hashlib.sha256(prefix + canonical(body)).hexdigest()

def rhe(n: int, d: int) -> int:
    q, r = divmod(n, d)
    twice = r * 2
    return q + (twice > d or (twice == d and q % 2 == 1))

def _dense(hist: list[dict[str, int]], size: int) -> list[int]:
    out = [0] * size
    previous = -1
    for item in hist:
        ordinal = item["ordinal"]
        if item["weight_q31"] > T:
            raise ValueError("PIL_NUMERIC_OVERFLOW")
        if ordinal <= previous or ordinal >= size:
            raise ValueError("PIL_GENRE_FAILED")
        out[ordinal] = item["weight_q31"]
        previous = ordinal
    if sum(out) != T:
        raise ValueError("PIL_GENRE_FAILED")
    return out

def _hist_sim(a: list[int], b: list[int]) -> int:
    return 10000 - rhe(10000 * sum(abs(x-y) for x, y in zip(a, b)), 2*T)

def _profile_sim(a: list[int | None], b: list[int | None]) -> int | None:
    values = [10000-abs(x-y) for x, y in zip(a, b) if x is not None and y is not None]
    return None if not values else rhe(sum(values), len(values))

def evaluate(model: dict[str, Any], feature: dict[str, Any]) -> list[dict[str, Any]]:
    if model["model_hash"] != artifact_hash(model, "model_hash"):
        raise ValueError("PIL_GENRE_FAILED")
    if feature["record_hash"] != artifact_hash(feature, "record_hash"):
        raise ValueError("PIL_GENRE_FAILED")
    if model["vocabulary_hash"] != feature["vocabulary_hash"] or model["trajectory_template_set_hash"] != feature["trajectory_template_set_hash"]:
        raise ValueError("PIL_GENRE_FAILED")
    max_vocab = 1 + max([x["ordinal"] for x in feature["chord_vocabulary_histogram_q31"]] + [x["ordinal"] for e in model["entries"] for x in e["chord_vocabulary_target_q31"]])
    max_traj = 1 + max([x["ordinal"] for x in feature["progression_histogram_q31"]] + [x["ordinal"] for e in model["entries"] for h in [e["progression_target_q31"], *e["novelty_exemplars_q31"]] for x in h])
    observed_vocab = _dense(feature["chord_vocabulary_histogram_q31"], max_vocab)
    observed_traj = _dense(feature["progression_histogram_q31"], max_traj)
    results = []
    for entry in model["entries"]:
        details = [
            _hist_sim(observed_vocab, _dense(entry["chord_vocabulary_target_q31"], max_vocab)),
            _hist_sim(observed_traj, _dense(entry["progression_target_q31"], max_traj)),
            _profile_sim(feature["function_profile_q"], entry["function_target_q"]),
            _profile_sim(feature["voice_leading_profile_q"], entry["voice_leading_target_q"]),
            _profile_sim(feature["harmonic_rhythm_profile_q"], entry["harmonic_rhythm_target_q"]),
        ]
        weights = entry["detail_weights_q"]
        if sum(weights) != 10000:
            raise ValueError("PIL_GENRE_FAILED")
        available = [(v,w) for v,w in zip(details, weights) if v is not None and w]
        idiom = [(details[i],weights[i]) for i in (2,3,4) if details[i] is not None and weights[i]]
        if not available or not idiom:
            raise ValueError("PIL_GENRE_FAILED")
        cliché = sum(observed_traj[i] for i in entry["cliche_template_ordinals"] if i < len(observed_traj))
        novelty = min(rhe(10000*sum(abs(x-y) for x,y in zip(observed_traj,_dense(h,max_traj))),2*T) for h in entry["novelty_exemplars_q31"])
        result = {"schema":"cps.perceptual-genre-result","schema_version":"1.0.0","genre_id":entry["genre_id"],"model_ordinal":entry["ordinal"],"model_hash":model["model_hash"],"feature_record_hash":feature["record_hash"],"harmonic_detail_q":dict(zip(("chord_vocabulary","progression","function","voice_leading","harmonic_rhythm"),details)),"typicality_q":rhe(sum(v*w for v,w in available),sum(w for _,w in available)),"idiomaticity_q":rhe(sum(v*w for v,w in idiom),sum(w for _,w in idiom)),"cliche_dependence_q":rhe(10000*cliché,T),"novelty_q":novelty,"missing_groups":MISSING,"result_hash":""}
        result["result_hash"] = artifact_hash(result,"result_hash")
        results.append(result)
    return sorted(results,key=lambda r:(-r["typicality_q"],r["model_ordinal"],r["genre_id"].encode()))
