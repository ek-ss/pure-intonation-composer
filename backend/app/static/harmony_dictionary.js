// 5D Harmony Dictionary workbench.
// Stale-request guard: every async load captures state.version and drops its
// result if the equave/axis changed in flight.
const el = (id) => document.getElementById(id);

const state = {
  version: 0,
  equave: "2/1",
  config: null,
  axes: {},
  selectedAxis: null,
  chords: { page: 0, data: null },
  evaluation: null,
  cadences: null,
  context: null,
  voices: [],
};

function status(message, kind) {
  const node = el("hd-status");
  node.textContent = message;
  node.className = kind || "";
}

async function postJson(endpoint, body) {
  const response = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`);
  return data;
}

function audioContext() {
  if (!state.context) state.context = new AudioContext();
  return state.context;
}

function stopAudio() {
  for (const voice of state.voices) { try { voice.stop(); } catch { /* already stopped */ } }
  state.voices = [];
}

function ratioToCents(text) {
  const [num, den] = String(text).split("/").map(Number);
  return 1200 * Math.log2(den ? num / den : num);
}

// Play root-relative ratio texts. mode "exact" sounds the exact ratios;
// "edo" snaps each tone to its nearest 12-EDO semitone. Per-voice gain is
// equalized by voice count so chord sizes compare at the same loudness.
function playRatios(ratios, mode, { rootCents = 0, duration = 1.6 } = {}) {
  stopAudio();
  const context = audioContext();
  if (context.state === "suspended") context.resume();
  const start = context.currentTime + 0.02;
  const base = Number(el("hd-base-frequency").value);
  const gainPerVoice = 0.12 / Math.sqrt(ratios.length);
  state.voices = ratios.map((text) => {
    let cents = ratioToCents(text);
    if (mode === "edo") cents = Math.round(cents / 100) * 100;
    const oscillator = context.createOscillator(), gain = context.createGain();
    oscillator.type = el("hd-waveform").value;
    oscillator.frequency.value = base * 2 ** ((rootCents + cents) / 1200);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(gainPerVoice, start + 0.02);
    gain.gain.setTargetAtTime(0.0001, start + duration * 0.75, 0.12);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start(start);
    oscillator.stop(start + duration);
    return oscillator;
  });
}

// ---------------------------------------------------------------- config

async function loadConfig() {
  const version = state.version;
  status("Loading config…", "loading");
  try {
    const response = await fetch("/api/harmony-dictionary/config");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Config failed (${response.status})`);
    if (version !== state.version) return;
    state.config = data;
    renderConfig();
    status("Ready");
  } catch (error) {
    if (version === state.version) status(error.message, "error");
  }
}

function renderConfig() {
  const config = state.config;
  const file = config.files[state.equave];
  let html = `<dl class="hd-config-list">`;
  html += `<dt>Dictionary</dt><dd>${config.dictionary_version}</dd>`;
  html += `<dt>Templates</dt><dd>${config.templates_version} (${config.templates.length})</dd>`;
  html += `<dt>Loop policy</dt><dd>${config.loop_policy.limit} steps / ${config.loop_policy.tolerance_mc} mc</dd>`;
  html += `<dt>File ${state.equave}</dt><dd>${file.available ? "sealed ✓" : `unavailable (${file.code})`}</dd>`;
  if (file.available) {
    html += `<dt>File hash</dt><dd class="hd-hash">${file.hash.slice(0, 26)}…</dd>`;
    html += `<dt>Stability profile</dt><dd class="hd-hash">${file.stability_profile_hash.slice(0, 26)}…</dd>`;
    html += `<dt>Dictionaries</dt><dd>${file.dictionary_count} · ${file.variant_total} variants</dd>`;
  }
  html += `<dt>Thresholds</dt><dd>T≥${config.thresholds.T_high} · D≤${config.thresholds.D_low} · margin ${config.thresholds.margin}</dd>`;
  html += `</dl>`;
  el("hd-config").innerHTML = html;
  const datalist = el("hd-templates");
  datalist.innerHTML = config.templates.map((name) => `<option value="${name}">`).join("");
  const axisSelect = el("hd-chord-axis");
  axisSelect.innerHTML = config.axes[state.equave].map((generator) => `<option value="${generator}">g=${generator}</option>`).join("");
  if (state.selectedAxis !== null && config.axes[state.equave].includes(state.selectedAxis)) axisSelect.value = String(state.selectedAxis);
}

