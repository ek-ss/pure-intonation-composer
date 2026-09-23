const el = id => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";

// ---------- constants ----------
const MAX_INPUT_BYTES = 20 * 1024 * 1024;
const SUPPORTED_PROJECT_VERSIONS = ["1.2.0", "1.3.0"];
const SUPPORTED_PLAN_VERSIONS = ["2.0.0"];
const MAX_DIMS = 5;
const PALETTE = ["#98e7ca", "#83b7ff", "#caa8ff", "#ffd47e", "#ff9d9a", "#a9b9ff", "#7ee0d2", "#e3a8ff"];

// ---------- state ----------
const state = {
  project: null,
  plan: null,
  model: null,
  planModel: null,
  errors: [],
  warnings: [],
  selection: -1,
  view: "lattice",
  axisX: 0,
  axisY: 1,
  sectionFilter: "all",
  collapse: true,
};

// ---------- pure helpers ----------
function isInt(value) { return Number.isInteger(value); }
function isRatioText(value) { return typeof value === "string" && /^[1-9][0-9]*\/[1-9][0-9]*$/.test(value); }
function parseRatio(text) {
  if (!isRatioText(text)) return null;
  const [num, den] = text.split("/").map(Number);
  return { num, den };
}
function ratioCents(text) { const ratio = parseRatio(text); if (!ratio) return null; return 1200 * Math.log2(ratio.num / ratio.den); }
function isIntVector(value, dims) { return Array.isArray(value) && value.length === dims && value.every(isInt); }
function bigGcd(a, b) { while (b) { [a, b] = [b, a % b]; } return a; }
function rootRatio(generators, anchor) {
  let num = 1n, den = 1n;
  for (let j = 0; j < generators.length; j++) {
    const ratio = parseRatio(generators[j]);
    if (!ratio) return null;
    const exp = isInt(anchor[j]) ? anchor[j] : 0;
    if (exp >= 0) { num *= BigInt(ratio.num) ** BigInt(exp); den *= BigInt(ratio.den) ** BigInt(exp); }
    else { num *= BigInt(ratio.den) ** BigInt(-exp); den *= BigInt(ratio.num) ** BigInt(-exp); }
  }
  const g = bigGcd(num, den);
  return { num: num / g, den: den / g };
}
function rootRatioText(generators, anchor) { const ratio = rootRatio(generators, anchor); return ratio ? `${ratio.num}/${ratio.den}` : "?"; }
function rootCents(generators, anchor) { const ratio = rootRatio(generators, anchor); if (!ratio) return null; return 1200 * Math.log2(Number(ratio.num) / Number(ratio.den)); }
function equaveCents(equaveText) { return ratioCents(equaveText); }
function circlePosition(cents, equaveC) { return (((cents % equaveC) + equaveC) % equaveC) / equaveC; }
function circleAngle(cents, equaveC) { return circlePosition(cents, equaveC) * Math.PI * 2 - Math.PI / 2; }
function chordColor(chordId) { let hash = 0; for (const ch of String(chordId)) hash = (hash * 31 + ch.charCodeAt(0)) | 0; return PALETTE[Math.abs(hash) % PALETTE.length]; }
function referenceLabel(chord) { return `${chord.reference_divisions}分割参照 [${(chord.canonical_steps || []).join(",")}]`; }
// ---------- validation ----------
function validateProject(data) {
  const errors = [];
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return { errors: ["入力は JSON オブジェクトである必要があります。"], dims: 0 };
  }
  if (data.schema !== "cps.arrangement-project") errors.push(`schema が "${data.schema ?? ""}" です（cps.arrangement-project を期待）。`);
  if (!SUPPORTED_PROJECT_VERSIONS.includes(data.schema_version)) errors.push(`未対応の schema_version "${data.schema_version ?? ""}"（対応: ${SUPPORTED_PROJECT_VERSIONS.join(", ")}）。`);
  let dims = 0;
  const lattice = data.lattice;
  if (!lattice || typeof lattice !== "object") errors.push("lattice が欠落しています。");
  else {
    if (!isRatioText(lattice.equave)) errors.push("lattice.equave が有効な比率ではありません。");
    if (!Array.isArray(lattice.generators) || lattice.generators.length < 1 || lattice.generators.length > MAX_DIMS || !lattice.generators.every(isRatioText)) {
      errors.push(`lattice.generators は 1〜${MAX_DIMS} 個の比率文字列である必要があります。`);
    } else dims = lattice.generators.length;
  }
  const clock = data.clock;
  if (!clock || typeof clock !== "object" || !isInt(clock.ticks_per_beat) || clock.ticks_per_beat < 1 || !isInt(clock.beats_per_bar) || clock.beats_per_bar < 1 || !isInt(clock.bars) || clock.bars < 1 || !isInt(clock.total_ticks) || clock.total_ticks < 1) {
    errors.push("clock のフィールドが不正です。");
  }
  const chordIds = new Set();
  if (!Array.isArray(data.resolved_chords) || data.resolved_chords.length < 1) errors.push("resolved_chords が空または欠落しています。");
  else data.resolved_chords.forEach((chord, i) => {
    if (typeof chord.id !== "string" || !chord.id) { errors.push(`resolved_chords[${i}].id が欠落しています。`); return; }
    if (chordIds.has(chord.id)) errors.push(`resolved_chords[${i}].id "${chord.id}" が重複しています。`);
    chordIds.add(chord.id);
    if (dims && !isIntVector(chord.anchor_vector, dims)) errors.push(`resolved_chords[${i}].anchor_vector が ${dims} 次元の整数ベクトルではありません。`);
    const voices = Array.isArray(chord.voice_offsets) ? chord.voice_offsets.length : -1;
    if (voices < 2 || voices > 8) errors.push(`resolved_chords[${i}].voice_offsets は 2〜8 声である必要があります。`);
    else if (dims && !chord.voice_offsets.every(vector => isIntVector(vector, dims))) errors.push(`resolved_chords[${i}].voice_offsets に次元不一致があります。`);
    if (!Array.isArray(chord.equave_exponents) || chord.equave_exponents.length !== voices || !chord.equave_exponents.every(isInt)) errors.push(`resolved_chords[${i}].equave_exponents が不正です。`);
    if (!Array.isArray(chord.exact_ratios) || chord.exact_ratios.length !== voices || !chord.exact_ratios.every(isRatioText)) errors.push(`resolved_chords[${i}].exact_ratios が不正です。`);
  });
  if (!Array.isArray(data.harmony_occurrences)) errors.push("harmony_occurrences が欠落しています。");
  else data.harmony_occurrences.forEach((occ, i) => {
    if (!chordIds.has(occ.resolved_chord_id)) errors.push(`harmony_occurrences[${i}].resolved_chord_id "${occ.resolved_chord_id}" が存在しません。`);
    if (!isInt(occ.start_tick) || occ.start_tick < 0) errors.push(`harmony_occurrences[${i}].start_tick が不正です。`);
    if (!isInt(occ.duration_ticks) || occ.duration_ticks < 1) errors.push(`harmony_occurrences[${i}].duration_ticks が不正です。`);
    if (clock && isInt(clock.total_ticks) && isInt(occ.start_tick) && isInt(occ.duration_ticks) && occ.start_tick + occ.duration_ticks > clock.total_ticks) errors.push(`harmony_occurrences[${i}] が total_ticks を超えています。`);
  });
  if (!Array.isArray(data.form) || data.form.length < 1) errors.push("form が空または欠落しています。");
  else data.form.forEach((section, i) => {
    if (typeof section.id !== "string" || !section.id || typeof section.role !== "string" || !isInt(section.start_bar) || section.start_bar < 0 || !isInt(section.bars) || section.bars < 1) errors.push(`form[${i}] が不正です。`);
  });
  return { errors, dims };
}

