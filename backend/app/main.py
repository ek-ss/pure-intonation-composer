from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.composition.harmony import generate_harmony
from app.generators.cps import generate_cps
from app.generators.euler_fokker import generate_euler_fokker
from app.generators.series import harmonic_series, subharmonic_series
from app.graphs.harmonic import build_johnson_graph, shortest_path, random_walk, weighted_walk
from app.models import (
    CPSRequest,
    EulerFokkerRequest,
    HarmonicGraphRequest,
    HarmonyRequest,
    RatioRequest,
    ScalaRequest,
    SeriesRequest,
)
from app.exporters.scala import scala_text
from app.tuning.analysis import cents, monzo
from app.tuning.ratios import parse_ratio, ratio_text

app = FastAPI(title="Pure Intonation Workbench API", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False, status_code=204)
def favicon() -> Response:
    return Response(status_code=204)


def pitch_payload(ratios: list[Fraction]) -> dict[str, object]:
    return {
        "count": len(ratios),
        "pitches": [
            {"ratio": ratio_text(ratio), "cents": round(cents(ratio), 5), "monzo": monzo(ratio)}
            for ratio in ratios
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/cps")
def cps(request: CPSRequest) -> dict[str, object]:
    try:
        return pitch_payload(generate_cps(request.factors, request.choose, request.kind, request.octave_reduce))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/euler-fokker")
def euler_fokker(request: EulerFokkerRequest) -> dict[str, object]:
    return pitch_payload(generate_euler_fokker(request.factors, request.octave_reduce))


@app.post("/api/harmonic-series")
def harmonic(request: SeriesRequest) -> dict[str, object]:
    return pitch_payload(harmonic_series(request.count, request.octave_reduce))


@app.post("/api/subharmonic-series")
def subharmonic(request: SeriesRequest) -> dict[str, object]:
    return pitch_payload(subharmonic_series(request.count, request.octave_reduce))


@app.post("/api/analyze-ratio")
def analyze_ratio(request: RatioRequest) -> dict[str, object]:
    try:
        ratio = parse_ratio(request.ratio)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail="ratio must be a positive fraction") from error
    return pitch_payload([ratio])["pitches"][0]


@app.post("/api/harmonic-graph")
def harmonic_graph(request: HarmonicGraphRequest) -> dict[str, object]:
    """Build a CPS Johnson graph and optionally traverse it with a fixed seed."""
    try:
        graph = build_johnson_graph(request.factors, request.choose)
        payload: dict[str, object] = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "nodes": [
                {"index": index, "factors": node.factors, "ratio": ratio_text(node.ratio)}
                for index, node in enumerate(graph.nodes)
            ],
            "edges": [{"source": left, "target": right} for left, right in graph.edges],
        }
        if request.operation == "shortest_path":
            if request.end is None:
                raise ValueError("end is required for shortest_path")
            payload["walk"] = shortest_path(graph, request.start, request.end)
        elif request.operation == "random_walk":
            payload["walk"] = random_walk(graph, request.start, request.steps, request.seed)
        elif request.operation == "weighted_walk":
            payload["walk"] = weighted_walk(graph, request.start, request.steps, request.seed, request.metric)
        return payload
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/harmony")
def compose_harmony(request: HarmonyRequest) -> dict[str, object]:
    """Compose a deterministic, connected CPS harmony progression."""
    try:
        graph = build_johnson_graph(request.factors, request.choose)
        progression = generate_harmony(
            graph,
            request.length,
            request.seed,
            request.start,
            request.metric,
        )
        return {
            "length": len(progression.nodes),
            "seed": request.seed,
            "metric": request.metric,
            "chords": [
                {
                    "node": index,
                    "factors": graph.nodes[index].factors,
                    "ratio": ratio_text(graph.nodes[index].ratio),
                    "transition_score": (
                        None if position == 0 else progression.transition_scores[position - 1]
                    ),
                }
                for position, index in enumerate(progression.nodes)
            ],
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/export/scala")
def export_scala(request: ScalaRequest) -> Response:
    try:
        ratios = [parse_ratio(value) for value in request.ratios]
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail="ratios must be positive fractions") from error
    return Response(scala_text(request.name, ratios), media_type="text/plain")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
