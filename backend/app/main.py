from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.audio.render import Envelope, NoteEvent, render_wav
from app.composition.harmony import generate_harmony
from app.composition.bass import generate_bass
from app.composition.melody import generate_melody
from app.composition.voice_leading import voice_lead
from app.generators.cps import generate_cps
from app.generators.euler_fokker import generate_euler_fokker
from app.generators.series import harmonic_series, subharmonic_series
from app.graphs.harmonic import build_johnson_graph, shortest_path, random_walk, weighted_walk
from app.graphs.layout import reference_layered_grid_layout
from app.jobs import RenderJobs
from app.models import (
    CPSRequest,
    BassRequest,
    EulerFokkerRequest,
    HarmonicGraphRequest,
    HarmonyRequest,
    HumanizeRequest,
    IntervalRequest,
    JsonExportRequest,
    MidiRequest,
    RatioRequest,
    ScalaRequest,
    SeriesRequest,
    SnapRequest,
    VoiceLeadingRequest,
    MelodyRequest,
    EuclideanRhythmRequest,
    PhaseShiftRequest,
    RhythmStateGraphRequest,
    RenderRequest,
    RhythmMidiRequest,
    ScaleSaveRequest,
    ScalaImportRequest,
)
from app.exporters.midi import MidiDrumHit, MidiNote, drum_midi_bytes, microtonal_midi_bytes, midi_bytes
from app.rhythm.engine import euclidean_rhythm, humanize, phase_shift, state_transition_graph
from app.exporters.scala import scala_text
from app.exporters.scala_import import parse_scala
from app.scales import delete_scale, get_scale, list_scales, save_scale
from app.tuning.analysis import cents, monzo
from app.tuning.ratios import parse_interval, parse_ratio, ratio_text, reduce_to_octave
from app.tuning.snap import snap_ratio

app = FastAPI(title="Pure Intonation Workbench API", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
render_jobs = RenderJobs()
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


def render_request(request: RenderRequest) -> bytes:
    return render_wav(
        [NoteEvent(parse_ratio(event.ratio), event.start_seconds, event.duration_seconds, event.velocity) for event in request.events],
        request.base_frequency,
        request.waveform,
        Envelope(request.attack_seconds, request.decay_seconds, request.sustain_level, request.release_seconds),
        request.sample_rate,
        request.delay_seconds,
        request.reverb_amount,
    )


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
    return {"ratio": ratio_text(ratio), "cents": round(cents(ratio), 5), "monzo": monzo(ratio)}


@app.post("/api/analyze-interval")
def analyze_interval(request: IntervalRequest) -> dict[str, object]:
    """Analyze an interval expression (ratio, cents, EDO degree, decimal, or '=expr')."""
    try:
        ratio = parse_interval(request.value)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"ratio": ratio_text(ratio), "cents": round(cents(ratio), 5), "monzo": monzo(ratio)}


@app.post("/api/tuning/snap")
def tuning_snap(request: SnapRequest) -> dict[str, object]:
    """Snap ratios to the nearest EDO step or prime-limit rational."""
    try:
        pitches = [
            {
                "original": ratio_text(ratio),
                "ratio": ratio_text(snapped := snap_ratio(ratio, request.mode, request.value)),
                "cents": round(cents(snapped), 5),
            }
            for ratio in (parse_ratio(value) for value in request.ratios)
        ]
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"pitches": pitches}


