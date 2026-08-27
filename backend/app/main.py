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
from app.composition.rhythm import (
    CompositionClock,
    RhythmGeneratorSettings,
    RhythmLayer,
    RhythmMapping,
    compile_rhythm,
    generate_compose_rhythm,
)
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
    ComposeRhythmApplyRequest,
    ComposeRhythmGenerateRequest,
    EulerFokkerRequest,
    HarmonicGraphRequest,
    HarmonyRequest,
    HumanizeRequest,
    IntervalRequest,
    JsonExportRequest,
    LatticeAnalyzeRequest,
    LatticeChordRequest,
    LatticeHarmonyRequest,
    LatticeProgressionRequest,
    LatticeScaleRequest,
    PrimeExplorerRequest,
    MinimalFunctionalRequest,
    MinimalFunctionalMidiRequest,
    JPopRequest,
    KawaiiFuturePopRequest,
    CompositionExploreRequest,
    VitalPackRequest,
    MotifVitalPackRequest,
    VitalPackMidiRequest,
    VitalPackSectionRequest,
    MotifCompareRequest,
    MotifDevelopRequest,
    MotifGenerateRequest,
    MotifVariationRequest,
    PrimeChordRequest,
    PrimeProgressionRequest,
    LatticeWalkRequest,
    MidiRequest,
    MidiToolkitProcessRequest,
    RatioRequest,
    ScalaRequest,
    SeriesRequest,
    SnapRequest,
    VoiceLeadingRequest,
    MelodyRequest,
    EuclideanRhythmRequest,
    DrumGenerateRequest,
    OptimizeRotationsRequest,
    PhaseShiftRequest,
    RhythmAnalyzeRequest,
    RhythmStateGraphRequest,
    RenderRequest,
    RhythmMidiRequest,
    ScaleSaveRequest,
    ScalaImportRequest,
)
from app.lattice import (
    ExponentBasis,
    LatticePitch,
    cents_distance,
    enumerate_domain,
    evaluate,
    generate_lattice_chord,
    lattice_distance,
    lattice_walk,
    monzo_distance,
    normalize,
    reconstruct,
    root_progression,
)
from app.prime_explorer import discover_chords, explore as explore_prime_limit, progression_metrics
from app.composition.minimal_functional import generate_minimal_functional
from app.composition.jpop import generate_jpop
from app.composition.kawaii_future_pop import generate_kawaii_future_pop
from app.composition.explorer import explore_compositions, explorer_profiles
from app.composition.vital_pack import (
    DRUM_PROFILES,
    PROFILES,
    generate_motif_vital_pack,
    generate_vital_pack,
    vital_pack_profiles,
)
from app.motif.engine import compare as compare_motif
from app.motif.engine import develop as develop_motif
from app.motif.engine import generate as generate_motif
from app.midi_toolkit import midi_scale_catalog, process_performance
from app.motif.engine import vary as vary_motif
from app.exporters.midi import (
    MidiArrangementTrack,
    MidiDrumHit,
    MidiNote,
    arrangement_midi_bytes,
    drum_midi_bytes,
    microtonal_midi_bytes,
    midi_bytes,
)
from app.rhythm.drums import (
    LayerSpec,
    accent_velocities,
    analysis_length,
    analyze_layers,
    optimize_rotations,
    phase_offsets,
)
from app.rhythm.engine import euclidean_rhythm, humanize, phase_shift, state_transition_graph
from app.arrangement.models import (
    ArrangeGenerateRequest,
    ArrangeMigrationRequest,
    ArrangeProjectRequest,
)
from app.arrangement.phase import HarmonicPhaseShiftRequest, generate_phase_shift
from app.arrangement.profiles import profile_summaries
from app.arrangement.project import (
    generate_arrangement,
    migrate_arrangement_project,
    project_midi_bytes,
    project_render_wav,
)
from app.exporters.scala import scala_text
from app.exporters.scala_import import parse_scala
from app.scales import delete_scale, get_scale, list_scales, save_scale
from app.tuning.analysis import cents, monzo
from app.tuning.ratios import parse_interval, parse_ratio, ratio_text, reduce_to_octave
from app.tuning.snap import snap_ratio
from app.bp import (
    BPChordSearchRequest,
    BPComposeRequest,
    BPExportRequest,
    BPProgressionRequest,
    BPRenderRequest,
    BPScaleRequest,
    chord_search as bp_chord_search,
    compose as bp_compose,
    export_midi as bp_export_midi,
    export_scala as bp_export_scala,
    generate_scale as bp_generate_scale,
    progression_search as bp_progression_search,
    render_audio as bp_render_audio,
)
from app.rhythm.mixed_meter import (
    MixedMeterExportRequest,
    MixedMeterGenerateRequest,
    MixedMeterValidateRequest,
    export_midi as mixed_meter_export_midi,
    generate as generate_mixed_meter,
    pattern_library as mixed_meter_pattern_library,
    render_wav as render_mixed_meter_wav,
    validate_pattern as validate_mixed_meter_pattern,
)

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


