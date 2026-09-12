"""CLI for evaluation-free SongProgram compilation and WAV rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.compiler import CompilerIdentity  # noqa: E402
from app.songprogram.connected import canonical_lf  # noqa: E402
from app.songprogram.unscored_generation import generate_unscored  # noqa: E402


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--compiler-identity", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--asset-directory", type=Path, required=True)
    parser.add_argument("--render-manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    identity_payload = _json(arguments.compiler_identity)
    identity = CompilerIdentity(**identity_payload)
    render_manifest = _json(arguments.render_manifest)

    def resolve_asset(uri: str) -> bytes:
        digest = uri.rsplit("/", 1)[-1]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("invalid content-addressed asset URI")
        return (arguments.asset_directory / f"{digest}.wav").read_bytes()

    receipt = generate_unscored(
        _json(arguments.program),
        seed=arguments.seed,
        compiler_identity=identity,
        catalog_bytes=arguments.catalog.read_bytes(),
        resolve_asset=resolve_asset,
        render_manifest_digest=render_manifest["render_manifest_digest"],
        output_directory=arguments.output,
    )
    sys.stdout.buffer.write(canonical_lf(receipt))


if __name__ == "__main__":
    main()