function validatePlan(data, project) {
  const errors = [];
  if (typeof data !== "object" || data === null || Array.isArray(data)) return { errors: ["計画は JSON オブジェクトである必要があります。"] };
  if (data.schema !== "cps.composition-plan") errors.push(`計画の schema が "${data.schema ?? ""}" です（cps.composition-plan を期待）。`);
  if (!SUPPORTED_PLAN_VERSIONS.includes(data.schema_version)) errors.push(`未対応の計画 schema_version "${data.schema_version ?? ""}"（対応: ${SUPPORTED_PLAN_VERSIONS.join(", ")}）。`);
  if (!Array.isArray(data.sections) || data.sections.length < 1 || !Array.isArray(data.harmonic_trajectory)) return { errors };
  const projectSectionIds = new Set(project.form.map(section => section.id));
  const planSectionIds = new Set(data.sections.map(section => section.section_id));
  const projectTotalBars = project.form.reduce((sum, section) => sum + section.bars, 0);
  if (!isInt(data.total_bars) || data.total_bars !== projectTotalBars) errors.push(`計画の total_bars ${data.total_bars} が Project の ${projectTotalBars} と一致しません。`);
  for (const id of planSectionIds) if (!projectSectionIds.has(id)) errors.push(`計画の section "${id}" が Project に存在しません。`);
  for (const id of projectSectionIds) if (!planSectionIds.has(id)) errors.push(`Project の section "${id}" が計画に存在しません。`);
  const phraseIds = new Set();
  data.sections.forEach((section, i) => {
    if (!Array.isArray(section.phrases)) { errors.push(`計画 sections[${i}].phrases が欠落しています。`); return; }
    section.phrases.forEach((phrase, j) => {
      if (typeof phrase.phrase_id !== "string" || phraseIds.has(phrase.phrase_id)) errors.push(`計画の phrase_id "${phrase.phrase_id}" が重複しています。`);
      phraseIds.add(phrase.phrase_id);
      if (!isInt(phrase.start_bar) || phrase.start_bar < 0 || !isInt(phrase.length_bars) || phrase.length_bars < 1 || phrase.start_bar + phrase.length_bars > section.bars) errors.push(`計画 ${section.section_id} の phrase[${j}] が section 範囲を超えています。`);
    });
  });
  data.harmonic_trajectory.forEach((entry, i) => {
    if (!phraseIds.has(entry.phrase_id)) errors.push(`harmonic_trajectory[${i}].phrase_id "${entry.phrase_id}" が計画に存在しません。`);
  });
  return { errors };
}
// ---------- model ----------
function buildModel(project) {
  const clock = project.clock;
  const ticksPerBar = clock.ticks_per_beat * clock.beats_per_bar;
  const totalBars = clock.total_ticks / ticksPerBar;
  const chordsById = new Map(project.resolved_chords.map(chord => [chord.id, chord]));
  const lattice = project.lattice;
  const equaveC = equaveCents(lattice.equave) ?? 1200;
  const occurrences = project.harmony_occurrences
    .map((occ, index) => ({
      index,
      chordIndex: occ.chord_index,
      chord: chordsById.get(occ.resolved_chord_id),
      sectionId: occ.section_id,
      startTick: occ.start_tick,
      durationTicks: occ.duration_ticks,
      startBar: occ.start_tick / ticksPerBar,
      durationBars: occ.duration_ticks / ticksPerBar,
    }))
    .sort((a, b) => a.startTick - b.startTick || a.index - b.index);
  return { project, clock, ticksPerBar, totalBars, lattice, equaveC, chordsById, occurrences };
}