@app.get("/lattice", include_in_schema=False)
def lattice_lab() -> FileResponse:
    return FileResponse(STATIC_DIR / "lattice.html")


@app.get("/harmonic-pitch-circle", include_in_schema=False)
def harmonic_pitch_circle() -> FileResponse:
    return FileResponse(STATIC_DIR / "harmonic_pitch_circle.html")


@app.get("/prime-limit-explorer", include_in_schema=False)
def prime_limit_explorer() -> FileResponse:
    return FileResponse(STATIC_DIR / "prime_limit_explorer.html")


@app.get("/minimal-functional-composer", include_in_schema=False)
def minimal_functional_composer() -> FileResponse:
    return FileResponse(STATIC_DIR / "minimal_functional_composer.html")


@app.get("/motif-development", include_in_schema=False)
def motif_development() -> FileResponse:
    return FileResponse(STATIC_DIR / "motif_development.html")


@app.get("/midi-toolkit", include_in_schema=False)
def midi_toolkit() -> FileResponse:
    return FileResponse(STATIC_DIR / "midi_toolkit.html")


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
        [
            NoteEvent(
                parse_ratio(event.ratio),
                event.start_seconds,
                event.duration_seconds,
                event.velocity,
            )
            for event in request.events
        ],
        request.base_frequency,
        request.waveform,
        Envelope(
            request.attack_seconds,
            request.decay_seconds,
            request.sustain_level,
            request.release_seconds,
        ),
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
        return pitch_payload(
            generate_cps(request.factors, request.choose, request.kind, request.octave_reduce)
        )
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
                {
                    "index": index,
                    "factors": node.factors,
                    "ratio": ratio_text(node.ratio),
                    "sub_ratio": ratio_text(reduce_to_octave(2 / node.ratio)),
                }
                for index, node in enumerate(graph.nodes)
            ],
            "edges": [{"source": left, "target": right} for left, right in graph.edges],
        }
        if request.layout == "reference_layered_grid":
            layout = reference_layered_grid_layout(
                graph, request.reference or 0, sort_mode=request.sort_mode
            )
            payload["layout"] = {
                "kind": "reference_layered_grid",
                "reference": layout.reference,
                "sort_mode": layout.sort_mode,
                "positions": [{"x": x, "y": y} for x, y in layout.positions],
                "shared_counts": list(layout.shared_counts),
                "distances": list(layout.distances),
                "layers": [
                    {
                        "shared": shared,
                        "distance": max(layout.distances) - shared,
                        "nodes": list(members),
                    }
                    for shared, members in layout.layers
                ],
                "edge_directions": list(layout.edge_directions),
            }
        if request.operation == "shortest_path":
            if request.end is None:
                raise ValueError("end is required for shortest_path")
            payload["walk"] = shortest_path(graph, request.start, request.end)
        elif request.operation == "random_walk":
            payload["walk"] = random_walk(graph, request.start, request.steps, request.seed)
        elif request.operation == "weighted_walk":
            payload["walk"] = weighted_walk(
                graph, request.start, request.steps, request.seed, request.metric
            )
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
                [{"ratio": ratio_text(note), "cents": round(cents(note), 5)} for note in voice]
                for voice in melody.voices
            ],
        }
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _composition_clock(
    request: ComposeRhythmApplyRequest | ComposeRhythmGenerateRequest,
) -> CompositionClock:
    clock = request.clock
    return CompositionClock(
        beats_per_bar=clock.beats_per_bar,
        subdivisions_per_beat=clock.subdivisions_per_beat,
        bars=clock.bars,
        ticks_per_beat=clock.ticks_per_beat,
        tempo_bpm=clock.tempo_bpm,
    )


def _composition_pitches(
    request: ComposeRhythmApplyRequest | ComposeRhythmGenerateRequest,
) -> tuple[list[list[Fraction]], list[Fraction], list[list[Fraction]]]:
    composition = request.composition
    return (
        [[parse_ratio(value) for value in chord] for chord in composition.chords],
        [parse_ratio(value) for value in composition.bass],
        [[parse_ratio(value) for value in voice] for voice in composition.melody],
    )


