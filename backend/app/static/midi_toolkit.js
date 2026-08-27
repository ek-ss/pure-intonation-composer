const mt = id => document.getElementById(id);
const mtState = {
  midiAccess: null, input: null, recording: false, recordStartMs: 0,
  recordTimer: null, clockTimer: null, raw: [], active: new Map(), sustained: new Set(),
  sustainDown: false, project: null, audio: null, voices: [], syntheticHeld: new Set(),
  scaleCatalog: [], scale: { id: "custom", name: "Custom scale", family: "Custom", equave_ratio: "2/1" },
};
const KEYBOARD_NOTES = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76];
const COMPUTER_KEYS = ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";"];
const WHITE_KEY_OFFSETS = new Map([[0, 0], [2, 1], [4, 2], [5, 3], [7, 4], [9, 5], [11, 6]]);
const WHITE_KEY_SEMITONES = [0, 2, 4, 5, 7, 9, 11];
const FUNDAMENTAL_COLOR = "#78d7ff";
const THIRD_HARMONIC_COLOR = "#f49ad1";

function mtStatus(text, kind = "") { mt("midi-toolkit-status").textContent = text; mt("midi-toolkit-status").className = kind; }
function mtOutput(text, kind = "") { mt("midi-toolkit-output-status").textContent = text; mt("midi-toolkit-output-status").className = kind; }
function noteName(note) { return `${["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][note % 12]}${Math.floor(note / 12) - 1}`; }
function beatMs() { return 60000 / Number(mt("midi-toolkit-tempo").value); }
function inputChannelAllowed(channel) { const selected = Number(mt("midi-toolkit-channel").value); return !selected || selected === channel; }
function audioContext() { return mtState.audio || (mtState.audio = new AudioContext()); }
function ratioNumber(text) { const [numerator, denominator] = String(text).split("/").map(Number); return numerator / denominator; }
function whiteKeyIndex(note) { const offset = WHITE_KEY_OFFSETS.get(note % 12); return offset == null ? null : Math.floor(note / 12) * 7 + offset; }
function midiForWhiteKeyIndex(index) { const octave = Math.floor(index / 7), degree = ((index % 7) + 7) % 7; return Math.max(0, Math.min(127, octave * 12 + WHITE_KEY_SEMITONES[degree])); }
function scaleTonePairs() { return scaleRatios().map(text => ({ text, value: ratioNumber(text) })).filter(tone => tone.value > 0).sort((left, right) => left.value - right.value); }
function tunedPitch(note) {
  const root = Number(mt("midi-toolkit-root").value), base = Number(mt("midi-toolkit-base").value), equave = ratioNumber(mt("midi-toolkit-equave").value || "2/1"), tones = scaleTonePairs(), keyIndex = whiteKeyIndex(note), rootIndex = whiteKeyIndex(root);
  if (keyIndex == null || rootIndex == null || !tones.length) return { ratio: 1, text: "Unavailable", period: 0, degree: 0, frequency: base };
  const degree = keyIndex - rootIndex, period = Math.floor(degree / tones.length), scaleIndex = ((degree % tones.length) + tones.length) % tones.length, tone = tones[scaleIndex], ratio = tone.value * equave ** period;
  return { ratio, text: tone.text, period, degree: scaleIndex + 1, frequency: base * ratio };
}

