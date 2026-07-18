from __future__ import annotations

import re
from fractions import Fraction

_EXPRESSION_PATTERN = re.compile(r"^[0-9+*/()^. ]+$")


def parse_ratio(value: str) -> Fraction:
    numerator, denominator = value.split("/", maxsplit=1)
    ratio = Fraction(int(numerator), int(denominator))
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    return ratio


def reduce_to_octave(ratio: Fraction) -> Fraction:
    """Move a positive ratio into the half-open interval [1, 2)."""
    while ratio >= 2:
        ratio /= 2
    while ratio < 1:
        ratio *= 2
    return ratio


def ratio_text(ratio: Fraction) -> str:
    return f"{ratio.numerator}/{ratio.denominator}"


def _approximate(value: float) -> Fraction:
    return Fraction(value).limit_denominator(1_000_000)


def parse_interval(text: str) -> Fraction:
    """Parse an interval expression into a positive ratio.

    Supported forms:
    - ratio ``n/m`` (e.g. ``3/2``)
    - cents as a dotted float ``748.2`` (values >= 10 convert via 2**(c/1200))
    - EDO degree ``n\\m`` (e.g. ``5\\12`` = 2**(5/12))
    - plain decimal ratio ``1.33`` (dotted values below 10)
    - math expression starting with ``=`` (e.g. ``=2**(6/12)``, ``^`` maps to ``**``)
    """
    value = text.strip()
    if not value:
        raise ValueError("interval expression must not be empty")
    if value.startswith("="):
        expression = value[1:].replace("^", "**")
        if not expression or not _EXPRESSION_PATTERN.match(expression):
            raise ValueError("expression may only contain digits and + * / ( ) ^ .")
        try:
            result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        except (ArithmeticError, SyntaxError, ValueError) as error:
            raise ValueError(f"invalid interval expression: {error}") from error
        if not isinstance(result, (int, float)) or result <= 0:
            raise ValueError("interval expression must evaluate to a positive number")
        return Fraction(result) if isinstance(result, int) else _approximate(result)
    if "\\" in value:
        degree, _, steps = value.partition("\\")
        try:
            ratio = _approximate(2 ** (int(degree) / int(steps)))
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError("EDO degree must be 'n\\m' with nonzero m") from error
        return ratio
    if "/" in value:
        try:
            return parse_ratio(value)
        except ZeroDivisionError as error:
            raise ValueError("ratio denominator must be nonzero") from error
    if "." in value:
        try:
            number = float(value)
        except ValueError as error:
            raise ValueError(f"invalid interval: {text}") from error
        if 0 < number < 10:
            return Fraction(value)
        return _approximate(2 ** (number / 1200))
    raise ValueError(f"unrecognized interval expression: {text}")
