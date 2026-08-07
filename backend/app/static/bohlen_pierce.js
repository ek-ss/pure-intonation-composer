const bp = id => document.getElementById(id);
const bpState = { scale: null, chords: [], selectedChord: null, selectedPitch: null, chordPitchIds: new Set(), progression: null, project: null, view: "circle", nodes: [], audio: null, scheduled: [], history: [], future: [] };
const BP_COLORS = { harmony: "#98e7ca", bass: "#ffd47e", melody: "#86b9ff", drone: "#b1a3ce", kick: "#ff9daf", snare: "#e3a8ff", hat: "#c3d36b" };

function bpStatus(message, kind = "") { bp("bp-status").textContent = message; bp("bp-status").className = `experiment-status ${kind}`; }
async function bpPost(url, payload) { const response = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }); const type = response.headers.get("content-type") || ""; if (!response.ok) { const data = type.includes("json") ? await response.json() : {}; throw new Error(typeof data.detail === "string" ? data.detail : "Request failed"); } return type.includes("json") ? response.json() : response.blob(); }
function bpDownload(data, filename, type = "application/json") { const blob = data instanceof Blob ? data : new Blob([typeof data === "string" ? data : JSON.stringify(data, null, 2)], { type }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(link.href), 1200); }
function bpFraction(text) { const [numerator, denominator] = String(text).split("/").map(Number); return numerator / denominator; }
function bpTritaveNormalize(value) { while (value < 1) value *= 3; while (value >= 3) value /= 3; return value; }
function bpTritavePosition(ratio) { return Math.log(bpTritaveNormalize(bpFraction(ratio))) / Math.log(3); }
function bpRatios() { return bpState.scale?.pitches.map(pitch => pitch.ratio) || []; }
function bpSnapshot() { if (bpState.scale) { bpState.history.push(structuredClone(bpState.scale)); bpState.history = bpState.history.slice(-40); bpState.future = []; } }