function soundingPitches() {
  const base = Number(mt("midi-toolkit-base").value), exact = mt("midi-toolkit-thru-tuning").value === "scale";
  return [...mtState.active.values()].map(active => {
    const mapped = tunedPitch(active.note), frequency = active.audio?.frequency || (exact ? mapped.frequency : 440 * 2 ** ((active.note - 69) / 12));
    return { note: active.note, velocity: active.velocity, frequency, ratio: frequency / base, label: active.audio?.ratioText || (exact ? mapped.text : noteName(active.note)) };
  });
}
function renderPitchCircle() {
  const svg = mt("midi-toolkit-pitch-circle"); if (!svg) return;
  const equave = Number(mt("midi-toolkit-circle-mode").querySelector("button.active")?.dataset.circleEquave || 2), periodCents = 1200 * Math.log2(equave), divisions = equave === 2 ? 12 : 13;
  const center = 180, fundamentalRadius = 126, harmonicRadius = 91, notes = soundingPitches();
  const circlePoint = (ratio, radius, offset = 0) => { const cents = ((1200 * Math.log2(ratio) % periodCents) + periodCents) % periodCents, angle = -Math.PI / 2 + cents / periodCents * Math.PI * 2, adjusted = radius - offset; return { cents, angle, x: center + Math.cos(angle) * adjusted, y: center + Math.sin(angle) * adjusted }; };
  const pairs = notes.map((note, index) => ({ note, fundamental: circlePoint(note.ratio, fundamentalRadius, (index % 3) * 3), third: circlePoint(note.ratio * 3, harmonicRadius, (index % 3) * 2) }));
  const ticks = Array.from({ length: divisions }, (_, index) => {
    const angle = -Math.PI / 2 + index / divisions * Math.PI * 2, inner = fundamentalRadius - 8, outer = fundamentalRadius + 1, labelRadius = fundamentalRadius + 18;
    const x1 = center + Math.cos(angle) * inner, y1 = center + Math.sin(angle) * inner, x2 = center + Math.cos(angle) * outer, y2 = center + Math.sin(angle) * outer, lx = center + Math.cos(angle) * labelRadius, ly = center + Math.sin(angle) * labelRadius;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#4a566d" stroke-width="1"/><text x="${lx}" y="${ly}" fill="#8290a8" font-size="8" text-anchor="middle" dominant-baseline="middle">${index}</text>`;
  }).join("");
  const fundamentalPolygon = pairs.length > 1 ? `<path d="${pairs.map((pair, index) => `${index ? "L" : "M"}${pair.fundamental.x},${pair.fundamental.y}`).join(" ")} Z" fill="rgba(120,215,255,.08)" stroke="${FUNDAMENTAL_COLOR}" stroke-opacity=".55" stroke-width="1.5"/>` : "";
  const harmonicPolygon = pairs.length > 1 ? `<path d="${pairs.map((pair, index) => `${index ? "L" : "M"}${pair.third.x},${pair.third.y}`).join(" ")} Z" fill="none" stroke="${THIRD_HARMONIC_COLOR}" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="4 4"/>` : "";
  const markers = pairs.map(pair => {
    const fundamentalLabelRadius = 105, flx = center + Math.cos(pair.fundamental.angle) * fundamentalLabelRadius, fly = center + Math.sin(pair.fundamental.angle) * fundamentalLabelRadius;
    const thirdLabelRadius = 70, tlx = center + Math.cos(pair.third.angle) * thirdLabelRadius, tly = center + Math.sin(pair.third.angle) * thirdLabelRadius;
    return `<g><line x1="${pair.fundamental.x}" y1="${pair.fundamental.y}" x2="${pair.third.x}" y2="${pair.third.y}" stroke="${THIRD_HARMONIC_COLOR}" stroke-opacity=".38" stroke-width="1.5" stroke-dasharray="3 4"/><circle cx="${pair.fundamental.x}" cy="${pair.fundamental.y}" r="${7 + pair.note.velocity / 64}" fill="${FUNDAMENTAL_COLOR}" stroke="#f7fbff" stroke-width="1.5"><title>${noteName(pair.note.note)} · ${pair.note.label} · ${pair.note.frequency.toFixed(2)} Hz</title></circle><text x="${flx}" y="${fly}" fill="${FUNDAMENTAL_COLOR}" font-size="10" font-weight="700" text-anchor="middle" dominant-baseline="middle">${pair.note.label}</text><circle cx="${pair.third.x}" cy="${pair.third.y}" r="6" fill="${THIRD_HARMONIC_COLOR}" stroke="#fff0f8" stroke-width="1.25"><title>3rd harmonic of ${noteName(pair.note.note)} · ${(pair.note.frequency * 3).toFixed(2)} Hz</title></circle><text x="${tlx}" y="${tly}" fill="${THIRD_HARMONIC_COLOR}" font-size="9" font-weight="700" text-anchor="middle" dominant-baseline="middle">3f</text></g>`;
  }).join("");
  svg.innerHTML = `<circle cx="180" cy="180" r="${fundamentalRadius}" fill="none" stroke="#39455b" stroke-width="2"/><circle cx="180" cy="180" r="${harmonicRadius}" fill="none" stroke="${THIRD_HARMONIC_COLOR}" stroke-opacity=".22" stroke-width="1" stroke-dasharray="3 5"/>${ticks}${fundamentalPolygon}${harmonicPolygon}${markers}<circle cx="180" cy="180" r="39" fill="#111824" stroke="#39455b"/><text x="180" y="173" fill="#dce6f5" font-size="13" font-weight="700" text-anchor="middle">${equave === 2 ? "OCTAVE" : "TRITAVE"}</text><text x="180" y="191" fill="#8290a8" font-size="10" text-anchor="middle">${notes.length ? `${notes.length} + ${notes.length} guides` : "waiting"}</text><text x="180" y="21" fill="#9fb0c8" font-size="9" text-anchor="middle">1/1 · ${equave}/1</text>`;
  svg.setAttribute("aria-label", notes.length ? `${notes.length} sounding tones and ${notes.length} third-harmonic guide points on the ${equave === 2 ? "octave" : "tritave"} pitch circle` : `Empty ${equave === 2 ? "octave" : "tritave"} pitch circle`);
  const summary = notes.length ? notes.map(note => `${noteName(note.note)} → ${note.label}`).join(" · ") : "No active notes";
  mt("midi-toolkit-circle-summary").textContent = summary; mt("midi-toolkit-circle-summary").title = summary;
}

