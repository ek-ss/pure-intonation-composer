"use strict";

const mm = (id) => document.getElementById(id);
const mmState = { library: null, patternId: "MM_3575", customPattern: null, project: null, comparison: { A: null, B: null }, favorites: new Set(JSON.parse(localStorage.getItem("pure-intonation.mixed-meter-favorites") || "[]")), audio: null, sources: [], startedAt: 0, playbackOffset: 0, pausedBeat: 0, timer: null, playheadFrame: null };
const mmRoleNames = { kick: "Kick", snare: "Snare", closed_hat: "Closed Hat", open_hat: "Open Hat", percussion: "Percussion", tom_fill: "Tom Fill", crash: "Crash" };

function mmStatus(message, kind = "") { mm("mm-status").textContent = message; mm("mm-status").className = `experiment-status ${kind}`; }
async function mmApi(path, body) {
  const response = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: body === undefined ? {} : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || `Request failed (${response.status})`); }
  return response;
}
function mmDownload(blob, name) { const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 500); }
function mmTrackConfigs() {
  return [...document.querySelectorAll(".mm-track-row")].map((row) => ({ id: `track-${row.dataset.role}`, role: row.dataset.role, midi_note: Number(row.dataset.note), density_mode: row.querySelector("select").value, base_density: Number(row.querySelector('[data-kind="density"]').value), min_density: Number(row.querySelector('[data-kind="min"]').value), max_density: Number(row.querySelector('[data-kind="max"]').value), tension_response: Number(row.querySelector('[data-kind="response"]').value), structural_clarity: Number(row.querySelector('[data-kind="clarity"]').value), syncopation: Number(row.querySelector('[data-kind="syncopation"]').value), variation: Number(mm("mm-variation").value), velocity_range: [Number(row.querySelector('[data-kind="velocity-min"]').value), Number(row.querySelector('[data-kind="velocity-max"]').value)], muted: row.querySelector('[data-kind="mute"]').checked, solo: row.querySelector('[data-kind="solo"]').checked, locked: row.querySelector('[data-kind="lock"]').checked }));
}
function mmRequest() {
  const form = mm("mm-form").value;
  const request = { pattern_id: mmState.patternId, custom_pattern: mmState.customPattern, form, tension_repeats: Number(mm("mm-tension-repeats").value), stable_repeats: Number(mm("mm-stable-repeats").value), resolved_repeats: Number(mm("mm-resolved-repeats").value), density_profile: mm("mm-density-profile").value, tracks: mmTrackConfigs(), tempo_bpm: Number(mm("mm-tempo").value), subdivision: Number(mm("mm-subdivision").value), variation: Number(mm("mm-variation").value), syncopation: Number(mm("mm-syncopation").value), humanize: Number(mm("mm-humanize").value), seed: Number(mm("mm-seed").value), allow_unaligned: mm("mm-allow-unaligned").checked };
  if (form === "custom") request.sections = mm("mm-custom-form").value.split(",").map((value, index) => { const role = value.trim(); return { id: `${role}-${index + 1}`, role, pattern_id: role === "stable" || role === "resolved" ? "MM_4_4" : role === "pre_resolution" ? "MM_3_5" : mmState.customPattern ? null : mmState.patternId, inline_pattern: role === "tension" ? mmState.customPattern : null, repeats: 1, tension_mode: "blend", tension_curve: role === "stable" || role === "resolved" ? [.15] : role === "pre_resolution" ? [.55, .35] : [.5, .85] }; });
  request.locked_events = mmState.project?.events?.filter((event) => event.locked && event.structural_role === "user") || [];
  return request;
}
function mmRenderLibrary() {
  mm("mm-pattern-grid").replaceChildren(...mmState.library.patterns.map((pattern) => {
    const button = document.createElement("button"); button.className = `mm-pattern-card${pattern.id === mmState.patternId && !mmState.customPattern ? " active" : ""}`;
    button.innerHTML = `<strong>${mmState.favorites.has(pattern.id) ? "★ " : ""}${pattern.name}</strong><span>${pattern.meters.map((n) => `${n}/${pattern.denominator}`).join(" · ")}</span><small>${pattern.total_beats} beats · phase ${pattern.phase_path.join("→")}</small>`;
    button.onclick = () => { mmState.patternId = pattern.id; mmState.customPattern = null; mmRenderLibrary(); mm("mm-pattern-summary").textContent = `${pattern.id} · ${pattern.four_four_equivalent_bars} × 4/4`; };
    button.ondblclick = async () => { button.onclick(); await mmGenerate(); mmPlay(); };
    return button;
  }));
}
function mmRenderTracks(tracks) {
  mm("mm-track-list").replaceChildren(...tracks.map((track) => {
    const row = document.createElement("div"); row.className = "mm-track-row"; row.dataset.role = track.role; row.dataset.note = track.midi_note;
    row.innerHTML = `<strong>${mmRoleNames[track.role]}</strong><select aria-label="${track.role} density mode"><option value="hybrid">Hybrid</option><option value="manual">Manual</option><option value="tension_linked">Tension linked</option><option value="section">Section</option></select><label>Density<input data-kind="density" type="range" min="0" max="1" step=".05" value="${track.base_density}"></label><label>Response<input data-kind="response" type="range" min="-1" max="1" step=".05" value="${track.tension_response}"></label><label>Min<input data-kind="min" type="number" min="0" max="1" step=".05" value="${track.min_density}"></label><label>Max<input data-kind="max" type="number" min="0" max="1" step=".05" value="${track.max_density}"></label><label>Clarity<input data-kind="clarity" type="range" min="0" max="1" step=".05" value="${track.structural_clarity}"></label><label>Sync<input data-kind="syncopation" type="range" min="0" max="1" step=".05" value="${track.syncopation}"></label><label>Vel min<input data-kind="velocity-min" type="number" min="1" max="127" value="${track.velocity_range[0]}"></label><label>Vel max<input data-kind="velocity-max" type="number" min="1" max="127" value="${track.velocity_range[1]}"></label><label><input data-kind="mute" type="checkbox">Mute</label><label><input data-kind="solo" type="checkbox">Solo</label><label><input data-kind="lock" type="checkbox">Lock track</label>`;
    return row;
  }));
}
function mmDraw() {
  const canvas = mm("mm-timeline-canvas"), ctx = canvas.getContext("2d"), project = mmState.project;
  ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = "#0d121c"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!project) { ctx.fillStyle = "#718099"; ctx.font = "22px sans-serif"; ctx.fillText("Generate a section to inspect its phase and events", 36, 62); return; }
  const left = 110, top = 58, right = 24, rowH = 53, width = canvas.width - left - right, total = project.total_beats;
  project.sections.forEach((section, index) => { const x = left + section.start_beat / total * width, w = (section.end_beat - section.start_beat) / total * width; ctx.fillStyle = index % 2 ? "#182536" : "#142019"; ctx.fillRect(x, 12, w, canvas.height - 25); ctx.fillStyle = "#d7e1ef"; ctx.font = "16px sans-serif"; ctx.fillText(section.role.replace("_", " "), x + 6, 34); });
  ctx.setLineDash([5, 8]); ctx.strokeStyle = "#263247"; for (let beat = 0; beat <= total; beat += 4) { const x = left + beat / total * width; ctx.beginPath(); ctx.moveTo(x, 42); ctx.lineTo(x, canvas.height - 14); ctx.stroke(); } ctx.setLineDash([]);
  project.bars.forEach((bar) => { const x = left + bar.start_beat / total * width; ctx.strokeStyle = bar.phase === 0 ? "#70d8ad" : bar.phase === 2 ? "#ff9a8e" : "#ffd47e"; ctx.lineWidth = bar.macro_start ? 4 : 2; ctx.beginPath(); ctx.moveTo(x, 42); ctx.lineTo(x, canvas.height - 14); ctx.stroke(); bar.group_boundaries.slice(1, -1).forEach((boundary) => { const gx = left + boundary / total * width; ctx.strokeStyle = "#52647d"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(gx, 55); ctx.lineTo(gx, canvas.height - 14); ctx.stroke(); }); ctx.fillStyle = "#9aa9bd"; ctx.font = "13px sans-serif"; ctx.fillText(`${bar.meter}/${bar.denominator} φ${bar.phase}`, x + 4, 53); });
  const roles = Object.keys(mmRoleNames); roles.forEach((role, i) => { const y = top + i * rowH; ctx.fillStyle = "#b9c5d6"; ctx.font = "14px sans-serif"; ctx.fillText(mmRoleNames[role], 8, y + 20); ctx.strokeStyle = "#263247"; ctx.beginPath(); ctx.moveTo(left, y + 27); ctx.lineTo(canvas.width - right, y + 27); ctx.stroke(); });
  project.events.forEach((event) => { const i = roles.indexOf(event.role), x = left + event.pulse_position / total * width, y = top + i * rowH + 11; ctx.fillStyle = event.locked ? "#ffd47e" : event.structural_role === "offbeat" ? "#ff9a8e" : "#70d8ad"; ctx.fillRect(x - 3, y, 7, 22); });
  if (mmState.sources.length && mmState.audio) { const beat = mmState.playbackOffset + (mmState.audio.currentTime - mmState.startedAt) * project.settings.tempo_bpm / 60, x = left + Math.min(total, beat) / total * width; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, 8); ctx.lineTo(x, canvas.height - 10); ctx.stroke(); }
}
function mmRenderProject() {
  const project = mmState.project; if (!project) return;
  mm("mm-timeline-summary").textContent = `${project.bars.length} bars · ${project.total_beats} beats · ${project.events.length} hits`;
  mm("mm-project-metrics").innerHTML = `<span>${project.sections.length} sections</span><span>${project.events.length} events</span><span>${project.settings.tempo_bpm} BPM</span><span>${project.warnings.length ? project.warnings.join("; ") : "4/4 aligned"}</span>`;
  const rows = project.density.map((item) => `<tr><td>${mmRoleNames[item.role]}</td><td>${item.section_id}</td><td>${item.target_density}</td><td>${item.actual_density}</td><td>${item.event_count}</td></tr>`).join("");
  mm("mm-density-report").innerHTML = `<table class="experiment-table"><thead><tr><th>Track</th><th>Section</th><th>Target</th><th>Actual</th><th>Hits</th></tr></thead><tbody>${rows}</tbody></table>`;
  mmDraw();
}
async function mmGenerate() { mmStatus("Generating", "loading"); try { mmState.project = await (await mmApi("/api/rhythm/mixed-meter/generate", mmRequest())).json(); mmRenderProject(); mmStatus("Generated"); } catch (error) { mmStatus(error.message, "error"); } }