// ------------------------------------------------------------------ axes

function equaveCents() {
  const [num, den] = state.equave.split("/").map(Number);
  return (1200 * num) / den;
}

async function loadAxes() {
  const version = state.version;
  el("hd-axes").innerHTML = `<p class="hint">Loading axes…</p>`;
  try {
    const results = await Promise.all(
      state.config.axes[state.equave].map((generator) => postJson("/api/harmony-dictionary/axis", { equave: state.equave, generator }))
    );
    if (version !== state.version) return;
    state.axes = {};
    for (const detail of results) state.axes[detail.generator] = detail;
    renderAxes();
  } catch (error) {
    if (version === state.version) el("hd-axes").innerHTML = `<p class="hint hd-error">${error.message}</p>`;
  }
}

function errorColor(cents) {
  const width = Math.abs(cents);
  if (width < 5) return "var(--accent)";
  if (width < 10) return "#ffd47e";
  return "#ff9d9a";
}

function renderAxes() {
  const container = el("hd-axes");
  container.innerHTML = "";
  const span = equaveCents();
  for (const [generator, detail] of Object.entries(state.axes)) {
    const card = document.createElement("div");
    card.className = "hd-axis-card" + (state.selectedAxis === Number(generator) ? " active" : "");
    const loop = detail.loop;
    const loopText = loop.found ? `loop ${loop.n} ≈ ${loop.k}×E (${loop.distance_mc} mc)` : loop.code;
    card.innerHTML = `<div class="hd-axis-head"><strong>g=${generator}</strong><span>${loopText} · ${detail.point_count} points</span></div>`;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 340 64");
    const x = (cents) => 12 + (cents / span) * 316;
    const baseline = document.createElementNS("http://www.w3.org/2000/svg", "line");
    baseline.setAttribute("x1", 12); baseline.setAttribute("x2", 328);
    baseline.setAttribute("y1", 40); baseline.setAttribute("y2", 40);
    baseline.setAttribute("class", "hd-axis-baseline");
    svg.appendChild(baseline);
    for (let grid = 0; grid <= Math.floor(span / 100); grid++) {
      const tick = document.createElementNS("http://www.w3.org/2000/svg", "line");
      tick.setAttribute("x1", x(grid * 100)); tick.setAttribute("x2", x(grid * 100));
      tick.setAttribute("y1", 36); tick.setAttribute("y2", 44);
      tick.setAttribute("class", "hd-axis-grid");
      svg.appendChild(tick);
    }
    for (const point of detail.points) {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", x(point.reduced_cents));
      circle.setAttribute("cy", 40);
      circle.setAttribute("r", 3.5);
      circle.setAttribute("fill", errorColor(point.signed_12edo_error_cents));
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `n=${point.n} ${point.reduced_ratio} ${point.reduced_cents.toFixed(2)}c (12-EDO ${point.signed_12edo_error_cents >= 0 ? "+" : ""}${point.signed_12edo_error_cents.toFixed(2)}c)`;
      circle.appendChild(title);
      svg.appendChild(circle);
    }
    card.appendChild(svg);
    card.addEventListener("click", () => {
      state.selectedAxis = Number(generator);
      el("hd-chord-axis").value = String(generator);
      state.chords.page = 0;
      renderAxes();
      loadChords();
    });
    container.appendChild(card);
  }
  el("hd-axes-summary").textContent = `${Object.keys(state.axes).length} axes · click to select`;
}