function startThru(note, velocity, key) {
  if (!mt("midi-toolkit-thru").checked) return;
  try {
    const context = audioContext(), oscillator = context.createOscillator(), gain = context.createGain(), exact = mt("midi-toolkit-thru-tuning").value === "scale", mapped = tunedPitch(note);
    const frequency = exact ? mapped.frequency : 440 * 2 ** ((note - 69) / 12), now = context.currentTime; oscillator.type = "triangle"; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(.0001, now); gain.gain.exponentialRampToValueAtTime(.035 * velocity / 100, now + .012);
    oscillator.connect(gain).connect(context.destination); oscillator.start(); mtState.voices.push(oscillator);
    const active = mtState.active.get(key); if (active) active.audio = { oscillator, gain, frequency, ratioText: exact ? mapped.text : noteName(note) };
  } catch (_) { mtStatus("Audio thru unavailable", "error"); }
}
function stopThru(active) {
  if (!active?.audio) return;
  const { oscillator, gain } = active.audio, now = audioContext().currentTime;
  try { gain.gain.cancelScheduledValues(now); gain.gain.setTargetAtTime(.0001, now, .035); oscillator.stop(now + .18); } catch (_) { /* already stopped */ }
}
function updateKeyboard(note, active) { const key = mt("midi-toolkit-keyboard").querySelector(`[data-note="${note}"]`); if (key) key.classList.toggle("active", active); }
function updateMonitor(note, velocity = 0) { const mapped = note == null ? null : tunedPitch(note); mt("midi-toolkit-note").textContent = note == null ? "--" : `${noteName(note)} → ${mapped.text} · degree ${mapped.degree} · ${velocity}`; mt("midi-toolkit-capture-count").textContent = `${mtState.raw.length} notes`; }

function noteOn(note, velocity, channel = 1, now = performance.now()) {
  if (!inputChannelAllowed(channel)) return;
  if (whiteKeyIndex(note) == null) { mtStatus(`${noteName(note)} ignored · white keys only`, "error"); return; }
  const key = `${channel}:${note}`; if (mtState.active.has(key)) finishNote(key, now);
  const captureStart = mtState.recording && now >= mtState.recordStartMs ? now : null;
  mtState.active.set(key, { note, velocity, channel, captureStart, audio: null });
  startThru(note, velocity, key); updateKeyboard(note, true); updateMonitor(note, velocity); renderPitchCircle();
}
function finishNote(key, now = performance.now()) {
  const active = mtState.active.get(key); if (!active) return;
  stopThru(active);
  if (active.captureStart != null) {
    const startBeats = (active.captureStart - mtState.recordStartMs) / beatMs();
    const durationBeats = Math.max(.03, (now - active.captureStart) / beatMs());
    mtState.raw.push({ midi_note: active.note, start_beats: startBeats, duration_beats: durationBeats, velocity: active.velocity, channel: active.channel });
  }
  mtState.active.delete(key); mtState.sustained.delete(key); updateKeyboard(active.note, false); updateMonitor(null); renderPitchCircle();
  renderRoll();
}
function noteOff(note, channel = 1, now = performance.now()) {
  const key = `${channel}:${note}`; if (mtState.sustainDown) mtState.sustained.add(key); else finishNote(key, now);
}
function releaseSustain(now = performance.now()) { [...mtState.sustained].forEach(key => finishNote(key, now)); mtState.sustained.clear(); }
function midiMessage(event) {
  const [status, data1, data2] = event.data, command = status & 0xf0, channel = (status & 0x0f) + 1, now = performance.now();
  if (command === 0x90 && data2 > 0) noteOn(data1, data2, channel, now);
  else if (command === 0x80 || (command === 0x90 && data2 === 0)) noteOff(data1, channel, now);
  else if (command === 0xb0 && data1 === 64) { mtState.sustainDown = data2 >= 64; if (!mtState.sustainDown) releaseSustain(now); }
}
function refreshInputs() {
  const inputs = mtState.midiAccess ? [...mtState.midiAccess.inputs.values()] : [];
  const previous = mt("midi-toolkit-input").value;
  mt("midi-toolkit-input").innerHTML = inputs.length ? inputs.map(input => `<option value="${input.id}">${input.name || "MIDI Input"}</option>`).join("") : '<option value="">No device</option>';
  mt("midi-toolkit-input").value = inputs.some(input => input.id === previous) ? previous : inputs[0]?.id || "";
  selectInput();
}
function selectInput() {
  if (mtState.input) mtState.input.onmidimessage = null;
  mtState.input = mtState.midiAccess?.inputs.get(mt("midi-toolkit-input").value) || null;
  if (mtState.input) { mtState.input.onmidimessage = midiMessage; mtStatus(`Connected · ${mtState.input.name}`); }
}
async function connectMidi() {
  if (!navigator.requestMIDIAccess) { mtStatus("Web MIDI is unavailable in this browser", "error"); return; }
  try { mtStatus("Requesting MIDI access...", "loading"); mtState.midiAccess = await navigator.requestMIDIAccess(); mtState.midiAccess.onstatechange = refreshInputs; refreshInputs(); }
  catch (_) { mtStatus("MIDI access was not granted", "error"); }
}

