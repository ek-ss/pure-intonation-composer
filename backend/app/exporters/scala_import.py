from __future__ import annotations

from fractions import Fraction


def parse_scala(content: str) -> list[Fraction]:
    """Parse Scala .scl text into a ratio list that always starts with 1/1.

    Lines starting with '!' are comments, the first remaining line is the
    description, the second is the note count, and each following line is an
    entry: a cents value (contains '.') or a ratio 'n/m'.
    """
    lines = [line.strip() for line in content.splitlines()]
    lines = [line for line in lines if line and not line.startswith("!")]
    if len(lines) < 2:
        raise ValueError("scala content must contain a description and a note count")
    try:
        count = int(lines[1])
    except ValueError as error:
        raise ValueError("scala note count must be an integer") from error
    if count < 0:
        raise ValueError("scala note count must be non-negative")
    entries: list[Fraction] = []
    for line in lines[2:]:
        token = line.split()[0]
        if "." in token:
            cents_value = float(token)
            ratio = Fraction(2 ** (cents_value / 1200)).limit_denominator(1_000_000)
        else:
            ratio = Fraction(token)
        if ratio <= 0:
            raise ValueError("scala entries must be positive")
        entries.append(ratio)
    return [Fraction(1)] + entries
