const fp = id => document.getElementById(id);
const fpState = { project: null, context: null, voices: [], timer: null, activeChord: [] };
const FP_SCALES = {
  bright: ["1/1", "9/8", "5/4", "4/3", "3/2", "5/3", "15/8"],
  minor: ["1/1", "9/8", "6/5", "4/3", "3/2", "8/5", "9/5"],
  color: ["1/1", "8/7", "6/5", "5/4", "4/3", "3/2", "12/7", "7/4"],
};
const FP_VITAL_ROLES = {
  bass: ["PI05 Warm Bass", "root anchor"],
  harmony: ["PI02 Dream Chord", "fractional comping"],
  melody: ["PI04 Gentle Pluck", "hook melody"],
  texture: ["PI03 Air Pad", "background texture"],
};
const FP_VITAL_DRUMS = {
  36: { id: "pi09_kick", instrument: "PI09 Pop Kick", detail: "Vital synthesized kick", file: "PI 09 Pop Kick.vital" },
  38: { id: "pi10_snare", instrument: "PI10 Pop Snare", detail: "Vital noise-body snare", file: "PI 10 Pop Snare.vital" },
  42: { id: "pi11_hat", instrument: "PI11 Pop Closed Hat", detail: "Vital noise hat", file: "PI 11 Pop Closed Hat.vital" },
  39: { id: "pi12_perc", instrument: "PI12 Pop Perc", detail: "Vital tonal percussion", file: "PI 12 Pop Perc.vital" },
};
const FP_VITAL_DRUM_ORDER = [36, 38, 42, 39];
const FP_COLORS = { intro: "#83b7ff", verse: "#98e7ca", pre_chorus: "#ffd47e", chorus: "#ff9d9a", bridge: "#e3a8ff", outro: "#7ee0d3" };

function fpStatus(message, kind = "") { fp("fractional-pop-status").textContent = message; fp("fractional-pop-status").className = kind; }
function fpRatioValue(value) { const match = String(value).trim().match(/^(\d+)\s*\/\s*(\d+)$/); if (!match || Number(match[2]) === 0) throw new Error(`Invalid ratio: ${value}`); return Number(match[1]) / Number(match[2]); }
function fpOctaveValue(value) { let result = fpRatioValue(value); while (result < 1) result *= 2; while (result >= 2) result /= 2; return result; }
function fpRatios() { const values = fp("fractional-pop-scale").value.split(",").map(value => value.trim()).filter(Boolean); if (values.length < 5) throw new Error("Pop scale requires at least five ratios."); values.forEach(fpRatioValue); return values; }
function fpRoots(length, color) { const source = color === "bittersweet" ? [0, 1, 3, 5] : color === "open" ? [0, 3, 4] : [0, 3, 4, 5]; return [...new Set(source.filter(value => value < length))]; }
function fpChordVocabulary(length) {
  const color = fp("fractional-pop-color").value, labels = ["I", "ii", "iii", "IV", "V", "vi", "vii", "VIII"];
  return fpRoots(length, color).map(root => {
    let tones = [0, 2, 4], tags = ["stable"];
    if (color === "open") { tones = [0, 3, 4]; tags = ["open", "suspended", "color"]; }
    else if (length >= 7 && color === "bittersweet" && (root === 1 || root === 5)) { tones = [0, 2, 4, 6]; tags = ["stable", "dense", "color"]; }
    else if (root === 4) tags = ["stable", "cadential"];
    return { id: `pop_degree_${root}`, name: `${labels[root] || `degree ${root + 1}`} ${tones.length === 4 ? "seventh" : color === "open" ? "suspended" : "triad"}`, mode: "degree_template", tones, root_degree: root, tags };
  });
}
function fpControls() { return { energy: Number(fp("fractional-pop-energy").value), density: Number(fp("fractional-pop-density").value), syncopation: Number(fp("fractional-pop-sync").value), harmonic_complexity: Number(fp("fractional-pop-complexity").value), repetition: Number(fp("fractional-pop-repetition").value), root_variety: Number(fp("fractional-pop-root-variety").value), section_contrast: Number(fp("fractional-pop-contrast").value), humanization: 0.08, melody_enabled: fp("fractional-pop-melody").checked, drums_enabled: fp("fractional-pop-drums").checked }; }
function fpPerformance() { const mode = fp("fractional-pop-performance").value; if (mode === "auto") return null; return { mode, allowed_modes: [mode], mode_weights: { [mode]: 1 }, rate_subdivisions: Number(fp("fractional-pop-rate").value), gate: .84, velocity_curve: "phrase", arpeggio: { order: "up_down", octave_span: 2, rotate_per_chord: true }, stride: { low_note_source: "root", chord_tones: "shell", bass_conflict: "coordinate" } }; }
function fpRequest() { const ratios = fpRatios(); return { scale: { scale_id: "fractional-pop-user-scale", ratios, base_frequency: Number(fp("fractional-pop-base").value) }, chord_vocabulary: fpChordVocabulary(ratios.length), genre_profile: "pop", clock: { tempo_bpm: Number(fp("fractional-pop-tempo").value), beats_per_bar: 4, subdivisions_per_beat: 4, bars: Number(fp("fractional-pop-bars").value) }, controls: fpControls(), harmony_performance: fpPerformance(), seed: Number(fp("fractional-pop-seed").value) }; }
function fpMapVitalRoles(project) {
  const mapped = [];
  project.tracks.forEach(track => {
    if (track.role !== "drums") { mapped.push({ ...track, instrument: FP_VITAL_ROLES[track.role]?.[0] || track.instrument }); return; }
    const sourceMix = project.mix?.[track.id], sourceWaveform = project.render_settings?.waveforms?.[track.id] || track.waveform;
    if (project.mix) delete project.mix[track.id];
    if (project.render_settings?.waveforms) delete project.render_settings.waveforms[track.id];
    FP_VITAL_DRUM_ORDER.map(note => FP_VITAL_DRUMS[note]).forEach(profile => {
      mapped.push({ ...track, id: profile.id, instrument: profile.instrument, event_count: 0 });
      if (project.mix && sourceMix) project.mix[profile.id] = { ...sourceMix };
      if (project.render_settings?.waveforms) project.render_settings.waveforms[profile.id] = sourceWaveform;
    });
  });
  project.events = project.events.map(event => {
    if (event.kind !== "drum") return event;
    const profile = FP_VITAL_DRUMS[event.drum_note] || FP_VITAL_DRUMS[39];
    return { ...event, track_id: profile.id };
  });
  mapped.forEach(track => { track.event_count = project.events.filter(event => event.track_id === track.id).length; });
  project.tracks = mapped;
  return project;
}

