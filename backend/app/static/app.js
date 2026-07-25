const el = id => document.getElementById(id);
const state = { pitches: [], active: new Map(), context: null, focus: null, graph: null, showGraph: false, recording: false, recorded: [], walk: null, layout: null, gridLayout: null, reference: 0, compositionNode: null };
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
  renderHarmonyStackOnCircle(ctx, mid, radius);
  if(state.active.size===2){
    const [a,b]=[...state.active.keys()];
    const [an,ad]=ratioParts(state.pitches[a].ratio), [bn,bd]=ratioParts(state.pitches[b].ratio);
    let n=an*bd, d=ad*bn; const g=gcd(n,d); n/=g; d/=g;
    while(n>=d*2) d*=2; while(n<d) n*=2;
    ctx.strokeStyle="#ffd47e"; ctx.lineWidth=3; ctx.beginPath(); ctx.moveTo(points[a].x,points[a].y); ctx.lineTo(points[b].x,points[b].y); ctx.stroke();
    ctx.fillStyle="#ffd47e"; ctx.font="bold 13px system-ui"; ctx.textAlign="center";
    ctx.fillText(`${n}/${d}`, (points[a].x+points[b].x)/2, (points[a].y+points[b].y)/2-8);
  }
  if(typeof latticeState!=="undefined"&&latticeState.tones.length){
    latticeState.tones.forEach((tone,i)=>{
      const angle=((tone.cents%1200)+1200)%1200/1200*Math.PI*2-Math.PI/2;
      const x=mid+Math.cos(angle)*(radius+16), y=mid+Math.sin(angle)*(radius+16);
      ctx.fillStyle="#fff4cf"; ctx.save(); ctx.translate(x,y); ctx.rotate(Math.PI/4); ctx.fillRect(-6,-6,12,12); ctx.restore();
      ctx.fillStyle="#fff4cf"; ctx.font="11px system-ui"; ctx.textAlign="center";
      ctx.fillText(tone.normalized_ratio, mid+Math.cos(angle)*(radius+40), mid+Math.sin(angle)*(radius+40)+4);
      ctx.fillStyle="#10131c"; ctx.fillText(String(i+1), x, y+3.5);
    });
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
    const onPath = order.has(index), current = index === state.compositionNode;
    ctx.fillStyle = current ? "#ff9ab0" : onPath ? "#ffd47e" : "#98e7ca"; ctx.beginPath(); ctx.arc(point.x, point.y, current ? 16 : onPath ? 13 : 9, 0, Math.PI * 2); ctx.fill();
    if (current) { ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(point.x, point.y, 22, 0, Math.PI * 2); ctx.stroke(); }
    ctx.fillStyle = "#10131c"; ctx.font = "bold 10px system-ui"; ctx.textAlign = "center"; ctx.fillText(String(index + 1), point.x, point.y + 4);
    if (onPath) { ctx.fillStyle = "#ffd47e"; ctx.font = "bold 11px system-ui"; ctx.fillText(`#${order.get(index) + 1}`, point.x, point.y - 15); }
    ctx.fillStyle = "#aeb9d0"; ctx.font = "12px system-ui"; ctx.fillText(nodes[index].ratio, point.x, point.y + 26);
  });
  renderHarmonyStack(ctx, 18, 18);
  el("circle").onclick = event => { const nearest = nearestGraphNode(points, event); if (nearest.distance < 28) { selectCompositionNode(nearest.index); playGraphNode(nodes, nearest.index); } };
}
async function loadGridLayout() {
  try {
    const input = composeState.graph === state.graph ? composeState.graphInput : { factors: parseFactors(), choose: Number(el("choose").value) };
    const data = await postJson("/api/harmonic-graph", { ...input, layout: "reference_layered_grid", reference: state.reference, sort_mode: el("grid-sort").value });
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
    const isReference = index === layout.reference, onPath = order.has(index), current = index === state.compositionNode;
    ctx.fillStyle = current ? "#ff9ab0" : onPath || isReference ? "#ffd47e" : "#98e7ca";
    ctx.beginPath(); ctx.arc(point.x, point.y, current ? 16 : isReference ? 15 : onPath ? 13 : 9, 0, Math.PI * 2); ctx.fill();
    if (isReference) { ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(point.x, point.y, 20, 0, Math.PI * 2); ctx.stroke(); }
    ctx.fillStyle = "#10131c"; ctx.font = "bold 10px system-ui"; ctx.textAlign = "center"; ctx.fillText(String(index + 1), point.x, point.y + 4);
    if (onPath) { ctx.fillStyle = "#ffd47e"; ctx.font = "bold 11px system-ui"; ctx.fillText(`#${order.get(index) + 1}`, point.x, point.y - 26); }
    ctx.fillStyle = "#aeb9d0"; ctx.font = "11px system-ui";
    ctx.fillText(`{${nodes[index].factors.join(",")}}`, point.x, point.y + 26);
    ctx.fillText(sub ? nodes[index].sub_ratio : nodes[index].ratio, point.x, point.y + 40);
  });
  renderHarmonyStack(ctx, 18, 18);
  el("circle").onclick = event => { const nearest = nearestGraphNode(points, event); if (nearest.distance < 28) { selectCompositionNode(nearest.index); playGraphNode(nodes, nearest.index); } };
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
function stopAll() { [...state.active.keys()].forEach(stop); stopAllLatticeTones(); }
el("generator").onchange=syncGeneratorFields; el("choose").oninput=event=>el("choose-value").textContent=event.target.value; el("generate").onclick=generate; el("stop").onclick=stopAll;
el("base-frequency").oninput=e=>el("base-output").textContent=`${e.target.value} Hz`; ["attack","decay","release"].forEach(id=>el(id).oninput=e=>el(`${id}-output`).textContent=`${e.target.value} ms`); el("sustain").oninput=e=>el("sustain-output").textContent=`${e.target.value}%`;
document.addEventListener("keydown", event=>{if(event.defaultPrevented || event.repeat || /INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return; const index=keyboardKeys.indexOf(event.key.toUpperCase()); if(index>=0){event.preventDefault();play(index);}}); document.addEventListener("keyup",event=>{if(event.defaultPrevented)return;const index=keyboardKeys.indexOf(event.key.toUpperCase());if(index>=0)stop(index)});
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
const composeState = { chords: [], bass: [], melody: [], scheduled: [], activeStep: null, playhead: null, playheadFrame: null, graph: null, graphInput: null };
function setComposeStatus(text, kind = "") { const s = el("compose-status"); s.textContent = text; s.className = kind; }
function ratioValue(ratio) { const [n, d] = ratio.split("/").map(Number); return n / d; }
function ratioMul(ratio, factor) { const [n, d] = ratio.split("/").map(Number); let num = n * factor, den = d; const g = gcd(num, den); num /= g; den /= g; while (num >= den * 2) den *= 2; while (num < den) num *= 2; return `${num}/${den}`; }
function chordTones(chord) {
  if (Array.isArray(chord.tones) && chord.tones.length) return [...new Set(chord.tones)];
  const tones = [chord.ratio];
  chord.factors.filter(f => f !== 1).forEach(f => { const tone = ratioMul(chord.ratio, f); if (!tones.includes(tone)) tones.push(tone); });
  return tones;
}
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
    button.className = index === composeState.activeStep ? "active" : "";
    const score = chord.transition_score === null ? "" : `Δ ${chord.transition_score.toFixed(2)}`;
    button.innerHTML = `<span class="chord-index">${index + 1}</span><span>${chord.ratio}</span><span class="chord-score">${score}</span>`;
    button.title = chordTones(chord).join("  ");
    button.onclick = () => selectCompositionStep(index, true);
    el("progression").append(button);
  });
}
async function generateHarmony() {
  try {
    const choose = Number(el("harmony-choose").value), factors = parseFactors(el("harmony-factors").value);
    setComposeStatus("Generating…", "loading");
    const data = await postJson("/api/compose/harmony", { factors, choose, length: Number(el("harmony-length").value), seed: Number(el("harmony-seed").value), metric: el("harmony-metric").value });
    const graph = await postJson("/api/harmonic-graph", { factors, choose });
    composeState.chords = data.chords; composeState.bass = []; composeState.melody = []; composeState.activeStep = 0;
    composeState.graph = graph; composeState.graphInput = { factors, choose }; state.graph = graph; state.walk = data.chords.map(chord => chord.node); state.layout = null; state.gridLayout = null; state.compositionNode = data.chords[0]?.node ?? null; el("graph-toggle").hidden = false;
    el("composition-roll-panel").hidden = false; renderProgression(); renderCompositionRoll(); setComposeStatus(`${data.length} chords`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
function requireChords() { if (!composeState.chords.length) throw new Error("先に和声進行を生成してください。"); }
async function generateBass() {
  try {
    requireChords(); setComposeStatus("Bass…", "loading");
    const data = await postJson("/api/compose/bass", { chords: composeState.chords.map(chordTones), strategy: el("bass-strategy").value });
    composeState.bass = data.notes; renderCompositionRoll(); setComposeStatus(`Bass: ${data.notes.length} notes`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
async function generateMelody() {
  try {
    requireChords(); setComposeStatus("Melody…", "loading");
    const data = await postJson("/api/compose/melody", { chords: composeState.chords.map(chordTones), voice_count: Number(el("melody-voices").value), seed: Number(el("harmony-seed").value), contour: el("melody-contour").value });
    composeState.melody = data.voices; renderCompositionRoll(); setComposeStatus(`Melody: ${data.voices.length} voices`, "");
  } catch (error) { setComposeStatus(error.message, "error"); }
}
function scheduleTone(frequency, start, duration, level = 0.2) {
  const context = audioContext(), osc = context.createOscillator(), gain = context.createGain();
  osc.type = el("waveform").value; osc.frequency.value = frequency;
  gain.gain.setValueAtTime(.0001, start); gain.gain.exponentialRampToValueAtTime(level, start + .02); gain.gain.setTargetAtTime(.0001, start + duration, .08);
  osc.connect(gain).connect(context.destination); osc.start(start); osc.stop(start + duration + .6);
  composeState.scheduled.push(osc);
}
function stopProgression() { composeState.scheduled.forEach(osc => { try { osc.stop(); } catch { /* already stopped */ } }); composeState.scheduled = []; stopCompositionPlayhead(); }
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
  startCompositionPlayhead(now, step);
  setComposeStatus("Playing…", "loading");
}
function auditionChord(chord) { stopProgression(); const now = audioContext().currentTime + 0.05; chordTones(chord).forEach(r => scheduleTone(Number(el("base-frequency").value) * ratioValue(r), now, 1.2)); }
function syncCompositionNode() { state.compositionNode = composeState.chords[composeState.activeStep]?.node ?? null; }
function selectCompositionStep(index, audition = false) {
  const chord = composeState.chords[index]; if (!chord) return;
  composeState.activeStep = index; syncCompositionNode();
  if (chord.lattice && typeof latticeState !== "undefined") { latticeState.activeWalkStep = index; renderLatticeKeyboard(); }
  if (audition) auditionChord(chord);
  renderProgression(); renderCompositionRoll(); renderCircle();
}
function selectCompositionNode(node) { const step = composeState.chords.findIndex(chord => chord.node === node); if (step >= 0) selectCompositionStep(step); }
function renderHarmonyStack(ctx, left, top) {
  const chord = composeState.chords[composeState.activeStep]; if (!chord) return;
  const tones = chordTones(chord), descriptor = chord.lattice ? `r=(${chord.lattice.root_vector.join(",")})` : `{${chord.factors.join(",")}}`;
  const width = Math.max(128, Math.min(240, descriptor.length * 6 + 16)), row = 17, height = 30 + tones.length * row;
  ctx.fillStyle = "#10131ce6"; ctx.fillRect(left, top, width, height); ctx.strokeStyle = "#40506d"; ctx.strokeRect(left, top, width, height);
  ctx.fillStyle = "#ffd47e"; ctx.font = "bold 11px system-ui"; ctx.textAlign = "left"; ctx.fillText(`Step ${composeState.activeStep + 1}`, left + 8, top + 14);
  ctx.fillStyle = "#aeb9d0"; ctx.font = "10px system-ui"; ctx.fillText(descriptor, left + 8, top + 26);
  tones.forEach((ratio, index) => { const y = top + 32 + index * row; ctx.fillStyle = "#98e7ca"; ctx.fillRect(left + 8, y, width - 16, 13); ctx.fillStyle = "#092118"; ctx.font = "10px system-ui"; ctx.textAlign = "center"; ctx.fillText(ratio, left + width / 2, y + 10); });
}
function renderHarmonyStackOnCircle(ctx, mid, radius) {
  const chord = composeState.chords[composeState.activeStep]; if (!chord) return;
  const points = chordTones(chord).map(ratio => { const angle = (centsForRatio(ratio) / 1200) * Math.PI * 2 - Math.PI / 2; return { ratio, x: mid + Math.cos(angle) * (radius + 16), y: mid + Math.sin(angle) * (radius + 16) }; });
  ctx.strokeStyle = "#ffd47e"; ctx.lineWidth = 3; ctx.globalAlpha = .8; ctx.beginPath(); points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y)); if (points.length > 2) ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1;
  points.forEach(point => { ctx.fillStyle = "#ffd47e"; ctx.beginPath(); ctx.arc(point.x, point.y, 8, 0, Math.PI * 2); ctx.fill(); });
  renderHarmonyStack(ctx, 18, 18);
}
function centsForRatio(ratio) { return 1200 * Math.log2(ratioValue(ratio)); }
function compositionViewModel() {
  const notes = [];
  composeState.chords.forEach((chord, step) => chordTones(chord).forEach(ratio => notes.push({ layer:"harmony", step, ratio, cents:centsForRatio(ratio) })));
  composeState.bass.forEach((note, step) => notes.push({ layer:"bass", step, ratio:note.ratio, cents:centsForRatio(note.ratio), strategy:note.strategy, leap:note.leap_cents }));
  composeState.melody.forEach((voice, voiceIndex) => voice.forEach((note, step) => notes.push({ layer:"melody", voice:voiceIndex, step, ratio:note.ratio, cents:centsForRatio(note.ratio) })));
  return notes;
}
function renderCompositionRoll() {
  const canvas = el("composition-roll"); if (!canvas || !composeState.chords.length) return;
  const ctx = canvas.getContext("2d"), width = canvas.width, height = canvas.height, left = 68, right = 20, top = 20, bottom = 40, steps = composeState.chords.length;
  const notes = compositionViewModel(), values = notes.map(note => note.cents), low = Math.floor((Math.min(...values, 0) - 240) / 1200) * 1200, high = Math.ceil((Math.max(...values, 1200) + 240) / 1200) * 1200, range = Math.max(1200, high - low);
  const x = step => left + (step + .5) * (width - left - right) / steps, y = cents => top + (high - cents) / range * (height - top - bottom), band = (width - left - right) / steps;
  ctx.clearRect(0, 0, width, height); ctx.fillStyle = "#111622"; ctx.fillRect(0, 0, width, height);
  for (let cent = low; cent <= high; cent += 1200) { const py = y(cent); ctx.strokeStyle = "#30394d"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(left, py); ctx.lineTo(width - right, py); ctx.stroke(); ctx.fillStyle = "#aeb9d0"; ctx.font = "12px system-ui"; ctx.textAlign = "right"; ctx.fillText(`${cent}c`, left - 8, py + 4); }
  composeState.chords.forEach((chord, step) => { const px = left + step * band; ctx.fillStyle = step === composeState.activeStep ? "#98e7ca22" : "#ffffff06"; ctx.fillRect(px, top, band, height - top - bottom); ctx.strokeStyle = "#30394d"; ctx.beginPath(); ctx.moveTo(px, top); ctx.lineTo(px, height - bottom); ctx.stroke(); ctx.fillStyle = "#aeb9d0"; ctx.textAlign = "center"; ctx.font = "12px system-ui"; ctx.fillText(String(step + 1), x(step), height - 15); });
  if (el("roll-harmony").checked) composeState.chords.forEach((chord, step) => chordTones(chord).forEach(ratio => { const py = y(centsForRatio(ratio)); ctx.fillStyle = "#98e7ca"; ctx.fillRect(x(step) - 19, py - 8, 38, 16); ctx.fillStyle = "#092118"; ctx.font = "10px system-ui"; ctx.textAlign = "center"; ctx.fillText(ratio, x(step), py + 3); }));
  if (el("roll-bass").checked && composeState.bass.length) { ctx.strokeStyle = "#ffd47e"; ctx.lineWidth = 5; ctx.beginPath(); composeState.bass.forEach((note, step) => step ? ctx.lineTo(x(step), y(centsForRatio(note.ratio))) : ctx.moveTo(x(step), y(centsForRatio(note.ratio)))); ctx.stroke(); composeState.bass.forEach((note, step) => { ctx.fillStyle = "#ffd47e"; ctx.beginPath(); ctx.arc(x(step), y(centsForRatio(note.ratio)), 7, 0, Math.PI * 2); ctx.fill(); }); }
  if (el("roll-melody").checked) composeState.melody.forEach((voice, voiceIndex) => { const colors = ["#83b7ff", "#caa8ff", "#ff9ab0", "#f7c568"], color = colors[voiceIndex % colors.length]; ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.beginPath(); voice.forEach((note, step) => step ? ctx.lineTo(x(step), y(centsForRatio(note.ratio))) : ctx.moveTo(x(step), y(centsForRatio(note.ratio)))); ctx.stroke(); voice.forEach((note, step) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x(step), y(centsForRatio(note.ratio)), 5, 0, Math.PI * 2); ctx.fill(); }); });
  if (composeState.playhead !== null) { const px = left + composeState.playhead * band; ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(px, top); ctx.lineTo(px, height - bottom); ctx.stroke(); }
  const active = composeState.activeStep; const chord = composeState.chords[active]; const extra = composeState.bass[active] ? ` · bass ${composeState.bass[active].ratio}` : ""; el("roll-status").textContent = `${steps} steps`; el("roll-inspector").textContent = chord ? `Step ${active + 1}: ${chordTones(chord).join(" · ")}${extra}` : "";
}
function startCompositionPlayhead(startTime, stepSeconds) { stopCompositionPlayhead(); const context = audioContext(); const frame = () => { const position = (context.currentTime - startTime) / stepSeconds; if (position < 0) { composeState.playhead = 0; } else if (position <= composeState.chords.length) { composeState.playhead = position; composeState.activeStep = Math.min(composeState.chords.length - 1, Math.floor(position)); syncCompositionNode(); } else { stopCompositionPlayhead(); return; } renderCompositionRoll(); if (state.showGraph) renderCircle(); composeState.playheadFrame = requestAnimationFrame(frame); }; frame(); }
function stopCompositionPlayhead() { if (composeState.playheadFrame) cancelAnimationFrame(composeState.playheadFrame); composeState.playheadFrame = null; composeState.playhead = null; if (composeState.chords.length) renderCompositionRoll(); }
el("composition-roll").onclick = event => { if (!composeState.chords.length) return; const rect = event.currentTarget.getBoundingClientRect(), x = (event.clientX - rect.left) * event.currentTarget.width / rect.width, step = Math.max(0, Math.min(composeState.chords.length - 1, Math.floor((x - 68) / (event.currentTarget.width - 88) * composeState.chords.length))); selectCompositionStep(step, true); };
[
  "roll-harmony", "roll-bass", "roll-melody"
].forEach(id => el(id).onchange = renderCompositionRoll);
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

// ---- Drums: coordinated 4-layer sequencer (development_plan_rhythm.md R12) ----
const DRUM_LAYER_DEFS = [
  { name: "kick", steps: 16, pulses: 5, note: 36, color: "#ffd47e", phase_increment: 0, phase_update_bars: 4, base_velocity: 110 },
  { name: "snare", steps: 16, pulses: 3, note: 38, color: "#ff9d9a", phase_increment: 1, phase_update_bars: 4, base_velocity: 100 },
  { name: "hat", steps: 13, pulses: 8, note: 42, color: "#98e7ca", phase_increment: 1, phase_update_bars: 3, base_velocity: 80 },
  { name: "perc", steps: 17, pulses: 6, note: 46, color: "#83b7ff", phase_increment: 2, phase_update_bars: 5, base_velocity: 90 },
];
const DRUM_STEPS_PER_BAR = 16;
function setRhythmStatus(text, kind = "") { const s = el("rhythm-status"); s.textContent = text; s.className = kind; }
const drumState = { layers: [], scheduled: [], playhead: null };
function euclideanLocal(steps, pulses) { return Array.from({ length: steps }, (_, i) => (i * pulses) % steps < pulses && pulses > 0 ? 1 : 0); }
function rotateRight(pattern, r) { const n = pattern.length, rot = ((r % n) + n) % n; return pattern.map((_, i) => pattern[(i - rot + n) % n]); }
function drumLayers() { return drumState.layers; }
function buildDrumUI() {
  const box = el("drum-layers"); box.innerHTML = "";
  drumState.layers = DRUM_LAYER_DEFS.map(def => ({ ...def, pattern: euclideanLocal(def.steps, def.pulses), rotation: 0, velocities: [], phase_offsets: [] }));
  drumState.layers.forEach((layer, row) => {
    const line = document.createElement("div"); line.className = "drum-row";
    const head = document.createElement("div"); head.className = "drum-head";
    head.innerHTML = `<span class="drum-name" style="color:${layer.color}">${layer.name}</span>`;
    const steps = document.createElement("input"); steps.type = "number"; steps.min = 1; steps.max = 32; steps.value = layer.steps; steps.title = "ステップ数";
    const pulses = document.createElement("input"); pulses.type = "number"; pulses.min = 0; pulses.max = 32; pulses.value = layer.pulses; pulses.title = "パルス数";
    const badge = document.createElement("span"); badge.className = "drum-rot"; badge.id = `drum-rot-${layer.name}`;
    steps.onchange = () => { layer.steps = Math.max(1, Math.min(32, Number(steps.value))); layer.pattern = euclideanLocal(layer.steps, Math.min(Number(pulses.value), layer.steps)); pulses.value = Math.min(Number(pulses.value), layer.steps); renderDrumRow(row); markCollisions(); };
    pulses.onchange = () => { layer.pulses = Math.max(0, Math.min(layer.steps, Number(pulses.value))); layer.pattern = euclideanLocal(layer.steps, layer.pulses); renderDrumRow(row); markCollisions(); };
    head.append(steps, pulses, badge);
    const cells = document.createElement("div"); cells.className = "drum-cells"; cells.id = `drum-cells-${layer.name}`;
    line.append(head, cells); box.append(line);
    renderDrumRow(row);
  });
  markCollisions();
}
function renderDrumRow(row) {
  const layer = drumState.layers[row], cells = el(`drum-cells-${layer.name}`);
  cells.innerHTML = "";
  layer.pattern.forEach((active, i) => {
    const cell = document.createElement("div");
    cell.className = `step${active ? " on" : ""}`; cell.style.setProperty("--layer-color", layer.color);
    if (active && layer.velocities.length) cell.style.opacity = .45 + .55 * (layer.velocities[i] || layer.base_velocity) / 127;
    cell.textContent = active ? "" : i + 1;
    cell.onclick = () => { layer.pattern[i] = active ? 0 : 1; renderDrumRow(row); markCollisions(); };
    cells.append(cell);
  });
  el(`drum-rot-${layer.name}`).textContent = `rot ${layer.rotation}`;
}
function markCollisions() {
  const layers = drumState.layers; if (!layers.length) return;
  const window = Math.min(layers.reduce((a, l) => lcm(a, l.steps), 1), 64);
  const counts = Array.from({ length: window }, (_, t) => layers.reduce((n, l) => n + l.pattern[t % l.steps], 0));
  layers.forEach((layer, row) => {
    [...el(`drum-cells-${layer.name}`).children].forEach((cell, i) => {
      let max = 0;
      for (let t = i; t < window; t += layer.steps) max = Math.max(max, counts[t]);
      cell.classList.toggle("clash", layer.pattern[i] === 1 && max >= 2);
    });
  });
}
function lcm(a, b) { return a / gcd(a, b) * b; }
async function generateDrums() {
  try {
    setRhythmStatus("Generating…", "loading");
    const bars = Number(el("drum-bars").value);
    const data = await postJson("/api/drums/generate", {
      bars, seed: Number(el("drum-seed").value),
      layers: drumState.layers.map(l => ({ name: l.name, steps: l.steps, pulses: l.pulses, rotation: l.name === "kick" ? 0 : null, phase_increment: l.phase_increment, phase_update_bars: l.phase_update_bars, base_velocity: l.base_velocity })),
    });
    data.layers.forEach((result, row) => Object.assign(drumState.layers[row], { pattern: result.pattern, rotation: result.rotation, velocities: result.velocities, phase_offsets: result.phase_offsets }));
    drumState.layers.forEach((_, row) => renderDrumRow(row)); markCollisions();
    const m = data.metrics;
    el("drum-metrics").textContent = `density ${m.combined_density.toFixed(2)} · collisions ${Object.values(m.pairwise_collisions).reduce((a, b) => a + b, 0)} · all-four ${m.four_layer_collisions} · syncopation ${m.syncopation.toFixed(2)}`;
    setRhythmStatus(`${bars} bars`, "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
}
function drumHit(layer, time, velocity) {
  const context = audioContext(), osc = context.createOscillator(), gain = context.createGain(), level = .4 * velocity / 127;
  const settings = { kick: ["sine", 130, .14], snare: ["square", 190, .09], hat: ["square", 6000, .03], perc: ["triangle", 700, .06] }[layer.name];
  osc.type = settings[0]; osc.frequency.setValueAtTime(settings[1], time);
  if (layer.name === "kick") osc.frequency.exponentialRampToValueAtTime(45, time + settings[2]);
  gain.gain.setValueAtTime(level, time); gain.gain.exponentialRampToValueAtTime(.0001, time + settings[2]);
  osc.connect(gain).connect(context.destination); osc.start(time); osc.stop(time + settings[2] + .05);
  drumState.scheduled.push(osc);
}
function stopDrums() {
  drumState.scheduled.forEach(osc => { try { osc.stop(); } catch { /* already stopped */ } });
  drumState.scheduled = [];
  if (drumState.playhead) { clearInterval(drumState.playhead); drumState.playhead = null; }
  document.querySelectorAll(".drum-cells .now").forEach(c => c.classList.remove("now"));
  setRhythmStatus("", "");
}
function playDrums() {
  if (!drumState.layers.length || !drumState.layers[0].phase_offsets.length) { setRhythmStatus("先にドラムを生成してください。", "error"); return; }
  stopDrums();
  const bars = Number(el("drum-bars").value), stepDur = beatSeconds() / 4, now = audioContext().currentTime + .1;
  drumState.layers.forEach(layer => {
    for (let bar = 0; bar < bars; bar++) {
      const effective = rotateRight(layer.pattern, layer.phase_offsets[bar % layer.phase_offsets.length]);
      for (let s = 0; s < DRUM_STEPS_PER_BAR; s++) {
        const index = (bar * DRUM_STEPS_PER_BAR + s) % layer.steps;
        if (effective[index]) drumHit(layer, now + (bar * DRUM_STEPS_PER_BAR + s) * stepDur, layer.velocities[index] || layer.base_velocity);
      }
    }
  });
  const started = performance.now();
  drumState.playhead = setInterval(() => {
    const step = Math.floor((performance.now() - started) / 1000 / stepDur);
    if (step >= bars * DRUM_STEPS_PER_BAR) { stopDrums(); return; }
    document.querySelectorAll(".drum-cells .now").forEach(c => c.classList.remove("now"));
    drumState.layers.forEach(layer => {
      const cells = el(`drum-cells-${layer.name}`).children, index = step % layer.steps;
      if (cells[index]) cells[index].classList.add("now");
    });
  }, Math.max(30, stepDur * 1000 / 2));
  setRhythmStatus("Playing…", "loading");
}
function drumTimelinePattern(layer, bars) {
  const full = [], velocities = [];
  for (let bar = 0; bar < bars; bar++) {
    const effective = rotateRight(layer.pattern, layer.phase_offsets[bar % layer.phase_offsets.length]);
    for (let s = 0; s < DRUM_STEPS_PER_BAR; s++) {
      const index = (bar * DRUM_STEPS_PER_BAR + s) % layer.steps;
      full.push(effective[index]); velocities.push(effective[index] ? layer.velocities[index] || layer.base_velocity : 0);
    }
  }
  return { pattern: full, velocities };
}
el("drums-generate").onclick = generateDrums;
el("drums-play").onclick = playDrums;
el("drums-stop").onclick = stopDrums;
el("drums-export-midi").onclick = async () => {
  try {
    if (!drumState.layers.length || !drumState.layers[0].phase_offsets.length) throw new Error("先にドラムを生成してください。");
    const bars = Number(el("drum-bars").value);
    const layers = drumState.layers.map(layer => ({ note: layer.note, ...drumTimelinePattern(layer, bars) }));
    const response = await fetch("/api/export/rhythm/midi", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ layers, steps_per_beat: 4 }) });
    if (!response.ok) throw new Error((await response.json()).detail || "MIDI エクスポートに失敗しました。");
    download(await response.blob(), "drums.mid"); setRhythmStatus("MIDI を保存しました", "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
};
el("drums-export-json").onclick = async () => {
  try {
    if (!drumState.layers.length) throw new Error("先にドラムを生成してください。");
    const bars = Number(el("drum-bars").value);
    const rhythm = { generator: "coordinated-drums", bars, seed: Number(el("drum-seed").value), layers: drumState.layers.map(l => ({ name: l.name, steps: l.steps, pulses: l.pulses, pattern: l.pattern, rotation: l.rotation, note: l.note, velocities: l.velocities, phase_offsets: l.phase_offsets })) };
    const data = await postJson("/api/export/json", { name: "Drum Composition", composition: { rhythm } });
    download(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), "drums.json");
    setRhythmStatus("JSON を保存しました", "");
  } catch (error) { setRhythmStatus(error.message, "error"); }
};
buildDrumUI();

// ---- Lattice Lab (G9 exponent-lattice harmony laboratory, experimental) ----
const latticeState = { points: [], tones: [], offsets: [], walk: null, walkPitches: null, walkHarmonies: null, activeWalkStep: 0, activeKeys: new Map(), selected: null, dims: 0 };
const LATTICE_KEYS = "ASDFGHJKL;QWERTY".split("");
const GROUP_COLORS = ["#98e7ca", "#83b7ff", "#caa8ff", "#ffd47e", "#ff9d9a", "#a9b9ff", "#7ed6f2", "#f2a97e"];
function setLatticeStatus(text, kind = "") { const s = el("lattice-status"); s.textContent = text; s.className = kind; }
function parseInts(source) { const values = source.split(",").map(v => Number(v.trim())).filter(v => !Number.isNaN(v)); if (!values.length || values.some(v => !Number.isInteger(v))) throw new Error("整数をカンマ区切りで入力してください。"); return values; }
function latticeGenerators() { const g = parseInts(el("lattice-generators").value); if (g.some(v => v < 2) || g.length > 8) throw new Error("生成子は2以上の整数を8個まで入力してください。"); return g; }
function parseVectorRows(source, dims) {
  return source.split("\n").map(l => l.trim()).filter(Boolean).map(line => {
    const v = parseInts(line);
    if (v.length !== dims) throw new Error(`各ベクトルは ${dims} 次元にしてください。`);
    return v;
  });
}
function latticeKeyboardTones() {
  if (latticeState.tones.length) return latticeState.tones;
  return latticeState.walkHarmonies?.[latticeState.activeWalkStep]?.tones || [];
}
function startLatticeTone(index) {
  const tone = latticeKeyboardTones()[index];
  if (!tone || latticeState.activeKeys.has(index)) return;
  const context = audioContext(), osc = context.createOscillator(), gain = context.createGain(), now = context.currentTime;
  const attack = Number(el("attack").value) / 1000, decay = Number(el("decay").value) / 1000, sustain = Number(el("sustain").value) / 100;
  osc.type = el("waveform").value;
  osc.frequency.value = Number(el("base-frequency").value) * ratioValue(tone.normalized_ratio);
  gain.gain.setValueAtTime(.0001, now);
  gain.gain.exponentialRampToValueAtTime(.24, now + attack);
  gain.gain.exponentialRampToValueAtTime(Math.max(.001, .24 * sustain), now + attack + decay);
  osc.connect(gain).connect(context.destination); osc.start();
  latticeState.activeKeys.set(index, { osc, gain });
  el("lattice-keyboard").querySelector(`[data-lattice-index="${index}"]`)?.classList.add("active");
  setLatticeStatus(`${LATTICE_KEYS[index]} · ${tone.normalized_ratio}`, "");
}
function stopLatticeTone(index) {
  const voice = latticeState.activeKeys.get(index); if (!voice) return;
  const now = audioContext().currentTime, release = Number(el("release").value) / 1000;
  voice.gain.gain.cancelScheduledValues(now);
  voice.gain.gain.setTargetAtTime(.0001, now, release / 5);
  voice.osc.stop(now + release);
  latticeState.activeKeys.delete(index);
  el("lattice-keyboard").querySelector(`[data-lattice-index="${index}"]`)?.classList.remove("active");
}
function stopAllLatticeTones() { [...latticeState.activeKeys.keys()].forEach(stopLatticeTone); }
function renderLatticeKeyboard() {
  stopAllLatticeTones();
  const box = el("lattice-keyboard"); box.innerHTML = "";
  latticeKeyboardTones().slice(0, LATTICE_KEYS.length).forEach((tone, index) => {
    const button = document.createElement("button");
    button.className = "key"; button.dataset.latticeIndex = index;
    button.innerHTML = `<span class="key-name">${LATTICE_KEYS[index]}</span><span class="ratio">${tone.normalized_ratio}</span>`;
    button.onpointerdown = event => { event.preventDefault(); startLatticeTone(index); };
    button.onpointerup = () => stopLatticeTone(index);
    button.onpointercancel = () => stopLatticeTone(index);
    button.onpointerleave = () => stopLatticeTone(index);
    box.append(button);
  });
}
function syncLatticeAxes() {
  const dims = latticeState.dims;
  ["lattice-axis-x", "lattice-axis-y"].forEach((id, which) => {
    const select = el(id); select.innerHTML = "";
    for (let i = 0; i < dims; i++) { const option = document.createElement("option"); option.value = i; option.textContent = `a${i + 1}`; select.append(option); }
    select.value = which === 0 ? 0 : Math.min(1, dims - 1);
    select.onchange = renderLatticeCanvas;
  });
}
async function generateLattice() {
  try {
    stopAllLatticeTones();
    const generators = latticeGenerators();
    setLatticeStatus("Generating…", "loading");
    const data = await postJson("/api/exponent-lattice/scale", { generators, minimum: parseInts(el("lattice-min").value), maximum: parseInts(el("lattice-max").value), collision_policy: el("lattice-collision").value });
    latticeState.points = data.points; latticeState.dims = generators.length; latticeState.tones = []; latticeState.offsets = []; latticeState.walk = null; latticeState.walkPitches = null; latticeState.walkHarmonies = null;
    syncLatticeAxes(); renderLatticeTable(); renderLatticeCanvas(); renderLatticeKeyboard();
    setLatticeStatus(data.basis.warnings.length ? data.basis.warnings.join(" ") : `${data.point_count} points`, data.basis.warnings.length ? "error" : "");
  } catch (error) { setLatticeStatus(error.message, "error"); }
}
function renderLatticeTable() {
  const body = el("lattice-points"); body.innerHTML = "";
  latticeState.points.slice(0, 256).forEach((point, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td class="monzo">(${point.vector.join(",")})</td><td>${point.ratio}</td><td>${point.normalized_ratio}</td><td>${point.octave_shift}</td><td>${point.cents.toFixed(1)}</td><td>${point.collision_group}</td>`;
    row.onclick = () => { stopProgression(); scheduleTone(Number(el("base-frequency").value) * ratioValue(point.normalized_ratio), audioContext().currentTime + .05, 1.2); setLatticeStatus(`(${point.vector.join(",")}) → ${point.normalized_ratio} · group ${point.collision_group}`, ""); };
    body.append(row);
  });
  if (latticeState.points.length > 256) setLatticeStatus(`先頭256件を表示 (全 ${latticeState.points.length} 点)`, "");
}
function latticeProjection() {
  const canvas = el("lattice-canvas"), size = canvas.width, margin = 36;
  const ax = Number(el("lattice-axis-x").value || 0), ay = Number(el("lattice-axis-y").value || 0);
  const minimum = parseInts(el("lattice-min").value), maximum = parseInts(el("lattice-max").value);
  const sx = (size - margin * 2) / Math.max(1, maximum[ax] - minimum[ax]), sy = (size - margin * 2) / Math.max(1, maximum[ay] - minimum[ay]);
  const scale = Math.min(sx, sy);
  return { canvas, size, ax, ay, project: v => ({ x: margin + (v[ax] - minimum[ax]) * scale + (size - margin * 2 - (maximum[ax] - minimum[ax]) * scale) / 2, y: size - margin - (v[ay] - minimum[ay]) * scale - (size - margin * 2 - (maximum[ay] - minimum[ay]) * scale) / 2 }) };
}
function drawArrow(ctx, from, to, color, label) {
  const angle = Math.atan2(to.y - from.y, to.x - from.x), head = 7;
  ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(to.x, to.y); ctx.lineTo(to.x - head * Math.cos(angle - .5), to.y - head * Math.sin(angle - .5)); ctx.lineTo(to.x - head * Math.cos(angle + .5), to.y - head * Math.sin(angle + .5)); ctx.fill();
  if (label) { ctx.font = "10px system-ui"; ctx.textAlign = "center"; ctx.fillText(label, (from.x + to.x) / 2, (from.y + to.y) / 2 - 5); }
}
function renderLatticeCanvas() {
  const { canvas, size, ax, ay, project } = latticeProjection(), ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, size, size);
  latticeState.points.forEach(point => {
    const p = project(point.vector);
    ctx.fillStyle = GROUP_COLORS[point.collision_group % GROUP_COLORS.length];
    ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#aeb9d0"; ctx.font = "9px system-ui"; ctx.textAlign = "center";
    ctx.fillText(point.normalized_ratio, p.x, p.y - 8);
  });
  if (latticeState.offsets.length) {
    latticeState.offsets.slice(1).forEach((offset, i) => {
      drawArrow(ctx, project(latticeState.offsets[i]), project(offset), "#98e7ca", `Δ${i + 1}`);
    });
    const origin = project(latticeState.offsets[0]);
    ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(origin.x, origin.y, 9, 0, Math.PI * 2); ctx.stroke();
  }
  if (latticeState.walk && latticeState.walk.length > 1) {
    latticeState.walk.slice(1).forEach((vector, i) => drawArrow(ctx, project(latticeState.walk[i]), project(vector), "#ffd47e"));
  }
  if (latticeState.selected) {
    const p = project(latticeState.selected);
    ctx.strokeStyle = "#fff4cf"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(p.x, p.y, 10, 0, Math.PI * 2); ctx.stroke();
  }
  canvas.onclick = async event => {
    const rect = canvas.getBoundingClientRect(), x = (event.clientX - rect.left) * size / rect.width, y = (event.clientY - rect.top) * size / rect.height;
    const nearest = latticeState.points.reduce((best, point) => { const p = project(point.vector), d = Math.hypot(p.x - x, p.y - y); return d < best.distance ? { point, distance: d } : best; }, { point: null, distance: Infinity });
    if (!nearest.point || nearest.distance >= 24) { latticeState.selected = null; el("lattice-inspector").textContent = ""; renderLatticeCanvas(); return; }
    stopProgression(); scheduleTone(Number(el("base-frequency").value) * ratioValue(nearest.point.normalized_ratio), audioContext().currentTime + .05, 1.2);
    const point = nearest.point;
    if (latticeState.selected && latticeState.selected.join() !== point.vector.join()) {
      try {
        const generators = latticeGenerators();
        const analysis = await postJson("/api/exponent-lattice/analyze", { generators, vectors: [latticeState.selected, point.vector] });
        const d = analysis.distances[0], terms = generators.map((g, i) => `${g}^${point.vector[i]}`).join(" · ");
        el("lattice-inspector").textContent = `(${latticeState.selected.join(",")}) → (${point.vector.join(",")}): lattice L1 ${d.lattice_l1} · L2 ${d.lattice_l2.toFixed(2)} · monzo ${d.monzo} · cents ${d.cents.toFixed(1)} ｜ N(root · ${terms})`;
      } catch (error) { setLatticeStatus(error.message, "error"); }
      latticeState.selected = null;
    } else {
      latticeState.selected = point.vector;
      el("lattice-inspector").textContent = `(${point.vector.join(",")}) → ${point.ratio} = ${point.normalized_ratio} × 2^${-point.octave_shift} · ${point.cents.toFixed(1)} cents · group ${point.collision_group} ｜ 別の点をクリックすると距離を表示`;
    }
    renderLatticeCanvas();
  };
}
function orderLatticeTones() {
  if (!latticeState.tones.length) return;
  const mode = el("lattice-order").value;
  const pairs = latticeState.offsets.map((offset, i) => ({ offset, tone: latticeState.tones[i] }));
  if (mode === "ascending") pairs.sort((a, b) => a.tone.cents - b.tone.cents);
  else if (mode === "lexicographic") pairs.sort((a, b) => { for (let i = 0; i < a.offset.length; i++) { if (a.offset[i] !== b.offset[i]) return a.offset[i] - b.offset[i]; } return 0; });
  else if (mode === "nearest") {
    const remaining = pairs.splice(0), ordered = [remaining.shift()];
    while (remaining.length) {
      const last = ordered.at(-1).offset;
      let best = 0, distance = Infinity;
      remaining.forEach((candidate, i) => { const d = candidate.offset.reduce((sum, v, j) => sum + Math.abs(v - last[j]), 0); if (d < distance) { distance = d; best = i; } });
      ordered.push(remaining.splice(best, 1)[0]);
    }
    pairs.push(...ordered);
  }
  latticeState.offsets = pairs.map(p => p.offset); latticeState.tones = pairs.map(p => p.tone);
  renderLatticeCanvas(); renderCircle(); renderLatticeKeyboard();
  setLatticeStatus(`${latticeState.tones.length} tones: ${latticeState.tones.map(t => t.normalized_ratio).join("  ")}`, "");
}
el("lattice-order").onchange = orderLatticeTones;
async function generateLatticeChord() {
  try {
    const generators = latticeGenerators();
    setLatticeStatus("Generating chord…", "loading");
    const data = await postJson("/api/exponent-lattice/chord", {
      root: el("lattice-root").value,
      generators,
      allowed_differences: parseVectorRows(el("lattice-allowed").value, generators.length),
      tone_count: Number(el("lattice-chord-size").value),
      seed: Number(el("lattice-chord-seed").value),
      minimum: parseInts(el("lattice-min").value),
      maximum: parseInts(el("lattice-max").value)
    });
    el("lattice-diffs").value = data.differences.map(difference => difference.join(", ")).join("\n");
    latticeState.tones = data.tones; latticeState.offsets = data.offsets;
    latticeState.walk = null; latticeState.walkPitches = null; latticeState.walkHarmonies = null; latticeState.activeWalkStep = 0;
    if (!latticeState.points.length) { latticeState.dims = generators.length; syncLatticeAxes(); }
    orderLatticeTones();
    setLatticeStatus(`Generated chord · ${data.tones.length} tones · seed ${data.seed}`, "");
  } catch (error) { setLatticeStatus(error.message, "error"); }
}
async function reconstructHarmony() {
  try {
    const generators = latticeGenerators();
    const differences = parseVectorRows(el("lattice-diffs").value, generators.length);
    const data = await postJson("/api/exponent-lattice/harmony", { root: el("lattice-root").value, generators, differences });
    latticeState.tones = data.tones; latticeState.offsets = data.offsets; latticeState.walk = null; latticeState.walkPitches = null; latticeState.walkHarmonies = null; latticeState.activeWalkStep = 0;
    if (!latticeState.points.length) { latticeState.dims = generators.length; syncLatticeAxes(); }
    orderLatticeTones();
  } catch (error) { setLatticeStatus(error.message, "error"); }
}
async function latticeWalk() {
  try {
    const generators = latticeGenerators();
    const harmonyDifferences = parseVectorRows(el("lattice-diffs").value, generators.length);
    const data = await postJson("/api/exponent-lattice/walk", { generators, start_vector: generators.map(() => 0), allowed_differences: parseVectorRows(el("lattice-allowed").value, generators.length), root: el("lattice-root").value, harmony_differences: harmonyDifferences, length: Number(el("lattice-walk-length").value), seed: Number(el("lattice-walk-seed").value), minimum: parseInts(el("lattice-min").value), maximum: parseInts(el("lattice-max").value), boundary: el("lattice-boundary").value });
    latticeState.walk = data.path; latticeState.walkPitches = data.pitches; latticeState.walkHarmonies = data.harmonies; latticeState.activeWalkStep = 0; latticeState.tones = []; latticeState.offsets = [];
    if (!latticeState.points.length) { latticeState.dims = generators.length; syncLatticeAxes(); }
    renderLatticeCanvas(); renderCircle(); renderLatticeKeyboard();
    setLatticeStatus(`walk: ${data.path.length} steps · ${data.harmonies[0]?.tones.length || 0} tones per harmony`, "");
  } catch (error) { setLatticeStatus(error.message, "error"); }
}
el("lattice-scale").onclick = generateLattice;
el("lattice-chord-generate").onclick = generateLatticeChord;
el("lattice-harmony").onclick = reconstructHarmony;
el("lattice-walk").onclick = latticeWalk;
el("lattice-walk-play").onclick = () => {
  const harmonies = latticeState.walkHarmonies;
  if (!harmonies || !harmonies.length) { setLatticeStatus("先にウォークを生成してください。", "error"); return; }
  stopProgression();
  const base = Number(el("base-frequency").value), now = audioContext().currentTime + .1;
  const voiceCount = Math.max(1, ...harmonies.map(harmony => harmony.tones.length));
  const level = Math.min(.18, .32 / Math.sqrt(voiceCount));
  harmonies.forEach((harmony, i) => {
    harmony.tones.forEach(tone => scheduleTone(base * ratioValue(tone.normalized_ratio), now + i * .35, .3, level));
  });
  setLatticeStatus(`Playing walk · ${harmonies.length} harmonies × ${voiceCount} tones`, "loading");
};
function latticeComposeChord(harmony) {
  const tones = harmony.tones.map(tone => tone.normalized_ratio), generators = latticeGenerators();
  return {
    node: null,
    factors: [],
    ratio: tones[0],
    tones,
    transition_score: null,
    lattice: {
      generators,
      root_ratio: el("lattice-root").value,
      root_vector: harmony.root_vector,
      harmony_differences: parseVectorRows(el("lattice-diffs").value, generators.length),
      tone_vectors: harmony.tones.map(tone => tone.vector),
      offsets: harmony.tones.map(tone => tone.offset || tone.vector)
    }
  };
}
function sendLatticeToCompose(harmonies, label) {
  composeState.chords = harmonies.map(latticeComposeChord);
  composeState.bass = []; composeState.melody = [];
  composeState.activeStep = 0; composeState.graph = null; composeState.graphInput = null;
  state.compositionNode = null; state.walk = null; state.showGraph = false;
  el("visual-title").textContent = "Pitch circle"; el("graph-toggle").hidden = true; el("walk-controls").hidden = true;
  el("composition-roll-panel").hidden = false;
  renderProgression(); renderCompositionRoll(); renderCircle();
  setComposeStatus(`${label}: ${composeState.chords.length} chords`, "");
  document.querySelector(".compose").scrollIntoView({ behavior: "smooth" });
}
el("lattice-send-compose").onclick = () => {
  if (!latticeState.tones.length) { setLatticeStatus("先にハーモニーを再構成してください。", "error"); return; }
  const rootVector = latticeState.offsets[0]?.map(() => 0) || [];
  sendLatticeToCompose([{
    root_vector: rootVector,
    tones: latticeState.tones.map((tone, index) => ({ ...tone, offset: latticeState.offsets[index] }))
  }], "Lattice chord");
};
el("lattice-walk-compose").onclick = () => {
  if (!latticeState.walkHarmonies?.length) { setLatticeStatus("先にウォークを生成してください。", "error"); return; }
  sendLatticeToCompose(latticeState.walkHarmonies, "Lattice walk");
};
const latticePanel = el("lattice-panel");
latticePanel.addEventListener("keydown", event => {
  if (event.repeat || /INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return;
  const index = LATTICE_KEYS.indexOf(event.key.toUpperCase());
  if (index < 0 || !latticeKeyboardTones()[index]) return;
  event.preventDefault(); event.stopPropagation(); startLatticeTone(index);
});
latticePanel.addEventListener("keyup", event => {
  const index = LATTICE_KEYS.indexOf(event.key.toUpperCase());
  if (index < 0) return;
  event.preventDefault(); event.stopPropagation(); stopLatticeTone(index);
});
window.addEventListener("blur", stopAllLatticeTones);
