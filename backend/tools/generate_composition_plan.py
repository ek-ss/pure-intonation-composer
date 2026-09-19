"""Generate a canonical ordered-form CompositionPlan from profile 2.0."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_generation import (  # noqa: E402
    CompositionGenerationError,
    generate_composition_plan,
)
from app.songprogram.search import canonical_bytes  # noqa: E402


def _profile(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("profile must be a JSON object")
    return value


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if not arguments.profile.is_file():
        parser.error(f"--profile does not exist or is not a file: {arguments.profile}")
    try:
        plan = generate_composition_plan(_profile(arguments.profile), arguments.seed)
    except (OSError, json.JSONDecodeError, ValueError, CompositionGenerationError) as error:
        parser.error(str(error))
    payload = canonical_bytes(plan) + b"\n"
    if arguments.output is None:
        sys.stdout.buffer.write(payload)
    else:
        _atomic_write(arguments.output, payload)


if __name__ == "__main__":
    main()
