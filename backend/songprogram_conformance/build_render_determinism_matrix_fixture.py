"""Independent owner tool for the GEN0-C determinism-matrix golden fixture.

This module intentionally imports no production renderer code.  The three
projects are silent boundary cases, so their normative PCM is derived directly
from the renderer contract's 256 trailing frames.
"""

from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any


BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
SOURCE = BACKEND / "songprogram_conformance/fixtures/compiler/gen0b_melody_project.json"
RENDER = BACKEND / "songprogram_conformance/fixtures/render"
SCHEMAS = BACKEND / "songprogram_conformance/schemas"
OUT = BACKEND / "songprogram_conformance/fixtures/render_determinism_matrix"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def canonical_lf(value: Any) -> bytes:
    return canonical(value) + b"\n"


def sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def domain_hash(domain: str, value: Any) -> str:
    return sha(domain.encode("utf-8") + b"\0" + canonical_lf(value))


def project_hash(project: dict[str, Any]) -> str:
    return sha(project["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + canonical(project))


def _project(case_id: str, tracks: list[tuple[str, str]]) -> dict[str, Any]:
    project = deepcopy(json.loads(SOURCE.read_text(encoding="utf-8")))
    project["compiler"]["instrument_catalog_digest"] = json.loads(
        (RENDER / "render_manifest.json").read_text(encoding="utf-8")
    )["catalog_digest"]
    project["source_program"]["hash"] = sha(("matrix:" + case_id).encode())
    project["tracks"] = [
        {
            "id": track_id,
            "role": "harmony",
            "instrument_id": instrument,
            "register_millicents": [-1200000, 3600000],
            "maximum_polyphony": 8,
            "drum_map": None,
        }
        for track_id, instrument in tracks
    ]
    project["material_instances"] = []
    project["resolved_chords"] = []
    project["harmony_occurrences"] = []
    project["events"] = []
    project["mix"] = {track_id: {"gain_q": 10000, "pan_q": 0} for track_id, _ in tracks}
    return project


def _drum_project() -> dict[str, Any]:
    project = _project("drum_note_36", [("drums", "drum_fixture_kit")])
    project["tracks"][0].update(
        {"role": "drums", "register_millicents": None, "drum_map": {"kick": 36}}
    )
    source = deepcopy(json.loads(SOURCE.read_text(encoding="utf-8"))["events"][0]["source"])
    project["events"] = [
        {
            "id": "ev_azq5zat6j2rc3zb2uflq",
            "kind": "drum",
            "track_id": "drums",
            "section_id": "sec_a",
            "start_tick": 0,
            "duration_ticks": 120,
            "velocity": 127,
            "articulation": "normal",
            "drum_note": 36,
            "ratio": None,
            "chord_index": None,
            "pitch_provenance": None,
            "source": source,
        }
    ]
    return project


def _silent_result(project: dict[str, Any], render_manifest_digest: str) -> dict[str, Any]:
    samples: list[int]
    if project["events"]:
        asset = next((RENDER / "assets").glob("f1c222*.wav")).read_bytes()
        samples = list(struct.unpack("<8i", asset[44:]))
    else:
        samples = []
    frames = len(samples) + 256
    pcm = b"".join(struct.pack("<ii", value, value) for value in samples) + b"\0" * 256 * 2 * 4
    wav = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 2, 48000, 384000, 8, 32)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )
    p_hash = project_hash(project)
    tracks = [
        {
            "track_id": row["id"],
            "format": "pcm-s32le-stereo-interleaved/v1",
            "frame_count": frames,
            "pcm_byte_length": len(pcm),
            "pcm_hash": sha(pcm),
            "saturation_count": 0,
            "peak_absolute_sample": max((abs(v) for v in samples), default=0),
        }
        for row in sorted(project["tracks"], key=lambda item: item["id"].encode())
    ]
    report = {
        "schema": "cps.reference-render-report",
        "schema_version": "1.1.0",
        "project_artifact_hash": p_hash,
        "render_manifest_digest": render_manifest_digest,
        "catalog_digest": project["compiler"]["instrument_catalog_digest"],
        "wav_hash": sha(wav),
        "pcm_hash": sha(pcm),
        "frame_count": frames,
        "saturation_count": 0,
        "peak_absolute_sample": max((abs(v) for v in samples), default=0),
        "track_hashes": tracks,
    }
    track_pairs = [[row["track_id"], row["pcm_hash"]] for row in tracks]
    return {
        "project_hash": p_hash,
        "wav_hash": sha(wav),
        "pcm_hash": sha(pcm),
        "report_hash": domain_hash("cps.reference-render-report/v1.1", report),
        "track_set_hash": domain_hash("cps.render-track-set/v1", track_pairs),
    }


