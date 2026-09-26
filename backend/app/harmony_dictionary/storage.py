"""Sealed JSON storage for the five-dimensional harmony dictionary.

Canonical bytes, domain-separated SHA-256, atomic writes, and fail-closed
verification on read.  A sealed file is a single JSON object whose ``hash``
field binds every other field; the file bytes must be exactly the canonical
serialization of the sealed object (byte parity on regeneration).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

# 1.1.0: sealed files now carry decicent fields (tolerance_dc / distance_dc /
# approximation_dc) and the folded interval vectors of dictionary 1.1.0.
# Files sealed under 1.0.0 must not be mixed with these.
SCHEMA_VERSION = "1.1.0"


class StorageError(ValueError):
    """A stable storage failure with a machine-readable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON bytes (sorted keys, two-space indent, trailing LF)."""
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def seal(payload: dict[str, Any], domain: str, *, hash_field: str = "hash") -> dict[str, Any]:
    """Return a copy of ``payload`` with its ``hash_field`` bound to the body."""
    body = {key: value for key, value in payload.items() if key != hash_field}
    digest = "sha256:" + hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_bytes(body)).hexdigest()
    sealed = dict(payload)
    sealed[hash_field] = digest
    return sealed


def write_sealed(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write the canonical bytes of ``payload``."""
    data = canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_sealed(path: Path, domain: str, *, hash_field: str = "hash") -> dict[str, Any]:
    """Read and verify a sealed file; fail closed on any mismatch."""
    if not path.exists():
        raise StorageError("DICTIONARY_MISSING", str(path))
    data = path.read_bytes()
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StorageError("DICTIONARY_CORRUPT", f"{path}: {error}") from error
    if not isinstance(payload, dict):
        raise StorageError("DICTIONARY_CORRUPT", f"{path}: top level must be an object")
    expected = payload.get(hash_field)
    body = {key: value for key, value in payload.items() if key != hash_field}
    digest = "sha256:" + hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_bytes(body)).hexdigest()
    if not isinstance(expected, str) or expected != digest:
        raise StorageError("DICTIONARY_HASH_MISMATCH", f"{path}: file {expected!r} != computed {digest}")
    if data != canonical_bytes(payload):
        raise StorageError("DICTIONARY_NOT_CANONICAL", str(path))
    return payload