function buildPlanModel(plan, project) {
  const formById = new Map(project.form.map(section => [section.id, section]));
  const trajectoryByPhrase = new Map(plan.harmonic_trajectory.map(entry => [entry.phrase_id, entry]));
  const phrases = [];
  for (const section of plan.sections) {
    const formSection = formById.get(section.section_id);
    if (!formSection) continue;
    for (const phrase of section.phrases) {
      const entry = trajectoryByPhrase.get(phrase.phrase_id);
      phrases.push({
        phraseId: phrase.phrase_id,
        sectionId: section.section_id,
        startBar: formSection.start_bar + phrase.start_bar,
        lengthBars: phrase.length_bars,
        stateId: entry ? entry.state_id : null,
        harmonicFunction: entry ? entry.harmonic_function : null,
        rootDegreeOrdinal: entry ? entry.root_degree_ordinal : null,
      });
    }
  }
  return { phrases: phrases.sort((a, b) => a.startBar - b.startBar || a.phraseId.localeCompare(b.phraseId)) };
}

function filteredOccurrences() {
  if (!state.model) return [];
  const all = state.model.occurrences;
  if (state.sectionFilter === "all") return all;
  return all.filter(occ => occ.sectionId === state.sectionFilter);
}

function isSelectedChord(chord) {
  return state.selection >= 0 && state.model.occurrences[state.selection]?.chord.id === chord.id;
}

function isDimmedChord(chord) {
  if (state.sectionFilter === "all") return false;
  return !state.model.occurrences.some(occ => occ.chord.id === chord.id && occ.sectionId === state.sectionFilter);
}