function bpScaleRequest(overrides = {}) {
  return {
    preset: bp("bp-preset").value,
    prime_limit: Number(bp("bp-prime-limit").value),
    b_min: Number(bp("bp-b-min").value), b_max: Number(bp("bp-b-max").value),
    c_min: Number(bp("bp-c-min").value), c_max: Number(bp("bp-c-max").value),
    max_tenney_height: Number(bp("bp-tenney").value), max_pitches: Number(bp("bp-max-pitches").value),
    root_frequency_hz: Number(bp("bp-root-frequency").value),
    ratios: bp("bp-manual-ratios").value.split(",").map(value => value.trim()).filter(Boolean),
    ...overrides,
  };
}
async function bpGenerateScale(overrides = {}) {
  try {
    bpStatus("Generating scale...", "loading");
    const scale = await bpPost("/api/bp/scales/generate", bpScaleRequest(overrides));
    if (bpState.scale) bpSnapshot();
    bpState.scale = scale; bpState.chords = []; bpState.selectedChord = null; bpState.progression = null; bpState.project = null;
    bpState.selectedPitch = scale.pitches[0] || null; bpState.chordPitchIds.clear();
    bp("bp-manual-ratios").value = scale.pitches.map(pitch => pitch.ratio).join(", ");
    bpRenderAll(); bpStatus(`${scale.name}: ${scale.pitches.length} pitches`);
  } catch (error) { bpStatus(error.message, "error"); }
}
function bpRenderAll() { bpRenderPitchList(); bpRenderPitchView(); bpRenderChordList(); bpRenderProgression(); bpRenderComposition(); }
function bpRenderPitchList() {
  const scale = bpState.scale;
  bp("bp-scale-summary").textContent = scale ? `${scale.pitches.length} tones · ${scale.temperament}` : "";
  bp("bp-pitch-list").innerHTML = scale ? scale.pitches.map(pitch => `<button class="experiment-row${bpState.selectedPitch?.id === pitch.id ? " active" : ""}" data-pitch="${pitch.id}"><span><strong>${pitch.ratio}</strong><small>${Number(pitch.cents_from_root).toFixed(2)}c · (b=${pitch.b}, c=${pitch.c})</small></span><small>${Number(pitch.edt13_error_cents) >= 0 ? "+" : ""}${Number(pitch.edt13_error_cents).toFixed(1)}c EDT</small></button>`).join("") : "";
  bp("bp-pitch-list").querySelectorAll("button").forEach(node => { node.onclick = event => bpSelectPitch(node.dataset.pitch, event.shiftKey); });
}
function bpSelectPitch(id, addToChord = false) {
  const pitch = bpState.scale?.pitches.find(item => item.id === id); if (!pitch) return;
  bpState.selectedPitch = pitch;
  if (addToChord) { bpState.selectedChord = null; if (bpState.chordPitchIds.has(id)) bpState.chordPitchIds.delete(id); else bpState.chordPitchIds.add(id); }
  bpPlayRatios([pitch.ratio], .7); bpRenderPitchList(); bpRenderPitchView(); bpRenderAdHocChord();
}
function bpRenderAdHocChord() {
  if (bpState.selectedChord) return bpRenderSelectedChord();
  const pitches = bpState.scale?.pitches.filter(pitch => bpState.chordPitchIds.has(pitch.id)) || [];
  bp("bp-selected-chord").innerHTML = pitches.map(pitch => `<span>${pitch.ratio}<br>(b=${pitch.b}, c=${pitch.c})</span>`).join("");
}
function bpCanvas() { const canvas = bp("bp-pitch-canvas"), dpr = window.devicePixelRatio || 1, width = Math.max(420, canvas.clientWidth || 760), height = parseFloat(getComputedStyle(canvas).height) || 430; canvas.width = width * dpr; canvas.height = height * dpr; const context = canvas.getContext("2d"); context.scale(dpr, dpr); context.clearRect(0, 0, width, height); return { canvas, context, width, height }; }
function bpRenderPitchView() { if (!bpState.scale) return; if (bpState.view === "circle") bpRenderCircle(); else bpRenderLattice(); }
function bpRenderCircle() {
  const { context, width, height } = bpCanvas(), cx = width / 2, cy = height / 2, radius = Math.min(width, height) * .34;
  context.strokeStyle = "#30394d"; context.lineWidth = 1;
  const rings = bp("bp-show-registers").checked ? [.72, 1, 1.18] : [1];
  rings.forEach((factor, index) => { context.setLineDash(index === 1 ? [] : [4, 5]); context.beginPath(); context.arc(cx, cy, radius * factor, 0, Math.PI * 2); context.stroke(); }); context.setLineDash([]);
  if (bp("bp-show-edt").checked) for (let step = 0; step < 13; step++) { const angle = -Math.PI / 2 + step / 13 * Math.PI * 2, inner = radius * 1.24, outer = radius * 1.29; context.strokeStyle = "#556175"; context.beginPath(); context.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner); context.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer); context.stroke(); context.fillStyle = "#77839a"; context.font = "10px system-ui"; context.textAlign = "center"; context.fillText(String(step), cx + Math.cos(angle) * radius * 1.36, cy + Math.sin(angle) * radius * 1.36 + 3); }
  const nodes = bpState.scale.pitches.map(pitch => { const angle = -Math.PI / 2 + Number(pitch.tritave_position) * Math.PI * 2; return { pitch, x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, angle }; });
  if (bp("bp-show-edges").checked) { context.strokeStyle = "#98e7ca55"; nodes.forEach((left, index) => nodes.slice(index + 1).forEach(right => { const delta = bpTritaveNormalize(bpFraction(right.pitch.ratio) / bpFraction(left.pitch.ratio)); if ([5 / 3, 7 / 3, 9 / 5, 7 / 5, 9 / 7].some(target => Math.abs(delta - target) < .00001)) { context.beginPath(); context.moveTo(left.x, left.y); context.lineTo(right.x, right.y); context.stroke(); } })); }
  bpState.nodes = nodes;
  nodes.forEach(({ pitch, x, y }) => { const selected = bpState.selectedPitch?.id === pitch.id, chord = bpState.chordPitchIds.has(pitch.id) || bpState.selectedChord?.pitch_ids.includes(pitch.id); context.fillStyle = selected ? "#ffd47e" : chord ? "#e3a8ff" : "#98e7ca"; context.beginPath(); context.arc(x, y, selected ? 9 : chord ? 8 : 6, 0, Math.PI * 2); context.fill(); context.strokeStyle = Number(pitch.prime_exponents["7"] || 0) ? "#ff9daf" : "#edf1fb"; context.stroke(); context.fillStyle = "#edf1fb"; context.font = selected ? "700 12px system-ui" : "10px system-ui"; context.textAlign = "center"; context.fillText(pitch.ratio, x, y - 13); });
  context.fillStyle = "#edf1fb"; context.font = "700 13px system-ui"; context.textAlign = "center"; context.fillText("1/1 · 3/1 equave", cx, cy); context.fillStyle = "#8c98ad"; context.font = "11px system-ui"; context.fillText(`${(1200 * Math.log2(3)).toFixed(3)} cents`, cx, cy + 18);
}
function bpRenderLattice() {
  const { context, width, height } = bpCanvas(), pitches = bpState.scale.pitches, bValues = pitches.map(pitch => pitch.b), cValues = pitches.map(pitch => pitch.c), bMin = Math.min(...bValues), bMax = Math.max(...bValues), cMin = Math.min(...cValues), cMax = Math.max(...cValues), pad = 58;
  const x = value => pad + (value - bMin) / Math.max(1, bMax - bMin) * (width - pad * 2), y = value => height - pad - (value - cMin) / Math.max(1, cMax - cMin) * (height - pad * 2);
  context.strokeStyle = "#30394d"; context.fillStyle = "#8c98ad"; context.font = "11px system-ui";
  for (let value = bMin; value <= bMax; value++) { context.beginPath(); context.moveTo(x(value), pad); context.lineTo(x(value), height - pad); context.stroke(); context.fillText(`5^${value}`, x(value) - 10, height - 25); }
  for (let value = cMin; value <= cMax; value++) { context.beginPath(); context.moveTo(pad, y(value)); context.lineTo(width - pad, y(value)); context.stroke(); context.fillText(`7^${value}`, 12, y(value) + 4); }
  bpState.nodes = pitches.map(pitch => ({ pitch, x: x(pitch.b), y: y(pitch.c) }));
  bpState.nodes.forEach(({ pitch, x: px, y: py }) => { const selected = pitch.id === bpState.selectedPitch?.id, chord = bpState.chordPitchIds.has(pitch.id) || bpState.selectedChord?.pitch_ids.includes(pitch.id); context.fillStyle = selected ? "#ffd47e" : chord ? "#e3a8ff" : "#98e7ca"; context.beginPath(); context.arc(px, py, selected ? 10 : 7, 0, Math.PI * 2); context.fill(); context.fillStyle = "#edf1fb"; context.textAlign = "center"; context.fillText(pitch.ratio, px, py - 13); });
}