@app.post("/api/compose/rhythm/apply")
def compose_rhythm_apply(request: ComposeRhythmApplyRequest) -> dict[str, object]:
    """Map existing polymetric Rhythm layers onto Compose pitch material."""
    try:
        chords, bass, melody = _composition_pitches(request)
        layers = [
            RhythmLayer(
                layer.name,
                tuple(layer.pattern),
                tuple(layer.velocities_for()),
                tuple(layer.phase_offsets),
            )
            for layer in request.layers
        ]
        mappings = [
            RhythmMapping(
                mapping.source_layer,
                mapping.target,
                mapping.policy,
                mapping.overflow,
                mapping.gate,
                mapping.register_octave,
                mapping.velocity_scale,
                mapping.collision,
                mapping.articulation,
            )
            for mapping in request.mappings
        ]
        return compile_rhythm(
            _composition_clock(request),
            chords,
            bass,
            melody,
            layers,
            mappings,
            request.chord_durations,
        ).payload()
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/rhythm/generate")
def compose_rhythm_generate(request: ComposeRhythmGenerateRequest) -> dict[str, object]:
    """Generate seeded Compose-native rhythm and compile timed rational events."""
    try:
        chords, bass, melody = _composition_pitches(request)
        target_settings = (
            [
                RhythmGeneratorSettings(
                    generator.target,
                    generator.strategy,
                    generator.profile,
                    generator.density,
                    generator.syncopation,
                )
                for generator in request.generators
            ]
            if request.generators is not None
            else None
        )
        layers, mappings, durations, compiled = generate_compose_rhythm(
            _composition_clock(request),
            chords,
            bass,
            melody,
            request.strategy,
            request.profile,
            request.density,
            request.syncopation,
            request.seed,
            request.targets,
            request.composition.transition_scores,
            target_settings,
        )
        return {
            "strategy": request.strategy,
            "profile": request.profile,
            "seed": request.seed,
            "generators": [
                {
                    "target": setting.target,
                    "strategy": setting.strategy,
                    "profile": setting.profile,
                    "density": setting.density,
                    "syncopation": setting.syncopation,
                }
                for setting in (
                    target_settings
                    or [
                        RhythmGeneratorSettings(
                            target,
                            request.strategy,
                            request.profile,
                            request.density,
                            request.syncopation,
                        )
                        for target in request.targets
                    ]
                )
            ],
            "layers": [
                {
                    "name": layer.name,
                    "pattern": list(layer.pattern),
                    "velocities": list(layer.velocities),
                    "phase_offsets": list(layer.phase_offsets),
                }
                for layer in layers
            ],
            "mappings": [
                {
                    "source_layer": mapping.source_layer,
                    "target": mapping.target,
                    "policy": mapping.policy,
                    "overflow": mapping.overflow,
                    "gate": mapping.gate,
                    "register_octave": mapping.register_octave,
                    "velocity_scale": mapping.velocity_scale,
                    "collision": mapping.collision,
                    "articulation": mapping.articulation,
                }
                for mapping in mappings
            ],
            "chord_durations": durations,
            **compiled.payload(),
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


@app.post("/api/rhythm/optimize-rotations")
def rhythm_optimize_rotations(request: OptimizeRotationsRequest) -> dict[str, object]:
    """Optimize each layer's rotation sequentially against already-placed layers."""
    try:
        specs = [layer.to_spec() for layer in request.layers]
        results = optimize_rotations(specs, request.max_analysis_steps)
        return {
            "analysis_length": analysis_length(
                [spec.steps for spec in specs], request.max_analysis_steps
            ),
            "layers": [
                {
                    "name": result.name,
                    "pattern": result.pattern,
                    "rotation": result.rotation,
                    "score": result.score,
                    "breakdown": result.breakdown,
                }
                for result in results
            ],
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/analyze")
def rhythm_analyze(request: RhythmAnalyzeRequest) -> dict[str, object]:
    """Analyze binary rhythm layers on the shared analysis grid."""
    try:
        layers = {layer.name: layer.pattern for layer in request.layers}
        if len(layers) != len(request.layers):
            raise ValueError("layer names must be unique")
        return analyze_layers(layers, request.max_analysis_steps)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/drums/generate")
def drums_generate(request: DrumGenerateRequest) -> dict[str, object]:
    """Generate coordinated drum layers with rotations, phase offsets, and velocities."""
    try:
        specs = [layer.to_spec() for layer in request.layers]
        if len({spec.name for spec in specs}) != len(specs):
            raise ValueError("layer names must be unique")
        if request.optimize:
            rotations = [
                result.rotation for result in optimize_rotations(specs, request.max_analysis_steps)
            ]
        else:
            rotations = [(spec.rotation or 0) % spec.steps for spec in specs]
        layers: list[dict[str, object]] = []
        patterns: dict[str, list[int]] = {}
        for spec, rotation in zip(specs, rotations):
            pattern = euclidean_rhythm(spec.steps, spec.pulses, rotation)
            layers.append(
                {
                    "name": spec.name,
                    "pattern": pattern,
                    "rotation": rotation,
                    "velocities": accent_velocities(pattern, spec.base_velocity),
                    "phase_offsets": phase_offsets(
                        LayerSpec(
                            spec.name,
                            spec.steps,
                            spec.pulses,
                            rotation,
                            spec.phase_increment,
                            spec.phase_update_bars,
                            spec.base_velocity,
                        ),
                        request.bars,
                    ),
                }
            )
            patterns[spec.name] = pattern
        return {
            "bars": request.bars,
            "layers": layers,
            "metrics": analyze_layers(patterns, request.max_analysis_steps),
        }
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
        return Response(
            audio,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=composition.wav"},
        )
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
    return Response(
        job.audio,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=composition.wav"},
    )


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
                await websocket.send_json(
                    {"type": "improvise", "state": state, "seed": message.get("seed", 0)}
                )
            else:
                await websocket.send_json({"type": "error", "message": "unknown transport command"})
    except WebSocketDisconnect:
        return


@app.post("/api/export/midi")
def export_midi(request: MidiRequest) -> Response:
    """Export rational notes as a standard MIDI type-0 file."""
    try:
        notes = [
            MidiNote(parse_ratio(note.ratio), note.start_beats, note.duration_beats, note.velocity)
            for note in request.notes
        ]
        if request.pitch_bend:
            data = microtonal_midi_bytes(
                notes,
                request.base_frequency,
                request.ticks_per_beat,
                request.pitch_bend_range_semitones,
            )
        else:
            data = midi_bytes(notes, request.base_frequency, request.ticks_per_beat)
        return Response(
            data,
            media_type="audio/midi",
            headers={"Content-Disposition": "attachment; filename=composition.mid"},
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/midi-toolkit/process")
def process_midi_toolkit_performance(
    request: MidiToolkitProcessRequest,
) -> dict[str, object]:
    """Quantize a keyboard performance and map it to an exact-ratio motif."""
    try:
        return process_performance(request.model_dump())
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/midi-toolkit/scales")
def midi_toolkit_scales() -> dict[str, object]:
    """List built-in scale assignments and available scale generators."""
    catalog = midi_scale_catalog()
    catalog["stored"] = list_scales()
    return catalog


@app.post("/api/export/rhythm/midi")
def export_rhythm_midi(request: RhythmMidiRequest) -> Response:
    """Export binary rhythm patterns as GM percussion MIDI (channel 10)."""
    try:
        hits: list[MidiDrumHit] = []
        if request.layers is not None:
            for layer in request.layers:
                velocities = layer.velocities_for()
                hits.extend(
                    MidiDrumHit(
                        layer.note,
                        (cycle * len(layer.pattern) + index) / request.steps_per_beat,
                        velocities[index],
                    )
                    for cycle in range(request.cycles)
                    for index, active in enumerate(layer.pattern)
                    if active
                )
        else:
            if request.pattern is None:
                raise ValueError("pattern is required when layers are not provided")
            velocities = request.velocities_for()
            hits.extend(
                MidiDrumHit(
                    request.note,
                    (cycle * len(request.pattern) + index) / request.steps_per_beat,
                    velocities[index],
                )
                for cycle in range(request.cycles)
                for index, active in enumerate(request.pattern)
                if active
            )
        data = drum_midi_bytes(hits, request.ticks_per_beat)
        return Response(
            data,
            media_type="audio/midi",
            headers={"Content-Disposition": "attachment; filename=rhythm.mid"},
        )
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


def _lattice_basis_payload(basis: ExponentBasis) -> dict[str, object]:
    return {
        "generators": list(basis.generators),
        "prime_matrix": [
            {str(prime): exponent for prime, exponent in sorted(row.items())}
            for row in basis.prime_matrix()
        ],
        "dependencies": [list(vector) for vector in basis.dependencies()],
        "warnings": basis.warnings(),
    }


def _lattice_pitch_payload(point: LatticePitch) -> dict[str, object]:
    return {
        "vector": list(point.vector),
        "ratio": ratio_text(point.raw_ratio),
        "normalized_ratio": ratio_text(point.normalized_ratio),
        "octave_shift": point.octave_shift,
        "cents": round(point.cents, 5),
        "pitch_class_id": point.pitch_class_id,
        "collision_group": point.collision_group,
    }


@app.post("/api/exponent-lattice/scale")
def exponent_lattice_scale(request: LatticeScaleRequest) -> dict[str, object]:
    """Enumerate a bounded exponent-lattice domain with collision diagnostics."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        points = enumerate_domain(basis, tuple(request.minimum), tuple(request.maximum))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if request.collision_policy == "merge":
        seen: set[str] = set()
        merged: list[LatticePitch] = []
        for point in points:
            if point.pitch_class_id in seen:
                continue
            seen.add(point.pitch_class_id)
            merged.append(point)
        points = merged
    return {
        "basis": _lattice_basis_payload(basis),
        "point_count": len(points),
        "points": [_lattice_pitch_payload(point) for point in points],
    }


@app.post("/api/prime-limit/explore")
def prime_limit_explore(request: PrimeExplorerRequest) -> dict[str, object]:
    """Enumerate, octave-reduce, cluster, and select a prime-lattice scale."""
    try:
        return explore_prime_limit(
            tuple(request.primes),
            request.exponent_limit,
            request.height_limit,
            request.tolerance_cents,
            request.target_count,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/minimal-functional/generate")
def minimal_functional_generate(request: MinimalFunctionalRequest) -> dict[str, object]:
    return generate_minimal_functional(request.model_dump())


@app.post("/api/minimal-functional/midi")
def minimal_functional_midi(request: MinimalFunctionalMidiRequest) -> Response:
    try:
        notes = tuple(
            MidiNote(parse_ratio(note.ratio), note.start_beats, note.duration_beats, note.velocity)
            for note in request.notes
        )
        drums = tuple(MidiDrumHit(hit.note, hit.start_beat, hit.velocity) for hit in request.drums)
        data = arrangement_midi_bytes(
            [
                MidiArrangementTrack("Harmony", notes=notes),
                MidiArrangementTrack("Drums", drums=drums),
            ],
            request.tempo_bpm,
            request.beats_per_bar,
            base_frequency=request.base_frequency,
        )
        return Response(
            data,
            media_type="audio/midi",
            headers={"Content-Disposition": "attachment; filename=minimal-functional-study.mid"},
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/vital-pack-composer", include_in_schema=False)
def vital_pack_composer() -> FileResponse:
    return FileResponse(STATIC_DIR / "vital_pack_composer.html")


@app.get("/fractional-pop-composer", include_in_schema=False)
def fractional_pop_composer() -> FileResponse:
    return FileResponse(STATIC_DIR / "fractional_pop_composer.html")


@app.get("/jpop-composer", include_in_schema=False)
def jpop_composer() -> FileResponse:
    return FileResponse(STATIC_DIR / "jpop_composer.html")


@app.get("/kawaii-future-pop", include_in_schema=False)
def kawaii_future_pop() -> FileResponse:
    return FileResponse(STATIC_DIR / "kawaii_future_pop.html")


@app.get("/composition-explorer", include_in_schema=False)
def composition_explorer() -> FileResponse:
    return FileResponse(STATIC_DIR / "composition_explorer.html")


@app.get("/compose/bohlen-pierce", include_in_schema=False)
def bohlen_pierce_workbench() -> FileResponse:
    return FileResponse(STATIC_DIR / "bohlen_pierce.html")


@app.get("/compose/mixed-meter-drums", include_in_schema=False)
def mixed_meter_drum_section() -> FileResponse:
    return FileResponse(STATIC_DIR / "mixed_meter_drums.html")


@app.post("/api/bp/scales/generate")
def generate_bohlen_pierce_scale(request: BPScaleRequest) -> dict[str, object]:
    try:
        return bp_generate_scale(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/chords/search")
def search_bohlen_pierce_chords(request: BPChordSearchRequest) -> dict[str, object]:
    try:
        return bp_chord_search(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/progressions/search")
def search_bohlen_pierce_progressions(request: BPProgressionRequest) -> dict[str, object]:
    try:
        return bp_progression_search(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/compose/generate")
def generate_bohlen_pierce_composition(request: BPComposeRequest) -> dict[str, object]:
    try:
        return bp_compose(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/render/audio")
def render_bohlen_pierce_audio(request: BPRenderRequest) -> Response:
    try:
        return Response(bp_render_audio(request), media_type="audio/wav", headers={"Content-Disposition": "attachment; filename=bohlen-pierce.wav"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/export/midi")
def export_bohlen_pierce_midi(request: BPExportRequest) -> Response:
    try:
        return Response(bp_export_midi(request), media_type="audio/midi", headers={"Content-Disposition": "attachment; filename=bohlen-pierce-mpe.mid"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/bp/export/scala")
def export_bohlen_pierce_scala(payload: dict[str, object]) -> Response:
    try:
        pitches = cast(list[dict[str, object]], payload.get("pitches", []))
        return Response(bp_export_scala(pitches, str(payload.get("name", "Pure BP scale"))), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=bohlen-pierce.scl"})
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/rhythm/mixed-meter/patterns")
def get_mixed_meter_patterns() -> dict[str, object]:
    return mixed_meter_pattern_library()


@app.post("/api/rhythm/mixed-meter/validate")
def validate_mixed_meter(request: MixedMeterValidateRequest) -> dict[str, object]:
    try:
        return validate_mixed_meter_pattern(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/mixed-meter/generate")
def generate_mixed_meter_drums(request: MixedMeterGenerateRequest) -> dict[str, object]:
    try:
        return generate_mixed_meter(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/mixed-meter/preview")
def preview_mixed_meter_drums(request: MixedMeterExportRequest) -> Response:
    try:
        return Response(render_mixed_meter_wav(request.project), media_type="audio/wav", headers={"Content-Disposition": "attachment; filename=mixed-meter-drums.wav"})
    except (ValueError, ZeroDivisionError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rhythm/mixed-meter/export/midi")
def export_mixed_meter_midi(request: MixedMeterExportRequest) -> Response:
    try:
        return Response(mixed_meter_export_midi(request), media_type="audio/midi", headers={"Content-Disposition": "attachment; filename=mixed-meter-drums.mid"})
    except (ValueError, ZeroDivisionError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/instruments/vital-pack")
def get_vital_pack_profiles() -> dict[str, object]:
    return vital_pack_profiles()


@app.post("/api/compose/vital-pack")
def compose_vital_pack(request: VitalPackRequest) -> dict[str, object]:
    return generate_vital_pack(request.model_dump())


@app.post("/api/compose/jpop")
def compose_jpop(request: JPopRequest) -> dict[str, object]:
    return generate_jpop(request.model_dump())


@app.post("/api/compose/kawaii-future-pop")
def compose_kawaii_future_pop(request: KawaiiFuturePopRequest) -> dict[str, object]:
    return generate_kawaii_future_pop(request.model_dump())


@app.get("/api/composition-explorer/profiles")
def get_composition_explorer_profiles() -> dict[str, object]:
    return explorer_profiles()


@app.post("/api/composition-explorer/explore")
def explore_instrument_constrained_compositions(
    request: CompositionExploreRequest,
) -> dict[str, object]:
    try:
        return explore_compositions(request.model_dump())
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/motif-vital-pack")
def compose_motif_vital_pack(request: MotifVitalPackRequest) -> dict[str, object]:
    """Arrange selected Motif Development Tree nodes with Vital Pack profiles."""
    try:
        return generate_motif_vital_pack(request.model_dump())
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/compose/vital-pack/section")
def regenerate_vital_pack_section(request: VitalPackSectionRequest) -> dict[str, object]:
    plan = generate_vital_pack(
        request.model_dump() | {"seed": request.seed + request.section_index + 1}
    )
    if request.section_index >= len(plan["sections"]):
        raise HTTPException(
            status_code=422,
            detail=f"section_index must be below section_count ({len(plan['sections'])})",
        )
    section = plan["sections"][request.section_index]
    start = (int(section["start_bar"]) - 1) * 4
    end = start + int(section["bars"]) * 4
    replacement_ids = (
        [profile[0] for profile in DRUM_PROFILES]
        if request.scope == "rhythm"
        else [item[0] for item in PROFILES]
        if request.scope == "voicing"
        else None
    )
    selected_events = [
        event
        for event in plan["events"]
        if start <= event["start_beat"] < end
        and (replacement_ids is None or event["instrument_id"] in replacement_ids)
    ]
    selected_ids = sorted({event["instrument_id"] for event in selected_events})
    return {
        "scope": request.scope,
        "section": section,
        "replace_harmony": request.scope in {"harmony", "instruments"},
        "replace_instruments": selected_ids,
        "harmony": [
            event
            for event in plan["harmony"]
            if request.scope in {"harmony", "instruments"} and start <= event["start_beat"] < end
        ],
        "events": selected_events,
        "automation": [
            event
            for event in plan["automation"]
            if event["start_beat"] == start and event["instrument_id"] in selected_ids
        ],
        "tuning_timeline": [
            event
            for event in plan["tuning_timeline"]
            if start <= event["time"] < end and event["instrument_id"] in selected_ids
        ],
        "mts_timeline": [
            event
            for event in plan["mts_timeline"]
            if start <= event["time"] < end and event["instrument_id"] in selected_ids
        ],
        "sidechain_envelope": [
            event
            for event in plan["sidechain_envelope"]
            if ({"DRUMS", "PI09"} & set(selected_ids)) and start <= event["start_beat"] < end
        ],
    }


@app.post("/api/compose/vital-pack/midi")
def vital_pack_midi(request: VitalPackMidiRequest) -> Response:
    try:
        track_names = [
            "PI01",
            "PI02",
            "PI03",
            "PI04",
            "PI05",
            "PI06",
            "PI07",
            "PI08",
            "PI22",
            "PIANO",
            *(profile[0] for profile in DRUM_PROFILES),
            "PI13",
            "PI14",
            "PI15",
            "PI16",
            "PI17",
            "PI18",
            "PI19",
            "PI20",
            "PI21",
            "DRUMS",
        ]
        tracks = []
        for name in track_names:
            matching = [event for event in request.events if event.instrument_id == name]
            if not matching:
                continue
            tracks.append(
                MidiArrangementTrack(
                    name,
                    notes=tuple(
                        MidiNote(
                            parse_ratio(event.ratio),
                            event.start_beat,
                            event.duration_beats,
                            event.velocity,
                        )
                        for event in matching
                        if event.ratio
                    ),
                    drums=tuple(
                        MidiDrumHit(event.note, event.start_beat, event.velocity)
                        for event in matching
                        if event.note is not None
                    ),
                )
            )
        data = arrangement_midi_bytes(
            tracks,
            request.tempo_bpm,
            4,
            base_frequency=request.base_frequency,
            markers=[
                (round(beat * 480), name) for beat, name in request.section_markers
            ],
            time_signatures=[
                (round(beat * 480), numerator, denominator)
                for beat, numerator, denominator in request.time_signatures
            ],
        )
        return Response(
            data,
            media_type="audio/midi",
            headers={"Content-Disposition": "attachment; filename=vital-pack-arrangement.mid"},
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/motif/generate")
def motif_generate(request: MotifGenerateRequest) -> dict[str, object]:
    """Generate a deterministic prime-basis motif from a three- or four-note anchor chord."""
    try:
        return generate_motif(request.model_dump())
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/motif/compare")
def motif_compare(request: MotifCompareRequest) -> dict[str, object]:
    """Compare two inline motifs without collapsing monzo and pitch-circle distance."""
    try:
        source = [note.model_dump() for note in request.source_notes]
        target = [note.model_dump() for note in request.target_notes]
        return compare_motif(
            source,
            target,
            [parse_ratio(value) for value in request.anchor_chord],
            tuple(request.prime_basis),
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/motif/variation")
def motif_variation(request: MotifVariationRequest) -> dict[str, object]:
    """Create a deterministic transformed variation adapted to a target chord."""
    try:
        payload = request.model_dump()
        payload["source_notes"] = [note.model_dump() for note in request.source_notes]
        return vary_motif(payload)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/motif/develop")
def motif_develop(request: MotifDevelopRequest) -> dict[str, object]:
    """Expand a theme through deterministic formal-role variations."""
    try:
        payload = request.model_dump()
        payload["source_notes"] = [note.model_dump() for note in request.source_notes]
        return develop_motif(payload)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/prime-limit/chords")
def prime_limit_chords(request: PrimeChordRequest) -> dict[str, object]:
    try:
        return discover_chords(
            tuple(request.primes),
            request.exponent_limit,
            request.height_limit,
            request.tolerance_cents,
            request.target_count,
            request.tone_count,
            request.candidate_limit,
            request.ranking_mode,
            tuple(request.root_vector),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/prime-limit/progression")
def prime_limit_progression(request: PrimeProgressionRequest) -> dict[str, object]:
    try:
        return {"transitions": progression_metrics(request.chords)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/exponent-lattice/harmony")
def exponent_lattice_harmony(request: LatticeHarmonyRequest) -> dict[str, object]:
    """Reconstruct a chord from independent root-relative vectors."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        root = parse_ratio(request.root)
        if request.root_vector is not None:
            implied = evaluate(basis, tuple(request.root_vector))
            if normalize(implied)[0] != normalize(root)[0]:
                raise ValueError("root_vector does not match the root pitch class")
        offsets, tones = reconstruct(
            root,
            basis,
            [tuple(vector) for vector in request.chord_vectors],
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "offsets": [list(offset) for offset in offsets],
        "tones": [
            {
                "vector": list(tone.vector),
                "raw_ratio": ratio_text(tone.raw_ratio),
                "normalized_ratio": ratio_text(tone.normalized_ratio),
                "octave_shift": tone.octave_shift,
                "cents": round(tone.cents, 5),
            }
            for tone in tones
        ],
        "root": ratio_text(root),
    }


@app.post("/api/exponent-lattice/chord")
def exponent_lattice_chord(request: LatticeChordRequest) -> dict[str, object]:
    """Generate seeded root-relative chord vectors with unique pitches."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        root = parse_ratio(request.root)
        chord_vectors, offsets, tones = generate_lattice_chord(
            root,
            basis,
            [tuple(difference) for difference in request.allowed_differences],
            request.tone_count,
            request.seed,
            tuple(request.minimum),
            tuple(request.maximum),
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "root": ratio_text(root),
        "seed": request.seed,
        "chord_vectors": [list(vector) for vector in chord_vectors],
        "differences": [list(vector) for vector in chord_vectors],
        "offsets": [list(offset) for offset in offsets],
        "tones": [
            {
                "vector": list(tone.vector),
                "raw_ratio": ratio_text(tone.raw_ratio),
                "normalized_ratio": ratio_text(tone.normalized_ratio),
                "octave_shift": tone.octave_shift,
                "cents": round(tone.cents, 5),
            }
            for tone in tones
        ],
    }


def _lattice_harmony_sequence(
    root: Fraction,
    basis: ExponentBasis,
    path: list[tuple[int, ...]],
    chord_vectors: list[tuple[int, ...]],
) -> dict[str, object]:
    pitches = []
    harmonies = []
    chord_offsets: list[list[int]] = []
    for vector in path:
        sounding_root = root * evaluate(basis, vector)
        normalized_ratio, _shift = normalize(sounding_root)
        pitches.append(
            {
                "vector": list(vector),
                "normalized_ratio": ratio_text(normalized_ratio),
                "cents": round(cents(normalized_ratio), 5),
            }
        )
        offsets, tones = reconstruct(sounding_root, basis, chord_vectors)
        if not chord_offsets:
            chord_offsets = [list(offset) for offset in offsets]
        harmonies.append(
            {
                "root_vector": list(vector),
                "tones": [
                    {
                        "vector": [
                            coordinate + offset for coordinate, offset in zip(vector, tone.vector)
                        ],
                        "offset": list(tone.vector),
                        "raw_ratio": ratio_text(tone.raw_ratio),
                        "normalized_ratio": ratio_text(tone.normalized_ratio),
                        "octave_shift": tone.octave_shift,
                        "cents": round(tone.cents, 5),
                    }
                    for tone in tones
                ],
            }
        )
    return {
        "path": [list(vector) for vector in path],
        "pitches": pitches,
        "chord_offsets": chord_offsets,
        "harmony_offsets": chord_offsets,
        "harmonies": harmonies,
    }


@app.post("/api/exponent-lattice/progression")
def exponent_lattice_progression(request: LatticeProgressionRequest) -> dict[str, object]:
    """Accumulate root motion and apply one root-relative chord at every step."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        root = parse_ratio(request.root)
        path = root_progression(
            basis,
            tuple(request.start_vector),
            [tuple(difference) for difference in request.progression_differences],
        )
        return _lattice_harmony_sequence(
            root,
            basis,
            path,
            [tuple(vector) for vector in request.chord_vectors],
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/exponent-lattice/walk")
def exponent_lattice_walk(request: LatticeWalkRequest) -> dict[str, object]:
    """Run a seeded root walk and apply one root-relative chord at every step."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        root = parse_ratio(request.root)
        path = lattice_walk(
            basis,
            tuple(request.start_vector),
            [tuple(difference) for difference in request.allowed_differences],
            request.length,
            request.seed,
            tuple(request.minimum),
            tuple(request.maximum),
            request.boundary,
        )
        return _lattice_harmony_sequence(
            root,
            basis,
            path,
            [tuple(vector) for vector in request.chord_vectors],
        )
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/exponent-lattice/analyze")
def exponent_lattice_analyze(request: LatticeAnalyzeRequest) -> dict[str, object]:
    """Report basis diagnostics and pairwise lattice/monzo/cents distances."""
    try:
        basis = ExponentBasis(tuple(request.generators))
        vectors = [tuple(vector) for vector in request.vectors]
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                distances.append(
                    {
                        "i": i,
                        "j": j,
                        "lattice_l1": lattice_distance(vectors[i], vectors[j], 1),
                        "lattice_l2": lattice_distance(vectors[i], vectors[j], 2),
                        "monzo": monzo_distance(basis, vectors[i], vectors[j]),
                        "cents": cents_distance(basis, vectors[i], vectors[j]),
                    }
                )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"basis": _lattice_basis_payload(basis), "distances": distances}


@app.get("/api/arrange/profiles")
def arrange_profiles() -> dict[str, object]:
    """List the built-in genre profiles."""
    return {"profiles": profile_summaries()}


@app.post("/api/arrange/generate")
def arrange_generate(request: ArrangeGenerateRequest) -> dict[str, object]:
    """Compile scale + chord vocabulary + genre profile into an arrangement."""
    try:
        return generate_arrangement(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/arrange/midi")
def arrange_midi(request: ArrangeProjectRequest) -> Response:
    """Export a generated ArrangementProject as SMF type 1 (microtonal)."""
    try:
        data = project_midi_bytes(request.arrangement)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(
        content=data,
        media_type="audio/midi",
        headers={"Content-Disposition": "attachment; filename=arrangement.mid"},
    )


@app.post("/api/arrange/render")
def arrange_render(request: ArrangeProjectRequest) -> Response:
    """Render a generated ArrangementProject to a preview WAV mixdown."""
    try:
        data = project_render_wav(request.arrangement)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(
        content=data,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=arrangement.wav"},
    )


@app.post("/api/arrange/phase-shift")
def arrange_phase_shift(request: HarmonicPhaseShiftRequest) -> dict[str, object]:
    """Compile dual-rhythm harmonic phase streams from an arrangement project."""
    try:
        return generate_phase_shift(request)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/arrange/migrate")
def arrange_migrate(request: ArrangeMigrationRequest) -> dict[str, object]:
    """Migrate a canonical arrangement project to the current schema."""
    try:
        return migrate_arrangement_project(request.arrangement)
    except (ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