function metronomeClick(when, accent) {
  try { const context = audioContext(), oscillator = context.createOscillator(), gain = context.createGain(); oscillator.frequency.value = accent ? 1100 : 760; gain.gain.setValueAtTime(.0001, when); gain.gain.exponentialRampToValueAtTime(.06, when + .004); gain.gain.exponentialRampToValueAtTime(.0001, when + .055); oscillator.connect(gain).connect(context.destination); oscillator.start(when); oscillator.stop(when + .07); } catch (_) { /* capture remains available */ }
}
function record() {
  stopCapture(false); if (!mt("midi-toolkit-overdub").checked) { mtState.raw = []; mtState.project = null; }
  const countInBeats = Number(mt("midi-toolkit-count-in").value) * 4, delay = countInBeats * beatMs();
  mtState.recordStartMs = performance.now() + delay; mtState.recording = true;
  if (countInBeats) { const context = audioContext(), start = context.currentTime + .04; for (let beat = 0; beat < countInBeats; beat++) metronomeClick(start + beat * beatMs() / 1000, beat % 4 === 0); }
  mtStatus(countInBeats ? `Count-in · ${countInBeats} beats` : "Recording", "loading");
  mtState.recordTimer = setTimeout(() => { if (mtState.recording) mtStatus("Recording", "loading"); }, delay);
  mtState.clockTimer = setInterval(() => { const beats = Math.max(0, (performance.now() - mtState.recordStartMs) / beatMs()); mt("midi-toolkit-clock").textContent = `${beats.toFixed(2)} beats`; }, 50);
  updateMonitor(null); renderRoll();
}
function stopCapture(processAfter = true) {
  if (mtState.recordTimer) clearTimeout(mtState.recordTimer); if (mtState.clockTimer) clearInterval(mtState.clockTimer);
  mtState.recordTimer = null; mtState.clockTimer = null;
  if (mtState.recording) [...mtState.active.keys()].forEach(key => finishNote(key));
  mtState.recording = false; mtState.sustainDown = false; releaseSustain();
  mtStatus(mtState.raw.length ? `Captured · ${mtState.raw.length} notes` : "Ready"); updateMonitor(null);
  if (processAfter && mtState.raw.length) void processPerformance();
}
function clearPerformance() { stopCapture(false); mtState.raw = []; mtState.project = null; mt("midi-toolkit-clock").textContent = "0.00 beats"; mt("midi-toolkit-process-status").textContent = "Unprocessed"; renderAll(); mtStatus("Cleared"); }
function demoPhrase() {
  stopCapture(false); mtState.raw = [
    [60, 0, .42, 96], [64, .015, .40, 84], [67, .025, .44, 80], [62, .5, .22, 104],
    [64, .75, .22, 88], [67, 1, .46, 98], [71, 1.5, .22, 108], [69, 1.75, .22, 90],
    [65, 2, .46, 92], [69, 2.01, .44, 82], [72, 2.02, .42, 78], [67, 2.75, .22, 105],
    [64, 3, .72, 86], [60, 3.75, .24, 100],
  ].map(([midi_note, start_beats, duration_beats, velocity]) => ({ midi_note, start_beats, duration_beats, velocity, channel: 1 }));
  mtState.project = null; updateMonitor(null); renderRoll(); void processPerformance(); mtStatus("Demo phrase loaded");
}

