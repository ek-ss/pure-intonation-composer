const el = id => document.getElementById(id);
const state = { pitches: [], active: new Map(), context: null, focus: null, graph: null, showGraph: false, recording: false, recorded: [], walk: null, layout: null, gridLayout: null, reference: 0 };
const keyboardKeys = "ASDFGHJKL;QWERTYUIOPZXCVBNM".split("");

function setStatus(text, kind = "") { const status = el("status"); status.textContent = text; status.className = kind; }
function parseFactors(source = el("factors").value) {
  const values = source.split(",").map(v => Number(v.trim())).filter(Boolean);
  if (!values.length || values.some(v => !Number.isInteger(v) || v < 1)) throw new Error("因子には1以上の整数を入力してください。");
  return values;
}
function syncGeneratorFields() {
  const type = el("generator").value;
  const series = type === "harmonic" || type === "subharmonic";
  el("factor-field").hidden = series; el("choose-field").hidden = type !== "cps"; el("count-field").hidden = !series;
  if (type === "euler") { el("factors").value = el("factors").value.replace(/(^|,\s*)1,?\s*/g, "") || "3, 5, 7"; }
}
async function generate() {
  const type = el("generator").value; const octaveReduce = el("octave").checked;
  let endpoint, body, name;
  try {
    if (type === "cps") { const factors = parseFactors(); endpoint = "/api/cps"; body = { factors, choose:Number(el("choose").value), kind:"harmonic", octave_reduce:octaveReduce }; name = `CPS(${factors.length},${body.choose})`; }
    if (type === "euler") { const factors = parseFactors(); endpoint = "/api/euler-fokker"; body = { factors, octave_reduce:octaveReduce }; name = "Euler–Fokker"; }
    if (type === "harmonic" || type === "subharmonic") { endpoint = `/api/${type}-series`; body = { count:Number(el("count").value), octave_reduce:octaveReduce }; name = type === "harmonic" ? "Harmonic series" : "Subharmonic series"; }
    setStatus("Generating…", "loading"); const response = await fetch(endpoint, { method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify(body) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "生成に失敗しました。");
    state.pitches = data.pitches; state.focus = null; state.graph = null; state.showGraph = false; state.walk = null; state.layout = null; state.gridLayout = null; state.reference = 0; el("graph-toggle").hidden = type !== "cps";
    if(type === "cps") { const graphResponse = await fetch("/api/harmonic-graph", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({factors:body.factors,choose:body.choose})}); state.graph = await graphResponse.json(); }
    el("walk-controls").hidden = true;
    el("scale-name").textContent = `${name} · ${data.count} intervals`; render(); setStatus(`${data.count} intervals`, "");
  } catch (error) { setStatus(error.message, "error"); }
}
function render() { renderCircle(); renderPitches(); renderKeyboard(); }
function ratioParts(ratio) { return ratio.split("/").map(Number); }
function gcd(a,b) { while (b) [a,b] = [b,a%b]; return a; }
function primeWeight(value) { let number=value, divisor=2, weight=0; while(divisor*divisor<=number){while(number%divisor===0){weight += divisor===2 ? 1 : divisor===3 ? 2 : divisor===5 ? 3 : 4; number/=divisor;} divisor += divisor===2 ? 1 : 2;} return weight+(number>1 ? (number===3?2:number===5?3:4):0); }
function harmony(index, reference=state.focus) { if (reference === null) return { level:"neutral", color:"#98e7ca", label:"" }; if (index === reference) return { level:"selected", color:"#ffd47e", label:"発音中" }; const [an,ad]=ratioParts(state.pitches[index].ratio), [bn,bd]=ratioParts(state.pitches[reference].ratio); let numerator=an*bd, denominator=ad*bn, factor=gcd(numerator,denominator); numerator/=factor; denominator/=factor; while(numerator>=denominator*2) denominator*=2; while(numerator<denominator) numerator*=2; const complexity=primeWeight(numerator)+primeWeight(denominator); if(complexity<=5) return {level:"strong",color:"#98e7ca",label:"強い調和"}; if(complexity<=9) return {level:"close",color:"#83b7ff",label:"近い調和"}; return {level:"distant",color:"#caa8ff",label:"遠い関係"}; }
function circlePoint(pitch, mid, radius) { const angle=(pitch.cents/1200)*Math.PI*2-Math.PI/2; return {angle,x:mid+Math.cos(angle)*radius,y:mid+Math.sin(angle)*radius}; }
function renderCircle() {
  const canvas = el("circle"), ctx = canvas.getContext("2d"), size = canvas.width, mid = size / 2, radius = size * .36, focus = state.focus;
  if(state.showGraph && state.graph) { renderGraph(ctx, size); return; }
  ctx.clearRect(0,0,size,size); ctx.strokeStyle="#30394d"; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(mid,mid,radius,0,Math.PI*2); ctx.stroke();
  if(el("harmonics-toggle").checked){
    const count=Number(el("harmonics-count").value);
    ctx.save(); ctx.setLineDash([4,4]);
    for(let h=3;h<=count;h+=2){
      const angle=((1200*Math.log2(h))%1200)/1200*Math.PI*2-Math.PI/2;
      ctx.strokeStyle="#2c3550"; ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(mid+Math.cos(angle)*radius*.55,mid+Math.sin(angle)*radius*.55); ctx.lineTo(mid+Math.cos(angle)*(radius+18),mid+Math.sin(angle)*(radius+18)); ctx.stroke();
      ctx.fillStyle="#56617d"; ctx.font="10px system-ui"; ctx.textAlign="center";
      ctx.fillText(`${h}/${2**Math.floor(Math.log2(h))}`,mid+Math.cos(angle)*(radius+46),mid+Math.sin(angle)*(radius+46)+3);
    }
    ctx.restore();
  }
  const points=state.pitches.map(pitch=>circlePoint(pitch,mid,radius));
  points.forEach(point=>{ctx.strokeStyle="#40506d";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mid,mid);ctx.lineTo(point.x,point.y);ctx.stroke();});
  if(focus!==null){ const source=points[focus]; points.forEach((point,index)=>{if(index===focus)return;const relation=harmony(index);ctx.globalAlpha=.72;ctx.strokeStyle=relation.color;ctx.lineWidth=relation.level==="strong"?4:2;ctx.beginPath();ctx.moveTo(source.x,source.y);ctx.lineTo(point.x,point.y);ctx.stroke();});ctx.globalAlpha=1; }
  ctx.fillStyle="#aeb9d0"; ctx.font="15px system-ui"; ctx.textAlign="center"; ctx.fillText("1/1",mid,mid+5);
  state.pitches.forEach((pitch,index) => { const point=points[index], relation=harmony(index); const active=state.active.has(index); ctx.fillStyle=relation.color; ctx.beginPath(); ctx.arc(point.x,point.y,active?16:10,0,Math.PI*2); ctx.fill(); if(active){ctx.strokeStyle="#fff4cf";ctx.lineWidth=3;ctx.beginPath();ctx.arc(point.x,point.y,22,0,Math.PI*2);ctx.stroke();} ctx.fillStyle="#10131c";ctx.font="bold 10px system-ui";ctx.fillText(String(index+1),point.x,point.y+4);ctx.fillStyle=relation.color;ctx.font="13px system-ui";ctx.fillText(pitch.ratio,mid+Math.cos(point.angle)*(radius+31),point.y+Math.sin(point.angle)*31+4); });
  if(state.active.size===2){
    const [a,b]=[...state.active.keys()];
    const [an,ad]=ratioParts(state.pitches[a].ratio), [bn,bd]=ratioParts(state.pitches[b].ratio);
    let n=an*bd, d=ad*bn; const g=gcd(n,d); n/=g; d/=g;
    while(n>=d*2) d*=2; while(n<d) n*=2;
    ctx.strokeStyle="#ffd47e"; ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(points[a].x,points[a].y); ctx.lineTo(points[b].x,points[b].y); ctx.stroke();
    ctx.fillStyle="#ffd47e"; ctx.font="bold 13px system-ui"; ctx.textAlign="center";
    ctx.fillText(`${n}/${d}`, (points[a].x+points[b].x)/2, (points[a].y+points[b].y)/2-8);
  }
  canvas.onclick = event => { const rect=canvas.getBoundingClientRect(), x=(event.clientX-rect.left)*size/rect.width, y=(event.clientY-rect.top)*size/rect.height; let nearest=-1, distance=Infinity; state.pitches.forEach((pitch,i)=>{const a=pitch.cents/1200*Math.PI*2-Math.PI/2, px=mid+Math.cos(a)*radius, py=mid+Math.sin(a)*radius, d=Math.hypot(px-x,py-y);if(d<distance){distance=d;nearest=i}}); if(distance<28) play(nearest); };
}
function graphLayout(graph, size) {
  if (state.layout) return state.layout;
  const count = graph.nodes.length, mid = size / 2, radius = size * .36;
  const points = graph.nodes.map((_, i) => { const angle = i * 2.399963229, r = radius * Math.sqrt((i + .5) / count); return { x: mid + Math.cos(angle) * r, y: mid + Math.sin(angle) * r }; });
  const ideal = radius * 2.2 / Math.sqrt(count), iterations = 220;
  for (let iter = 0; iter < iterations; iter++) {
    const disp = points.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < count; i++) for (let j = i + 1; j < count; j++) {
      let dx = points[i].x - points[j].x, dy = points[i].y - points[j].y; const d = Math.hypot(dx, dy) || .01, force = ideal * ideal / d;
      dx /= d; dy /= d; disp[i].x += dx * force; disp[i].y += dy * force; disp[j].x -= dx * force; disp[j].y -= dy * force;
    }
    graph.edges.forEach(edge => {
      let dx = points[edge.source].x - points[edge.target].x, dy = points[edge.source].y - points[edge.target].y; const d = Math.hypot(dx, dy) || .01, force = d * d / ideal;
      dx /= d; dy /= d; disp[edge.source].x -= dx * force; disp[edge.source].y -= dy * force; disp[edge.target].x += dx * force; disp[edge.target].y += dy * force;
    });
    const temperature = radius * .3 * (1 - iter / iterations);
    points.forEach((point, i) => {
      const d = Math.hypot(disp[i].x, disp[i].y) || .01;
      point.x += disp[i].x / d * Math.min(d, temperature); point.y += disp[i].y / d * Math.min(d, temperature);
      const ox = point.x - mid, oy = point.y - mid, od = Math.hypot(ox, oy);
      if (od > radius + 14) { point.x = mid + ox / od * (radius + 14); point.y = mid + oy / od * (radius + 14); }
    });
  }
  state.layout = points; return points;
}
function nearestGraphNode(points, event) {
  const canvas = el("circle"), size = canvas.width, rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) * size / rect.width, y = (event.clientY - rect.top) * size / rect.height;
  return points.reduce((best, point, index) => Math.hypot(point.x - x, point.y - y) < best.distance ? { index, distance: Math.hypot(point.x - x, point.y - y) } : best, { index: -1, distance: Infinity });
}
function playGraphNode(nodes, index) { const pitch = state.pitches.findIndex(item => item.ratio === nodes[index]?.ratio); if (pitch >= 0) play(pitch); }
function renderGraph(ctx, size) {
  el("circle").ondblclick = null;
  if (state.gridLayout) { renderGrid(ctx, size); return; }
  const nodes = state.graph.nodes, points = graphLayout(state.graph, size);
  ctx.clearRect(0, 0, size, size);
  ctx.strokeStyle = "#40506d"; ctx.lineWidth = 1;
  state.graph.edges.forEach(edge => { ctx.beginPath(); ctx.moveTo(points[edge.source].x, points[edge.source].y); ctx.lineTo(points[edge.target].x, points[edge.target].y); ctx.stroke(); });
  const walk = state.walk, order = new Map();
  if (walk) walk.forEach((node, i) => { if (!order.has(node)) order.set(node, i); });
  if (walk && walk.length > 1) { ctx.strokeStyle = "#ffd47e"; ctx.lineWidth = 3; ctx.globalAlpha = .85; ctx.beginPath(); walk.forEach((node, i) => { const p = points[node]; i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); }); ctx.stroke(); ctx.globalAlpha = 1; }
  points.forEach((point, index) => {
    const onPath = order.has(index);
    ctx.fillStyle = onPath ? "#ffd47e" : "#98e7ca"; ctx.beginPath(); ctx.arc(point.x, point.y, onPath ? 13 : 9, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#10131c"; ctx.font = "bold 10px system-ui"; ctx.textAlign = "center"; ctx.fillText(String(index + 1), point.x, point.y + 4);
    if (onPath) { ctx.fillStyle = "#ffd47e"; ctx.font = "bold 11px system-ui"; ctx.fillText(`#${order.get(index) + 1}`, point.x, point.y - 15); }
    ctx.fillStyle = "#aeb9d0"; ctx.font = "12px system-ui"; ctx.fillText(nodes[index].ratio, point.x, point.y + 26);
  });
  el("circle").onclick = event => { const nearest = nearestGraphNode(points, event); if (nearest.distance < 28) playGraphNode(nodes, nearest.index); };
}
async function loadGridLayout() {
  try {
    const data = await postJson("/api/harmonic-graph", { factors: parseFactors(), choose: Number(el("choose").value), layout: "reference_layered_grid", reference: state.reference, sort_mode: el("grid-sort").value });
    if (!data.layout) throw new Error("サーバーがレイアウトを返しませんでした。サーバーを再起動してください。");
    state.graph = data; state.gridLayout = data.layout; state.reference = data.layout.reference; state.layout = null;
    renderCircle();
  } catch (error) { setStatus(error.message, "error"); }
}
function renderGrid(ctx, size) {
  const layout = state.gridLayout, nodes = state.graph.nodes, mid = size / 2;
  ctx.clearRect(0, 0, size, size);
  const maxX = Math.max(...layout.positions.map(p => Math.abs(p.x)), 1), maxY = Math.max(...layout.positions.map(p => p.y), 1);
  const scale = Math.min((size / 2 - 90) / maxX, (size / 2 - 60) / maxY);
  const points = layout.positions.map(p => ({ x: mid + p.x * scale, y: mid - (p.y - maxY / 2) * scale }));
  const directionColor = { inward: "#83b7ff", outward: "#40506d", lateral: "#56617d" };
  state.graph.edges.forEach((edge, i) => {
    ctx.globalAlpha = .55; ctx.strokeStyle = directionColor[layout.edge_directions[i]] || "#40506d"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(points[edge.source].x, points[edge.source].y); ctx.lineTo(points[edge.target].x, points[edge.target].y); ctx.stroke();
  });
  ctx.globalAlpha = 1;
  ctx.textAlign = "left"; ctx.font = "11px system-ui"; ctx.fillStyle = "#aeb9d0";
  layout.layers.forEach(layer => ctx.fillText(`Shared ${layer.shared} · Distance ${layer.distance}`, 8, points[layer.nodes[0]].y + 4));
  const walk = state.walk, order = new Map();
  if (walk) walk.forEach((node, i) => { if (!order.has(node)) order.set(node, i); });
  if (walk && walk.length > 1) { ctx.strokeStyle = "#ffd47e"; ctx.lineWidth = 3; ctx.globalAlpha = .85; ctx.beginPath(); walk.forEach((node, i) => { const p = points[node]; i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); }); ctx.stroke(); ctx.globalAlpha = 1; }
  const sub = el("ratio-mode").value === "subharmonic";
  points.forEach((point, index) => {
    const isReference = index === layout.reference, onPath = order.has(index);
    ctx.fillStyle = onPath || isReference ? "#ffd47e" : "#98e7ca";
    ctx.beginPath(); ctx.arc(point.x, point.y, isReference ? 15 : onPath ? 13 : 9, 0, Math.PI * 2); ctx.fill();
    if (isReference) { ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(point.x, point.y, 20, 0, Math.PI * 2); ctx.stroke(); }
    ctx.fillStyle = "#10131c"; ctx.font = "bold 10px system-ui"; ctx.textAlign = "center"; ctx.fillText(String(index + 1), point.x, point.y + 4);
    if (onPath) { ctx.fillStyle = "#ffd47e"; ctx.font = "bold 11px system-ui"; ctx.fillText(`#${order.get(index) + 1}`, point.x, point.y - 26); }
    ctx.fillStyle = "#aeb9d0"; ctx.font = "11px system-ui";
    ctx.fillText(`{${nodes[index].factors.join(",")}}`, point.x, point.y + 26);
    ctx.fillText(sub ? nodes[index].sub_ratio : nodes[index].ratio, point.x, point.y + 40);
  });
  el("circle").onclick = event => { const nearest = nearestGraphNode(points, event); if (nearest.distance < 28) playGraphNode(nodes, nearest.index); };
  el("circle").ondblclick = event => {
    const nearest = nearestGraphNode(points, event);
    if (nearest.distance < 28 && nearest.index !== state.reference) { state.reference = nearest.index; loadGridLayout(); }
  };
}
function monzoText(monzo) { return Object.entries(monzo).map(([p,e])=>`${p}:${e}`).join(" ") || "0"; }
function renderPitches() { el("pitches").innerHTML = state.pitches.map((p,i)=>{const relation=harmony(i);return `<tr><td>${keyboardKeys[i]||"–"}</td><td><span class="relation-dot" style="color:${relation.color}"></span>${p.ratio}</td><td>${p.cents.toFixed(2)}</td><td class="monzo">${monzoText(p.monzo)}</td><td><button data-index="${i}">Play</button><button class="del" data-del="${i}" title="削除">×</button></td></tr>`}).join(""); el("pitches").querySelectorAll("button[data-index]").forEach(button=>button.onclick=()=>play(Number(button.dataset.index))); el("pitches").querySelectorAll("button[data-del]").forEach(button=>button.onclick=()=>{stopAll();state.pitches.splice(Number(button.dataset.del),1);state.focus=null;render();}); }
function renderKeyboard() { const box=el("keyboard"); box.innerHTML=""; state.pitches.slice(0,16).forEach((pitch,i)=>{const node=el("key-template").content.cloneNode(true);const button=node.querySelector("button");button.querySelector(".key-name").textContent=keyboardKeys[i];button.querySelector(".ratio").textContent=pitch.ratio;button.onclick=()=>play(i);box.append(node)}); }
function audioContext() { if (!state.context) state.context = new AudioContext(); return state.context; }
function play(index) { const pitch=state.pitches[index]; if(!pitch) return; if(state.recording){state.recorded.push({ratio:pitch.ratio,time:performance.now()});renderTimeline();} stop(index); const context=audioContext(), osc=context.createOscillator(), gain=context.createGain(), now=context.currentTime, attack=Number(el("attack").value)/1000, decay=Number(el("decay").value)/1000, sustain=Number(el("sustain").value)/100; osc.type=el("waveform").value; osc.frequency.value=Number(el("base-frequency").value)*(Number(pitch.ratio.split("/")[0])/Number(pitch.ratio.split("/")[1])); gain.gain.setValueAtTime(.0001,now); gain.gain.exponentialRampToValueAtTime(.24,now+attack); gain.gain.exponentialRampToValueAtTime(Math.max(.001,.24*sustain),now+attack+decay); osc.connect(gain).connect(context.destination); osc.start(); state.active.set(index,{osc,gain}); state.focus=index; render(); }
function renderTimeline(){
  const box = el("timeline-events"); box.innerHTML = "";
  const events = state.recorded;
  el("timeline-length").textContent = events.length ? `${events.length} events` : "";
  if (!events.length) return;
  const t0 = events[0].time, span = Math.max(1, events.at(-1).time - t0);
  events.forEach(event => { const mark = document.createElement("span"); mark.style.left = `${(event.time - t0) / span * 88 + 4}%`; mark.textContent = event.ratio; box.append(mark); });
  const seconds = span / 1000, marks = Math.min(8, Math.max(1, Math.round(seconds)));
  for (let i = 0; i <= marks; i++) { const tick = document.createElement("span"); tick.className = "axis"; tick.style.left = `${i / marks * 88 + 4}%`; tick.textContent = `${(seconds * i / marks).toFixed(1)}s`; box.append(tick); }
}
function stop(index) { const voice=state.active.get(index); if(!voice) return; const now=audioContext().currentTime, release=Number(el("release").value)/1000; voice.gain.gain.cancelScheduledValues(now); voice.gain.gain.setTargetAtTime(.0001,now,release/5); voice.osc.stop(now+release); state.active.delete(index); if(state.focus===index) state.focus=[...state.active.keys()].at(-1) ?? null; render(); }
function stopAll() { [...state.active.keys()].forEach(stop); }
el("generator").onchange=syncGeneratorFields; el("choose").oninput=event=>el("choose-value").textContent=event.target.value; el("generate").onclick=generate; el("stop").onclick=stopAll;
el("base-frequency").oninput=e=>el("base-output").textContent=`${e.target.value} Hz`; ["attack","decay","release"].forEach(id=>el(id).oninput=e=>el(`${id}-output`).textContent=`${e.target.value} ms`); el("sustain").oninput=e=>el("sustain-output").textContent=`${e.target.value}%`;
document.addEventListener("keydown", event=>{if(event.repeat || /INPUT|SELECT/.test(event.target.tagName)) return; const index=keyboardKeys.indexOf(event.key.toUpperCase()); if(index>=0){event.preventDefault();play(index);}}); document.addEventListener("keyup",event=>{const index=keyboardKeys.indexOf(event.key.toUpperCase());if(index>=0)stop(index)});
el("scala").onclick=async()=>{ if(!state.pitches.length)return; const response=await fetch("/api/export/scala",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name:"Pure Intonation Workbench",ratios:state.pitches.map(p=>p.ratio)})}); const link=document.createElement("a");link.href=URL.createObjectURL(await response.blob());link.download="pure-intonation.scl";link.click();URL.revokeObjectURL(link.href); };
el("graph-toggle").onclick=()=>{if(!state.graph)return;state.showGraph=!state.showGraph;el("visual-title").textContent=state.showGraph?"Harmonic graph":"Pitch circle";el("graph-toggle").textContent=state.showGraph?"Circle":"Graph";el("walk-controls").hidden=!state.showGraph;syncWalkControls();renderCircle();};
function syncWalkControls(){const op=el("walk-operation").value;el("walk-end").hidden=op!=="shortest_path";el("walk-metric").hidden=op!=="weighted_walk";el("walk-steps").hidden=op==="shortest_path";el("walk-seed").hidden=op==="shortest_path";}
el("walk-operation").onchange=syncWalkControls;
el("graph-layout").onchange=()=>{
  const layered=el("graph-layout").value==="layered";
  el("grid-sort").hidden=!layered; el("grid-hint").hidden=!layered;
  if(layered){loadGridLayout();}else{state.gridLayout=null;renderCircle();}
};
el("grid-sort").onchange=()=>{if(el("graph-layout").value==="layered")loadGridLayout();};
el("ratio-mode").onchange=()=>renderCircle();
el("walk-run").onclick=async()=>{
  if(!state.graph) return;
  try{
    const body={factors:parseFactors(),choose:Number(el("choose").value),operation:el("walk-operation").value,start:0,steps:Number(el("walk-steps").value),seed:Number(el("walk-seed").value),metric:el("walk-metric").value};
    if(body.operation==="shortest_path") body.end=Number(el("walk-end").value)-1;
    setStatus("Walking…","loading");
    const data=await postJson("/api/harmonic-graph",body);
    state.walk=data.walk||null; renderCircle();
    setStatus(state.walk?`walk: ${state.walk.length} nodes`:"no path",state.walk?"":"error");
  }catch(error){setStatus(error.message,"error");}
};
el("record").onclick=()=>{state.recording=!state.recording;if(state.recording)state.recorded=[];el("record").textContent=state.recording?"Stop":"Record";renderTimeline();};
el("timeline-clear").onclick=()=>{state.recorded=[];renderTimeline();};
el("timeline-play").onclick=()=>{
  if(!state.recorded.length) return;
  stopProgression();
  const t0=state.recorded[0].time, now=audioContext().currentTime+.1, base=Number(el("base-frequency").value);
  state.recorded.forEach(event=>scheduleTone(base*ratioValue(event.ratio), now+(event.time-t0)/1000, .8));
};
syncGeneratorFields(); generate();

