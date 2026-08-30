"""Regenerate the frozen 1,000-record NumericContract dataset."""

from __future__ import annotations

import hashlib
import json
import random
from fractions import Fraction
from pathlib import Path

from .reference import chord_complexity, edo_phase_mc, odd_limit, pair_rms_mc, ratio_mc, wrap_mc

SEED = 1_592_639_710
COUNT = 1_000
OUT = Path(__file__).with_name("goldens") / f"numeric_seed_{SEED}.jsonl"
SIDE = OUT.with_suffix(".sha256")


def _fraction(randomizer: random.Random, maximum: int = 127) -> Fraction:
    return Fraction(randomizer.randint(1, maximum), randomizer.randint(1, maximum))


def build_records() -> list[dict[str, object]]:
    randomizer = random.Random(SEED)
    records: list[dict[str, object]] = []
    for index in range(COUNT):
        kind = ("ratio", "edo", "wrap", "rms", "odd", "complexity")[index % 6]
        if kind == "ratio":
            value = _fraction(randomizer, 511)
            record = {"i": index, "kind": kind, "input": {"ratio": f"{value.numerator}/{value.denominator}"}, "expected": ratio_mc(value)}
        elif kind == "edo":
            equave = randomizer.choice((Fraction(2), Fraction(3), Fraction(5, 2)))
            divisions = randomizer.randint(5, 31)
            step = randomizer.randint(-2 * divisions, 3 * divisions)
            record = {"i": index, "kind": kind, "input": {"equave": f"{equave.numerator}/{equave.denominator}", "divisions": divisions, "step": step}, "expected": edo_phase_mc(equave, divisions, step)}
        elif kind == "wrap":
            equave = randomizer.choice((Fraction(2), Fraction(3), Fraction(5, 2)))
            period = ratio_mc(equave)
            wrapped_input = randomizer.randint(-3 * period, 3 * period)
            record = {"i": index, "kind": kind, "input": {"value": wrapped_input, "period": period}, "expected": wrap_mc(wrapped_input, period)}
        elif kind == "rms":
            errors = tuple(randomizer.randint(-50_000, 50_000) for _ in range(randomizer.randint(2, 6)))
            record = {"i": index, "kind": kind, "input": {"errors": list(errors)}, "expected": pair_rms_mc(errors)}
        elif kind == "odd":
            value = _fraction(randomizer)
            equave = randomizer.choice((Fraction(2), Fraction(3)))
            record = {"i": index, "kind": kind, "input": {"ratio": f"{value.numerator}/{value.denominator}", "equave": f"{equave.numerator}/{equave.denominator}"}, "expected": odd_limit(value, equave)}
        else:
            equave = randomizer.choice((Fraction(2), Fraction(3)))
            ratios = tuple(_fraction(randomizer, 31) for _ in range(randomizer.randint(2, 4)))
            record = {"i": index, "kind": kind, "input": {"ratios": [f"{v.numerator}/{v.denominator}" for v in ratios], "equave": f"{equave.numerator}/{equave.denominator}"}, "expected": chord_complexity(ratios, equave)}
        records.append(record)
    return records


def dataset_bytes() -> bytes:
    lines = [json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for record in build_records()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    payload = dataset_bytes()
    OUT.write_bytes(payload)
    SIDE.write_text(hashlib.sha256(payload).hexdigest() + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