function scaleRatios() { return mt("midi-toolkit-scale").value.split(",").map(value => value.trim()).filter(Boolean); }
function setScaleMeta(scale) {
  mtState.scale = scale; mt("midi-toolkit-equave").value = scale.equave_ratio || "2/1";
  mt("midi-toolkit-scale-meta").textContent = `${scale.family || "Custom"} · ${scale.name} · ${scaleRatios().length} tones · equave ${mt("midi-toolkit-equave").value}`;
  const compatible = mt("midi-toolkit-equave").value === "2/1";
  [mt("midi-toolkit-send-motif"), mt("midi-toolkit-send-vital")].forEach(button => { button.disabled = !compatible; button.title = compatible ? "" : "Octave-based composer handoff requires a 2/1 equave"; });
}
function applyScale(scale, reprocess = true) {
  mt("midi-toolkit-scale").value = scale.ratios.join(", "); setScaleMeta(scale); mtState.project = null; renderAll();
  if (reprocess && mtState.raw.length) void processPerformance();
}
function appendScaleOptions(select, label, scales, prefix) {
  if (!scales.length) return; const group = document.createElement("optgroup"); group.label = label;
  scales.forEach(scale => { const option = document.createElement("option"); option.value = `${prefix}:${scale.id || scale.name}`; option.textContent = `${scale.name} (${scale.ratios?.length || scale.count})`; group.append(option); }); select.append(group);
}
async function loadScaleLibrary(preserve = false) {
  const select = mt("midi-toolkit-scale-library"), previous = preserve ? select.value : "preset:kawaii-sparkle-13";
  try {
    const response = await fetch("/api/midi-toolkit/scales"), data = await response.json(); if (!response.ok) throw new Error(data.detail || "Scale library unavailable");
    mtState.scaleCatalog = data.presets; select.innerHTML = '<option value="custom">Custom ratios</option>';
    [...new Set(data.presets.map(scale => scale.family))].forEach(family => appendScaleOptions(select, family, data.presets.filter(scale => scale.family === family), "preset"));
    appendScaleOptions(select, "Saved in Workbench", data.stored || [], "stored");
    select.value = [...select.options].some(option => option.value === previous) ? previous : "preset:kawaii-sparkle-13";
    await selectScale(false); mtStatus(`Scale library ready · ${data.presets.length} presets`);
  } catch (error) { select.innerHTML = '<option value="custom">Custom ratios</option>'; setScaleMeta(mtState.scale); mtStatus(error.message, "error"); }
}
async function selectScale(reprocess = true) {
  const value = mt("midi-toolkit-scale-library").value;
  if (value === "custom") { setScaleMeta({ id: "custom", name: "Custom ratios", family: "Custom", equave_ratio: mt("midi-toolkit-equave").value || "2/1" }); return; }
  if (value.startsWith("preset:")) { const scale = mtState.scaleCatalog.find(item => item.id === value.slice(7)); if (scale) applyScale(scale, reprocess); return; }
  if (value.startsWith("stored:")) {
    const name = value.slice(7), response = await fetch(`/api/scales/${encodeURIComponent(name)}`), data = await response.json(); if (!response.ok) throw new Error(data.detail || "Saved scale unavailable");
    applyScale({ id: `stored:${name}`, name, family: "Saved in Workbench", equave_ratio: "2/1", ratios: data.pitches.map(pitch => pitch.ratio) }, reprocess);
  }
}
async function generateAndAssignScale() {
  try {
    const primes = mt("midi-toolkit-prime-basis").value.split(",").map(item => Number(item.trim())).filter(Number.isInteger);
    const body = { primes, exponent_limit: Number(mt("midi-toolkit-exponent-limit").value), height_limit: Number(mt("midi-toolkit-height-limit").value), tolerance_cents: Number(mt("midi-toolkit-tolerance").value), target_count: Number(mt("midi-toolkit-target-count").value) };
    const response = await fetch("/api/prime-limit/explore", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }), data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Prime-lattice exploration failed");
    const ratios = data.scale.map(item => item.representative.normalized_ratio);
    mt("midi-toolkit-scale-library").value = "custom"; applyScale({ id: "generated:prime-limit", name: `Prime lattice [${primes.join(", ")}]`, family: "Prime-Limit Explorer", equave_ratio: "2/1", ratios }); mtStatus(`Assigned prime-lattice scale · ${ratios.length} tones`);
  } catch (error) { mtStatus(error.message, "error"); }
}
function updatePrimeGeneratorOutputs() { mt("midi-toolkit-exponent-value").textContent = mt("midi-toolkit-exponent-limit").value; mt("midi-toolkit-height-value").textContent = mt("midi-toolkit-height-limit").value; mt("midi-toolkit-tolerance-value").textContent = `${mt("midi-toolkit-tolerance").value} cents`; mt("midi-toolkit-target-value").textContent = mt("midi-toolkit-target-count").value; }
function processRequest() { return { notes: mtState.raw, tempo_bpm: Number(mt("midi-toolkit-tempo").value), root_midi: Number(mt("midi-toolkit-root").value), keyboard_mapping: "white_keys_scale", scale_id: mtState.scale.id, scale_name: mtState.scale.name, equave_ratio: mt("midi-toolkit-equave").value, scale_ratios: scaleRatios(), quantize_division: Number(mt("midi-toolkit-grid").value), quantize_strength: Number(mt("midi-toolkit-strength").value), swing: Number(mt("midi-toolkit-swing").value), maximum_polyphony: Number(mt("midi-toolkit-polyphony").value), minimum_duration_beats: Number(mt("midi-toolkit-min-gate").value), trim_start: mt("midi-toolkit-trim").checked, anchor_size: Number(mt("midi-toolkit-anchor-size").value) }; }
async function processPerformance() {
  if (!mtState.raw.length) { mtStatus("Record or load notes first", "error"); return; }
  try {
    mt("midi-toolkit-process-status").textContent = "Processing..."; mt("midi-toolkit-process-status").className = "loading";
    const response = await fetch("/api/midi-toolkit/process", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(processRequest()) });
    const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Motif processing failed");
    mtState.project = data; renderAll(); mt("midi-toolkit-process-status").textContent = data.warnings.length ? data.warnings.join(" · ") : "Exact-ratio motif ready"; mt("midi-toolkit-process-status").className = "";
  } catch (error) { mt("midi-toolkit-process-status").textContent = error.message; mt("midi-toolkit-process-status").className = "error"; }
}