function isDimmedOccurrence(occ) {
  return state.sectionFilter !== "all" && occ.sectionId !== state.sectionFilter;
}
// ---------- svg helpers ----------
function svgEl(name, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (parent) parent.append(node);
  return node;
}
function svgText(parent, x, y, text, attrs = {}) {
  const node = svgEl("text", Object.assign({ x, y }, attrs), parent);
  node.textContent = text;
  return node;
}
function clearSvg(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

// ---------- timeline ----------
function collapseRuns(occurrences) {
  const runs = [];
  for (const occ of occurrences) {
    const last = runs[runs.length - 1];
    if (last && last.last.chord.id === occ.chord.id && Math.abs(last.last.startBar + last.last.durationBars - occ.startBar) < 1e-9) {
      last.last = occ;
      last.occurrences.push(occ);
    } else {
      runs.push({ first: occ, last: occ, occurrences: [occ] });
    }
  }
  return runs;
}

function runToItem(run) {
  return { startBar: run.first.startBar, durationBars: run.last.startBar + run.last.durationBars - run.first.startBar, occ: run.first, sectionId: run.first.sectionId, chord: run.first.chord };
}

function splitRunAtSections(run, sections) {
  const start = run.first.startBar;
  const end = run.last.startBar + run.last.durationBars;
  const pieces = [];
  for (const section of sections) {
    const s0 = Math.max(start, section.start_bar);
    const s1 = Math.min(end, section.start_bar + section.bars);
    if (s1 - s0 < 1e-9) continue;
    let occ = run.first;
    for (const o of run.occurrences) { if (o.startBar >= s0 - 1e-9) { occ = o; break; } }
    pieces.push({ startBar: s0, durationBars: s1 - s0, occ, sectionId: section.id, chord: run.first.chord });
  }
  return pieces.length ? pieces : [runToItem(run)];
}

function assignLanes(items) {
  const laneEnds = [];
  for (const item of items) {
    let lane = laneEnds.findIndex(end => end <= item.startBar + 1e-9);
    if (lane === -1) { lane = laneEnds.length; laneEnds.push(0); }
    laneEnds[lane] = item.startBar + item.durationBars;
    item.lane = lane;
  }
  return Math.max(1, laneEnds.length);
}

function renderTimeline() {
  const svg = el("shv-timeline");
  clearSvg(svg);
  const summary = el("shv-timeline-summary");
  if (!state.model) {
    svg.setAttribute("viewBox", "0 0 1200 200");
    svgText(svg, 20, 40, "project.json を読み込んでください。", { class: "shv-placeholder" });
    summary.textContent = "";
    return;
  }
  const model = state.model;
  const W = 1200, H = 200, left = 46, right = W - 14;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const totalBars = model.totalBars;
  const x = bar => left + (bar / totalBars) * (right - left);
  let y = 10;
  if (state.planModel) {
    svgText(svg, left - 34, y + 11, "plan", { class: "shv-tl-label" });
    for (const phrase of state.planModel.phrases) {
      const x0 = x(phrase.startBar), x1 = x(phrase.startBar + phrase.lengthBars);
      svgEl("rect", { x: x0, y, width: Math.max(1, x1 - x0), height: 16, class: "shv-plan-band" }, svg);
      if (x1 - x0 > 52) {
        const label = [phrase.stateId, phrase.harmonicFunction].filter(Boolean).join(" ");
        svgText(svg, (x0 + x1) / 2, y + 11, label, { class: "shv-plan-label", "text-anchor": "middle" });
      }
    }
    y += 24;
  }
  for (const section of model.project.form) {
    const x0 = x(section.start_bar), x1 = x(section.start_bar + section.bars);
    svgEl("rect", { x: x0, y, width: Math.max(1, x1 - x0), height: 18, class: "shv-section-band" }, svg);
    if (x1 - x0 > 44) svgText(svg, (x0 + x1) / 2, y + 12, `${section.id} ${section.role}`, { class: "shv-section-label", "text-anchor": "middle" });
  }
  y += 26;
  const all = model.occurrences;
  const items = state.collapse
    ? collapseRuns(all).flatMap(run => (state.sectionFilter === "all" ? [runToItem(run)] : splitRunAtSections(run, model.project.form)))
    : all.map(occ => ({ startBar: occ.startBar, durationBars: occ.durationBars, occ, sectionId: occ.sectionId, chord: occ.chord }));
  const laneCount = assignLanes(items);
  const laneHeight = Math.min(16, (H - y - 24) / laneCount);
  for (const item of items) {
    const x0 = x(item.startBar), x1 = x(item.startBar + item.durationBars);
    const selected = state.selection >= 0 && model.occurrences[state.selection] === item.occ;
    const dimmed = state.sectionFilter !== "all" && item.sectionId !== state.sectionFilter;
    const rect = svgEl("rect", { x: x0, y: y + item.lane * laneHeight, width: Math.max(1.5, x1 - x0), height: Math.max(3, laneHeight - 2), class: `shv-occ${selected ? " selected" : ""}${dimmed ? " dimmed" : ""}`, fill: chordColor(item.chord.id) }, svg);
    if (x1 - x0 > 64) svgText(svg, (x0 + x1) / 2, y + item.lane * laneHeight + Math.max(3, laneHeight - 2) / 2 + 3, referenceLabel(item.chord), { class: "shv-occ-label", "text-anchor": "middle" });
    rect.addEventListener("click", () => selectOccurrence(model.occurrences.indexOf(item.occ)));
  }
  const axisY = H - 14;
  svgEl("line", { x1: left, y1: axisY - 4, x2: right, y2: axisY - 4, class: "shv-axis-line" }, svg);
  const step = Math.max(1, Math.round(totalBars / 16));
  for (let bar = 0; bar <= totalBars + 1e-9; bar += step) svgText(svg, x(bar), axisY + 4, String(Math.round(bar)), { class: "shv-axis-label", "text-anchor": "middle" });
  summary.textContent = `${model.project.form.length} sections · ${model.occurrences.length} occurrences · ${model.project.resolved_chords.length} chords`;
}
// ---------- projection ----------
function renderProjection() {
  const svg = el("shv-projection");
  clearSvg(svg);
  const title = el("shv-projection-title");
  if (!state.model) {
    title.textContent = state.view === "circle" ? "Pitch circle" : "Lattice 射影";
    svg.setAttribute("viewBox", "0 0 640 520");
    svgText(svg, 20, 40, "project.json を読み込んでください。", { class: "shv-placeholder" });
    el("shv-projection-summary").textContent = "";
    renderLegend();
    return;
  }
  if (state.view === "circle") { title.textContent = "Pitch circle"; renderCircle(svg); }
  else { title.textContent = "Lattice 射影"; renderLattice(svg); }
  renderLegend();
}

function renderLattice(svg) {
  const model = state.model;
  const dims = model.lattice.generators.length;
  const axX = Math.min(state.axisX, dims - 1);
  const axY = Math.min(state.axisY, dims - 1);
  const W = 640, H = 520, margin = 46;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const points = [];
  for (const chord of model.project.resolved_chords) {
    points.push({ kind: "root", chord, vector: chord.anchor_vector });
    chord.voice_offsets.forEach((offset, voice) => {
      points.push({ kind: "voice", chord, voice, vector: chord.anchor_vector.map((v, j) => v + offset[j]) });
    });
  }
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const point of points) {
    minX = Math.min(minX, point.vector[axX]); maxX = Math.max(maxX, point.vector[axX]);
    minY = Math.min(minY, point.vector[axY]); maxY = Math.max(maxY, point.vector[axY]);
  }
  if (!Number.isFinite(minX)) { minX = -1; maxX = 1; minY = -1; maxY = 1; }
  minX -= 1; maxX += 1; minY -= 1; maxY += 1;
  const scale = Math.min((W - margin * 2) / Math.max(1, maxX - minX), (H - margin * 2) / Math.max(1, maxY - minY));
  const px = value => margin + (value - minX) * scale + ((W - margin * 2) - (maxX - minX) * scale) / 2;
  const py = value => H - margin - (value - minY) * scale - ((H - margin * 2) - (maxY - minY) * scale) / 2;
  for (let gx = Math.ceil(minX); gx <= Math.floor(maxX); gx++) svgEl("line", { x1: px(gx), y1: margin / 2, x2: px(gx), y2: H - margin / 2, class: "shv-grid" }, svg);
  for (let gy = Math.ceil(minY); gy <= Math.floor(maxY); gy++) svgEl("line", { x1: margin / 2, y1: py(gy), x2: W - margin / 2, y2: py(gy), class: "shv-grid" }, svg);
  svgText(svg, W - margin / 2, H - margin / 2 + 16, `X: ${model.lattice.generators[axX]}`, { class: "shv-axis-label", "text-anchor": "middle" });
  svgText(svg, margin / 2 - 10, H / 2, `Y: ${model.lattice.generators[axY]}`, { class: "shv-axis-label", "text-anchor": "middle", transform: `rotate(-90 ${margin / 2 - 10} ${H / 2})` });
  for (const point of points) {
    if (point.kind !== "voice") continue;
    const selected = isSelectedChord(point.chord);
    svgEl("circle", { cx: px(point.vector[axX]), cy: py(point.vector[axY]), r: selected ? 5 : 3, class: `shv-voice${selected ? " selected" : ""}`, fill: chordColor(point.chord.id) }, svg);
  }
  const occurrences = model.occurrences;
  for (let i = 0; i + 1 < occurrences.length; i++) {
    const a = occurrences[i].chord, b = occurrences[i + 1].chord;
    if (a.id === b.id) continue;
    const x0 = px(a.anchor_vector[axX]), y0 = py(a.anchor_vector[axY]);
    const x1 = px(b.anchor_vector[axX]), y1 = py(b.anchor_vector[axY]);
    const dimmed = isDimmedOccurrence(occurrences[i]) || isDimmedOccurrence(occurrences[i + 1]);
    svgEl("line", { x1: x0, y1: y0, x2: x1, y2: y1, class: `shv-root-line${dimmed ? " dimmed" : ""}` }, svg);
    const delta = a.anchor_vector.map((v, j) => b.anchor_vector[j] - v);
    svgText(svg, (x0 + x1) / 2, (y0 + y1) / 2 - 5, `Δ(${delta.join(",")})`, { class: "shv-delta-label", "text-anchor": "middle" });
  }
  for (const point of points) {
    if (point.kind !== "root") continue;
    const selected = isSelectedChord(point.chord);
    const dimmed = isDimmedChord(point.chord);
    svgEl("circle", { cx: px(point.vector[axX]), cy: py(point.vector[axY]), r: selected ? 8 : 5, class: `shv-root${selected ? " selected" : ""}${dimmed ? " dimmed" : ""}`, fill: chordColor(point.chord.id) }, svg);
    if (selected) svgText(svg, px(point.vector[axX]), py(point.vector[axY]) - 12, `(${point.vector.join(",")})`, { class: "shv-root-label", "text-anchor": "middle" });
  }
  el("shv-projection-summary").textContent = `${model.project.resolved_chords.length} roots · ${points.length - model.project.resolved_chords.length} voices`;
}
// ---------- pitch circle ----------
function renderCircle(svg) {
  const model = state.model;
  const W = 640, H = 520, mid = W / 2, radius = Math.min(W, H) / 2 - 64;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svgEl("circle", { cx: mid, cy: mid, r: radius, class: "shv-ring" }, svg);
  svgText(svg, mid, mid - 6, `1/1 · ${model.lattice.equave} equave`, { class: "shv-circle-title", "text-anchor": "middle" });
  svgText(svg, mid, mid + 12, `${model.equaveC.toFixed(1)} cents`, { class: "shv-circle-subtitle", "text-anchor": "middle" });
  const pointAt = (cents, ringOffset = 0) => {
    const angle = circleAngle(cents, model.equaveC);
    const r = radius + ringOffset;
    return { x: mid + Math.cos(angle) * r, y: mid + Math.sin(angle) * r };
  };
  const occurrences = model.occurrences;
  for (let i = 0; i + 1 < occurrences.length; i++) {
    const a = occurrences[i].chord, b = occurrences[i + 1].chord;
    if (a.id === b.id) continue;
    const ca = rootCents(model.lattice.generators, a.anchor_vector);
    const cb = rootCents(model.lattice.generators, b.anchor_vector);
    if (ca === null || cb === null) continue;
    const p0 = pointAt(ca), p1 = pointAt(cb);
    const dimmed = isDimmedOccurrence(occurrences[i]) || isDimmedOccurrence(occurrences[i + 1]);
    svgEl("line", { x1: p0.x, y1: p0.y, x2: p1.x, y2: p1.y, class: `shv-root-line${dimmed ? " dimmed" : ""}` }, svg);
    const delta = a.anchor_vector.map((v, j) => b.anchor_vector[j] - v);
    svgText(svg, (p0.x + p1.x) / 2, (p0.y + p1.y) / 2 - 5, `Δ(${delta.join(",")})`, { class: "shv-delta-label", "text-anchor": "middle" });
  }
  for (const chord of model.project.resolved_chords) {
    const cents = rootCents(model.lattice.generators, chord.anchor_vector);
    if (cents === null) continue;
    const point = pointAt(cents);
    const selected = isSelectedChord(chord);
    const dimmed = isDimmedChord(chord);
    svgEl("circle", { cx: point.x, cy: point.y, r: selected ? 8 : 5, class: `shv-root${selected ? " selected" : ""}${dimmed ? " dimmed" : ""}`, fill: chordColor(chord.id) }, svg);
  }
  const occ = state.selection >= 0 ? occurrences[state.selection] : null;
  if (occ) {
    const chord = occ.chord;
    const positions = chord.exact_ratios.map((ratio, i) => {
      const cents = ratioCents(ratio);
      return { i, cents: cents === null ? 0 : cents, pos: cents === null ? 0 : circlePosition(cents, model.equaveC), exponent: chord.equave_exponents[i] };
    });
    const clusters = [];
    for (const item of positions) {
      let cluster = clusters.find(c => Math.abs(c.pos - item.pos) < 1e-9 || Math.abs(c.pos - item.pos) > 1 - 1e-9);
      if (!cluster) { cluster = { pos: item.pos, items: [] }; clusters.push(cluster); }
      cluster.items.push(item);
    }
    for (const cluster of clusters) {
      cluster.items.sort((a, b) => a.exponent - b.exponent);
      cluster.items.forEach((item, rank) => {
        const offset = (rank - (cluster.items.length - 1) / 2) * 14;
        const point = pointAt(item.cents, offset);
        svgEl("circle", { cx: point.x, cy: point.y, r: 6, class: "shv-voice selected", fill: chordColor(chord.id) }, svg);
        const angle = circleAngle(item.cents, model.equaveC);
        const lx = mid + Math.cos(angle) * (radius + 24 + offset);
        const ly = mid + Math.sin(angle) * (radius + 24 + offset);
        const label = `${chord.exact_ratios[item.i]}${offset ? ` e${item.exponent}` : ""}`;
        svgText(svg, lx, ly + 3, label, { class: "shv-voice-label", "text-anchor": "middle" });
      });
    }
  }
  el("shv-projection-summary").textContent = `${model.project.resolved_chords.length} roots on ${model.lattice.equave} equave circle`;
}
// ---------- details & table ----------
function detailRow(dl, label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  dl.append(dt, dd);
}