// ----------------------------------------------------------------- chords

async function loadChords() {
  const version = state.version;
  const generator = Number(el("hd-chord-axis").value) || state.config.axes[state.equave][0];
  const body = {
    equave: state.equave,
    generator,
    voice_count: Number(el("hd-voice-count").value),
    page: state.chords.page,
    page_size: 24,
    tonic: el("hd-chord-tonic").value.trim() || "1/1",
  };
  const template = el("hd-template").value.trim();
  if (template) body.template = template;
  const key = el("hd-key").value.trim();
  if (key) body.key = key;
  el("hd-entries").innerHTML = `<p class="hint">Loading…</p>`;
  try {
    const data = await postJson("/api/harmony-dictionary/chords", body);
    if (version !== state.version) return;
    state.chords.data = data;
    renderChords();
  } catch (error) {
    if (version === state.version) {
      state.chords.data = null;
      el("hd-entries").innerHTML = `<p class="hint hd-error">${error.message}</p>`;
      el("hd-chords-summary").textContent = "failed";
    }
  }
}

function renderChords() {
  const data = state.chords.data;
  const container = el("hd-entries");
  if (!data) { container.innerHTML = ""; return; }
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  el("hd-page-info").textContent = data.total ? `page ${data.page + 1}/${pages} · ${data.total} entries` : "no entries match the filters";
  el("hd-chords-summary").textContent = `${data.total} entries · tonic ${data.tonic}`;
  container.innerHTML = "";
  if (!data.total) {
    container.innerHTML = `<p class="hint">No entries match the current filters (template/key).</p>`;
    return;
  }
  for (const entry of data.entries) {
    const card = document.createElement("div");
    card.className = "hd-entry-card";
    let html = `<div class="hd-entry-head"><strong>${entry.key}</strong><span>${entry.variants.length} variants</span></div>`;
    for (const variant of entry.variants) {
      const stability = variant.stability_q;
      const label = stability >= data.thresholds.T_high ? "T" : stability <= data.thresholds.D_low ? "D" : "S";
      html += `<div class="hd-variant">`;
      html += `<span class="hd-variant-ratios">${variant.ratios.join(" · ")}</span>`;
      html += `<span class="hd-variant-meta">${variant.template}${variant.template_matched ? "" : " (≈)"} · ${variant.span_cents.toFixed(0)}c · q=${stability} <em class="hd-fn-${label.toLowerCase()}">${label}</em></span>`;
      html += `<span class="hd-variant-actions"><button data-mode="exact" data-ratios="${JSON.stringify(variant.ratios)}">Exact</button><button data-mode="edo" data-ratios="${JSON.stringify(variant.ratios)}">12-EDO</button></span>`;
      html += `</div>`;
    }
    card.innerHTML = html;
    for (const button of card.querySelectorAll("button[data-mode]")) {
      button.addEventListener("click", () => playRatios(JSON.parse(button.dataset.ratios), button.dataset.mode));
    }
    container.appendChild(card);
  }
}

// --------------------------------------------------------------- evaluate

function renderEvalVectors() {
  const container = el("hd-eval-vectors");
  const count = Number(el("hd-eval-voices").value);
  const basis = state.config ? state.config.axes[state.equave] : [3, 5, 7, 11, 13];
  container.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const row = document.createElement("div");
    row.className = "hd-vector-row";
    let html = `<span class="hd-vector-label">tone ${i}</span>`;
    for (let j = 0; j < 5; j++) {
      html += `<input class="hd-vector-input" data-tone="${i}" data-axis="${j}" value="0" inputmode="-" aria-label="tone ${i} axis ${basis[j]}">`;
    }
    html += `<input class="hd-register-input" data-tone="${i}" value="0" inputmode="-" aria-label="tone ${i} register">`;
    html += `<span class="hd-vector-basis">${basis.join("·")}</span>`;
    row.innerHTML = html;
    container.appendChild(row);
  }
}