// ---- Compose: harmony / bass / melody / export / render ----
const composeState = { chords: [], bass: [], melody: [], scheduled: [] };
function setComposeStatus(text, kind = "") { const s = el("compose-status"); s.textContent = text; s.className = kind; }
function ratioValue(ratio) { const [n, d] = ratio.split("/").map(Number); return n / d; }
function ratioMul(ratio, factor) { const [n, d] = ratio.split("/").map(Number); let num = n * factor, den = d; const g = gcd(num, den); num /= g; den /= g; while (num >= den * 2) den *= 2; while (num < den) num *= 2; return `${num}/${den}`; }
function chordTones(chord) { const tones = [chord.ratio]; chord.factors.filter(f => f !== 1).forEach(f => { const tone = ratioMul(chord.ratio, f); if (!tones.includes(tone)) tones.push(tone); }); return tones; }
async function postJson(endpoint, body) {
  const response = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "リクエストに失敗しました。");
  return data;
}
function renderProgression() {
  el("progression").innerHTML = "";
  composeState.chords.forEach((chord, index) => {
    const button = document.createElement("button");
    const score = chord.transition_score === null ? "" : `Δ ${chord.transition_score.toFixed(2)}`;
    button.innerHTML = `<span class="chord-index">${index + 1}</span><span>${chord.ratio}</span><span class="chord-score">${score}</span>`;
    button.title = chordTones(chord).join("  ");
    button.onclick = () => { stopProgression(); const now = audioContext().currentTime + 0.05; chordTones(chord).forEach(r => scheduleTone(Number(el("base-frequency").value) * ratioValue(r), now, 1.2)); };
    el("progression").append(button);
  });
}
async function generateHarmony() {
  try {
    const choose = Number(el("harmony-choose").value);
    setComposeStatus("Generating…", "loading");
    const data = await postJson("/api/compose/harmony", { factors: parseFactors(el("harmony-factors").value), choose, length: Number(el("harmony-length").value), seed: Number(el("harmony-seed").value), metric: el("harmony-metric").value });
    composeState.chords = data.chords; composeState.bass = []; composeState.melody = [];
    renderProgression(); setComposeStatus(`${data.length} chords`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
function requireChords() { if (!composeState.chords.length) throw new Error("先に和声進行を生成してください。"); }
async function generateBass() {
  try {
    requireChords(); setComposeStatus("Bass…", "loading");
    const data = await postJson("/api/compose/bass", { chords: composeState.chords.map(chordTones), strategy: el("bass-strategy").value });
    composeState.bass = data.notes; setComposeStatus(`Bass: ${data.notes.length} notes`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
async function generateMelody() {
  try {
    requireChords(); setComposeStatus("Melody…", "loading");
    const data = await postJson("/api/compose/melody", { chords: composeState.chords.map(chordTones), voice_count: Number(el("melody-voices").value), seed: Number(el("harmony-seed").value), contour: el("melody-contour").value });
    composeState.melody = data.voices; setComposeStatus(`Melody: ${data.voices.length} voices`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
function scheduleTone(frequency, start, duration, level = 0.2) {
  const context = audioContext(), osc = context.createOscillator(), gain = context.createGain();
  osc.type = el("waveform").value; osc.frequency.value = frequency;
  gain.gain.setValueAtTime(.0001, start); gain.gain.exponentialRampToValueAtTime(level, start + .02); gain.gain.setTargetAtTime(.0001, start + duration, .08);
  osc.connect(gain).connect(context.destination); osc.start(start); osc.stop(start + duration + .6);
  composeState.scheduled.push(osc);
}
function stopProgression() { composeState.scheduled.forEach(osc => { try { osc.stop(); } catch { /* already stopped */ } }); composeState.scheduled = []; }
function beatSeconds() { return 60 / Number(el("tempo").value); }
function playProgression() {
  if (!composeState.chords.length) { setComposeStatus("先に和声進行を生成してください。", "error"); return; }
  stopProgression();
  const base = Number(el("base-frequency").value), step = beatSeconds() * 2, now = audioContext().currentTime + .1;
  composeState.chords.forEach((chord, index) => {
    const start = now + index * step;
    chordTones(chord).forEach(r => scheduleTone(base * ratioValue(r), start, step));
    const bass = composeState.bass[index]; if (bass) scheduleTone(base * ratioValue(bass.ratio), start, step, .26);
    composeState.melody.forEach(voice => { const note = voice[index]; if (note) scheduleTone(base * 2 * ratioValue(note.ratio), start, step * .8, .13); });
  });
  setComposeStatus("Playing…", "loading");
}
function compositionEvents() {
  const step = beatSeconds() * 2, events = [];
  composeState.chords.forEach((chord, index) => {
    chordTones(chord).forEach(r => events.push({ ratio: r, start_seconds: index * step, duration_seconds: step }));
    const bass = composeState.bass[index]; if (bass) events.push({ ratio: bass.ratio, start_seconds: index * step, duration_seconds: step });
    composeState.melody.forEach(voice => { const note = voice[index]; if (note) events.push({ ratio: note.ratio, start_seconds: index * step, duration_seconds: step * .8 }); });
  });
  return { step, events };
}
function download(blob, filename) { const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); }
el("harmony-choose").oninput = e => el("harmony-choose-value").textContent = e.target.value;
el("compose-generate").onclick = generateHarmony;
el("bass-generate").onclick = generateBass;
el("melody-generate").onclick = generateMelody;
el("progression-play").onclick = playProgression;
el("progression-stop").onclick = () => { stopProgression(); setComposeStatus("", ""); };
el("export-midi").onclick = async () => {
  try {
    requireChords();
    const { step, events } = compositionEvents(), beat = beatSeconds();
    const notes = events.map(event => ({ ratio: event.ratio, start_beats: event.start_seconds / beat, duration_beats: event.duration_seconds / beat }));
    const response = await fetch("/api/export/midi", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ notes, base_frequency: Number(el("base-frequency").value), pitch_bend: el("midi-pitch-bend").checked }) });
    if (!response.ok) throw new Error("MIDI エクスポートに失敗しました。");
    download(await response.blob(), "composition.mid"); setComposeStatus(`${notes.length} notes → MIDI`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
};
el("export-json").onclick = async () => {
  try {
    requireChords();
    const composition = { seed: Number(el("harmony-seed").value), tempo: Number(el("tempo").value), chords: composeState.chords, bass: composeState.bass, melody: composeState.melody };
    const data = await postJson("/api/export/json", { name: "Pure Intonation Composition", composition });
    download(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), "composition.json");
    setComposeStatus("JSON を保存しました", "");
  } catch (error) { setComposeStatus(error.message, "error"); }
};
el("render-wav").onclick = async () => {
  try {
    requireChords();
    const { events } = compositionEvents();
    const waveform = { sawtooth: "saw" }[el("waveform").value] || el("waveform").value;
    el("render-status").textContent = "Rendering…";
    const job = await postJson("/api/render/jobs", { events, base_frequency: Number(el("base-frequency").value), waveform, attack_seconds: Number(el("attack").value) / 1000, decay_seconds: Number(el("decay").value) / 1000, sustain_level: Number(el("sustain").value) / 100, release_seconds: Number(el("release").value) / 1000, reverb_amount: .2 });
    let status = job.status;
    while (status !== "completed" && status !== "failed") {
      await new Promise(resolve => setTimeout(resolve, 600));
      const current = await (await fetch(`/api/render/jobs/${job.job_id}`)).json();
      status = current.status; el("render-status").textContent = `Render: ${status}`;
      if (current.error) throw new Error(current.error);
    }
    const player = el("render-player"); player.src = `/api/render/jobs/${job.job_id}/audio`; player.hidden = false;
    el("render-status").textContent = "Render: completed";
  } catch (error) { el("render-status").textContent = error.message; }
};

// ---- Rhythm: euclidean / humanize ----
const rhythmState = { pattern: [], hits: [], scheduled: [] };
function setRhythmStatus(text, kind = "") { const s = el("rhythm-status"); s.textContent = text; s.className = kind; }
function renderRhythmGrid() {
  const grid = el("rhythm-grid"); grid.innerHTML = "";
  const velocity = new Map(rhythmState.hits.map(hit => [hit.step, hit.velocity]));
  rhythmState.pattern.forEach((active, index) => {
    const cell = document.createElement("div");
    cell.className = `step${active ? " on" : ""}`;
    cell.textContent = active ? (velocity.has(index) ? velocity.get(index) : "●") : index + 1;
    if (velocity.has(index)) cell.style.opacity = .45 + .55 * velocity.get(index) / 127;
    grid.append(cell);
  });
}
async function generateRhythm() {
  try {
    setRhythmStatus("Generating…", "loading");
    const data = await postJson("/api/rhythm/euclidean", { steps: Number(el("rhythm-steps").value), pulses: Number(el("rhythm-pulses").value), rotation: Number(el("rhythm-rotation").value) });
    rhythmState.pattern = data.pattern; rhythmState.hits = [];
    renderRhythmGrid(); setRhythmStatus(`${data.pulses}/${data.steps}`, "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
}
async function humanizeRhythm() {
  try {
    if (!rhythmState.pattern.length) throw new Error("先にリズムを生成してください。");
    const data = await postJson("/api/rhythm/humanize", { pattern: rhythmState.pattern, seed: Number(el("humanize-seed").value), timing_amount_ms: Number(el("humanize-timing").value) });
    rhythmState.hits = data.hits; renderRhythmGrid(); setRhythmStatus(`Humanized (seed ${data.seed})`, "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
}
function stopRhythm() { rhythmState.scheduled.forEach(osc => { try { osc.stop(); } catch { /* already stopped */ } }); rhythmState.scheduled = []; }
function playRhythm() {
  if (!rhythmState.pattern.length) { setRhythmStatus("先にリズムを生成してください。", "error"); return; }
  stopRhythm();
  const context = audioContext(), step = beatSeconds() / 2, now = context.currentTime + .1;
  const hit = new Map(rhythmState.hits.map(h => [h.step, h]));
  for (let cycle = 0; cycle < 4; cycle++) {
    rhythmState.pattern.forEach((active, index) => {
      if (!active) return;
      const info = hit.get(index), start = now + (cycle * rhythmState.pattern.length + index) * step + (info ? info.timing_offset_ms / 1000 : 0);
      const osc = context.createOscillator(), gain = context.createGain(), level = .3 * (info ? info.velocity : 100) / 127;
      osc.type = "square"; osc.frequency.value = index % 4 === 0 ? 180 : 320;
      gain.gain.setValueAtTime(level, start); gain.gain.exponentialRampToValueAtTime(.0001, start + .07);
      osc.connect(gain).connect(context.destination); osc.start(start); osc.stop(start + .1);
      rhythmState.scheduled.push(osc);
    });
  }
  setRhythmStatus("Playing…", "loading");
}
el("rhythm-generate").onclick = generateRhythm;
el("humanize-run").onclick = humanizeRhythm;
el("rhythm-play").onclick = playRhythm;
el("rhythm-stop").onclick = () => { stopRhythm(); setRhythmStatus("", ""); };
el("rhythm-export-midi").onclick = async () => {
  try {
    if (!rhythmState.pattern.length) throw new Error("先にリズムを生成してください。");
    const velocities = rhythmState.pattern.map((_, index) => rhythmState.hits.find(hit => hit.step === index)?.velocity ?? 0);
    const response = await fetch("/api/export/rhythm/midi", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ pattern: rhythmState.pattern, note: Number(el("rhythm-note").value), velocities }) });
    if (!response.ok) throw new Error((await response.json()).detail || "MIDI エクスポートに失敗しました。");
    download(await response.blob(), "rhythm.mid"); setRhythmStatus("MIDI を保存しました", "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
};
el("rhythm-export-json").onclick = async () => {
  try {
    if (!rhythmState.pattern.length) throw new Error("先にリズムを生成してください。");
    const rhythm = { generator: "euclidean", steps: Number(el("rhythm-steps").value), pulses: Number(el("rhythm-pulses").value), rotation: Number(el("rhythm-rotation").value), pattern: rhythmState.pattern, seed: Number(el("humanize-seed").value), hits: rhythmState.hits };
    const data = await postJson("/api/export/json", { name: "Euclidean Rhythm", composition: { rhythm } });
    download(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), "rhythm.json");
    setRhythmStatus("JSON を保存しました", "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
};
generateRhythm();

// ---- Scale editor / snapping / harmonics ----
function jsMonzo(ratio) {
  const [numerator, denominator] = ratioParts(ratio), map = {};
  const factor = (value, sign) => { let number = value, divisor = 2; while (divisor * divisor <= number) { while (number % divisor === 0) { map[divisor] = (map[divisor] || 0) + sign; number /= divisor; } divisor += divisor === 2 ? 1 : 2; } if (number > 1) map[number] = (map[number] || 0) + sign; };
  factor(numerator, 1); factor(denominator, -1); return map;
}
el("note-add").onclick = async () => {
  const value = el("note-input").value.trim(); if (!value) return;
  try {
    const data = await postJson("/api/analyze-interval", { value });
    state.pitches.push(data); state.pitches.sort((a, b) => a.cents - b.cents);
    el("note-input").value = ""; render(); setStatus(`added ${data.ratio}`, "");
  } catch (error) { setStatus(error.message, "error"); }
};
el("note-input").onkeydown = event => { if (event.key === "Enter") el("note-add").click(); };
el("snap-all").onclick = async () => {
  if (!state.pitches.length) return;
  try {
    const data = await postJson("/api/tuning/snap", { ratios: state.pitches.map(p => p.ratio), mode: el("snap-mode").value, value: Number(el("snap-value").value) });
    state.pitches = data.pitches.map(p => ({ ratio: p.ratio, cents: p.cents, monzo: jsMonzo(p.ratio) }));
    state.focus = null; render(); setStatus(`snapped ${data.pitches.length} intervals`, "");
  } catch (error) { setStatus(error.message, "error"); }
};
el("harmonics-toggle").onchange = renderCircle;
el("harmonics-count").onchange = () => { if (el("harmonics-toggle").checked) renderCircle(); };

// ---- Scale browser ----
function setScalesStatus(text, kind = "") { const s = el("scales-status"); s.textContent = text; s.className = kind; }
function adoptPitches(pitches, name) {
  stopAll();
  state.pitches = pitches; state.focus = null; state.graph = null; state.gridLayout = null; state.showGraph = false; state.walk = null; state.layout = null;
  el("scale-name").textContent = name; render();
}
async function refreshScales() {
  try {
    const list = await (await fetch("/api/scales")).json();
    el("scale-list").innerHTML = "";
    list.forEach(item => {
      const row = document.createElement("div"); row.className = "scale-row";
      const title = document.createElement("span"); title.className = "scale-title"; title.textContent = item.name;
      const count = document.createElement("span"); count.className = "scale-count"; count.textContent = `${item.count} notes`;
      const load = document.createElement("button"); load.className = "quiet"; load.textContent = "Load";
      load.onclick = async () => {
        try {
          const data = await (await fetch(`/api/scales/${encodeURIComponent(item.name)}`)).json();
          adoptPitches(data.pitches, `${item.name} · ${data.count} intervals`);
        } catch (error) { setScalesStatus(error.message, "error"); }
      };
      const del = document.createElement("button"); del.className = "quiet del"; del.textContent = "×";
      del.onclick = async () => { await fetch(`/api/scales/${encodeURIComponent(item.name)}`, { method: "DELETE" }); refreshScales(); };
      row.append(title, count, load, del); el("scale-list").append(row);
    });
  } catch (error) { setScalesStatus(error.message, "error"); }
}
el("scale-save").onclick = async () => {
  if (!state.pitches.length) { setScalesStatus("先に音階を生成してください。", "error"); return; }
  try {
    const data = await postJson("/api/scales", { name: el("scale-save-name").value, ratios: state.pitches.map(p => p.ratio) });
    setScalesStatus(`saved "${data.name}"`, ""); refreshScales();
  } catch (error) { setScalesStatus(error.message, "error"); }
};
el("scala-import").onclick = () => el("scala-file").click();
el("scala-file").onchange = async event => {
  const file = event.target.files[0]; event.target.value = "";
  if (!file) return;
  try {
    const data = await postJson("/api/scales/import", { name: file.name.replace(/\.scl$/i, ""), content: await file.text() });
    adoptPitches(data.pitches, `${data.name} · ${data.count} intervals`); refreshScales();
    setScalesStatus(`imported "${data.name}"`, "");
  } catch (error) { setScalesStatus(error.message, "error"); }
};
refreshScales();