async function fpGenerate() {
  try {
    fpStatus("Composing...", "loading");
    const response = await fetch("/api/arrange/generate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(fpRequest()) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Pop generation failed");
    fpState.project = fpMapVitalRoles(data); fpState.activeChord = data.harmony_progression[0]?.tones || [];
    fpRenderAll(); fpStatus("Ready");
  } catch (error) { fpStatus(error.message, "error"); }
}

function fpRenderAll() { fpRenderForm(); fpRenderCircle(); fpRenderProgression(); fpRenderParts(); const project = fpState.project; fp("fractional-pop-summary").textContent = `${project.clock.bars} bars · ${project.clock.tempo_bpm} BPM`; fp("fractional-pop-scale-summary").textContent = `${fpRatios().length} exact ratios · ${project.source_scale.base_frequency} Hz`; fp("fractional-pop-progression-summary").textContent = `${project.harmony_progression.length} chord slots`; fp("fractional-pop-metrics").innerHTML = [`<span>${fp("fractional-pop-color").selectedOptions[0].textContent}</span>`, `<span>${project.form.length} sections</span>`, `<span>${project.events.length} events</span>`, `<span>${project.harmony_gestures.length} harmony gestures</span>`].join(""); }
function fpRenderForm() {
  const canvas = fp("fractional-pop-form"), context = canvas.getContext("2d"), project = fpState.project;
  const width = Math.max(1, Math.round(canvas.getBoundingClientRect().width)), height = 210, ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, width, height);
  project.form.forEach(section => { const x = section.start_bar / project.clock.bars * width, w = section.bars / project.clock.bars * width, color = FP_COLORS[section.canonical_role] || "#a9b9ff"; context.fillStyle = `${color}cc`; context.fillRect(x, 20, Math.max(1, w - 2), 72); context.fillStyle = "#10131c"; context.font = "12px sans-serif"; context.fillText(section.role, x + 5, 45); context.strokeStyle = "#edf1fb"; context.beginPath(); context.moveTo(x + 2, 84 - section.energy_start * 42); context.lineTo(x + w - 3, 84 - section.energy_end * 42); context.stroke(); });
  const buckets = new Array(project.clock.bars * 4).fill(0); project.events.forEach(event => { const beat = event.start_tick / project.clock.ticks_per_beat; const index = Math.min(buckets.length - 1, Math.floor(beat)); buckets[index] += 1; }); const peak = Math.max(...buckets, 1); buckets.forEach((count, index) => { const h = count / peak * 70; context.fillStyle = "#98e7ca"; context.fillRect(index / buckets.length * width, height - h - 12, Math.max(1, width / buckets.length - 1), h); }); context.fillStyle = "#aeb9d0"; context.fillText("event density", 6, height - 2);
}
function fpSvg(name, attrs = {}) { const node = document.createElementNS("http://www.w3.org/2000/svg", name); Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value)); return node; }
function fpRenderCircle() {
  const node = fp("fractional-pop-circle"), ratios = fpRatios(), active = new Set(fpState.activeChord.map(fpOctaveValue)); node.innerHTML = ""; node.append(fpSvg("circle", { cx: 260, cy: 260, r: 205, class: "circle-ring" }));
  ratios.forEach(ratio => { const value = fpOctaveValue(ratio), cents = 1200 * Math.log2(value), angle = cents / 1200 * Math.PI * 2 - Math.PI / 2, x = 260 + Math.cos(angle) * 205, y = 260 + Math.sin(angle) * 205, selected = [...active].some(item => Math.abs(1200 * Math.log2(item) - cents) < .01); node.append(fpSvg("line", { x1: 260, y1: 260, x2: x, y2: y, class: "fractional-pop-spoke" })); const group = fpSvg("g", { class: `fractional-pop-node${selected ? " active" : ""}` }); group.append(fpSvg("circle", { cx: x, cy: y, r: selected ? 24 : 20 })); const label = fpSvg("text", { x, y: y + 4, "text-anchor": "middle" }); label.textContent = ratio; group.append(label); node.append(group); });
  const title = fpSvg("text", { x: 260, y: 252, "text-anchor": "middle", class: "fractional-pop-circle-title" }); title.textContent = "Exact Ratio Scale"; const subtitle = fpSvg("text", { x: 260, y: 275, "text-anchor": "middle", class: "fractional-pop-circle-subtitle" }); subtitle.textContent = `${ratios.length} tones`; node.append(title, subtitle);
}
function fpRenderProgression() { const body = fp("fractional-pop-progression"); body.innerHTML = ""; const gestures = new Map(fpState.project.harmony_gestures.map(item => [item.chord_index, item.mode])); fpState.project.harmony_progression.forEach(slot => { const row = body.insertRow(); [slot.index + 1, slot.section_id, slot.name, gestures.get(slot.index) || "block", slot.root, slot.tones.join(" · ")].forEach(value => { const cell = row.insertCell(); cell.textContent = value; }); row.onclick = () => { fpState.activeChord = slot.tones; fpRenderCircle(); fpAuditionChord(slot.tones); }; }); }
function fpRenderParts() { const tracks = fpState.project.tracks; fp("fractional-pop-parts").innerHTML = tracks.map(track => { const drum = Object.values(FP_VITAL_DRUMS).find(profile => profile.id === track.id), detail = drum?.detail || FP_VITAL_ROLES[track.role]?.[1] || "texture", download = drum ? `<a class="vital-preset-link" href="/static/vital_presets/${encodeURIComponent(drum.file)}" download>Download .vital</a>` : ""; return `<article class="vital-track active"><strong>${track.instrument}</strong><span>${track.role}</span><small>${detail} · ${track.waveform}</small><b>${track.event_count} events</b>${download}</article>`; }).join(""); fp("fractional-pop-parts-summary").textContent = `${tracks.length} arranged roles`; }

