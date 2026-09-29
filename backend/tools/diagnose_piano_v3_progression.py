"""Diagnose where v3 cadence seeds fail progression resolution.

For each seed this runs the full v3 path and, on a ``PROGRESSION_NO_PATH``
failure, reports per-layer (per-bar) drop causes taken from the progression
resolver: polyphony, register (out of range), voice motion, crossing, and
no-match.  It measures *where* and *why* the path breaks without changing any
candidate selection, so it never alters a seed's outcome or hashes.

Example::

    python tools/diagnose_piano_v3_progression.py --equave 2/1 --seeds 0 1 2 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from tools.generate_piano_v3_cadence_trial import (  # noqa: E402
    TICKS_PER_BAR,
    V3TrialFailure,
    generate_one,
)


def _section_map(program: dict) -> list[tuple[str, int, int]]:
    """(section_id, start_bar, bars) for each section, in form order."""
    result: list[tuple[str, int, int]] = []
    cursor = 0
    for section in program.get("form", []):
        result.append((section["id"], cursor, section["bars"]))
        cursor += section["bars"]
    return result


def _locate(absolute_bar: int, sections: list[tuple[str, int, int]]) -> tuple[str | None, int]:
    for section_id, start_bar, bars in sections:
        if start_bar <= absolute_bar < start_bar + bars:
            return section_id, absolute_bar - start_bar
    return None, absolute_bar


def diagnose(equave: str, seed: int) -> dict:
    try:
        generate_one(equave, seed, skip_wav=True)
        return {"seed": seed, "equave": equave, "status": "success"}
    except V3TrialFailure as failure:
        diagnostics = failure.progression_diagnostics or {}
        program: dict = {}
        if "program.json" in failure.artifacts:
            program = json.loads(failure.artifacts["program.json"])
        sections = _section_map(program)
        layers = []
        for stat in diagnostics.get("layers", []):
            absolute_bar = stat["start_tick"] // TICKS_PER_BAR
            section_id, relative_bar = _locate(absolute_bar, sections)
            layers.append({
                "layer_index": stat["layer_index"],
                "section_id": section_id,
                "bar": relative_bar,
                "absolute_bar": absolute_bar,
                "total_candidates": stat["total_candidates"],
                "dropped": stat["dropped"],
                "reachable": stat["reachable"],
                "voices": stat.get("voices", []),
            })
        return {
            "seed": seed,
            "equave": equave,
            "status": "failed",
            "stage": failure.stage,
            "failure_code": failure.code,
            "broken_at_layer": diagnostics.get("broken_at_layer"),
            "layers": layers,
        }


def _summarize(result: dict) -> None:
    if result["status"] == "success":
        print(f"seed {result['seed']}: success")
        return
    broken = result["broken_at_layer"]
    print(
        f"seed {result['seed']}: FAILED at stage={result['stage']} "
        f"code={result['failure_code']} broken_at_layer={broken}"
    )
    for layer in result["layers"]:
        marker = " <-- broken" if layer["layer_index"] == broken else ""
        dropped = ", ".join(f"{k}={v}" for k, v in sorted(layer["dropped"].items())) or "-"
        print(
            f"  layer {layer['layer_index']:>2} bar {layer['bar']:>2}"
            f" ({layer['section_id']}): total={layer['total_candidates']}"
            f" reachable={layer['reachable']} dropped[{dropped}]{marker}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equave", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    results = [diagnose(args.equave, seed) for seed in args.seeds]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            _summarize(result)


if __name__ == "__main__":
    main()