async function bpSearchChords() {
  if (!bpState.scale) return;
  try { bpStatus("Searching BP chords...", "loading"); const result = await bpPost("/api/bp/chords/search", { pitches: bpState.scale.pitches, voice_count: Number(bp("bp-voices").value), required_pitch_ids: [...bpState.chordPitchIds], max_results: Number(bp("bp-chord-results").value), max_tenney_height: Number(bp("bp-chord-height").value), max_prime_distance: Number(bp("bp-prime-distance").value), max_tritave_width: Number(bp("bp-chord-width").value), min_odd_harmonic_overlap: Number(bp("bp-min-overlap").value), root_fixed: bp("bp-root-fixed").checked, allow_duplicates: bp("bp-duplicates").checked, weights: { harmonicity: Number(bp("bp-weight-harmonicity").value), odd_overlap: Number(bp("bp-weight-overlap").value), root_clarity: Number(bp("bp-weight-root").value), compactness: Number(bp("bp-weight-compactness").value), roughness: Number(bp("bp-weight-roughness").value), complexity: Number(bp("bp-weight-complexity").value) } }); bpState.chords = result.chords; bpState.selectedChord = result.chords[0] || null; bpState.chordPitchIds = new Set(bpState.selectedChord?.pitch_ids || []); bpRenderChordList(); bpRenderSelectedChord(); bpRenderPitchView(); bpStatus(`${result.chords.length} ranked chords · ${result.pareto_front.length} Pareto candidates`); } catch (error) { bpStatus(error.message, "error"); }
}
function bpRenderChordList() { bp("bp-chord-summary").textContent = `${bpState.chords.length} ranked candidates`; bp("bp-chord-list").innerHTML = bpState.chords.map((chord, index) => `<button class="experiment-row${chord.id === bpState.selectedChord?.id ? " active" : ""}" data-chord="${chord.id}"><span><strong>${index + 1}. ${chord.ratios.join(" · ")}</strong><small>${chord.normalized_integer_form.join(":")} · ${chord.tags.join(" / ")}</small></span><small>${Number(chord.metrics.total_score).toFixed(3)}</small></button>`).join(""); bp("bp-chord-list").querySelectorAll("button").forEach(node => { node.onclick = () => { bpState.selectedChord = bpState.chords.find(chord => chord.id === node.dataset.chord); bpState.chordPitchIds = new Set(bpState.selectedChord.pitch_ids); bpRenderChordList(); bpRenderSelectedChord(); bpRenderPitchView(); bpPlayRatios(bpState.selectedChord.ratios, 1); }; }); }
function bpRenderSelectedChord() { const chord = bpState.selectedChord; if (!chord) return bpRenderAdHocChord(); const labels = { total_score: "Score", harmonicity: "Harmonicity", odd_harmonic_overlap: "Odd overlap", root_clarity: "Root clarity", roughness_estimate: "Roughness", tenney_height: "Tenney height", tritave_compactness: "Compactness" }; bp("bp-selected-chord").innerHTML = Object.entries(labels).map(([key, label]) => `<span>${label}<br><strong>${Number(chord.metrics[key]).toFixed(3)}</strong></span>`).join(""); }