function mmStop(reset = true) { mmState.sources.forEach((source) => { try { source.stop(); } catch (_) {} }); mmState.sources = []; clearTimeout(mmState.timer); cancelAnimationFrame(mmState.playheadFrame); mmState.playheadFrame = null; if (reset) mmState.pausedBeat = 0; mmDraw(); }
function mmNoiseBuffer(context, seconds) { const buffer = context.createBuffer(1, context.sampleRate * seconds, context.sampleRate), data = buffer.getChannelData(0); for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1; return buffer; }
function mmScheduleHit(context, event, when) {
  const gain = context.createGain(); gain.gain.setValueAtTime(event.velocity / 127 * .45, when); gain.gain.exponentialRampToValueAtTime(.001, when + (event.role === "kick" ? .28 : .12)); gain.connect(context.destination);
  if (event.role === "kick" || event.role === "tom_fill") { const osc = context.createOscillator(); osc.frequency.setValueAtTime(event.role === "kick" ? 78 : 128, when); osc.frequency.exponentialRampToValueAtTime(42, when + .2); osc.connect(gain); osc.start(when); osc.stop(when + .3); mmState.sources.push(osc); }
  else { const source = context.createBufferSource(); source.buffer = mmNoiseBuffer(context, .18); const filter = context.createBiquadFilter(); filter.type = "highpass"; filter.frequency.value = event.role.includes("hat") || event.role === "crash" ? 4200 : 900; source.connect(filter).connect(gain); source.start(when); source.stop(when + .2); mmState.sources.push(source); }
}
function mmAnimatePlayhead() { mmDraw(); if (mmState.sources.length) mmState.playheadFrame = requestAnimationFrame(mmAnimatePlayhead); }
function mmPlay() {
  if (!mmState.project) return; mmStop(false); mmState.audio ||= new AudioContext(); const context = mmState.audio, beatSeconds = 60 / mmState.project.settings.tempo_bpm, origin = context.currentTime + .06, offset = mmState.pausedBeat;
  mmState.project.events.filter((event) => event.pulse_position >= offset).forEach((event) => mmScheduleHit(context, event, origin + (event.pulse_position - offset) * beatSeconds + event.timing_offset_ms / 1000));
  mmState.startedAt = context.currentTime; mmState.playbackOffset = offset; mmAnimatePlayhead(); const remaining = (mmState.project.total_beats - offset) * beatSeconds * 1000; mmState.timer = setTimeout(() => { mmState.pausedBeat = 0; if (mm("mm-loop").checked) mmPlay(); else mmStop(); }, remaining + 100); mmStatus("Playing");
}
function mmShowComparison() {
  const a = mmState.comparison.A, b = mmState.comparison.B;
  mm("mm-ab-status").textContent = `${a ? `A ${a.events.length} hits` : "A empty"} · ${b ? `B ${b.events.length} hits` : "B empty"}`;
}
function mmPause() { if (!mmState.project || !mmState.sources.length) return; const elapsed = (mmState.audio.currentTime - mmState.startedAt) * mmState.project.settings.tempo_bpm / 60; mmState.pausedBeat = Math.min(mmState.project.total_beats, mmState.pausedBeat + elapsed); mmStop(false); mmStatus(`Paused at beat ${mmState.pausedBeat.toFixed(1)}`); }