@app.post("/api/harmonic-graph")
def harmonic_graph(request: HarmonicGraphRequest) -> dict[str, object]:
    """Build a CPS Johnson graph and optionally traverse it with a fixed seed."""
    try:
        graph = build_johnson_graph(request.factors, request.choose)
        payload: dict[str, object] = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "nodes": [
                {"index": index, "factors": node.factors, "ratio": ratio_text(node.ratio), "sub_ratio": ratio_text(reduce_to_octave(2 / node.ratio))}
                for index, node in enumerate(graph.nodes)
            ],
            "edges": [{"source": left, "target": right} for left, right in graph.edges],
        }
        if request.layout == "reference_layered_grid":
            layout = reference_layered_grid_layout(graph, request.reference or 0, sort_mode=request.sort_mode)
            payload["layout"] = {
                "kind": "reference_layered_grid",
                "reference": layout.reference,
                "sort_mode": layout.sort_mode,
                "positions": [{"x": x, "y": y} for x, y in layout.positions],
                "shared_counts": list(layout.shared_counts),
                "distances": list(layout.distances),
                "layers": [{"shared": shared, "distance": max(layout.distances) - shared, "nodes": list(members)} for shared, members in layout.layers],
                "edge_directions": list(layout.edge_directions),
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


@app.post("/api/compose/voice-leading")
def compose_voice_leading(request: VoiceLeadingRequest) -> dict[str, object]:
    """Optimize a chord sequence for compact, non-crossing voice movement."""
    try:
        chords = [[parse_ratio(value) for value in chord] for chord in request.chords]
        progression = voice_lead(
            chords,
            request.max_leap_cents,
            request.register_low_cents,
            request.register_high_cents,
        )
        return {
            "voice_count": len(progression.chords[0]),
            "chords": [
                [
                    {
                        "ratio": ratio_text(ratio),
                        "cents": round(cents(ratio), 5),
                        "leap_cents": round(leap, 5),
                    }
                    for ratio, leap in zip(chord, chord_leaps)
                ]
                for chord, chord_leaps in zip(progression.chords, progression.leap_cents)
            ],
        }
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/bass")
def compose_bass(request: BassRequest) -> dict[str, object]:
    """Generate a continuous bass line using roots, fifths, and mirrored ratios."""
    try:
        bass = generate_bass(
            [[parse_ratio(value) for value in chord] for chord in request.chords],
            request.strategy,
            request.max_leap_cents,
            request.register_low_cents,
            request.register_high_cents,
        )
        return {
            "notes": [
                {
                    "ratio": ratio_text(note),
                    "cents": round(cents(note), 5),
                    "leap_cents": round(leap, 5),
                    "strategy": strategy,
                }
                for note, leap, strategy in zip(bass.notes, bass.leap_cents, bass.strategies)
            ]
        }
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/melody")
def compose_melody(request: MelodyRequest) -> dict[str, object]:
    """Generate independent, repeatable melodic voices from rational chord tones."""
    try:
        melody = generate_melody(
            [[parse_ratio(value) for value in chord] for chord in request.chords],
            request.voice_count,
            request.seed,
            request.contour,
            request.max_leap_cents,
            request.register_low_cents,
            request.register_high_cents,
            request.phrase_memory,
        )
        return {
            "seed": request.seed,
            "voices": [
                [
                    {"ratio": ratio_text(note), "cents": round(cents(note), 5)}
                    for note in voice
                ]
                for voice in melody.voices
            ],
        }
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/euclidean")
def rhythm_euclidean(request: EuclideanRhythmRequest) -> dict[str, object]:
    """Generate an evenly distributed Euclidean rhythm."""
    try:
        pattern = euclidean_rhythm(request.steps, request.pulses, request.rotation)
        return {"pattern": pattern, "steps": request.steps, "pulses": sum(pattern)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/state-graph")
def rhythm_state_graph(request: RhythmStateGraphRequest) -> dict[str, object]:
    """Return the binary rhythm state graph with Hamming-distance-one edges."""
    try:
        return state_transition_graph(request.steps)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/phase-shift")
def rhythm_phase_shift(request: PhaseShiftRequest) -> dict[str, object]:
    """Synchronize independently cycling rhythmic layers on one timeline."""
    try:
        return {"patterns": phase_shift(request.patterns, request.length, request.phases)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/humanize")
def rhythm_humanize(request: HumanizeRequest) -> dict[str, object]:
    """Apply seed-reproducible timing and velocity variation to a rhythm."""
    try:
        hits = humanize(
            request.pattern,
            request.seed,
            request.timing_amount_ms,
            request.velocity_amount,
            request.base_velocity,
        )
        return {"seed": request.seed, "hits": [hit.__dict__ for hit in hits]}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/render/wav")
def render_audio(request: RenderRequest) -> Response:
    """Offline-render rational notes to a downloadable WAV stream."""
    try:
        audio = render_request(request)
        return Response(audio, media_type="audio/wav", headers={"Content-Disposition": "attachment; filename=composition.wav"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/render/jobs", status_code=202)
def create_render_job(request: RenderRequest) -> dict[str, str]:
    """Queue a WAV render and return a job identifier immediately."""
    return {"job_id": render_jobs.submit(lambda: render_request(request)), "status": "queued"}


@app.get("/api/render/jobs/{job_id}")
def get_render_job(job_id: str) -> dict[str, str]:
    """Report queued, running, completed, or failed offline rendering state."""
    job = render_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    payload = {"job_id": job_id, "status": job.status}
    if job.error:
        payload["error"] = job.error
    return payload


@app.get("/api/render/jobs/{job_id}/audio")
def get_rendered_audio(job_id: str) -> Response:
    """Download the completed WAV for an async rendering job."""
    job = render_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    if job.status != "completed" or job.audio is None:
        raise HTTPException(status_code=409, detail=f"render job is {job.status}")
    return Response(job.audio, media_type="audio/wav", headers={"Content-Disposition": "attachment; filename=composition.wav"})


@app.websocket("/api/ws/transport")
async def transport(websocket: WebSocket) -> None:
    """WebSocket transport for play, pause, stop, and live-improvise commands."""
    await websocket.accept()
    state = "stopped"
    try:
        while True:
            message = await websocket.receive_json()
            command = message.get("command")
            if command in {"play", "pause", "stop"}:
                state = {"play": "playing", "pause": "paused", "stop": "stopped"}[command]
                await websocket.send_json({"type": "transport", "state": state})
            elif command == "improvise":
                await websocket.send_json({"type": "improvise", "state": state, "seed": message.get("seed", 0)})
            else:
                await websocket.send_json({"type": "error", "message": "unknown transport command"})
    except WebSocketDisconnect:
        return


@app.post("/api/export/midi")
def export_midi(request: MidiRequest) -> Response:
    """Export rational notes as a standard MIDI type-0 file."""
    try:
        notes = [MidiNote(parse_ratio(note.ratio), note.start_beats, note.duration_beats, note.velocity) for note in request.notes]
        if request.pitch_bend:
            data = microtonal_midi_bytes(notes, request.base_frequency, request.ticks_per_beat, request.pitch_bend_range_semitones)
        else:
            data = midi_bytes(notes, request.base_frequency, request.ticks_per_beat)
        return Response(data, media_type="audio/midi", headers={"Content-Disposition": "attachment; filename=composition.mid"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/export/rhythm/midi")
def export_rhythm_midi(request: RhythmMidiRequest) -> Response:
    """Export a binary rhythm pattern as GM percussion MIDI (channel 10)."""
    try:
        velocities = request.velocities_for()
        hits = [
            MidiDrumHit(request.note, index / request.steps_per_beat, velocities[index])
            for index, active in enumerate(request.pattern)
            if active
        ]
        data = drum_midi_bytes(hits, request.ticks_per_beat)
        return Response(data, media_type="audio/midi", headers={"Content-Disposition": "attachment; filename=rhythm.mid"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/export/json")
def export_json(request: JsonExportRequest) -> dict[str, object]:
    """Export a composition payload as structured JSON data."""
    return {"name": request.name, "composition": request.composition}


@app.post("/api/export/scala")
def export_scala(request: ScalaRequest) -> Response:
    try:
        ratios = [parse_ratio(value) for value in request.ratios]
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail="ratios must be positive fractions") from error
    return Response(scala_text(request.name, ratios), media_type="text/plain")


def scale_payload(name: str, ratios: list[Fraction]) -> dict[str, object]:
    return {"name": name, **pitch_payload(ratios)}


@app.get("/api/scales")
def scales_list() -> list[dict[str, object]]:
    """List stored scales in insertion order."""
    return list_scales()


@app.post("/api/scales")
def scales_save(request: ScaleSaveRequest) -> dict[str, object]:
    """Save or overwrite a named scale and return its pitch payload."""
    try:
        entry = save_scale(request.name, request.ratios)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return scale_payload(request.name, cast(list[Fraction], entry["ratios"]))


@app.post("/api/scales/import")
def scales_import(request: ScalaImportRequest) -> dict[str, object]:
    """Import a Scala .scl file, store it, and return its pitch payload."""
    try:
        ratios = parse_scala(request.content)
        save_scale(request.name, [ratio_text(ratio) for ratio in ratios])
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return scale_payload(request.name, ratios)


@app.get("/api/scales/{name}")
def scales_get(name: str) -> dict[str, object]:
    entry = get_scale(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="scale not found")
    return scale_payload(name, cast(list[Fraction], entry["ratios"]))


@app.delete("/api/scales/{name}")
def scales_delete(name: str) -> dict[str, object]:
    if not delete_scale(name):
        raise HTTPException(status_code=404, detail="scale not found")
    return {"name": name, "deleted": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
