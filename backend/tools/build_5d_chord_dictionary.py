"""Build the sealed five-dimensional harmony dictionary files.

One sealed JSON file per equave (``2/1``, ``3/1``) is written to
``backend/harmony_dictionary_data/``.  Each file carries the schema version,
the equave, the axis order, the loop policy, the 12-EDO template version,
the stability profile (and its hash), the classification thresholds, the
dictionary policy caps, every axis's loop + 1D points, and every axis x
voice-count dictionary (exact ratios, vectors, approximation errors,
provenance).  The whole body is bound by a domain-separated SHA-256 seal.

Usage:
    python tools/build_5d_chord_dictionary.py            # build (write)
    python tools/build_5d_chord_dictionary.py --check    # verify byte parity

``--check`` is the read-only verifier: it rebuilds every file in memory and
requires exact byte parity with what is on disk (and a valid seal).  The
build is deterministic, so parity holds if and only if the sealed files were
produced by the same code and version.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from fractions import Fraction
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.harmony_dictionary.authority import (  # noqa: E402
    AXES_BY_EQUAVE,
    DECIMAL_PRECISION,
    LOOP_LIMIT,
    LOOP_TOLERANCE_DC,
    OCTAVE,
    TRITAVE,
    axis_payload,
)
from app.harmony_dictionary.dictionary import (  # noqa: E402
    DICT_VERSION,
    DEFAULT_POLICY,
    build_axis_dictionary,
)
from app.harmony_dictionary.stability import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_THRESHOLDS,
)
from app.harmony_dictionary.storage import (  # noqa: E402
    SCHEMA_VERSION,
    StorageError,
    canonical_bytes,
    read_sealed,
    seal,
    write_sealed,
)
from app.harmony_dictionary.templates import TEMPLATES_VERSION  # noqa: E402

DATA_DIR = BACKEND / "harmony_dictionary_data"

EQUAVES: tuple[tuple[str, Fraction], ...] = (("2/1", OCTAVE), ("3/1", TRITAVE))
VOICE_COUNTS: tuple[int, ...] = (3, 4)


def _stability_profile_hash(profile: dict[str, object]) -> str:
    domain = "harmony-dictionary/stability-profile"
    digest = hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_bytes(profile)).hexdigest()
    return "sha256:" + digest


def _file_name(equave_text: str) -> str:
    return f"harmony_dictionary_{equave_text.replace('/', '-')}.json"


def build_equave_file(equave_text: str, equave: Fraction) -> dict[str, object]:
    """Assemble the complete (unsealed) payload for one equave."""
    axes = AXES_BY_EQUAVE[equave_text]
    axes_detail: dict[str, object] = {}
    dictionaries: dict[str, object] = {}
    for generator in axes:
        axes_detail[str(generator)] = axis_payload(equave, generator)
        for voice_count in VOICE_COUNTS:
            dictionaries[f"{generator}/{voice_count}"] = build_axis_dictionary(
                equave, generator, voice_count
            )
    profile = DEFAULT_PROFILE.as_dict()
    return {
        "schema_version": SCHEMA_VERSION,
        "equave": equave_text,
        "axes": list(axes),
        "loop_policy": {
            "limit": LOOP_LIMIT,
            "tolerance_dc": int(LOOP_TOLERANCE_DC),
            "decimal_precision": DECIMAL_PRECISION,
        },
        "templates_version": TEMPLATES_VERSION,
        "dictionary_version": DICT_VERSION,
        "stability_profile": profile,
        "stability_profile_hash": _stability_profile_hash(profile),
        "thresholds": DEFAULT_THRESHOLDS.as_dict(),
        "policy": DEFAULT_POLICY.as_dict(),
        "axes_detail": axes_detail,
        "dictionaries": dictionaries,
    }


def build_all() -> dict[str, Path]:
    """Build every equave file and write it atomically.  Returns path per equave."""
    written: dict[str, Path] = {}
    for equave_text, equave in EQUAVES:
        started = time.time()
        payload = build_equave_file(equave_text, equave)
        sealed = seal(payload, f"harmony-dictionary/{equave_text}")
        path = DATA_DIR / _file_name(equave_text)
        write_sealed(path, sealed)
        variants = sum(int(dictionary.get("variant_count", 0)) for dictionary in payload["dictionaries"].values())  # type: ignore[union-attr]
        failures = {
            code: sum(int(dictionary.get("failures", {}).get(code, 0)) for dictionary in payload["dictionaries"].values())  # type: ignore[union-attr]
            for code in ("NOT_ENOUGH_AXIS_POINTS", "LOOP_NOT_FOUND_WITHIN_LIMIT")
        }
        print(
            f"{equave_text}: wrote {path} "
            f"({len(payload['dictionaries'])} dictionaries, {variants} variants, "
            f"failures={failures}) in {time.time() - started:.1f}s"
        )
        written[equave_text] = path
    return written


def check_all() -> int:
    """Read-only verifier: seal + canonical form + byte parity on rebuild."""
    failures = 0
    for equave_text, equave in EQUAVES:
        path = DATA_DIR / _file_name(equave_text)
        try:
            on_disk = read_sealed(path, f"harmony-dictionary/{equave_text}")
        except StorageError as error:
            print(f"{equave_text}: FAIL {error.code} ({path})")
            failures += 1
            continue
        rebuilt = seal(build_equave_file(equave_text, equave), f"harmony-dictionary/{equave_text}")
        if canonical_bytes(rebuilt) == canonical_bytes(on_disk):
            print(f"{equave_text}: OK byte parity ({path})")
        else:
            print(f"{equave_text}: FAIL byte parity mismatch ({path})")
            failures += 1
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify byte parity instead of writing")
    parser.add_argument("--data-dir", type=Path, default=None, help="override the data directory")
    args = parser.parse_args()
    if args.data_dir is not None:
        global DATA_DIR
        DATA_DIR = args.data_dir
    if args.check:
        return check_all()
    build_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
