"""FastAPI router for the five-dimensional harmony dictionary workbench.

Five endpoints over the sealed per-equave dictionary files (read-only):

- ``GET  /api/harmony-dictionary/config``   supported equaves, axes, versions, caps
- ``POST /api/harmony-dictionary/axis``     equave/generator -> loop + 1D points
- ``POST /api/harmony-dictionary/chords``   equave/axis/voices/filter -> paged entries
- ``POST /api/harmony-dictionary/evaluate`` 5D vectors -> projection + exact re-evaluation
- ``POST /api/harmony-dictionary/cadences`` tonic/kind/seed -> progressions + report

The heavy builder never runs inside a request: the sealed files are read and
verified (fail-closed) on first use, then cached.  Input caps are enforced
with 422; a missing or corrupt dictionary file is a 503 with its storage code.
"""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.harmony_dictionary.authority import (
    AXES_BY_EQUAVE,
    DECIMAL_PRECISION,
    LOOP_LIMIT,
    LOOP_TOLERANCE_DC,
    AxisPoint,
    equave_ratio,
)
from app.harmony_dictionary.cadence import (
    CADENCE_TEMPLATES,
    build_classification_report,
    generate_cadence,
)
from app.harmony_dictionary.dictionary import DICT_VERSION, DEFAULT_POLICY
from app.harmony_dictionary.projection import evaluate_chord
from app.harmony_dictionary.stability import DEFAULT_THRESHOLDS, stability_q
from app.harmony_dictionary.storage import StorageError, read_sealed
from app.harmony_dictionary.templates import TEMPLATES, TEMPLATES_VERSION
from app.tuning.ratios import parse_ratio

router = APIRouter(prefix="/api/harmony-dictionary", tags=["harmony-dictionary"])

BACKEND = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("HARMONY_DICTIONARY_DIR", str(BACKEND / "harmony_dictionary_data")))

# Bounded input caps (versioned with the API, not with the dictionary).
MAX_VECTOR_COORDINATE = 64
MAX_CADENCES = 8
MAX_PAGE_SIZE = 100

_cache: dict[str, dict[str, object]] = {}


def _file_name(equave_text: str) -> str:
    return f"harmony_dictionary_{equave_text.replace('/', '-')}.json"


def _load(equave_text: str) -> dict[str, object]:
    """Load (and verify) one sealed equave file; fail closed on any problem."""
    if equave_text not in AXES_BY_EQUAVE:
        raise HTTPException(status_code=422, detail=f"unknown equave {equave_text!r}; supported: {sorted(AXES_BY_EQUAVE)}")
    if equave_text in _cache:
        return _cache[equave_text]
    path = DATA_DIR / _file_name(equave_text)
    try:
        payload = read_sealed(path, f"harmony-dictionary/{equave_text}")
    except StorageError as error:
        raise HTTPException(status_code=503, detail=f"{error.code}: {error}") from error
    axes: dict[int, list[AxisPoint]] = {}
    for generator in AXES_BY_EQUAVE[equave_text]:
        detail = payload["axes_detail"][str(generator)]  # type: ignore[index]
        axes[generator] = [
            AxisPoint(
                n=int(point["n"]),
                original_ratio=Fraction(str(point["original_ratio"])),
                reduced_ratio=Fraction(str(point["reduced_ratio"])),
                equave_exponent=int(point["equave_exponent"]),
                absolute_cents=float(point["absolute_cents"]),
                nearest_12edo_semitone=int(point["nearest_12edo_semitone"]),
                signed_12edo_error_cents=float(point["signed_12edo_error_cents"]),
                reduced_cents=float(point["reduced_cents"]),
            )
            for point in detail["points"]  # type: ignore[union-attr]
        ]
    dictionaries = {
        (int(key.split("/")[0]), int(key.split("/")[1])): value
        for key, value in payload["dictionaries"].items()  # type: ignore[union-attr]
    }
    entry = {"payload": payload, "axes": axes, "dictionaries": dictionaries}
    _cache[equave_text] = entry
    return entry


def _check_vectors(vectors: list[list[int]]) -> None:
    if not 3 <= len(vectors) <= 4:
        raise HTTPException(status_code=422, detail=f"a chord has 3 or 4 tones, got {len(vectors)}")
    for vector in vectors:
        if len(vector) != 5:
            raise HTTPException(status_code=422, detail=f"every tone vector needs five coordinates, got {len(vector)}")
        if any(abs(coordinate) > MAX_VECTOR_COORDINATE for coordinate in vector):
            raise HTTPException(
                status_code=422,
                detail=f"vector coordinates are bounded to [-{MAX_VECTOR_COORDINATE}, {MAX_VECTOR_COORDINATE}]",
            )