function bpTensionCurve() { return bp("bp-tension").value.split(",").map(Number).filter(value => Number.isFinite(value)); }
async function bpGenerateProgression() {
  if (!bpState.chords.length) await bpSearchChords(); if (!bpState.chords.length) return;
  try { bpStatus("Searching progression graph...", "loading"); const selected = bpState.selectedChord || bpState.chords[0]; bpState.progression = await bpPost("/api/bp/progressions/search", { chords: bpState.chords, length: Number(bp("bp-progression-length").value), center_chord_id: selected.id, end_chord_id: bp("bp-progression-method").value === "random-walk" ? null : selected.id, target_tension_curve: bpTensionCurve(), method: bp("bp-progression-method").value, beam_width: 32, seed: Number(bp("bp-seed").value) }); bpRenderProgression(); bpStatus(`Progression generated · cost ${bpState.progression.total_cost}`); } catch (error) { bpStatus(error.message, "error"); }
}
function bpRenderProgression() { const progression = bpState.progression?.progression || []; bp("bp-progression-summary").textContent = progression.length ? `${progression.length} chords · closure ${bpState.progression.loop_closure}` : "No progression"; bp("bp-progression-lane").innerHTML = progression.map(item => `<button data-step="${item.step}"><strong>${item.functional_role}</strong><small>${item.ratios.join(" · ")}</small><small>Tension ${Number(item.actual_tension).toFixed(2)} · VL ${Number(item.voice_leading).toFixed(2)}</small></button>`).join(""); bp("bp-progression-lane").querySelectorAll("button").forEach(node => { node.onclick = () => { const item = progression[Number(node.dataset.step)]; bpPlayRatios(item.ratios, 1); }; }); bpRenderTension(); }
function bpRenderTension() { const canvas = bp("bp-tension-canvas"), dpr = window.devicePixelRatio || 1, width = Math.max(520, canvas.clientWidth || 900), height = 190; canvas.width = width * dpr; canvas.height = height * dpr; const context = canvas.getContext("2d"); context.scale(dpr, dpr); context.clearRect(0, 0, width, height); context.strokeStyle = "#30394d"; [0, .25, .5, .75, 1].forEach(value => { const y = 18 + (1 - value) * 140; context.beginPath(); context.moveTo(42, y); context.lineTo(width - 14, y); context.stroke(); }); const progression = bpState.progression?.progression || []; const curves = [{ values: bpState.progression?.target_tension_curve || bpTensionCurve(), color: "#ffd47e", label: "Target" }, { values: progression.map(item => item.actual_tension), color: "#98e7ca", label: "Actual" }]; curves.forEach(curve => { if (!curve.values.length) return; context.strokeStyle = curve.color; context.lineWidth = 3; context.beginPath(); curve.values.forEach((value, index) => { const x = 42 + index / Math.max(1, curve.values.length - 1) * (width - 60), y = 18 + (1 - Number(value)) * 140; if (index) context.lineTo(x, y); else context.moveTo(x, y); }); context.stroke(); }); context.fillStyle = "#ffd47e"; context.fillText("Target", 44, 178); context.fillStyle = "#98e7ca"; context.fillText("Actual", 100, 178); }