function renderDetails() {
  const dl = el("shv-details");
  dl.innerHTML = "";
  const occ = state.selection >= 0 && state.model ? state.model.occurrences[state.selection] : null;
  if (!occ) {
    detailRow(dl, "選択", "出現を選択してください（タイムライン・表・図のクリック、または ←/→ キー）。");
    return;
  }
  const chord = occ.chord;
  detailRow(dl, "Section", occ.sectionId);
  detailRow(dl, "Start", `${occ.startTick} ticks · bar ${occ.startBar.toFixed(2)}`);
  detailRow(dl, "Duration", `${occ.durationTicks} ticks · ${occ.durationBars.toFixed(2)} bars`);
  detailRow(dl, "Chord ID", chord.id);
  detailRow(dl, "Chord index", String(occ.chordIndex ?? "?"));
  detailRow(dl, "参照", referenceLabel(chord));
  detailRow(dl, "Ratios", chord.exact_ratios.join("  "));
  detailRow(dl, "Anchor", `(${chord.anchor_vector.join(", ")})`);
  detailRow(dl, "Voice offsets", chord.voice_offsets.map(vector => `(${vector.join(",")})`).join("  "));
  detailRow(dl, "Equave exp", chord.equave_exponents.join("  "));
  detailRow(dl, "Root ratio", rootRatioText(state.model.lattice.generators, chord.anchor_vector));
}