function fpStop() { fpState.voices.forEach(voice => { try { voice.stop(); } catch {} }); fpState.voices = []; if (fpState.timer) clearTimeout(fpState.timer); fpState.timer = null; }
function fpContext() { return fpState.context || (fpState.context = new AudioContext()); }
function fpTone(frequency, start, duration, gain = .045, type = "triangle") { const context = fpContext(), oscillator = context.createOscillator(), envelope = context.createGain(); oscillator.type = type; oscillator.frequency.value = frequency; envelope.gain.setValueAtTime(.0001, start); envelope.gain.exponentialRampToValueAtTime(gain, start + .012); envelope.gain.setTargetAtTime(.0001, start + Math.min(duration * .72, 1.1), .08); oscillator.connect(envelope).connect(context.destination); oscillator.start(start); oscillator.stop(start + Math.min(duration, 2)); fpState.voices.push(oscillator); }
function fpDrum(note, start, velocity) { const frequency = note === 36 ? 90 : note === 38 ? 190 : 4200, type = note === 36 ? "sine" : "square"; fpTone(frequency, start, note === 36 ? .2 : .08, .08 * velocity / 127, type); }
async function fpPlay() { if (!fpState.project) return; fpStop(); const context = fpContext(); if (context.state === "suspended") await context.resume(); const project = fpState.project, now = context.currentTime + .08, secondsPerTick = 60 / project.clock.tempo_bpm / project.clock.ticks_per_beat; project.events.forEach(event => { const start = now + event.start_tick * secondsPerTick, duration = event.duration_ticks * secondsPerTick; if (event.kind === "drum") fpDrum(event.drum_note, start, event.velocity); else fpTone(project.source_scale.base_frequency * fpRatioValue(event.ratio), start, duration, Math.min(.06, .045 * event.velocity / 100), event.track_id.includes("bass") ? "sine" : "triangle"); }); const seconds = project.clock.total_ticks * secondsPerTick; fpStatus(`Playing ${seconds.toFixed(1)}s`, "loading"); fpState.timer = setTimeout(() => fpStatus("Ready"), seconds * 1000 + 250); }
async function fpAuditionChord(tones) { const context = fpContext(); if (context.state === "suspended") await context.resume(); const now = context.currentTime + .03, base = fpState.project.source_scale.base_frequency; tones.forEach((tone, index) => fpTone(base * fpRatioValue(tone), now + index * .025, 1.2, .04)); }
function fpDownload(blob, name) { const url = URL.createObjectURL(blob), anchor = document.createElement("a"); anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1200); }
async function fpExport(endpoint, name) { if (!fpState.project) return; try { fpStatus(`Exporting ${name}...`, "loading"); const response = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ arrangement: fpState.project }) }); if (!response.ok) throw new Error((await response.json()).detail || "Export failed"); fpDownload(await response.blob(), name); fpStatus(`${name} exported`); } catch (error) { fpStatus(error.message, "error"); } }