function transform(transpose = 0) { const whiteSteps = transpose === 12 ? 7 : transpose === -12 ? -7 : transpose; mtState.raw.forEach(note => { const index = whiteKeyIndex(note.midi_note); if (index != null) note.midi_note = midiForWhiteKeyIndex(index + whiteSteps); }); mtState.project = null; renderRoll(); void processPerformance(); }
function reversePerformance() { if (!mtState.raw.length) return; const end = Math.max(...mtState.raw.map(note => note.start_beats + note.duration_beats)); mtState.raw.forEach(note => { note.start_beats = Math.max(0, end - note.start_beats - note.duration_beats); }); mtState.raw.sort((a, b) => a.start_beats - b.start_beats || a.midi_note - b.midi_note); mtState.project = null; void processPerformance(); }
function normalizeVelocity() { if (!mtState.raw.length) return; const mean = mtState.raw.reduce((sum, note) => sum + note.velocity, 0) / mtState.raw.length; mtState.raw.forEach(note => { note.velocity = Math.max(45, Math.min(120, Math.round(94 + (note.velocity - mean) * .65))); }); mtState.project = null; void processPerformance(); }

function drawNotes(context, notes, range, duration, color, yOffset = 0) {
  const [low, high] = range, width = context.canvas.width, height = context.canvas.height, left = 48, top = 20, plotWidth = width - left - 12, plotHeight = height - top - 28;
  notes.forEach(note => { const pitch = note.midi_note; if (pitch == null) return; const x = left + note.start_beats / duration * plotWidth, y = top + (high - pitch) / Math.max(1, high - low + 1) * plotHeight + yOffset, w = Math.max(3, note.duration_beats / duration * plotWidth), h = Math.max(4, plotHeight / Math.max(12, high - low + 1) - 1); context.fillStyle = note.accent ? "#ffd47e" : color; context.fillRect(x, y, w, h); });
}
function renderRoll() {
  const canvas = mt("midi-toolkit-roll"), ratio = devicePixelRatio || 1, cssWidth = Math.max(320, canvas.clientWidth), cssHeight = Math.max(260, canvas.clientHeight); canvas.width = Math.round(cssWidth * ratio); canvas.height = Math.round(cssHeight * ratio);
  const context = canvas.getContext("2d"); context.clearRect(0, 0, canvas.width, canvas.height); context.fillStyle = "#0d121c"; context.fillRect(0, 0, canvas.width, canvas.height);
  const raw = mtState.raw, mapped = mtState.project?.midi_notes || [], all = raw.length ? raw : mapped, low = all.length ? Math.max(0, Math.min(...all.map(note => note.midi_note ?? 60)) - 2) : 48, high = all.length ? Math.min(127, Math.max(...all.map(note => note.midi_note ?? 72)) + 2) : 72, duration = Math.max(4, ...all.map(note => note.start_beats + note.duration_beats));
  const left = 48 * ratio, top = 20 * ratio, plotWidth = canvas.width - left - 12 * ratio, plotHeight = canvas.height - top - 28 * ratio; context.strokeStyle = "#273044"; context.lineWidth = ratio;
  for (let beat = 0; beat <= Math.ceil(duration); beat++) { const x = left + beat / duration * plotWidth; context.beginPath(); context.moveTo(x, top); context.lineTo(x, top + plotHeight); context.stroke(); context.fillStyle = "#8b96ac"; context.font = `${10 * ratio}px system-ui`; context.fillText(String(beat), x + 3 * ratio, canvas.height - 8 * ratio); }
  for (let note = low; note <= high; note++) if (note % 12 === 0) { const y = top + (high - note) / Math.max(1, high - low + 1) * plotHeight; context.beginPath(); context.moveTo(left, y); context.lineTo(left + plotWidth, y); context.stroke(); context.fillStyle = "#8b96ac"; context.fillText(noteName(note), 5 * ratio, y + 4 * ratio); }
  drawNotes(context, raw, [low, high], duration, "#60708d"); drawNotes(context, mapped, [low, high], duration, "#78d7ff", 2 * ratio);
  mt("midi-toolkit-roll-summary").textContent = `${raw.length} captured · ${mapped.length} mapped · ${duration.toFixed(2)} beats`;
}
function renderAnalysis() {
  const analysis = mtState.project?.analysis; if (!analysis) { mt("midi-toolkit-analysis").innerHTML = ""; mt("midi-toolkit-analysis-summary").textContent = "Waiting"; return; }
  const labels = { captured_notes: "Captured", motif_steps: "Motif steps", duration_beats: "Length", midi_range: "Range", average_velocity: "Velocity", maximum_polyphony: "Voices", note_density: "Density", syncopation: "Syncopation", anchor_chord: "Anchor chord", prime_basis: "Prime basis", contour: "Contour" };
  mt("midi-toolkit-analysis").innerHTML = Object.entries(labels).map(([key, label]) => `<article><strong>${label}</strong><span>${Array.isArray(analysis[key]) ? analysis[key].join(" · ") : analysis[key]}</span></article>`).join("");
  mt("midi-toolkit-analysis-summary").textContent = `${analysis.motif_steps} steps · ${analysis.maximum_polyphony} voices`;
}
function renderMotif() {
  const motif = mtState.project?.motif; if (!motif) { mt("midi-toolkit-motif").innerHTML = '<p class="hint">Build a motif from a captured performance.</p>'; mt("midi-toolkit-motif-summary").textContent = "No motif"; return; }
  mt("midi-toolkit-motif").innerHTML = motif.notes.map((note, index) => `<article class="midi-motif-note ${note.accent ? "accent" : ""}"><strong>${index + 1} · ${[note.ratio, ...note.harmony_tones].join(" + ")}</strong><span>${note.onset_beat} beat · ${note.duration_beats} gate</span><small>${note.velocity} velocity · ${note.chord_relation}</small></article>`).join("");
  mt("midi-toolkit-motif-summary").textContent = `${motif.notes.length} steps · ${motif.polyphony_signature.maximum} voices · affinity ${motif.chord_affinity.toFixed(2)}`;
}
function renderAll() { renderRoll(); renderAnalysis(); renderMotif(); renderPitchCircle(); updateMonitor(null); }

