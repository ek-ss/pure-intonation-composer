from __future__ import annotations

from fractions import Fraction

from app.tuning.ratios import parse_ratio

_SCALES: dict[str, list[Fraction]] = {}


def save_scale(name: str, ratios: list[str]) -> dict[str, object]:
    """Validate and store a named scale, replacing any existing entry."""
    if not 1 <= len(name) <= 80:
        raise ValueError("scale name must be between 1 and 80 characters")
    if not ratios:
        raise ValueError("scale must contain at least one ratio")
    parsed = [parse_ratio(value) for value in ratios]
    _SCALES[name] = parsed
    return {"name": name, "count": len(parsed), "ratios": parsed}


def list_scales() -> list[dict[str, object]]:
    """List stored scales in insertion order."""
    return [{"name": name, "count": len(ratios)} for name, ratios in _SCALES.items()]


def get_scale(name: str) -> dict[str, object] | None:
    """Return a stored scale entry, or None when the name is unknown."""
    ratios = _SCALES.get(name)
    if ratios is None:
        return None
    return {"name": name, "count": len(ratios), "ratios": ratios}


def delete_scale(name: str) -> bool:
    """Remove a stored scale, returning True when it existed."""
    return _SCALES.pop(name, None) is not None