async function mmExport(path, name) { if (!mmState.project) return; mmStatus(`Preparing ${name}`, "loading"); try { const blob = await (await mmApi(path, { project: mmState.project, humanized_positions: true })).blob(); mmDownload(blob, name); mmStatus(`${name} downloaded`); } catch (error) { mmStatus(error.message, "error"); } }
function mmExportJson() { if (!mmState.project) return; mmDownload(new Blob([JSON.stringify(mmState.project, null, 2)], { type: "application/json" }), "mixed-meter-drums.json"); }
function mmImportProject(project) { if (project.feature !== "mixed-meter-drums") throw new Error("This is not a Mixed Meter Drum project"); mmState.project = project; mm("mm-tempo").value = project.settings.tempo_bpm; mm("mm-seed").value = project.seed; mmRenderProject(); mmStatus("Project imported"); }

async function mmInit() {
  try { mmState.library = await (await mmApi("/api/rhythm/mixed-meter/patterns")).json(); mmRenderLibrary(); mmRenderTracks(mmState.library.track_defaults); mmStatus("Ready"); mmDraw(); } catch (error) { mmStatus(error.message, "error"); }
}
["variation", "syncopation", "humanize"].forEach((name) => mm(`mm-${name}`).oninput = () => { mm(`mm-${name}-out`).textContent = Number(mm(`mm-${name}`).value).toFixed(2); });
mm("mm-density-profile").onchange = () => { if (!mmState.library) return; const profile = mmState.library.density_profiles[mm("mm-density-profile").value]; document.querySelectorAll(".mm-track-row").forEach((row) => { const [density, response] = profile[row.dataset.role]; row.querySelector('[data-kind="density"]').value = density; row.querySelector('[data-kind="response"]').value = response; }); };
mm("mm-apply-preset").onclick = () => { const presets = { prime: ["MM_3575", "two_stage_resolution", "chorus_impact"], gentle: ["MM_3535", "direct_resolution", "build_up"], phase: ["MM_3733", "direct_resolution", "skeletal_tension"], held: ["MM_745", "direct_resolution", "chorus_impact"], symmetric: ["MM_5775", "two_stage_resolution", "build_up"] }; const [pattern, form, profile] = presets[mm("mm-quick-start").value]; mmState.patternId = pattern; mmState.customPattern = null; mm("mm-form").value = form; mm("mm-density-profile").value = profile; mm("mm-density-profile").onchange(); mmRenderLibrary(); mmGenerate(); };
mm("mm-favorite").onclick = () => { if (mmState.favorites.has(mmState.patternId)) mmState.favorites.delete(mmState.patternId); else mmState.favorites.add(mmState.patternId); localStorage.setItem("pure-intonation.mixed-meter-favorites", JSON.stringify([...mmState.favorites])); mmRenderLibrary(); };
mm("mm-duplicate").onclick = () => { const pattern = mmState.library.patterns.find((item) => item.id === mmState.patternId); if (!pattern) return; mm("mm-custom-name").value = `${pattern.name} copy`; mm("mm-custom-denominator").value = pattern.denominator; mm("mm-custom-meters").value = pattern.meters.join(","); mm("mm-custom-groups").value = pattern.groupings.map((group) => group.join("+")).join(" | "); mm("mm-custom-name").scrollIntoView({ behavior: "smooth", block: "center" }); };
mm("mm-form").onchange = () => { mm("mm-custom-form-wrap").hidden = mm("mm-form").value !== "custom"; };
mm("mm-use-custom").onclick = async () => { try { const meters = mm("mm-custom-meters").value.split(",").map(Number); const groupings = mm("mm-custom-groups").value.split("|").map((group) => group.trim().split("+").map(Number)); const pattern = { id: "MM_CUSTOM", name: mm("mm-custom-name").value, denominator: Number(mm("mm-custom-denominator").value), meters, groupings, tags: ["custom"] }; const result = await (await mmApi("/api/rhythm/mixed-meter/validate", { pattern, allow_unaligned: mm("mm-allow-unaligned").checked })).json(); mmState.customPattern = pattern; mmState.patternId = pattern.id; mmRenderLibrary(); mm("mm-validation").innerHTML = `<span>${result.aligned ? "4/4 aligned" : "Unaligned"}</span><span>${result.pattern.total_beats} beats</span><span>Phase ${result.pattern.phase_path.join("→")}</span>`; mmStatus("Custom pattern selected"); } catch (error) { mmStatus(error.message, "error"); } };
mm("mm-generate").onclick = mmGenerate; mm("mm-random-seed").onclick = () => { mm("mm-seed").value = Math.floor(Math.random() * 2147483647); mmGenerate(); };
mm("mm-timeline-canvas").onclick = (event) => { const project = mmState.project; if (!project) return; const canvas = event.currentTarget, rect = canvas.getBoundingClientRect(), px = (event.clientX - rect.left) * canvas.width / rect.width, py = (event.clientY - rect.top) * canvas.height / rect.height, roles = Object.keys(mmRoleNames), left = 110, top = 58, rowH = 53, width = canvas.width - left - 24; let best = null, distance = Infinity; project.events.forEach((item) => { const x = left + item.pulse_position / project.total_beats * width, y = top + roles.indexOf(item.role) * rowH + 22, candidate = Math.hypot(px - x, py - y); if (candidate < distance) { best = item; distance = candidate; } }); if (!best || distance > 18) return; if (best.structural_role === "user") { best.structural_role = best.previous_structural_role || "beat"; best.locked = false; } else { best.previous_structural_role = best.structural_role; best.structural_role = "user"; best.locked = true; } mmDraw(); mmStatus(best.locked ? "Event locked" : "Event unlocked"); };
mm("mm-play").onclick = mmPlay; mm("mm-pause").onclick = mmPause; mm("mm-stop").onclick = () => { mmStop(); mmStatus("Stopped"); };
mm("mm-midi").onclick = () => mmExport("/api/rhythm/mixed-meter/export/midi", "mixed-meter-drums.mid"); mm("mm-wav").onclick = () => mmExport("/api/rhythm/mixed-meter/preview", "mixed-meter-drums.wav"); mm("mm-json").onclick = mmExportJson;
mm("mm-import").onclick = () => mm("mm-import-file").click(); mm("mm-import-file").onchange = async (event) => { try { mmImportProject(JSON.parse(await event.target.files[0].text())); } catch (error) { mmStatus(error.message, "error"); } event.target.value = ""; };
mm("mm-transfer").onclick = () => { if (!mmState.project) return; sessionStorage.setItem("mixed-meter-compose-timeline", JSON.stringify(mmState.project.compose_timeline)); window.location.href = "/"; };
mm("mm-transfer-explorer").onclick = () => { if (!mmState.project) return; sessionStorage.setItem("mixed-meter-composition-explorer-project", JSON.stringify(mmState.project)); window.location.href = "/composition-explorer"; };
mm("mm-store-a").onclick = () => { if (mmState.project) mmState.comparison.A = structuredClone(mmState.project); mmShowComparison(); };
mm("mm-store-b").onclick = () => { if (mmState.project) mmState.comparison.B = structuredClone(mmState.project); mmShowComparison(); };
mm("mm-play-a").onclick = () => { if (!mmState.comparison.A) return; mmState.project = structuredClone(mmState.comparison.A); mmRenderProject(); mmPlay(); };
mm("mm-play-b").onclick = () => { if (!mmState.comparison.B) return; mmState.project = structuredClone(mmState.comparison.B); mmRenderProject(); mmPlay(); };
mmInit();
