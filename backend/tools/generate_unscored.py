"""CLI for evaluation-free SongProgram compilation and WAV rendering."""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--program", type=Path)
    parser.add_argument("--compiler-identity", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--asset-directory", type=Path)
    parser.add_argument("--render-manifest", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    input_names = (
        "program",
        "compiler_identity",
        "catalog",
        "asset_directory",
        "render_manifest",
    )
    if arguments.demo:
        supplied = [name for name in input_names if getattr(arguments, name) is not None]
        if supplied:
            parser.error("--demo cannot be combined with explicit input paths")
        fixture_root = BACKEND / "songprogram_conformance/fixtures"
        arguments.program = fixture_root / "pack/minimal_direct_song_program.json"
        arguments.catalog = fixture_root / "render/catalog.json"
        arguments.asset_directory = fixture_root / "render/assets"
        arguments.render_manifest = fixture_root / "render/render_manifest.json"
    else:
        missing = [
            f"--{name.replace('_', '-')}"
            for name in input_names
            if getattr(arguments, name) is None
        ]
        if missing:
            parser.error("normal mode requires: " + ", ".join(missing))

    paths = {
        "--program": arguments.program,
        "--catalog": arguments.catalog,
        "--render-manifest": arguments.render_manifest,
    }
    if not arguments.demo:
        paths["--compiler-identity"] = arguments.compiler_identity
    for option, path in paths.items():
        if not path.is_file():
            parser.error(f"{option} does not exist or is not a file: {path}")
    if not arguments.asset_directory.is_dir():
        parser.error(
            f"--asset-directory does not exist or is not a directory: {arguments.asset_directory}"
        )

    try:
        program = _json(arguments.program)
        catalog_bytes = arguments.catalog.read_bytes()
        render_manifest = _json(arguments.render_manifest)
        if arguments.demo:
            catalog_digest = (
                "sha256:"
                + hashlib.sha256(b"cps.instrument-catalog/v1\0" + catalog_bytes).hexdigest()
            )
            program["tracks"][0]["instrument_id"] = "pitched_fixture_2_1"
            program["production"]["catalog_digest"] = catalog_digest
            identity = CompilerIdentity(
                build_id="unscored-demo/v1",
                resolver_build_id="fixture-resolver",
                resolver_profile_hash="sha256:" + "10" * 32,
                budget_profile_digest="sha256:" + "11" * 32,
                instrument_catalog_digest=catalog_digest,
            )
        else:
            identity = CompilerIdentity(**_json(arguments.compiler_identity))
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as error:
        parser.error(str(error))

    def resolve_asset(uri: str) -> bytes:
        digest = uri.rsplit("/", 1)[-1]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("invalid content-addressed asset URI")
        return (arguments.asset_directory / f"{digest}.wav").read_bytes()

    receipt = generate_unscored(
        program,
        seed=arguments.seed,
        compiler_identity=identity,
        catalog_bytes=catalog_bytes,
        resolve_asset=resolve_asset,
        render_manifest_digest=render_manifest["render_manifest_digest"],
        output_directory=arguments.output,
    )
    sys.stdout.buffer.write(canonical_lf(receipt))


if __name__ == "__main__":
    main()