function readEvalVectors() {
  const count = Number(el("hd-eval-voices").value);
  const vectors = [], registers = [];
  for (let i = 0; i < count; i++) {
    vectors.push([...el("hd-eval-vectors").querySelectorAll(`.hd-vector-input[data-tone="${i}"]`)].map((input) => Number(input.value || 0)));
    registers.push(Number(el("hd-eval-vectors").querySelector(`.hd-register-input[data-tone="${i}"]`).value || 0));
  }
  return { vectors, registers };
}

async function loadEvaluation() {
  const version = state.version;
  el("hd-eval-status").textContent = "Evaluating…";
  const { vectors, registers } = readEvalVectors();
  const body = { equave: state.equave, vectors, registers };
  const tonic = el("hd-eval-tonic").value.trim();
  if (tonic) body.tonic = tonic;
  try {
    const data = await postJson("/api/harmony-dictionary/evaluate", body);
    if (version !== state.version) return;
    state.evaluation = data;
    renderEvalResult();
  } catch (error) {
    if (version === state.version) {
      el("hd-eval-status").textContent = error.message;
      el("hd-eval-result").innerHTML = `<p class="hint hd-error">${error.message}</p>`;
    }
  }
}

function renderEvalResult() {
  const result = state.evaluation;
  const container = el("hd-eval-result");
  if (!result) { container.innerHTML = ""; return; }
  const codeClass = result.code === "OK" ? "" : " hd-error";
  let html = `<p class="hd-eval-code${codeClass}">${result.code}${result.discrepancy ? ` · ${result.discrepancy}` : ""}</p>`;
  html += `<dl class="hd-eval-root"><dt>Root</dt><dd>${result.root.ratio} (${result.root.hypothesis}${result.root.uncertain ? ", uncertain" : ""})</dd>`;
  html += `<dt>Tones</dt><dd>${result.tones.map((tone) => tone.ratio).join(" · ")}</dd></dl>`;
  html += `<div class="table-wrap hd-eval-table"><table><thead><tr><th>Axis</th><th>Max err</th><th>RMS</th><th>Voice loss</th><th>Gate</th></tr></thead><tbody>`;
  for (const axis of result.axes) {
    const selected = result.selected_axis === axis.axis;
    html += `<tr class="${selected ? "hd-row-selected" : ""}"><td>g=${axis.generator}${selected ? " ✓" : ""}</td><td>${axis.max_error_cents.toFixed(2)}c</td><td>${axis.rms_error_cents.toFixed(2)}c</td><td>${axis.voice_loss}</td><td>${axis.passes_gate ? "pass" : "fail"}</td></tr>`;
  }
  html += `</tbody></table></div>`;
  if (result.approximate) {
    html += `<p class="hint">Approximate: key ${result.approximate.key} → ${result.approximate.template}${result.approximate.dictionary_hit ? " (dictionary hit)" : " (no dictionary hit)"}</p>`;
  }
  if (result.exact) {
    html += `<p class="hint">Exact: ${result.exact.template}${result.exact.stability_q !== undefined ? ` · stability_q=${result.exact.stability_q}` : ""}</p>`;
  }
  if (result.root_hypotheses) {
    html += `<p class="hint">Root hypotheses: ${result.root_hypotheses.map((item) => `tone_${item.index} (rms ${item.rms_error_cents.toFixed(2)}c)`).join(" · ")}</p>`;
  }
  html += `<div class="button-row"><button id="hd-eval-play-exact">Play exact</button><button id="hd-eval-play-edo" class="quiet">Play 12-EDO</button></div>`;
  container.innerHTML = html;
  el("hd-eval-status").textContent = result.code === "OK" ? `selected axis ${result.selected_axis}` : result.code;
  el("hd-eval-play-exact").addEventListener("click", () => playRatios(result.relative_ratios, "exact"));
  el("hd-eval-play-edo").addEventListener("click", () => playRatios(result.relative_ratios, "edo"));
}

