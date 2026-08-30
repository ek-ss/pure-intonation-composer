"""Reference implementation of CPS Canonical JSON v1.

This module deliberately imports no ``app`` production helpers.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


class CanonicalJsonError(ValueError):
    """Raised when a value is outside the canonical JSON subset."""


def _string(value: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalJsonError("strings and object keys must already be NFC")
    output = ['"']
    short = {8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}
    for char in value:
        codepoint = ord(char)
        if char == '"':
            output.append('\\"')
        elif char == "\\":
            output.append("\\\\")
        elif codepoint in short:
            output.append(short[codepoint])
        elif codepoint < 0x20:
            output.append(f"\\u{codepoint:04x}")
        elif 0xD800 <= codepoint <= 0xDFFF:
            raise CanonicalJsonError("unpaired UTF-16 surrogate is forbidden")
        else:
            output.append(char)
    output.append('"')
    return "".join(output)


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise CanonicalJsonError("floating-point values are forbidden")
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalJsonError("object keys must be strings")
        keys = sorted(value, key=lambda key: key.encode("utf-8"))
        return "{" + ",".join(f"{_string(key)}:{_encode(value[key])}" for key in keys) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    raise CanonicalJsonError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return CPS Canonical JSON v1 bytes with no trailing newline."""

    return _encode(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return a lowercase, prefix-free SHA-256 hex digest."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()