class AxisRequest(BaseModel):
    equave: str = Field(min_length=3, max_length=16)
    generator: int = Field(ge=2, le=10_000)
    limit: int | None = Field(default=None, ge=1, le=LOOP_LIMIT)


class ChordsRequest(BaseModel):
    equave: str = Field(min_length=3, max_length=16)
    generator: int = Field(ge=2, le=10_000)
    voice_count: Literal[3, 4]
    template: str | None = Field(default=None, max_length=64)
    key: str | None = Field(default=None, max_length=32)
    tonic: str = Field(default="1/1", min_length=1, max_length=32)
    page: int = Field(default=0, ge=0, le=10_000)
    page_size: int = Field(default=24, ge=1, le=MAX_PAGE_SIZE)


class EvaluateRequest(BaseModel):
    equave: str = Field(min_length=3, max_length=16)
    tonic: str | None = Field(default=None, min_length=1, max_length=32)
    vectors: list[list[int]] = Field(min_length=3, max_length=4)
    registers: list[int] | None = Field(default=None, min_length=3, max_length=4)
    root_vector: list[int] | None = Field(default=None)


class CadencesRequest(BaseModel):
    equave: str = Field(min_length=3, max_length=16)
    tonic: str = Field(default="1/1", min_length=1, max_length=32)
    kind: Literal["authentic", "predominant_chain", "open", "lattice"] = "authentic"
    seed: int = Field(default=0, ge=0, le=2**31)
    count: int = Field(default=1, ge=1, le=MAX_CADENCES)
    max_chords: int = Field(default=4, ge=2, le=4)
    beats: list[int] | None = Field(default=None, min_length=1, max_length=64)


@router.get("/config")
def config() -> dict[str, object]:
    files: dict[str, object] = {}
    for equave_text in sorted(AXES_BY_EQUAVE):
        path = DATA_DIR / _file_name(equave_text)
        try:
            payload = read_sealed(path, f"harmony-dictionary/{equave_text}")
        except StorageError as error:
            files[equave_text] = {"available": False, "code": error.code}
            continue
        dictionaries = payload["dictionaries"]  # type: ignore[index]
        files[equave_text] = {
            "available": True,
            "hash": payload["hash"],
            "stability_profile_hash": payload.get("stability_profile_hash"),
            "dictionary_count": len(dictionaries),
            "variant_total": sum(int(dictionary.get("variant_count", 0)) for dictionary in dictionaries.values()),
        }
    return {
        "equaves": sorted(AXES_BY_EQUAVE),
        "axes": {text: list(axes) for text, axes in AXES_BY_EQUAVE.items()},
        "loop_policy": {
            "limit": LOOP_LIMIT,
            "tolerance_dc": int(LOOP_TOLERANCE_DC),
            "decimal_precision": DECIMAL_PRECISION,
        },
        "templates_version": TEMPLATES_VERSION,
        "templates": sorted(TEMPLATES),
        "dictionary_version": DICT_VERSION,
        "thresholds": DEFAULT_THRESHOLDS.as_dict(),
        "policy": DEFAULT_POLICY.as_dict(),
        "files": files,
    }


@router.post("/axis")
def axis(request: AxisRequest) -> dict[str, object]:
    entry = _load(request.equave)
    payload = entry["payload"]
    if request.generator not in AXES_BY_EQUAVE[request.equave]:
        raise HTTPException(
            status_code=422,
            detail=f"generator {request.generator} is not an axis of {request.equave}; axes: {AXES_BY_EQUAVE[request.equave]}",
        )
    detail = payload["axes_detail"][str(request.generator)]  # type: ignore[index]
    points = list(detail["points"])  # type: ignore[assignment,union-attr]
    if request.limit is not None:
        points = points[: request.limit]
    return {
        "equave": request.equave,
        "generator": request.generator,
        "loop": detail["loop"],  # type: ignore[index]
        "negative_direction": detail["negative_direction"],  # type: ignore[index]
        "point_count": len(points),
        "points": points,
    }


