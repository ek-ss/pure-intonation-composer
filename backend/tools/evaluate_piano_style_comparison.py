"""Validate and compare paired full-song piano-style cohorts without ranking quality."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.perceptual import project_hash  # noqa: E402

STYLES = ("none", "ostinato", "obbligato", "mixed")
FILES = ("composition_plan.json", "program.json", "project.json", "receipt.json",
         "song_validity.json", "g1_features.json", "reference.wav", "evaluation_reference.mid",
         "evaluation_reference_midi.json")


def _load(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"JSON object required: {path}")
    return result


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        part = data[offset]
        offset += 1
        value = (value << 7) | (part & 127)
        if part < 128:
            return value, offset


def midi_track_notes(path: Path, track_name: str) -> tuple[int, set[int]]:
    """Count Note On messages and programs in one SMF1 named track."""
    payload = path.read_bytes()
    if payload[:4] != b"MThd" or int.from_bytes(payload[8:10], "big") != 1:
        raise ValueError(f"not a format-1 MIDI file: {path}")
    position = 14
    for _ in range(int.from_bytes(payload[10:12], "big")):
        if payload[position:position + 4] != b"MTrk":
            raise ValueError(f"missing MIDI track header: {path}")
        length = int.from_bytes(payload[position + 4:position + 8], "big")
        track = payload[position + 8:position + 8 + length]
        position += 8 + length
        index, name, notes, programs = 0, None, 0, set()
        while index < len(track):
            _, index = _vlq(track, index)
            status = track[index]
            index += 1
            if status == 0xFF:
                kind = track[index]
                index += 1
                size, index = _vlq(track, index)
                if kind == 3:
                    name = track[index:index + size].decode("ascii")
                index += size
            elif status in (0xF0, 0xF7):
                size, index = _vlq(track, index)
                index += size
            elif status & 0xF0 in (0xC0, 0xD0):
                if status & 0xF0 == 0xC0:
                    programs.add(track[index])
                index += 1
            else:
                if status & 0xF0 == 0x90 and track[index + 1] > 0:
                    notes += 1
                index += 2
        if name == track_name:
            return notes, programs
    raise ValueError(f"MIDI track {track_name} not found: {path}")


def evaluate(root: Path, seed_count: int = 8) -> dict:
    rows: list[dict] = []
    missing: list[dict] = []
    for seed in range(seed_count):
        paired: dict[str, dict] = {}
        for style in STYLES:
            directory = root / style / f"seed-{seed:04d}"
            absent = [name for name in FILES if not (directory / name).is_file()]
            if absent:
                missing.append({"seed": seed, "style": style, "files": absent})
                continue
            receipt = _load(directory / "receipt.json")
            plan = _load(directory / "composition_plan.json")
            program = _load(directory / "program.json")
            project = _load(directory / "project.json")
            g1 = _load(directory / "g1_features.json")
            validity = _load(directory / "song_validity.json")
            midi_manifest = _load(directory / "evaluation_reference_midi.json")
            if receipt["seed"] != seed or receipt.get("piano_style", "none") != style:
                raise ValueError(f"style or seed mismatch: {directory}")
            if (receipt["plan_hash"] != plan["plan_hash"]
                    or receipt["program_hash"] != program_hash(program)
                    or receipt["project_hash"] != project_hash(project)
                    or receipt["g1_feature_report_hash"] != g1["report_hash"]
                    or receipt["song_validity_hash"] != validity["assessment_hash"]
                    or receipt["midi_hash"] != midi_manifest["midi_hash"]
                    or receipt["midi_manifest_hash"] != midi_manifest["manifest_hash"]
                    or receipt["archive_eligible"] != validity["archive_eligible"]
                    or receipt["wav_hash"] != _digest(directory / "reference.wav")
                    or receipt["midi_hash"] != _digest(directory / "evaluation_reference.mid")):
                raise ValueError(f"artifact binding mismatch: {directory}")
            piano_notes = sum(event["kind"] == "note" and event["track_id"] == "trk_piano"
                              for event in project["events"])
            if style == "none":
                if piano_notes or any(track["id"] == "trk_piano" for track in project["tracks"]):
                    raise ValueError(f"unexpected piano: {directory}")
            else:
                midi_notes, programs = midi_track_notes(directory / "evaluation_reference.mid", "trk_piano")
                if piano_notes < 1 or midi_notes != piano_notes or programs != {0}:
                    raise ValueError(f"piano MIDI/Project mismatch: {directory}")
            with wave.open(str(directory / "reference.wav"), "rb") as audio:
                duration_ms = round(1000 * audio.getnframes() / audio.getframerate())
            paired[style] = {
                "seed": seed, "style": style, "plan_hash": plan["plan_hash"],
                "structural_seed": receipt["structural_seed"],
                "structural_rejection_ordinal": receipt["structural_rejection_ordinal"],
                "archive_eligible_g0": validity["archive_eligible"],
                "failure_codes_g0": validity["failure_codes"],
                "piano_note_count": piano_notes, "total_event_count": len(project["events"]),
                "section_count": len(project["form"]), "duration_ms": duration_ms,
                "g1_metrics_q": g1["metrics_q"], "wav_hash": receipt["wav_hash"],
                "midi_hash": receipt["midi_hash"],
            }
        if "none" in paired:
            baseline = paired["none"]
            for style, row in paired.items():
                if (row["plan_hash"] != baseline["plan_hash"]
                        or row["structural_seed"] != baseline["structural_seed"]
                        or row["structural_rejection_ordinal"] != baseline["structural_rejection_ordinal"]):
                    raise ValueError(f"unpaired generated input for seed {seed}: {style}")
                row["g1_delta_vs_none_q"] = {
                    key: value - baseline["g1_metrics_q"][key]
                    for key, value in row["g1_metrics_q"].items()
                }
        rows.extend(paired.values())
    summary = {}
    for style in STYLES:
        group = [row for row in rows if row["style"] == style]
        summary[style] = {
            "completed": len(group),
            "g0_eligible": sum(row["archive_eligible_g0"] for row in group),
            "piano_notes": sum(row["piano_note_count"] for row in group),
            "mean_g1_metrics_q": {
                key: round(mean(row["g1_metrics_q"][key] for row in group))
                for key in group[0]["g1_metrics_q"]
            } if group else {},
            "mean_g1_delta_vs_none_q": {
                key: round(mean(row["g1_delta_vs_none_q"][key] for row in group
                                if "g1_delta_vs_none_q" in row))
                for key in group[0]["g1_metrics_q"]
            } if group and all("g1_delta_vs_none_q" in row for row in group) else {},
        }
    report = {
        "schema": "cps.piano-style-comparison-report", "schema_version": "1.0.0",
        "non_authoritative": True, "seed_count": seed_count,
        "complete": not missing, "missing": missing,
        "rows": rows, "summary": summary,
    }
    report["report_hash"] = "sha256:" + hashlib.sha256(
        b"cps.piano-style-comparison-report/v1\0" + canonical_bytes(report)
    ).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 1000:
        parser.error("--seeds must be 1..1000")
    report = evaluate(args.root, args.seeds)
    (args.root / "piano_style_comparison_report.json").write_bytes(canonical_bytes(report))
    lines = ["# Piano style comparison (G0/G1 diagnostics)", "",
             f"Completed: {len(report['rows'])}/{args.seeds * len(STYLES)}; "
             f"missing: {len(report['missing'])}. G1 is uncalibrated and non-authoritative.", "",
             "| Style | Completed | G0 eligible | Piano notes |",
             "|---|---:|---:|---:|"]
    for style, item in report["summary"].items():
        lines.append(f"| {style} | {item['completed']} | {item['g0_eligible']} | {item['piano_notes']} |")
    failures = [row for row in report["rows"] if not row["archive_eligible_g0"]]
    if failures:
        lines.extend(("", "G0 failures (generation succeeded, archive gate did not pass):", "",
                      "| Seed | Style | Failure codes |", "|---:|---|---|"))
        for row in failures:
            lines.append(f"| {row['seed']} | {row['style']} | "
                         f"{', '.join(row['failure_codes_g0'])} |")
    lines.extend(("", "Piano note-on counts by seed:", "",
                  "| Seed | " + " | ".join(STYLES) + " |",
                  "|---:|" + "---:|" * len(STYLES)))
    for seed in range(args.seeds):
        counts = {row["style"]: row["piano_note_count"] for row in report["rows"]
                  if row["seed"] == seed}
        lines.append(f"| {seed} | " + " | ".join(str(counts.get(style, "—"))
                                                  for style in STYLES) + " |")
    lines.extend(("", "G1 mean differences (basis points) from the paired `none` seed; "
                  "not a quality ranking:", "",
                  "| Metric | " + " | ".join(STYLES[1:]) + " |",
                  "|---|" + "---:|" * 3))
    keys = report["summary"]["none"]["mean_g1_metrics_q"]
    for key in keys:
        values = [report["summary"][style]["mean_g1_delta_vs_none_q"].get(key)
                  for style in STYLES[1:]]
        lines.append("| " + key + " | " + " | ".join(str(value) if value is not None else "—"
                                                   for value in values) + " |")
    (args.root / "piano_style_comparison_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"complete": report["complete"], "completed": len(report["rows"]),
                      "missing": len(report["missing"]), "report_hash": report["report_hash"]}))


if __name__ == "__main__":
    main()