function stopPlayback() { mtState.voices.forEach(voice => { try { voice.stop(); } catch (_) { /* already stopped */ } }); mtState.voices = []; mtOutput("Stopped"); }
async function playNotes(notes, exact) {
  if (!notes?.length) return; stopPlayback();
  try { const context = audioContext(); if (context.state === "suspended") await context.resume(); const start = context.currentTime + .04, seconds = 60 / Number(mt("midi-toolkit-tempo").value), base = Number(mt("midi-toolkit-base").value); mtState.voices = notes.map(note => { const oscillator = context.createOscillator(), gain = context.createGain(), at = start + note.start_beats * seconds; oscillator.type = "triangle"; oscillator.frequency.value = exact ? base * Number(note.ratio.split("/")[0]) / Number(note.ratio.split("/")[1]) : 440 * 2 ** ((note.midi_note - 69) / 12); gain.gain.setValueAtTime(.0001, at); gain.gain.exponentialRampToValueAtTime(.045 * note.velocity / 100, at + .012); gain.gain.setTargetAtTime(.0001, at + Math.max(.03, note.duration_beats * seconds - .05), .035); oscillator.connect(gain).connect(context.destination); oscillator.start(at); oscillator.stop(at + note.duration_beats * seconds + .16); return oscillator; }); mtOutput(exact ? "Playing exact-ratio motif" : "Playing captured performance"); } catch (_) { mtOutput("Audio playback unavailable", "error"); }
}
function download(blob, name) { const url = URL.createObjectURL(blob), link = document.createElement("a"); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1200); }
async function exportMidi() { if (!mtState.project) return; try { const response = await fetch("/api/export/midi", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ notes: mtState.project.midi_notes, base_frequency: Number(mt("midi-toolkit-base").value), pitch_bend: true, pitch_bend_range_semitones: 2 }) }); if (!response.ok) throw new Error((await response.json()).detail || "MIDI export failed"); download(await response.blob(), "midi-toolkit-motif.mid"); mtOutput("MPE MIDI exported"); } catch (error) { mtOutput(error.message, "error"); } }
function exportJson() { if (mtState.project) download(new Blob([JSON.stringify(mtState.project, null, 2)], { type: "application/json" }), "midi-toolkit-project.json"); }
function importProject(project) { if (!project || project.feature !== "midi-creator-toolkit" || !Array.isArray(project.captured_notes) || !project.motif) throw new Error("Select a MIDI Creator Toolkit project JSON file"); mtState.project = project; mtState.raw = structuredClone(project.captured_notes); const settings = project.settings || {}; if (settings.tempo_bpm) mt("midi-toolkit-tempo").value = settings.tempo_bpm; if (settings.root_midi != null) mt("midi-toolkit-root").value = settings.root_midi; if (settings.scale_ratios) mt("midi-toolkit-scale").value = settings.scale_ratios.join(", "); mt("midi-toolkit-scale-library").value = "custom"; setScaleMeta({ id: settings.scale_id || "imported", name: settings.scale_name || "Imported scale", family: "Project JSON", equave_ratio: settings.equave_ratio || "2/1" }); renderAll(); mtOutput("Project imported"); }
function motifNotesForTransfer() { return mtState.project.motif.notes.map(({ ratio, onset_beat, duration_beats, velocity, accent, chord_relation, harmony_tones }) => ({ ratio, onset_beat, duration_beats, velocity, accent, chord_relation, harmony_tones })); }
function sendToMotif() { if (!mtState.project) return; sessionStorage.setItem("midi-toolkit-motif-transfer", JSON.stringify(mtState.project)); location.href = "/motif-development?source=midi-toolkit"; }
function sendToVital() { if (!mtState.project) return; const motif = mtState.project.motif, id = `midi-theme-${Date.now()}`; localStorage.setItem("pure-intonation.motif-vital-transfer", JSON.stringify({ version: 3, anchor_chord: motif.anchor_chord, prime_basis: motif.prime_basis, nodes: [{ id, source_motif_id: id, formal_role: "theme", target_chord: motif.anchor_chord, notes: motifNotesForTransfer(), transformation_chain: ["midi_performance"], identity_retention: 1 }], source_motif_ids: [id] })); location.href = "/vital-pack-composer?source=motif-tree"; }

