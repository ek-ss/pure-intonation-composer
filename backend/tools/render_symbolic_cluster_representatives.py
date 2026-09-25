"""Render cluster medoids directly from saved symbolic Projects for listening."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from fractions import Fraction

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.renderer import render_reference  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.song_validity import assess_completed_song  # noqa: E402
from tools.run_fixture_generation_cohort import (  # noqa: E402
    DEFAULT_GENERATION_MANIFEST, RENDER_FIXTURE, _trial_catalog, pcm_continuity,
)
from tools.cluster_symbolic_songs import distance_symbolic  # noqa: E402
from tools.generate_piano_solo import _piano_catalog  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _renderable(project: dict, catalog: dict) -> bool:
    entries = {row["instrument_id"]: row for row in catalog["entries"]}
    tracks = {row["id"]: row for row in project["tracks"]}
    base = project["lattice"]["base_frequency_millihz"]
    for event in project["events"]:
        if event["kind"] != "note":
            continue
        instrument = entries[tracks[event["track_id"]]["instrument_id"]]
        low, high = instrument["allowed_frequency_millihz"]
        if not low <= base * Fraction(event["ratio"]) <= high:
            return False
    return True


def _select_renderable(clusters: dict, cohort: Path, manifest: Path, limit: int | None,
                       catalog_source: str = "trial") -> list[tuple[int, int]]:
    catalog, _, _, _ = _build_catalog(_load(manifest), catalog_source)
    by_seed = {row["seed"]: row["features"] for row in clusters["rows"]}
    selected = []
    for group in clusters["clusters"][:limit]:
        original = group["representative_seed"]
        candidates = sorted(group["member_seeds"], key=lambda seed: (
            distance_symbolic(by_seed[original], by_seed[seed]), seed
        ))
        for seed in candidates:
            project = _load(cohort / f"seed-{seed:04d}" / "project.json")
            if _renderable(project, catalog):
                selected.append((original, seed))
                break
        else:
            # Preserve cluster coverage. The listening render may need an
            # explicitly labelled expanded instrument frequency envelope.
            selected.append((original, original))
    return selected


def _build_catalog(generation_manifest: dict, catalog_source: str):
    if catalog_source == "piano":
        return _piano_catalog(generation_manifest)
    return _trial_catalog(generation_manifest)


def _render(seed: int, cohort: str, output: str, manifest_path: str,
            catalog_source: str = "trial") -> dict:
    source = Path(cohort) / f"seed-{seed:04d}"
    destination = Path(output) / f"seed-{seed:04d}"
    existing = destination / "render_receipt.json"
    if existing.is_file():
        receipt = _load(existing)
        audio = destination / "reference.wav"
        if audio.is_file() and receipt["wav_hash"] == "sha256:" + hashlib.sha256(audio.read_bytes()).hexdigest():
            return {"seed": seed, "status": "success", "receipt": receipt}
        return {"seed": seed, "status": "failed", "error": "EXISTING_RENDER_TAMPERED"}
    try:
        project = _load(source / "project.json")
        program = _load(source / "program.json")
        symbolic = _load(source / "receipt.json")
        if (symbolic["seed"] != seed or symbolic.get("render_status") != "skipped"
                or symbolic["project_hash"] != project_hash(project)):
            raise ValueError("SYMBOLIC_SOURCE_MISMATCH")
        generation_manifest = _load(Path(manifest_path))
        catalog, catalog_bytes, digest, assets = _build_catalog(
            generation_manifest, catalog_source
        )
        if project["compiler"]["instrument_catalog_digest"] != digest:
            raise ValueError("CATALOG_MISMATCH")
        expanded = not _renderable(project, catalog)
        preview_project = project
        if expanded:
            preview_project = copy.deepcopy(project)
            catalog = copy.deepcopy(catalog)
            tracks = {track["id"]: track for track in project["tracks"]}
            by_instrument: dict[str, list[Fraction]] = {}
            base = project["lattice"]["base_frequency_millihz"]
            for event in project["events"]:
                if event["kind"] == "note":
                    instrument = tracks[event["track_id"]]["instrument_id"]
                    by_instrument.setdefault(instrument, []).append(base * Fraction(event["ratio"]))
            for entry in catalog["entries"]:
                frequencies = by_instrument.get(entry["instrument_id"])
                if frequencies:
                    low, high = entry["allowed_frequency_millihz"]
                    entry["allowed_frequency_millihz"] = [
                        min(low, min(value.numerator // value.denominator for value in frequencies)),
                        max(high, max(-(-value.numerator // value.denominator) for value in frequencies)),
                    ]
            catalog_bytes = canonical_bytes(catalog)
            digest = "sha256:" + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
            preview_project["compiler"]["instrument_catalog_digest"] = digest
        render_manifest = _load(RENDER_FIXTURE / "render_manifest.json")
        rendered = render_reference(
            preview_project, catalog_bytes, assets.__getitem__,
            render_manifest_digest=render_manifest["render_manifest_digest"],
            project_artifact_hash=project_hash(preview_project),
        )
        roles = {track["id"]: track["role"] for track in project["tracks"]}
        masks = {tuple(sorted({roles[event["track_id"]] for event in project["events"]
                               if event["section_id"] == section["id"]}))
                 for section in project["form"]}
        validity = assess_completed_song(
            program, project, symbolic_coverage={"overall_coverage_basis_points": 10000},
            arrangement={"status": "passed", "distinct_role_mask_count": len(masks)},
            pcm_continuity=pcm_continuity(rendered.wav),
        )
        receipt = {"schema": "cps.symbolic-cluster-listening-render", "schema_version": "1.0.0",
                   "seed": seed, "source_project_hash": symbolic["project_hash"],
                   "preview_project_hash": project_hash(preview_project),
                   "expanded_frequency_envelope": expanded,
                   "wav_hash": rendered.report["wav_hash"],
                   "song_validity_hash": validity["assessment_hash"],
                   "archive_eligible": validity["archive_eligible"] and not expanded,
                   "non_authoritative": True}
        destination.mkdir(parents=True, exist_ok=True)
        if expanded:
            (destination / "preview_project.json").write_bytes(canonical_bytes(preview_project))
            (destination / "preview_catalog.json").write_bytes(catalog_bytes)
        (destination / "reference.wav").write_bytes(rendered.wav)
        (destination / "song_validity.json").write_bytes(canonical_bytes(validity))
        (destination / "render_receipt.json").write_bytes(canonical_bytes(receipt))
        return {"seed": seed, "status": "success", "receipt": receipt}
    except (ValueError, KeyError, OSError) as error:
        return {"seed": seed, "status": "failed", "error": str(error)}


def run(clusters_path: Path, cohort: Path, output: Path, *, workers: int = 2,
        generation_manifest: Path = DEFAULT_GENERATION_MANIFEST, limit: int | None = None,
        catalog_source: str = "trial") -> dict:
    clusters = _load(clusters_path)
    selected = _select_renderable(clusters, cohort, generation_manifest, limit, catalog_source)
    if not selected or workers < 1:
        raise ValueError("empty representatives or invalid workers")
    seeds = [seed for _, seed in selected]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(_render, seeds, [str(cohort)] * len(seeds), [str(output)] * len(seeds),
                             [str(generation_manifest)] * len(seeds),
                             [catalog_source] * len(seeds)))
    for row, (original, _) in zip(rows, selected, strict=True):
        row["cluster_medoid_seed"] = original
    report = {"schema": "cps.symbolic-cluster-listening-cohort", "schema_version": "1.0.0",
              "cluster_report_hash": clusters["report_hash"],
              "rows": rows, "success_count": sum(row["status"] == "success" for row in rows),
              "failure_count": sum(row["status"] == "failed" for row in rows)}
    output.mkdir(parents=True, exist_ok=True)
    (output / "listening_report.json").write_bytes(canonical_bytes(report))
    by_medoid = {row["representative_seed"]: row for row in clusters["clusters"]}
    playlist = ["#EXTM3U"]
    index = ["# Section-cluster listening set", "",
             f"Source: `{cohort}` / cluster report `{clusters_path}`", "",
             "One WAV per cluster. Envelope-expanded previews are labelled and are not archive-eligible.", "",
             "| Cluster medoid | Audio seed | Members | Opening | Closure | Render | Listen |",
             "| ---: | ---: | ---: | --- | --- | --- | --- |"]
    for row in rows:
        medoid = row["cluster_medoid_seed"]
        seed = row["seed"]
        group = by_medoid[medoid]
        if row["status"] != "success":
            index.append(f"| {medoid} | {seed} | {group['member_count']} | — | — | {row['error']} | — |")
            continue
        receipt = row["receipt"]
        mode = "expanded preview" if receipt.get("expanded_frequency_envelope") else "reference"
        opening = f"{group['opening'][0]} bars / {group['opening'][3]}"
        closure = f"{group['closure'][0]} bars / {group['closure'][3]}"
        relative = f"seed-{seed:04d}/reference.wav"
        index.append(f"| {medoid} | {seed} | {group['member_count']} | {opening} | {closure} | {mode} | [WAV]({relative}) |")
        playlist.extend((f"#EXTINF:-1,cluster {medoid} seed {seed} ({mode})", relative))
    (output / "listening_index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    (output / "representatives.m3u").write_text("\n".join(playlist) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generation-manifest", type=Path, default=DEFAULT_GENERATION_MANIFEST)
    parser.add_argument("--catalog-source", choices=("trial", "piano"), default="trial",
                        help="instrument catalog for the listening render")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, help="render only the first N medoids for a pilot")
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(REPO / "local_authority"):
        parser.error("output must be in local_authority")
    report = run(args.clusters, args.cohort, args.output, workers=args.workers,
                 generation_manifest=args.generation_manifest, limit=args.limit,
                 catalog_source=args.catalog_source)
    print(json.dumps({"success": report["success_count"], "failed": report["failure_count"],
                      "seeds": [row["seed"] for row in report["rows"]]}, sort_keys=True))
    if report["failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