async function bpGenerateComposition() {
  if (!bpState.scale) await bpGenerateScale(); if (!bpState.progression) await bpGenerateProgression();
  try { bpStatus("Generating BP composition...", "loading"); bpState.project = await bpPost("/api/bp/compose/generate", { scale: bpState.scale.pitches, chords: bpState.chords, progression: bpState.progression?.progression || [], duration_bars: Number(bp("bp-bars").value), tempo_bpm: Number(bp("bp-tempo").value), form: bp("bp-form").value, chord_density: Number(bp("bp-chord-density").value), melodic_density: Number(bp("bp-melody-density").value), rhythmic_density: Number(bp("bp-rhythm-density").value), include_drone: bp("bp-drone").checked, timbre: bp("bp-timbre").value, root_frequency_hz: Number(bp("bp-root-frequency").value) / 2, seed: Number(bp("bp-seed").value) }); localStorage.setItem("pure-intonation.bp-project", JSON.stringify(bpState.project)); bpRenderComposition(); bpStatus(`${bpState.project.events.length} BP score events generated`); } catch (error) { bpStatus(error.message, "error"); }
}
function bpRenderComposition() { const project = bpState.project, canvas = bp("bp-arrangement-canvas"), dpr = window.devicePixelRatio || 1, width = Math.max(600, canvas.clientWidth || 1000), height = 220; canvas.width = width * dpr; canvas.height = height * dpr; const context = canvas.getContext("2d"); context.scale(dpr, dpr); context.clearRect(0, 0, width, height); if (!project) return; const total = project.metadata.duration_bars * project.metadata.beats_per_bar, roles = ["harmony", "bass", "melody", "drone", "kick", "snare", "hat"], lane = 24; roles.forEach((role, index) => { const y = 24 + index * lane; context.fillStyle = "#8c98ad"; context.font = "10px system-ui"; context.fillText(role, 6, y + 6); context.strokeStyle = "#273044"; context.beginPath(); context.moveTo(62, y + 8); context.lineTo(width - 8, y + 8); context.stroke(); project.events.filter(event => event.part_role === role).forEach(event => { const x = 62 + event.start_beat / total * (width - 72), w = Math.max(2, event.duration_beats / total * (width - 72)); context.fillStyle = BP_COLORS[role]; context.fillRect(x, y, w, 10); }); }); bp("bp-compose-summary").textContent = `${project.metadata.duration_bars} bars · ${project.events.length} events · ${project.metadata.timbre}`; bp("bp-composition-metrics").innerHTML = Object.entries(project.metrics).map(([key, value]) => `<span>${key.replaceAll("_", " ")}<br><strong>${Number(value).toFixed(3)}</strong></span>`).join(""); }