@router.post("/chords")
def chords(request: ChordsRequest) -> dict[str, object]:
    entry = _load(request.equave)
    payload = entry["payload"]
    if request.generator not in AXES_BY_EQUAVE[request.equave]:
        raise HTTPException(status_code=422, detail=f"generator {request.generator} is not an axis of {request.equave}")
    dictionary = entry["dictionaries"].get((request.generator, request.voice_count))  # type: ignore[index]
    if dictionary is None:
        raise HTTPException(status_code=422, detail=f"no dictionary for {request.equave} generator {request.generator} with {request.voice_count} voices")
    if int(dictionary.get("variant_count", 0)) == 0:
        raise HTTPException(status_code=422, detail=f"empty dictionary for {request.equave} generator {request.generator} with {request.voice_count} voices")
    try:
        tonic = parse_ratio(request.tonic)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"invalid tonic {request.tonic!r}: {error}") from error
    equave = equave_ratio(request.equave)

    entries = [item for item in dictionary["entries"]]  # type: ignore[index]
    if request.template is not None:
        entries = [item for item in entries if any(variant["template"] == request.template for variant in item["variants"])]  # type: ignore[union-attr]
    if request.key is not None:
        entries = [item for item in entries if item["key"] == request.key]  # type: ignore[index]
    total = len(entries)
    window = entries[request.page * request.page_size : (request.page + 1) * request.page_size]
    paged = []
    for item in window:
        variants = []
        for variant in item["variants"]:  # type: ignore[union-attr]
            ratios = [Fraction(text) for text in variant["ratios"]]  # type: ignore[union-attr]
            enriched = dict(variant)
            enriched["stability_q"] = stability_q(Fraction(1), ratios, tonic, equave=equave)
            variants.append(enriched)
        paged.append({"key": item["key"], "variants": variants})  # type: ignore[index]
    return {
        "equave": request.equave,
        "generator": request.generator,
        "voice_count": request.voice_count,
        "dictionary_version": dictionary.get("version"),
        "stability_profile_hash": payload.get("stability_profile_hash"),
        "thresholds": payload.get("thresholds"),
        "tonic": request.tonic,
        "total": total,
        "page": request.page,
        "page_size": request.page_size,
        "entries": paged,
    }


@router.post("/evaluate")
def evaluate(request: EvaluateRequest) -> dict[str, object]:
    entry = _load(request.equave)
    _check_vectors(request.vectors)
    if request.registers is not None and len(request.registers) != len(request.vectors):
        raise HTTPException(status_code=422, detail="registers must have one entry per tone")
    if request.registers is not None and any(abs(register) > MAX_VECTOR_COORDINATE for register in request.registers):
        raise HTTPException(status_code=422, detail=f"registers are bounded to [-{MAX_VECTOR_COORDINATE}, {MAX_VECTOR_COORDINATE}]")
    if request.root_vector is not None:
        if len(request.root_vector) != 5:
            raise HTTPException(status_code=422, detail=f"root_vector needs five coordinates, got {len(request.root_vector)}")
        if any(abs(coordinate) > MAX_VECTOR_COORDINATE for coordinate in request.root_vector):
            raise HTTPException(status_code=422, detail=f"root_vector coordinates are bounded to [-{MAX_VECTOR_COORDINATE}, {MAX_VECTOR_COORDINATE}]")
    tonic = None
    if request.tonic is not None:
        try:
            tonic = parse_ratio(request.tonic)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"invalid tonic {request.tonic!r}: {error}") from error
    try:
        equave = equave_ratio(request.equave)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result = evaluate_chord(
        request.vectors,
        equave=equave,
        root_vector=request.root_vector,
        registers=request.registers,
        axes=entry["axes"],  # type: ignore[arg-type]
        dictionaries=entry["dictionaries"],  # type: ignore[arg-type]
        tonic=tonic,
    )
    return result


@router.post("/cadences")
def cadences(request: CadencesRequest) -> dict[str, object]:
    entry = _load(request.equave)
    payload = entry["payload"]
    try:
        tonic = parse_ratio(request.tonic)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"invalid tonic {request.tonic!r}: {error}") from error
    try:
        equave = equave_ratio(request.equave)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if request.kind not in CADENCE_TEMPLATES:
        raise HTTPException(status_code=422, detail=f"unknown cadence kind {request.kind!r}")
    generated = []
    for offset in range(request.count):
        generated.append(
            generate_cadence(
                tonic,
                equave=equave,
                kind=request.kind,
                dictionaries=entry["dictionaries"],  # type: ignore[arg-type]
                seed=request.seed + offset,
                max_chords=request.max_chords,
                beats=request.beats,
            )
        )
    return {
        "equave": request.equave,
        "tonic": request.tonic,
        "kind": request.kind,
        "seed": request.seed,
        "stability_profile_hash": payload.get("stability_profile_hash"),
        "thresholds": payload.get("thresholds"),
        "cadences": generated,
        "report": build_classification_report(generated),
    }
