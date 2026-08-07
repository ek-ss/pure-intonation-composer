const ex = id => document.getElementById(id);
const state = { profiles: [], defaults: {}, result: null, selected: null, context: null, nodes: [] };
const SECTION_COLORS = { intro: "#59728f", verse: "#98e7ca", a: "#98e7ca", a_variation: "#69c9aa", pre: "#e3a8ff", b: "#e3a8ff", chorus: "#ffd47e", drop: "#ff9daf", final: "#ffbd70", bridge: "#86b9ff", instrumental: "#86b9ff", minimal: "#9ea8b8", break: "#b1a3ce", outro: "#6d7a8f" };
const SCORE_LABELS = { structural_coherence: "Structural coherence", section_contrast: "Section contrast", harmonic_interest: "Harmonic interest", tension_smoothness: "Tension smoothness", melodic_identity: "Melodic identity", rhythmic_identity: "Rhythmic identity", repetition_balance: "Repetition balance", ratio_color_usage: "Ratio color usage", instrumentation_fit: "Instrumentation fit", overall: "Overall" };
const MIX_CONTROLS = { fractional_pop: "pop", fractional_jpop: "jpop", kawaii_fractional_future_pop: "kawaii" };

function status(message, kind = "") { ex("explorer-status").textContent = message; ex("explorer-status").className = kind; }
function selectedIds() { return [...document.querySelectorAll(".explorer-instrument input:checked")].map(node => node.value); }
function ratios() {
  const values = ex("explorer-scale").value.split(",").map(value => value.trim()).filter(Boolean);
  if (values.length < 5) throw new Error("Select at least five scale ratios.");
  values.forEach(value => { const parts = value.split("/").map(Number); if (parts.length !== 2 || !parts[0] || !parts[1]) throw new Error(`Invalid ratio: ${value}`); });
  return values;
}
function feedback() {
  try { return JSON.parse(localStorage.getItem("pure-intonation.composition-explorer-feedback") || "{}") || {}; }
  catch (_) { return {}; }
}
function styleMix(normalized = true) {
  const values = Object.fromEntries(Object.entries(MIX_CONTROLS).map(([style, suffix]) => [style, Number(ex(`explorer-mix-${suffix}`).value)]));
  const total = Object.values(values).reduce((sum, value) => sum + value, 0);
  if (normalized && ex("explorer-style").value === "mixed" && total <= 0) throw new Error("Set at least one Style Mix ratio above zero.");
  return normalized && total > 0 ? Object.fromEntries(Object.entries(values).map(([style, value]) => [style, value / total])) : values;
}
function instrumentPriority(id) {
  if (ex("explorer-style").value !== "mixed") return .7;
  const mix = styleMix();
  const affinity = Object.entries(mix).reduce((sum, [style, weight]) => sum + (state.defaults[style]?.includes(id) ? weight : 0), 0);
  return Math.min(1, .35 + affinity * .65);
}
function request() {
  const ids = selectedIds();
  if (!ids.length) throw new Error("Select at least one Vital preset.");
  return {
    style: ex("explorer-style").value,
    style_mix: styleMix(),
    seed: Number(ex("explorer-seed").value),
    candidate_count: Number(ex("explorer-candidates").value),
    cluster_count: Number(ex("explorer-cluster-count").value),
    tempo_bpm: Number(ex("explorer-tempo").value),
    length_bars: Number(ex("explorer-bars").value),
    base_frequency: Number(ex("explorer-base").value),
    scale_ratios: ratios(),
    instrument_palette: ids.map(id => ({ id, preferred_roles: [], priority: instrumentPriority(id) })),
    missing_role_policy: ex("explorer-missing-role").value,
    form_temperature: Number(ex("explorer-form").value),
    harmony_temperature: Number(ex("explorer-harmony").value),
    part_temperature: Number(ex("explorer-parts").value),
    rhythm_temperature: Number(ex("explorer-rhythm").value),
    locked_components: [...document.querySelectorAll(".explorer-locks input:checked")].map(node => node.value),
    evaluation_weights: feedback().weights || {},
  };
}
function renderProfiles() {
  ex("explorer-instrument-list").innerHTML = state.profiles.map(profile => `<label class="explorer-instrument"><input type="checkbox" value="${profile.id}"><strong>${profile.id} ${profile.name}</strong><span>${profile.roles.join(" / ")}</span><small>${profile.midi_range.join("-")} · ${profile.max_polyphony} voice${profile.max_polyphony === 1 ? "" : "s"}</small></label>`).join("");
  document.querySelectorAll(".explorer-instrument input").forEach(node => { node.onchange = renderCapabilities; });
  applyStylePalette();
}
function applyStylePalette() {
  const style = ex("explorer-style").value;
  const rawMix = styleMix(false);
  const palette = style === "mixed"
    ? Object.entries(rawMix).flatMap(([item, weight]) => weight > 0 ? state.defaults[item] || [] : [])
    : state.defaults[style] || [];
  const defaults = new Set(palette);
  document.querySelectorAll(".explorer-instrument input").forEach(node => { node.checked = defaults.has(node.value); });
  renderCapabilities();
}
function updateStyleMix(applyPalette = false) {
  ex("explorer-style-mix").hidden = ex("explorer-style").value !== "mixed";
  if (applyPalette) applyStylePalette();
}
function renderStyleMixValues() {
  const values = styleMix(false), total = Object.values(values).reduce((sum, value) => sum + value, 0);
  Object.entries(MIX_CONTROLS).forEach(([style, suffix]) => { ex(`explorer-mix-${suffix}-value`).textContent = `${total > 0 ? Math.round(values[style] / total * 100) : 0}%`; });
}
function renderCapabilities() {
  const selected = new Set(selectedIds());
  const profiles = state.profiles.filter(profile => selected.has(profile.id));
  const roles = new Set(profiles.flatMap(profile => profile.roles));
  ex("explorer-instrument-summary").textContent = `${profiles.length} presets · ${roles.size} capabilities`;
  const notices = [];
  if (!roles.has("bass")) notices.push(["No bass", true]);
  if (![...roles].some(role => ["harmony", "rhythmic_harmony", "pad"].includes(role))) notices.push(["No dedicated harmony", true]);
  ["vocal", "harmony", "pulse", "accent", "kick", "snare", "hat", "perc"].filter(role => roles.has(role)).forEach(role => notices.push([role, false]));
  ex("explorer-capability-report").innerHTML = notices.map(([label, warning]) => `<span class="${warning ? "warning" : ""}">${label}</span>`).join("");
  ex("explorer-preset-downloads").innerHTML = profiles.filter(profile => profile.preset_file).map(profile => `<a href="/static/vital_presets/${encodeURIComponent(profile.preset_file)}" download>${profile.id} .vital</a>`).join("");
}
async function generate() {
  try {
    stop();
    const payload = request();
    status(`Generating ${payload.candidate_count} candidates...`, "loading");
    ex("explorer-generate").disabled = true;
    const response = await fetch("/api/composition-explorer/explore", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Composition exploration failed.");
    state.result = data;
    state.selected = data.representatives[0] || null;
    renderResults();
    status("Exploration complete");
  } catch (error) { status(error.message, "error"); }
  finally { ex("explorer-generate").disabled = false; }
}
function miniForm(sections) {
  return `<div class="explorer-mini-form">${sections.map(section => `<i style="flex:${section.bars};--section-color:${SECTION_COLORS[section.role] || "#98e7ca"}" title="${section.name}: ${section.bars} bars"></i>`).join("")}</div>`;
}
function renderResults() {
  const representatives = new Map(state.result.representatives.map(item => [item.id, item]));
  ex("explorer-cluster-grid").innerHTML = state.result.clusters.map(cluster => {
    const song = representatives.get(cluster.representative_id);
    return `<button class="explorer-cluster-card${state.selected?.id === song.id ? " active" : ""}" data-song="${song.id}"><header><strong>${cluster.label}</strong><span>${cluster.size} candidates</span></header>${miniForm(song.sections)}<span>${song.sections.map(section => section.role).join(" · ")}</span><span class="explorer-cluster-score">Score ${Number(song.scores.overall).toFixed(3)}</span><small>${song.id}</small></button>`;
  }).join("");
  document.querySelectorAll(".explorer-cluster-card").forEach(node => { node.onclick = () => { state.selected = representatives.get(node.dataset.song); renderResults(); }; });
  ex("explorer-result-summary").textContent = `${state.result.candidate_count} candidates · ${state.result.cluster_count} distinct families`;
  renderSelected();
}
function renderSelected() {
  const song = state.selected;
  if (!song) return;
  ex("explorer-selection-summary").textContent = `${song.metadata.style_name} · ${song.metadata.length_bars} bars · ${song.id}`;
  renderForm(song);
  const entries = Object.entries(song.scores);
  ex("explorer-scores").innerHTML = entries.map(([key, value], index) => `<div class="explorer-score-row"><span>${SCORE_LABELS[key] || key}</span><div class="explorer-score-track" style="--score-color:${index % 3 === 0 ? "#98e7ca" : index % 3 === 1 ? "#ffd47e" : "#e3a8ff"}"><i style="width:${Number(value) * 100}%"></i></div><output>${Number(value).toFixed(3)}</output></div>`).join("");
  ex("explorer-assignments").innerHTML = `<table><thead><tr><th>Section</th><th>Role</th><th>Vital preset</th><th>Fit</th></tr></thead><tbody>${song.assignments.map(item => `<tr><td>${item.section_role}</td><td>${item.part_role}</td><td>${item.instrument_id}</td><td>${Number(item.assignment_score).toFixed(2)}</td></tr>`).join("")}</tbody></table>`;
}
function renderForm(song) {
  const canvas = ex("explorer-form-canvas"), ratio = window.devicePixelRatio || 1, width = Math.max(600, canvas.clientWidth || 900), height = 220;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext("2d"); context.scale(ratio, ratio); context.clearRect(0, 0, width, height);
  const total = song.metadata.length_bars, top = 34, bandHeight = 104;
  context.font = "11px system-ui"; context.textBaseline = "middle";
  song.sections.forEach(section => {
    const x = section.start_bar / total * width, w = section.bars / total * width;
    context.fillStyle = SECTION_COLORS[section.role] || "#98e7ca"; context.globalAlpha = .72; context.fillRect(x, top, Math.max(2, w - 1), bandHeight); context.globalAlpha = 1;
    if (w > 52) { context.save(); context.beginPath(); context.rect(x + 4, top, w - 8, bandHeight); context.clip(); context.fillStyle = "#10131c"; context.font = "700 10px system-ui"; context.fillText(section.name, x + 7, top + 18); context.restore(); }
    const energyY = top + bandHeight - Number(section.energy) * 78;
    context.fillStyle = "#fff4cf"; context.beginPath(); context.arc(x + w / 2, energyY, 3, 0, Math.PI * 2); context.fill();
  });
  context.fillStyle = "#aeb9d0"; context.font = "11px system-ui"; context.fillText("FORM + ENERGY", 6, 16);
  context.strokeStyle = "#30394d"; context.beginPath(); context.moveTo(0, 166); context.lineTo(width, 166); context.stroke();
  const instruments = [...new Set(song.events.map(event => event.instrument_id))];
  context.fillStyle = "#aeb9d0"; context.fillText(`${instruments.length} active presets · ${song.events.length} score events`, 6, 190);
  context.fillStyle = "#edf1fb"; context.fillText(instruments.join("  "), 6, 208);
}
function fraction(value) { const [a, b] = value.split("/").map(Number); return a / b; }
function stop() { state.nodes.forEach(node => { try { node.stop(); } catch (_) {} }); state.nodes = []; }
function scheduleTone(context, destination, frequency, at, duration, velocity, waveform = "triangle") {
  const oscillator = context.createOscillator(), gain = context.createGain(); oscillator.type = waveform; oscillator.frequency.value = Math.max(20, Math.min(16000, frequency));
  const level = Math.max(.004, velocity / 127 * .035); gain.gain.setValueAtTime(.0001, at); gain.gain.exponentialRampToValueAtTime(level, at + .008); gain.gain.exponentialRampToValueAtTime(.0001, at + Math.max(.04, duration));
  oscillator.connect(gain).connect(destination); oscillator.start(at); oscillator.stop(at + Math.max(.06, duration) + .02); state.nodes.push(oscillator);
}
async function play() {
  if (!state.selected) return;
  stop(); const song = state.selected; const Audio = window.AudioContext || window.webkitAudioContext; state.context ||= new Audio(); if (state.context.state === "suspended") await state.context.resume();
  const focus = song.sections.find(section => ["chorus", "drop", "final"].includes(section.role)) || [...song.sections].sort((a, b) => b.energy - a.energy)[0];
  const offset = focus.start_bar * 4, end = offset + Math.min(8, focus.bars) * 4, beat = 60 / song.metadata.tempo_bpm, now = state.context.currentTime + .06;
  const master = state.context.createGain(); master.gain.value = .72; master.connect(state.context.destination);
  song.events.filter(event => event.start_beat >= offset && event.start_beat < end).forEach(event => {
    const at = now + (event.start_beat - offset) * beat, duration = Math.min(2.8, event.duration_beats * beat);
    if (event.ratio) {
      const waveform = event.part_role === "bass" ? "sine" : event.part_role === "harmony" ? "sawtooth" : event.part_role === "accent" ? "triangle" : "square";
      scheduleTone(state.context, master, song.metadata.base_frequency * fraction(event.ratio), at, duration, event.velocity, waveform);
    } else {
      const settings = { kick: [64, "sine", .18], snare: [190, "square", .09], hat: [4800, "square", .035], perc: [680, "triangle", .07] }[event.part_role];
      scheduleTone(state.context, master, settings[0], at, settings[2], event.velocity, settings[1]);
    }
  });
  status(`Playing ${focus.name} from ${song.id}`, "loading");
}
function rate(direction) {
  if (!state.selected) return;
  const stored = feedback(), weights = { ...(stored.weights || {}) }, ratings = [...(stored.ratings || [])];
  Object.entries(state.selected.scores).forEach(([key, value]) => { if (key === "overall") return; const current = Number(weights[key] || state.result.evaluation_weights[key] || 1); weights[key] = Math.max(.1, Math.min(3, current + direction * (Number(value) - .5) * .12)); });
  ratings.push({ candidate_id: state.selected.id, value: direction, scores: state.selected.scores, at: new Date().toISOString() });
  localStorage.setItem("pure-intonation.composition-explorer-feedback", JSON.stringify({ version: 1, weights, ratings: ratings.slice(-200) }));
  status(`${direction > 0 ? "Like" : "Dislike"} saved. Evaluation weights will apply to the next exploration.`);
}
function download() {
  if (!state.selected) return; const blob = new Blob([JSON.stringify(state.selected, null, 2)], { type: "application/json" }), link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${state.selected.id}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
async function midi() {
  if (!state.selected) return;
  try {
    const song = state.selected;
    status(`Exporting ${song.id} MIDI...`, "loading");
    const response = await fetch("/api/compose/vital-pack/midi", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ events: song.events, tempo_bpm: song.metadata.tempo_bpm, base_frequency: song.metadata.base_frequency }) });
    if (!response.ok) { const data = await response.json(); throw new Error(typeof data.detail === "string" ? data.detail : "MIDI export failed."); }
    const link = document.createElement("a"); link.href = URL.createObjectURL(await response.blob()); link.download = `${song.id}.mid`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(link.href), 1500); status(`${song.id} MPE MIDI exported`);
  } catch (error) { status(error.message, "error"); }
}
async function init() {
  try {
    const response = await fetch("/api/composition-explorer/profiles"), data = await response.json(); if (!response.ok) throw new Error("Could not load Vital profiles.");
    state.profiles = data.instruments; state.defaults = data.style_defaults; renderProfiles(); status("Ready");
  } catch (error) { status(error.message, "error"); }
}
["form", "harmony", "parts", "rhythm"].forEach(name => { ex(`explorer-${name}`).oninput = () => { ex(`explorer-${name}-value`).textContent = Number(ex(`explorer-${name}`).value).toFixed(2); }; });
Object.values(MIX_CONTROLS).forEach(suffix => { const input = ex(`explorer-mix-${suffix}`); input.oninput = renderStyleMixValues; input.onchange = () => { if (ex("explorer-style").value === "mixed") applyStylePalette(); }; });
ex("explorer-style").onchange = () => updateStyleMix(true); ex("explorer-style-palette").onclick = applyStylePalette;
ex("explorer-select-all").onclick = () => { document.querySelectorAll(".explorer-instrument input").forEach(node => { node.checked = true; }); renderCapabilities(); };
ex("explorer-clear").onclick = () => { document.querySelectorAll(".explorer-instrument input").forEach(node => { node.checked = false; }); renderCapabilities(); };
ex("explorer-generate").onclick = () => void generate(); ex("explorer-random").onclick = () => { ex("explorer-seed").value = String(Math.floor(Math.random() * 1_000_000_000)); void generate(); };
ex("explorer-play").onclick = () => void play(); ex("explorer-stop").onclick = () => { stop(); status("Stopped"); }; ex("explorer-like").onclick = () => rate(1); ex("explorer-dislike").onclick = () => rate(-1); ex("explorer-midi").onclick = () => void midi(); ex("explorer-json").onclick = download;
window.addEventListener("resize", () => { if (state.selected) renderForm(state.selected); });
void init();