function bpAudioContext() { const Audio = window.AudioContext || window.webkitAudioContext; bpState.audio ||= new Audio(); return bpState.audio; }
function bpStop() { bpState.scheduled.forEach(node => { try { node.stop(); } catch (_) {} }); bpState.scheduled = []; bpStatus("Stopped"); }
function bpTunedRatio(ratio) { const value = bpFraction(ratio), mode = bp("bp-audition-tuning").value; if (mode === "pure") return value; if (mode === "13-edt") return 3 ** (Math.round(bpTritavePosition(ratio) * 13) / 13); return 2 ** (Math.round(12 * Math.log2(value)) / 12); }
function bpScheduleRatio(ratio, at, duration, velocity = 88, timbre = null, rootFrequency = null) { const context = bpAudioContext(), destination = context.destination, fundamental = (rootFrequency ?? Number(bp("bp-root-frequency").value)) * bpTunedRatio(ratio), kind = timbre || bp("bp-timbre").value, harmonics = kind === "odd-harmonic" ? [1, 3, 5, 7, 9] : kind === "full-harmonic" ? [1, 2, 3, 4, 5] : [1]; harmonics.forEach(harmonic => { const oscillator = context.createOscillator(), gain = context.createGain(); oscillator.type = kind === "soft-square" ? "square" : kind === "hollow-pluck" ? "triangle" : "sine"; oscillator.frequency.value = Math.min(18000, fundamental * harmonic); const level = velocity / 127 * .12 / harmonic; gain.gain.setValueAtTime(.0001, at); gain.gain.exponentialRampToValueAtTime(Math.max(.0002, level), at + .012); gain.gain.exponentialRampToValueAtTime(.0001, at + duration); oscillator.connect(gain).connect(destination); oscillator.start(at); oscillator.stop(at + duration + .03); bpState.scheduled.push(oscillator); }); }
function bpScheduleDrum(note, at, velocity) { const context = bpAudioContext(), oscillator = context.createOscillator(), gain = context.createGain(), duration = note === 36 ? .25 : .13; oscillator.type = note === 36 ? "sine" : "triangle"; oscillator.frequency.setValueAtTime(note === 36 ? 75 : 185, at); oscillator.frequency.exponentialRampToValueAtTime(note === 36 ? 42 : 110, at + duration); gain.gain.setValueAtTime(velocity / 127 * .18, at); gain.gain.exponentialRampToValueAtTime(.0001, at + duration); oscillator.connect(gain).connect(context.destination); oscillator.start(at); oscillator.stop(at + duration); bpState.scheduled.push(oscillator); }
async function bpPlayRatios(ratios, duration = 1) { const context = bpAudioContext(); if (context.state === "suspended") await context.resume(); bpStop(); const now = context.currentTime + .04; ratios.forEach((ratio, index) => bpScheduleRatio(ratio, now + index * .012, duration, 88)); bpStatus(`Playing ${ratios.join(" · ")}`, "loading"); }
async function bpPlayProgression() { if (!bpState.progression) return; const context = bpAudioContext(); if (context.state === "suspended") await context.resume(); bpStop(); const now = context.currentTime + .05, beat = 60 / Number(bp("bp-tempo").value); bpState.progression.progression.forEach((item, index) => item.ratios.forEach((ratio, voice) => bpScheduleRatio(ratio, now + index * beat * 2 + voice * .012, beat * 1.7, 82 - voice * 4))); bpStatus("Playing BP progression", "loading"); }
async function bpPlayProject() { if (!bpState.project) return; const context = bpAudioContext(); if (context.state === "suspended") await context.resume(); bpStop(); const now = context.currentTime + .05, beat = 60 / bpState.project.metadata.tempo_bpm, root = bpState.project.metadata.root_frequency_hz; bpState.project.events.forEach(event => { if (event.ratio) bpScheduleRatio(event.ratio, now + event.start_beat * beat, Math.min(2.8, event.duration_beats * beat), event.velocity, null, root); else if (event.note) bpScheduleDrum(event.note, now + event.start_beat * beat, event.velocity); }); bpStatus("Playing BP composition", "loading"); }

function bpExportPayload() { if (!bpState.project) throw new Error("Generate a composition first."); return { events: bpState.project.events, tempo_bpm: bpState.project.metadata.tempo_bpm, beats_per_bar: bpState.project.metadata.beats_per_bar, root_frequency_hz: bpState.project.metadata.root_frequency_hz, sections: bpState.project.sections }; }
async function bpExportBlob(url, filename, payload) { try { bpStatus(`Preparing ${filename}...`, "loading"); const blob = await bpPost(url, payload); bpDownload(blob, filename); bpStatus(`${filename} exported`); } catch (error) { bpStatus(error.message, "error"); } }
async function bpExportScala() { if (!bpState.scale) return; await bpExportBlob("/api/bp/export/scala", "bohlen-pierce.scl", { name: bpState.scale.name, pitches: bpState.scale.pitches }); }
function bpImportProject(project) { if (!project || project.equave !== 3 || !Array.isArray(project.events)) throw new Error("This is not a Bohlen-Pierce project."); bpState.project = project; if (Array.isArray(project.scale)) bpState.scale = { id: "imported", name: "Imported BP scale", equave: 3, temperament: "pure-ratio", root_frequency_hz: project.metadata.root_frequency_hz, pitches: project.scale }; if (Array.isArray(project.progression)) bpState.progression = { progression: project.progression, target_tension_curve: project.progression.map(item => item.target_tension || 0), loop_closure: project.metrics?.loop_closure || 0 }; bpRenderAll(); bpStatus("BP project imported"); }