def build(out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    projects_dir = out / "projects"
    projects_dir.mkdir(exist_ok=True)
    projects = {
        "silent_one_2_1": _project("silent_one_2_1", [("harmony", "pitched_fixture_2_1")]),
        "silent_one_3_1": _project("silent_one_3_1", [("harmony", "pitched_fixture_3_1")]),
        "silent_two_tracks": _project(
            "silent_two_tracks",
            [("a_harmony", "pitched_fixture_2_1"), ("z_harmony", "pitched_fixture_3_1")],
        ),
        "drum_note_36": _drum_project(),
    }
    for case_id, project in projects.items():
        (projects_dir / f"{case_id}.json").write_bytes(canonical_lf(project))

    input_paths = [
        *sorted(projects_dir.glob("*.json")),
        RENDER / "catalog.json",
        RENDER / "render_manifest.json",
        *sorted((RENDER / "assets").glob("*.wav")),
        SCHEMAS / "arrangement_project_1_2.schema.json",
    ]
    files = []
    for path in sorted(
        input_paths,
        key=lambda p: unicodedata.normalize("NFC", p.relative_to(REPO).as_posix()).encode(),
    ):
        relative = unicodedata.normalize("NFC", path.relative_to(REPO).as_posix())
        raw = path.read_bytes()
        files.append({"path": relative, "byte_length": len(raw), "sha256": sha(raw)})
    fixture_set = {"schema": "cps.render-fixture-set", "schema_version": "1.0.0", "files": files}
    fixture_set_bytes = canonical_lf(fixture_set)
    (out / "fixture_set.json").write_bytes(fixture_set_bytes)

    render_manifest = json.loads((RENDER / "render_manifest.json").read_text(encoding="utf-8"))
    cases = []
    for case_id, project in sorted(projects.items(), key=lambda row: row[0].encode()):
        cases.append(
            {
                "case_id": case_id,
                **_silent_result(project, render_manifest["render_manifest_digest"]),
            }
        )
    manifest = {
        "schema": "cps.render-determinism-matrix-manifest",
        "schema_version": "1.0.0",
        "contract": "gen0-c-render-determinism-matrix/v1",
        "fixture_set_hash": sha(fixture_set_bytes),
        "project_schema_hash": sha((SCHEMAS / "arrangement_project_1_2.schema.json").read_bytes()),
        "catalog_digest": render_manifest["catalog_digest"],
        "render_manifest_digest": render_manifest["render_manifest_digest"],
        "renderer_build_hash": render_manifest["renderer_build"]["source_sha256"],
        "invocation_count": 100,
        "case_schedule": "invocation-ordinal-mod-case-count/v1",
        "python_hash_seeds": [0, 1, 7, 42],
        "worker_counts": [1, 2, 4, 8],
        "test_block_sizes": [64, 256, 1024],
        "cases": cases,
    }
    manifest["manifest_hash"] = domain_hash("cps.render-determinism-matrix-manifest/v1", manifest)
    (out / "matrix_manifest.json").write_bytes(canonical_lf(manifest))

    invocations = [
        [
            ordinal,
            cases[ordinal % len(cases)]["case_id"],
            *[
                cases[ordinal % len(cases)][key]
                for key in ("wav_hash", "pcm_hash", "report_hash", "track_set_hash")
            ],
        ]
        for ordinal in range(100)
    ]
    sequence_hash = domain_hash("cps.render-determinism-sequence/v1", invocations)
    case_results = [
        [row[key] for key in ("case_id", "wav_hash", "pcm_hash", "report_hash", "track_set_hash")]
        for row in cases
    ]
    result_set_hash = domain_hash("cps.render-block-case-result-set/v1", case_results)
    receipt = {
        "schema": "cps.render-determinism-matrix-receipt",
        "schema_version": "1.0.0",
        "manifest_hash": manifest["manifest_hash"],
        "baseline_sequence_hash": sequence_hash,
        "process_coordinates": [
            {
                "python_hash_seed": seed,
                "workers": workers,
                "invocation_count": 100,
                "sequence_hash": sequence_hash,
            }
            for seed in (0, 1, 7, 42)
            for workers in (1, 2, 4, 8)
        ],
        "block_coordinates": [
            {"block_size": size, "case_count": len(cases), "case_result_set_hash": result_set_hash}
            for size in (64, 256, 1024)
        ],
        "all_process_equal": True,
        "all_blocks_equal": True,
    }
    receipt["receipt_hash"] = domain_hash("cps.render-determinism-matrix-receipt/v1", receipt)
    (out / "matrix_receipt.json").write_bytes(canonical_lf(receipt))


if __name__ == "__main__":
    build()