function renderTable() {
  const body = el("shv-table-body");
  body.innerHTML = "";
  if (!state.model) { el("shv-table-summary").textContent = ""; return; }
  const all = state.model.occurrences;
  for (const occ of filteredOccurrences()) {
    const row = document.createElement("tr");
    if (state.selection >= 0 && all[state.selection] === occ) row.className = "selected";
    const ratios = occ.chord.exact_ratios.slice(0, 2).join(" ") + (occ.chord.exact_ratios.length > 2 ? ` +${occ.chord.exact_ratios.length - 2}` : "");
    for (const text of [String(all.indexOf(occ) + 1), occ.sectionId, occ.startBar.toFixed(1), referenceLabel(occ.chord), ratios]) {
      const cell = document.createElement("td");
      cell.textContent = text;
      row.append(cell);
    }
    row.addEventListener("click", () => selectOccurrence(all.indexOf(occ)));
    body.append(row);
  }
  el("shv-table-summary").textContent = `${filteredOccurrences().length} / ${all.length}`;
}
// ---------- status & loading ----------
function setStatus(message, kind = "") {
  const node = el("shv-status");
  node.textContent = message;
  node.className = kind;
}

async function readJsonFile(file) {
  if (file.size > MAX_INPUT_BYTES) throw new Error(`${file.name} が 20 MiB を超えています。`);
  const text = await file.text();
  try { return JSON.parse(text); } catch (error) { throw new Error(`${file.name}: 壊れた JSON（${error.message}）`); }
}

