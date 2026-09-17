"""Run a non-authoritative multi-seed sample/compile/render diversity trial."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.fallback import (  # noqa: E402
    _search_decision_hash,
    execute_broad_prior_production,
)
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.structural_sampler import (  # noqa: E402
    _hash,
    execute_structural_sampler,
    structural_program_hash,
)
from tests.test_songprogram_fallback import _production_v11_request  # noqa: E402
from tests.test_songprogram_structural_sampler import _authorities  # noqa: E402

RENDER_FIXTURE = BACKEND / "songprogram_conformance" / "fixtures" / "render"
ROLE_ORDER = ("drums", "bass", "harmony", "melody", "texture")


def _trial_catalog() -> tuple[dict[str, Any], bytes, str]:
    base = json.loads((RENDER_FIXTURE / "catalog.json").read_text())
    pitched = next(item for item in base["entries"] if item["kind"] == "pitched")
    drum = next(item for item in base["entries"] if item["kind"] == "drum_kit")
    entries = [drum]
    for role in ROLE_ORDER[1:]:
        item = json.loads(json.dumps(pitched))
        item["instrument_id"] = f"trial_{role}"
        item["role"] = role
        entries.append(item)
    catalog = {
        "schema": base["schema"],
        "schema_version": base["schema_version"],
        "engine": base["engine"],
        "entries": entries,
    }
    payload = canonical_bytes(catalog)
    digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + payload).hexdigest()
    return catalog, payload, digest


def _one(seed: int, output: str) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {"seed": seed, "status": "sampler_failed"}
    try:
        request, sampler, structural_manifest = _authorities()
        request["root_seed"] = seed
        request["cohort_index"] = seed
        request["request_hash"] = _hash(
            "cps.structural-sampler-request/v1.1", request, omit="request_hash"
        )
        sampled = execute_structural_sampler(request, sampler, structural_manifest)
        if sampled["result"]["status"] != "success":
            row["error"] = sampled["result"]["error"]
            return row
        structural = sampled["structural_program"]
        production_request, production_manifest, _, _ = _production_v11_request()
        active_roles = sorted(
            {item["role"] for item in structural["realizations"]}, key=ROLE_ORDER.index
        )
        production_request.update(
            root_seed=seed,
            cohort_index=seed,
            structural_program=structural,
            structural_program_hash=structural_program_hash(structural),
            active_roles=active_roles,
            structural_lowering_manifest_hash=structural_manifest["manifest_hash"],
        )
        production_request["request_hash"] = _search_decision_hash(
            production_request, "request_hash"
        )
        produced = execute_broad_prior_production(
            production_request,
            production_manifest,
            _production_v11_request()[2],
            structural_manifest,
        )
        if produced["status"] != "success":
            row.update(status="production_failed", error=produced["error"])
            return row
        program = produced["output"]["program"]
        catalog, catalog_bytes, catalog_digest = _trial_catalog()
        program["production"]["catalog_digest"] = catalog_digest
        for track in program["tracks"]:
            track["instrument_id"] = (
                "drum_fixture_kit" if track["role"] == "drums" else f"trial_{track['role']}"
            )
        identity = CompilerIdentity(
            "fixture-cohort/v1",
            "fixture-resolver",
            "sha256:" + "10" * 32,
            "sha256:" + "11" * 32,
            catalog_digest,
        )
        compile_started = time.monotonic()
        project = compile_sp0(program, identity)
        compile_ms = round((time.monotonic() - compile_started) * 1000)
        manifest = json.loads((RENDER_FIXTURE / "render_manifest.json").read_text())

        def resolve(uri: str) -> bytes:
            return (RENDER_FIXTURE / "assets" / f"{uri.rsplit('/', 1)[-1]}.wav").read_bytes()

        rendered = render_reference(
            project,
            catalog_bytes,
            resolve,
            render_manifest_digest=manifest["render_manifest_digest"],
            project_artifact_hash=project_hash(project),
        )
        destination = Path(output) / f"seed-{seed:04d}"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "program.json").write_bytes(canonical_bytes(program))
        (destination / "project.json").write_bytes(canonical_bytes(project))
        (destination / "preview.wav").write_bytes(rendered.wav)
        pitched = [event for event in project["events"] if event["kind"] == "note"]
        vectors = [
            tuple(event["pitch_provenance"]["final_vector"])
            for event in pitched
            if event["pitch_provenance"].get("final_vector") is not None
        ]
        vector_counts = Counter(vectors)
        row.update(
            status="success",
            program_hash=program_hash(program),
            project_hash=project_hash(project),
            wav_hash=rendered.report["wav_hash"],
            event_count=len(project["events"]),
            compile_ms=compile_ms,
            roles=active_roles,
            material_kinds=sorted(
                [item["kind"] for item in program["materials"] if item["kind"] != "rhythm_cell"]
            ),
            equave=program["lattice"]["equave"],
            generators=program["lattice"]["generators"],
            pitched_event_count=len(pitched),
            vector_observation_count=len(vectors),
            nonzero_vector_count=sum(any(value != 0 for value in vector) for vector in vectors),
            unique_vectors=[list(vector) for vector in sorted(set(vectors))],
            vector_event_count=[
                {"vector": list(vector), "event_count": count}
                for vector, count in sorted(vector_counts.items())
            ],
        )
        return row
    except Exception as error:  # trial ledger must retain every failed coordinate
        row.update(status="compile_or_render_failed", error=f"{type(error).__name__}:{error}")
        return row
    finally:
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)


def _duplicates(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values = [row[key] for row in rows if row["status"] == "success"]
    unique = len(set(values))
    duplicates = len(values) - unique
    return {
        "total": len(values),
        "unique": unique,
        "duplicates": duplicates,
        "duplicate_basis_points": round(10000 * duplicates / len(values)) if values else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 1000 or not 1 <= args.workers <= 32:
        parser.error("seeds must be 1..1000 and workers 1..32")
    args.output.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(_one, range(args.seeds), [str(args.output)] * args.seeds))
    rows.sort(key=lambda row: row["seed"])
    successes = [row for row in rows if row["status"] == "success"]
    role_presence = Counter(role for row in successes for role in row["roles"])
    material_counts = Counter(kind for row in successes for kind in row["material_kinds"])
    equaves = Counter(row["equave"] for row in successes)
    vectors = Counter(tuple(vector) for row in successes for vector in row["unique_vectors"])
    vector_events: Counter[tuple[int, ...]] = Counter()
    for row in successes:
        vector_events.update(
            {tuple(item["vector"]): item["event_count"] for item in row["vector_event_count"]}
        )
    report = {
        "schema": "cps.fixture-generation-cohort-report",
        "schema_version": "1.0.0",
        "non_authoritative": True,
        "seed_count": args.seeds,
        "worker_count": args.workers,
        "compile_survival": {
            "success": len(successes),
            "failed": args.seeds - len(successes),
            "basis_points": round(10000 * len(successes) / args.seeds),
        },
        "duplicates": {
            key: _duplicates(rows, key) for key in ("program_hash", "project_hash", "wav_hash")
        },
        "role_presence": dict(sorted(role_presence.items())),
        "role_presence_basis_points": {
            role: round(10000 * count / len(successes)) if successes else 0
            for role, count in sorted(role_presence.items())
        },
        "material_kind_count": dict(sorted(material_counts.items())),
        "lattice_exposure": {
            "equave_count": dict(sorted(equaves.items())),
            "unique_vector_count": len(vectors),
            "vector_candidate_presence": [
                {"vector": list(vector), "candidate_count": count}
                for vector, count in sorted(vectors.items())
            ],
            "vector_event_count": [
                {"vector": list(vector), "event_count": count}
                for vector, count in sorted(vector_events.items())
            ],
            "pitched_event_count": sum(row["pitched_event_count"] for row in successes),
            "nonzero_vector_count": sum(row["nonzero_vector_count"] for row in successes),
        },
        "rows": rows,
    }
    payload = canonical_bytes(report)
    (args.output / "cohort_report.json").write_bytes(payload)
    sys.stdout.buffer.write(payload)


if __name__ == "__main__":
    main()