// ---------------------------------------------------------------- cadences

async function loadCadences() {
  const version = state.version;
  el("hd-cadence-status").textContent = "Generating…";
  const body = {
    equave: state.equave,
    tonic: el("hd-cadence-tonic").value.trim() || "1/1",
    kind: el("hd-cadence-kind").value,
    seed: Number(el("hd-cadence-seed").value || 0),
    count: Number(el("hd-cadence-count").value || 1),
  };
  try {
    const data = await postJson("/api/harmony-dictionary/cadences", body);
    if (version !== state.version) return;
    state.cadences = data;
    renderCadences();
  } catch (error) {
    if (version === state.version) {
      el("hd-cadence-status").textContent = error.message;
      el("hd-cadences").innerHTML = `<p class="hint hd-error">${error.message}</p>`;
    }
  }
}

function contourSvg(values) {
  const width = 340, height = 64;
  const x = (index) => 12 + (index / Math.max(1, values.length - 1)) * (width - 24);
  const y = (value) => height - 8 - (value / 10000) * (height - 20);
  const points = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  let svg = `<svg viewBox="0 0 ${width} ${height}" class="hd-contour"><polyline points="${points}" class="hd-contour-line"/>`;
  values.forEach((value, index) => { svg += `<circle cx="${x(index).toFixed(1)}" cy="${y(value).toFixed(1)}" r="3" class="hd-contour-dot"/>`; });
  return svg + `</svg>`;
}

function renderCadences() {
  const data = state.cadences;
  const container = el("hd-cadences");
  if (!data) { container.innerHTML = ""; return; }
  container.innerHTML = "";
  data.cadences.forEach((cadence, index) => {
    const card = document.createElement("div");
    card.className = "hd-cadence-card";
    let html = `<div class="hd-cadence-head"><strong>${cadence.kind} #${index} (seed ${cadence.seed})</strong><span>${cadence.code}${cadence.failure_reason ? ` · ${cadence.failure_reason}` : ""}</span></div>`;
    if (cadence.code === "OK") {
      html += `<div class="hd-cadence-timeline">`;
      for (const chord of cadence.chords) {
        html += `<span class="hd-chord-box hd-fn-${chord.function.toLowerCase()}"><strong>${chord.function}</strong><small>${chord.template}</small><small>root ${chord.root_ratio}</small></span>`;
      }
      html += `</div>`;
      const contour = cadence.diagnostics.stability_contour;
      html += `<div class="hd-cadence-contour">${contourSvg(contour)}<span class="hint">stability contour: ${contour.join(" → ")}</span></div>`;
      const landing = cadence.diagnostics.final_landing;
      const voice = cadence.diagnostics.voice_leading;
      const tendency = cadence.diagnostics.tendency_resolution;
      html += `<p class="hint">landing: ${landing.lands ? "✓" : "✗"} (${landing.final_root}) · voice leading: ${voice.every((item) => item.within_cap) ? "within cap" : "cap exceeded"} · tendency: ${tendency.all_resolved ? "all resolved" : `${tendency.final_unresolved_voices} dangling`}</p>`;
      html += `<p class="hint">T/D/S: ${cadence.classifications.map((item) => `${item.candidate}→${item.final}`).join(" · ")}</p>`;
      html += `<div class="button-row"><button data-cadence="${index}">Play cadence</button></div>`;
    }
    card.innerHTML = html;
    const button = card.querySelector("button[data-cadence]");
    if (button) button.addEventListener("click", () => playCadence(cadence));
    container.appendChild(card);
  });
  renderCadenceReport(data.report);
  el("hd-cadence-status").textContent = `${data.cadences.length} cadence(s) · coverage ${(data.report.coverage * 100).toFixed(0)}%`;
}