function loadProjectData(data) {
  const { errors, dims } = validateProject(data);
  state.errors = errors;
  if (errors.length) {
    state.project = null; state.model = null; state.planModel = null; state.selection = -1;
    syncControls();
    setStatus(errors[0] + (errors.length > 1 ? `（+${errors.length - 1}）` : ""), "error");
    renderAll();
    return;
  }
  state.project = data;
  state.model = buildModel(data);
  state.selection = -1;
  if (state.axisX >= dims) state.axisX = 0;
  if (state.axisY >= dims) state.axisY = Math.min(1, dims - 1);
  syncControls();
  if (state.plan) applyPlan(state.plan);
  else setStatus(`project.json · ${data.form.length} sections · ${data.harmony_occurrences.length} occurrences · ${data.resolved_chords.length} chords`);
  renderAll();
}

function applyPlan(data) {
  const { errors } = validatePlan(data, state.project);
  if (errors.length) {
    state.plan = data; state.planModel = null; state.warnings = errors;
    setStatus(`計画レイヤー非表示: ${errors[0]}${errors.length > 1 ? `（+${errors.length - 1}）` : ""}`, "error");
    return;
  }
  state.plan = data;
  state.planModel = buildPlanModel(data, state.project);
  state.warnings = [];
  setStatus(`project.json + composition_plan.json · ${state.planModel.phrases.length} phrases`);
}

async function loadProjectFile(file) {
  try {
    const data = await readJsonFile(file);
    loadProjectData(data);
  } catch (error) { setStatus(error.message, "error"); }
}

async function loadPlanFile(file) {
  let data;
  try { data = await readJsonFile(file); } catch (error) { setStatus(error.message, "error"); return; }
  if (!state.project) {
    state.plan = data;
    setStatus("計画を保存しました。project.json を読み込むと計画レイヤーが表示されます。", "loading");
    return;
  }
  applyPlan(data);
  renderAll();
}