bp("bp-scale-generate").onclick = () => void bpGenerateScale();
bp("bp-ratio-add").onclick = () => { const ratios = [...bpRatios(), bp("bp-ratio-input").value.trim()]; bp("bp-preset").value = "manual"; bp("bp-manual-ratios").value = ratios.join(", "); void bpGenerateScale({ preset: "manual", ratios }); };
function bpGcd(a, b) { while (b) [a, b] = [b, a % b]; return Math.abs(a); }
function bpMultiplySelected(numerator, denominator) {
  if (!bpState.selectedPitch) return;
  const [n, d] = bpState.selectedPitch.ratio.split("/").map(Number);
  const common = bpGcd(n * numerator, d * denominator);
  bp("bp-ratio-input").value = `${n * numerator / common}/${d * denominator / common}`;
  bp("bp-ratio-add").click();
}
bp("bp-multiply-5").onclick = () => bpMultiplySelected(5, 3);
bp("bp-multiply-7").onclick = () => bpMultiplySelected(7, 3);
bp("bp-multiply-9-7").onclick = () => bpMultiplySelected(9, 7);
bp("bp-undo").onclick = () => { if (!bpState.history.length || !bpState.scale) return; bpState.future.push(structuredClone(bpState.scale)); bpState.scale = bpState.history.pop(); bpRenderAll(); };
bp("bp-redo").onclick = () => { if (!bpState.future.length || !bpState.scale) return; bpState.history.push(structuredClone(bpState.scale)); bpState.scale = bpState.future.pop(); bpRenderAll(); };
bp("bp-view-tabs").querySelectorAll("button").forEach(node => { node.onclick = () => { bp("bp-view-tabs").querySelectorAll("button").forEach(button => button.classList.toggle("active", button === node)); bpState.view = node.dataset.view; bpRenderPitchView(); }; });
["bp-show-edt", "bp-show-edges", "bp-show-registers"].forEach(id => { bp(id).onchange = bpRenderPitchView; });
bp("bp-pitch-canvas").onclick = event => { const rect = event.currentTarget.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top, nearest = bpState.nodes.reduce((best, node) => Math.hypot(node.x - x, node.y - y) < Math.hypot(best.x - x, best.y - y) ? node : best, bpState.nodes[0]); if (nearest && Math.hypot(nearest.x - x, nearest.y - y) < 22) bpSelectPitch(nearest.pitch.id, event.shiftKey); };
bp("bp-chord-search").onclick = () => void bpSearchChords(); bp("bp-chord-play").onclick = () => bpState.selectedChord && void bpPlayRatios(bpState.selectedChord.ratios, 1.2); bp("bp-chord-clear").onclick = () => { bpState.selectedChord = null; bpState.chordPitchIds.clear(); bpRenderSelectedChord(); bpRenderPitchView(); };
bp("bp-progression-generate").onclick = () => void bpGenerateProgression(); bp("bp-progression-play").onclick = () => void bpPlayProgression(); bp("bp-stop").onclick = bpStop;
bp("bp-compose-generate").onclick = () => void bpGenerateComposition(); bp("bp-compose-play").onclick = () => void bpPlayProject();
bp("bp-midi").onclick = () => { try { void bpExportBlob("/api/bp/export/midi", "bohlen-pierce-mpe.mid", bpExportPayload()); } catch (error) { bpStatus(error.message, "error"); } }; bp("bp-wav").onclick = () => { try { void bpExportBlob("/api/bp/render/audio", "bohlen-pierce.wav", { ...bpExportPayload(), timbre: bp("bp-timbre").value }); } catch (error) { bpStatus(error.message, "error"); } }; bp("bp-scala").onclick = () => void bpExportScala(); bp("bp-json").onclick = () => bpState.project && bpDownload(bpState.project, "bohlen-pierce-project.json"); bp("bp-import").onclick = () => bp("bp-import-file").click(); bp("bp-import-file").onchange = async event => { try { bpImportProject(JSON.parse(await event.target.files[0].text())); } catch (error) { bpStatus(error.message, "error"); } };
window.addEventListener("resize", () => { bpRenderPitchView(); bpRenderTension(); bpRenderComposition(); });
void bpGenerateScale();