function buildScreenKeyboard() { mt("midi-toolkit-keyboard").innerHTML = KEYBOARD_NOTES.map(note => `<button type="button" data-note="${note}">${noteName(note)}</button>`).join(""); [...mt("midi-toolkit-keyboard").querySelectorAll("button")].forEach(button => { const note = Number(button.dataset.note), key = `screen:${note}`; button.onpointerdown = event => { event.preventDefault(); mtState.syntheticHeld.add(key); noteOn(note, 96, 1); }; button.onpointerup = button.onpointercancel = button.onpointerleave = () => { if (mtState.syntheticHeld.delete(key)) noteOff(note, 1); }; }); }
function keyboardEvent(event, down) { if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return; const index = COMPUTER_KEYS.indexOf(event.key.toLowerCase()); if (index < 0 || (down && event.repeat)) return; event.preventDefault(); const key = `computer:${event.key.toLowerCase()}`, note = KEYBOARD_NOTES[index]; if (down) { mtState.syntheticHeld.add(key); noteOn(note, 94, 1); } else if (mtState.syntheticHeld.delete(key)) noteOff(note, 1); }

mt("midi-toolkit-connect").onclick = () => void connectMidi(); mt("midi-toolkit-input").onchange = selectInput;
mt("midi-toolkit-circle-mode").querySelectorAll("button").forEach(button => { button.onclick = () => { mt("midi-toolkit-circle-mode").querySelectorAll("button").forEach(item => { const selected = item === button; item.classList.toggle("active", selected); item.setAttribute("aria-pressed", String(selected)); }); renderPitchCircle(); }; });
mt("midi-toolkit-thru-tuning").onchange = renderPitchCircle; mt("midi-toolkit-root").onchange = () => { const root = Number(mt("midi-toolkit-root").value); if (whiteKeyIndex(root) == null) { mt("midi-toolkit-root").value = midiForWhiteKeyIndex(Math.floor(root / 12) * 7); mtStatus("Root MIDI reset to a white key", "error"); } renderPitchCircle(); }; mt("midi-toolkit-base").onchange = renderPitchCircle;
mt("midi-toolkit-scale-library").onchange = () => void selectScale().catch(error => mtStatus(error.message, "error")); mt("midi-toolkit-scale-refresh").onclick = () => void loadScaleLibrary(true); mt("midi-toolkit-scale-generate").onclick = () => void generateAndAssignScale();
["midi-toolkit-exponent-limit", "midi-toolkit-height-limit", "midi-toolkit-tolerance", "midi-toolkit-target-count"].forEach(id => { mt(id).oninput = updatePrimeGeneratorOutputs; });
mt("midi-toolkit-scale").oninput = () => { mt("midi-toolkit-scale-library").value = "custom"; mtState.project = null; setScaleMeta({ id: "custom", name: "Custom ratios", family: "Custom", equave_ratio: mt("midi-toolkit-equave").value || "2/1" }); renderPitchCircle(); };
mt("midi-toolkit-record").onclick = record; mt("midi-toolkit-stop").onclick = () => stopCapture(true); mt("midi-toolkit-clear").onclick = clearPerformance; mt("midi-toolkit-demo").onclick = demoPhrase;
mt("midi-toolkit-process").onclick = () => void processPerformance();
mt("midi-toolkit-strength").oninput = () => { mt("midi-toolkit-strength-value").textContent = `${Math.round(Number(mt("midi-toolkit-strength").value) * 100)}%`; };
mt("midi-toolkit-swing").oninput = () => { mt("midi-toolkit-swing-value").textContent = `${Math.round(Number(mt("midi-toolkit-swing").value) * 100)}%`; };
[...document.querySelectorAll("[data-transpose]")].forEach(button => { button.onclick = () => transform(Number(button.dataset.transpose)); });
mt("midi-toolkit-reverse").onclick = reversePerformance; mt("midi-toolkit-normalize").onclick = normalizeVelocity;
mt("midi-toolkit-play").onclick = () => void playNotes(mtState.project?.midi_notes, true); mt("midi-toolkit-play-raw").onclick = () => void playNotes(mtState.raw, false); mt("midi-toolkit-play-stop").onclick = stopPlayback;
mt("midi-toolkit-midi").onclick = () => void exportMidi(); mt("midi-toolkit-json").onclick = exportJson; mt("midi-toolkit-import").onclick = () => mt("midi-toolkit-import-file").click();
mt("midi-toolkit-import-file").onchange = async event => { try { importProject(JSON.parse(await event.target.files[0].text())); } catch (error) { mtOutput(error.message, "error"); } event.target.value = ""; };
mt("midi-toolkit-send-motif").onclick = sendToMotif; mt("midi-toolkit-send-vital").onclick = sendToVital;
window.addEventListener("keydown", event => keyboardEvent(event, true)); window.addEventListener("keyup", event => keyboardEvent(event, false)); window.addEventListener("resize", renderRoll);
buildScreenKeyboard(); updatePrimeGeneratorOutputs(); renderAll(); void loadScaleLibrary();