function fpSync() { ["energy", "density", "sync", "complexity", "repetition", "root-variety", "contrast"].forEach(name => { fp(`fractional-pop-${name}-value`).textContent = Number(fp(`fractional-pop-${name}`).value).toFixed(2); }); }
fp("fractional-pop-scale-preset").onchange = () => { const preset = fp("fractional-pop-scale-preset").value; if (FP_SCALES[preset]) fp("fractional-pop-scale").value = FP_SCALES[preset].join(", "); if (fpState.project) fpRenderCircle(); };
fp("fractional-pop-scale").oninput = () => { fp("fractional-pop-scale-preset").value = "custom"; };
["energy", "density", "sync", "complexity", "repetition", "root-variety", "contrast"].forEach(name => { fp(`fractional-pop-${name}`).oninput = fpSync; });
fp("fractional-pop-generate").onclick = () => void fpGenerate();
fp("fractional-pop-random").onclick = () => { fp("fractional-pop-seed").value = String(Math.floor(Math.random() * 1_000_000_000)); void fpGenerate(); };
fp("fractional-pop-play").onclick = () => void fpPlay(); fp("fractional-pop-stop").onclick = () => { fpStop(); fpStatus("Stopped"); };
fp("fractional-pop-midi").onclick = () => void fpExport("/api/arrange/midi", "fractional-pop.mid"); fp("fractional-pop-wav").onclick = () => void fpExport("/api/arrange/render", "fractional-pop.wav");
fp("fractional-pop-json").onclick = () => { if (!fpState.project) return; fpDownload(new Blob([JSON.stringify(fpState.project, null, 2)], { type: "application/json" }), "fractional-pop-project.json"); };
window.addEventListener("blur", fpStop); window.addEventListener("resize", () => { if (fpState.project) fpRenderForm(); }); fpSync(); void fpGenerate();