function renderCadenceReport(report) {
  const container = el("hd-cadence-report");
  if (!report || !report.chord_count) { container.innerHTML = ""; return; }
  const rows = ["tonic", "dominant", "subdominant"];
  const columns = ["tonic", "dominant", "subdominant", "ambiguous"];
  let html = `<div class="hd-report-grid"><div><h3>Confusion matrix (truth × final)</h3><table class="hd-matrix"><thead><tr><th></th>${columns.map((column) => `<th>${column}</th>`).join("")}</tr></thead><tbody>`;
  for (const row of rows) {
    html += `<tr><td>${row}</td>${columns.map((column) => `<td>${report.confusion_matrix[row][column]}</td>`).join("")}</tr>`;
  }
  html += `</tbody></table></div><div><h3>Coverage &amp; I/IV</h3>`;
  html += `<p class="hint">${report.chord_count} chords · coverage ${(report.coverage * 100).toFixed(1)}%</p>`;
  if (report.iv_misclassification_examples.length) {
    html += `<p class="hint">I/IV examples: ${report.iv_misclassification_examples.map((item) => `${item.function} root=${item.root} q=${item.stability_q}→${item.final}`).join(" · ")}</p>`;
  } else {
    html += `<p class="hint">No I/IV misclassifications.</p>`;
  }
  html += `</div></div>`;
  container.innerHTML = html;
}

async function playCadence(cadence) {
  stopAudio();
  const context = audioContext();
  if (context.state === "suspended") context.resume();
  const base = Number(el("hd-base-frequency").value);
  let at = context.currentTime + 0.05;
  for (const chord of cadence.chords) {
    const rootCents = ratioToCents(chord.root_ratio);
    const gainPerVoice = 0.12 / Math.sqrt(chord.ratios.length);
    for (const ratio of chord.ratios) {
      const oscillator = context.createOscillator(), gain = context.createGain();
      oscillator.type = el("hd-waveform").value;
      oscillator.frequency.value = base * 2 ** ((rootCents + ratioToCents(ratio)) / 1200);
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(gainPerVoice, at + 0.02);
      gain.gain.setTargetAtTime(0.0001, at + 0.9, 0.12);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(at);
      oscillator.stop(at + 1.25);
      state.voices.push(oscillator);
    }
    at += 1.3;
  }
}

// ----------------------------------------------------------- save / load

function saveSession() {
  const file = state.config ? state.config.files[state.equave] : null;
  const payload = {
    schema_version: 1,
    saved_at: new Date().toISOString(),
    equave: state.equave,
    file_hash: file && file.available ? file.hash : null,
    stability_profile_hash: file && file.available ? file.stability_profile_hash : null,
    chords: { filters: { axis: el("hd-chord-axis").value, voice_count: el("hd-voice-count").value, template: el("hd-template").value, key: el("hd-key").value, tonic: el("hd-chord-tonic").value }, data: state.chords.data },
    evaluation: { inputs: { tonic: el("hd-eval-tonic").value, voices: el("hd-eval-voices").value, vectors: readEvalVectors().vectors, registers: readEvalVectors().registers }, result: state.evaluation },
    cadences: { inputs: { tonic: el("hd-cadence-tonic").value, kind: el("hd-cadence-kind").value, seed: el("hd-cadence-seed").value, count: el("hd-cadence-count").value }, data: state.cadences },
  };
  localStorage.setItem("harmony-dictionary-v1", JSON.stringify(payload));
  status("Session saved (with profile hash)");
}