async function handleFiles(fileList) {
  for (const file of [...fileList]) {
    let data;
    try { data = await readJsonFile(file); } catch (error) { setStatus(error.message, "error"); continue; }
    if (data && typeof data === "object" && !Array.isArray(data) && data.schema === "cps.arrangement-project") {
      loadProjectData(data);
    } else if (data && typeof data === "object" && !Array.isArray(data) && data.schema === "cps.composition-plan") {
      if (!state.project) { state.plan = data; setStatus("計画を保存しました。project.json を読み込むと計画レイヤーが表示されます。", "loading"); }
      else { applyPlan(data); renderAll(); }
    } else {
      setStatus(`${file.name}: 未対応の schema（${data && typeof data === "object" ? data.schema ?? "不明" : "オブジェクト以外"}）`, "error");
    }
  }
}
// ---------- controls ----------
function syncControls() {
  const dims = state.model ? state.model.lattice.generators.length : 0;
  for (const [id, preferred] of [["shv-axis-x", state.axisX], ["shv-axis-y", state.axisY]]) {
    const select = el(id);
    select.innerHTML = "";
    for (let d = 0; d < dims; d++) {
      const option = document.createElement("option");
      option.value = String(d);
      option.textContent = `a${d + 1} (${state.model.lattice.generators[d]})`;
      select.append(option);
    }
    const value = dims ? Math.min(preferred, dims - 1) : 0;
    select.value = String(value);
    if (id === "shv-axis-x") state.axisX = value; else state.axisY = value;
  }
  const filter = el("shv-section-filter");
  filter.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "全 sections";
  filter.append(allOption);
  if (state.model) {
    for (const section of state.model.project.form) {
      const option = document.createElement("option");
      option.value = section.id;
      option.textContent = `${section.id} (${section.role})`;
      filter.append(option);
    }
  }
  if (![...filter.options].some(option => option.value === state.sectionFilter)) state.sectionFilter = "all";
  filter.value = state.sectionFilter;
}

// ---------- selection & render ----------
function selectOccurrence(index) {
  if (!state.model || index < 0 || index >= state.model.occurrences.length) return;
  state.selection = index;
  renderAll();
}

function moveSelection(delta) {
  if (!state.model) return;
  const list = filteredOccurrences();
  if (!list.length) return;
  const current = state.selection >= 0 ? list.indexOf(state.model.occurrences[state.selection]) : -1;
  const next = current === -1 ? (delta > 0 ? 0 : list.length - 1) : (current + delta + list.length) % list.length;
  selectOccurrence(state.model.occurrences.indexOf(list[next]));
}

function renderAll() {
  renderTimeline();
  renderProjection();
  renderDetails();
  renderTable();
}

function renderLegend() {
  const legend = el("shv-legend");
  legend.innerHTML = "";
  if (!state.model) return;
  const add = (text, color) => { const span = document.createElement("span"); span.textContent = text; if (color) span.style.color = color; legend.append(span); };
  if (state.view === "lattice") {
    add("根（コード色）", "#98e7ca");
    add("声部（淡色）", "#83b7ff");
    add("線 = 時間順の根遷移 Δanchor", "#ffd47e");
    const dims = state.model.lattice.generators.length;
    if (dims >= 3) {
      const hidden = state.model.lattice.generators.map((g, i) => (i === state.axisX || i === state.axisY ? null : `a${i + 1} (${g})`)).filter(Boolean);
      if (hidden.length) add(`選択外次元: ${hidden.join(", ")}`, "#aeb9d0");
    }
  } else {
    add("根（コード色）", "#98e7ca");
    add("選択声部（分数ラベル）", "#ffd47e");
    add("同心円 = equave 指数の差", "#83b7ff");
    add(`equave ${state.model.lattice.equave} = ${state.model.equaveC.toFixed(1)} cents`, "#aeb9d0");
  }
}

// ---------- events ----------
el("shv-project-file").addEventListener("change", event => { const file = event.target.files[0]; if (file) void loadProjectFile(file); event.target.value = ""; });
el("shv-plan-file").addEventListener("change", event => { const file = event.target.files[0]; if (file) void loadPlanFile(file); event.target.value = ""; });
const dropzone = el("shv-dropzone");
["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", event => { if (event.dataTransfer && event.dataTransfer.files.length) void handleFiles(event.dataTransfer.files); });
function setView(view) {
  state.view = view;
  el("shv-view-lattice").classList.toggle("active", view === "lattice");
  el("shv-view-circle").classList.toggle("active", view === "circle");
  renderProjection();
}
el("shv-view-lattice").addEventListener("click", () => setView("lattice"));
el("shv-view-circle").addEventListener("click", () => setView("circle"));
el("shv-axis-x").addEventListener("change", event => { state.axisX = Number(event.target.value); renderProjection(); });
el("shv-axis-y").addEventListener("change", event => { state.axisY = Number(event.target.value); renderProjection(); });
el("shv-section-filter").addEventListener("change", event => { state.sectionFilter = event.target.value; renderAll(); });
el("shv-collapse").addEventListener("change", event => { state.collapse = event.target.checked; renderTimeline(); });
el("shv-prev").addEventListener("click", () => moveSelection(-1));
el("shv-next").addEventListener("click", () => moveSelection(1));
document.addEventListener("keydown", event => {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  if (/INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return;
  event.preventDefault();
  moveSelection(event.key === "ArrowLeft" ? -1 : 1);
});

// ---------- init ----------
syncControls();
renderAll();