function loadSession() {
  try {
    const saved = JSON.parse(localStorage.getItem("harmony-dictionary-v1") || "null");
    if (!saved) throw new Error("No saved session");
    state.equave = saved.equave || "2/1";
    el("hd-equave").value = state.equave;
    if (saved.chords && saved.chords.filters) {
      el("hd-chord-axis").value = saved.chords.filters.axis || "";
      el("hd-voice-count").value = saved.chords.filters.voice_count || "3";
      el("hd-template").value = saved.chords.filters.template || "";
      el("hd-key").value = saved.chords.filters.key || "";
      el("hd-chord-tonic").value = saved.chords.filters.tonic || "1/1";
    }
    if (saved.evaluation && saved.evaluation.inputs) {
      el("hd-eval-tonic").value = saved.evaluation.inputs.tonic || "1/1";
      el("hd-eval-voices").value = saved.evaluation.inputs.voices || "3";
      renderEvalVectors();
      saved.evaluation.inputs.vectors.forEach((vector, i) => vector.forEach((value, j) => {
        const input = el("hd-eval-vectors").querySelector(`.hd-vector-input[data-tone="${i}"][data-axis="${j}"]`);
        if (input) input.value = String(value);
      }));
    }
    if (saved.cadences && saved.cadences.inputs) {
      el("hd-cadence-tonic").value = saved.cadences.inputs.tonic || "1/1";
      el("hd-cadence-kind").value = saved.cadences.inputs.kind || "authentic";
      el("hd-cadence-seed").value = saved.cadences.inputs.seed || "0";
      el("hd-cadence-count").value = saved.cadences.inputs.count || "1";
    }
    state.version++;
    state.selectedAxis = Number(el("hd-chord-axis").value) || null;
    state.chords.page = 0;
    loadConfig().then(() => { loadAxes(); loadChords(); });
    status(`Session loaded${saved.file_hash ? ` (hash ${saved.file_hash.slice(0, 14)}…)` : ""}`);
  } catch (error) {
    status(error.message, "error");
  }
}

// ------------------------------------------------------------------- init

function init() {
  el("hd-equave").addEventListener("change", () => {
    state.equave = el("hd-equave").value;
    state.version++;
    state.selectedAxis = null;
    state.chords.page = 0;
    stopAudio();
    renderEvalVectors();
    loadConfig().then(() => { loadAxes(); loadChords(); });
  });
  el("hd-chord-axis").addEventListener("change", () => {
    state.selectedAxis = Number(el("hd-chord-axis").value);
    state.chords.page = 0;
    renderAxes();
    loadChords();
  });
  for (const id of ["hd-voice-count", "hd-template", "hd-key", "hd-chord-tonic"]) {
    el(id).addEventListener("change", () => { state.chords.page = 0; loadChords(); });
    el(id).addEventListener("keydown", (event) => { if (event.key === "Enter") { state.chords.page = 0; loadChords(); } });
  }
  el("hd-page-prev").addEventListener("click", () => { state.chords.page = Math.max(0, state.chords.page - 1); loadChords(); });
  el("hd-page-next").addEventListener("click", () => { state.chords.page += 1; loadChords(); });
  el("hd-base-frequency").addEventListener("input", () => { el("hd-base-value").textContent = `${el("hd-base-frequency").value} Hz`; });
  el("hd-eval-voices").addEventListener("change", renderEvalVectors);
  el("hd-evaluate").addEventListener("click", loadEvaluation);
  el("hd-eval-tonic").addEventListener("keydown", (event) => { if (event.key === "Enter") loadEvaluation(); });
  el("hd-generate-cadence").addEventListener("click", loadCadences);
  el("hd-cadence-tonic").addEventListener("keydown", (event) => { if (event.key === "Enter") loadCadences(); });
  el("hd-save").addEventListener("click", saveSession);
  el("hd-load").addEventListener("click", loadSession);
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;
    if (event.key === "[") { state.chords.page = Math.max(0, state.chords.page - 1); loadChords(); }
    if (event.key === "]") { state.chords.page += 1; loadChords(); }
  });
  renderEvalVectors();
  loadConfig().then(() => { loadAxes(); loadChords(); });
}

document.addEventListener("DOMContentLoaded", init);
