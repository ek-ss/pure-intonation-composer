const el = id => document.getElementById(id);
const state = { pitches: [], active: new Map(), context: null, focus: null, graph: null, showGraph: false, recording: false, recorded: [] };
const keyboardKeys = "ASDFGHJKL;QWERTYUIOPZXCVBNM".split("");

function setStatus(text, kind = "") { const status = el("status"); status.textContent = text; status.className = kind; }
function parseFactors() {
  const values = el("factors").value.split(",").map(v => Number(v.trim())).filter(Boolean);
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
    state.pitches = data.pitches; state.focus = null; state.graph = null; state.showGraph = false; el("graph-toggle").hidden = type !== "cps";
    if(type === "cps") { const graphResponse = await fetch("/api/harmonic-graph", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({factors:body.factors,choose:body.choose})}); state.graph = await graphResponse.json(); }
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
  const points=state.pitches.map(pitch=>circlePoint(pitch,mid,radius));
  points.forEach(point=>{ctx.strokeStyle="#40506d";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mid,mid);ctx.lineTo(point.x,point.y);ctx.stroke();});
  if(focus!==null){ const source=points[focus]; points.forEach((point,index)=>{if(index===focus)return;const relation=harmony(index);ctx.globalAlpha=.72;ctx.strokeStyle=relation.color;ctx.lineWidth=relation.level==="strong"?4:2;ctx.beginPath();ctx.moveTo(source.x,source.y);ctx.lineTo(point.x,point.y);ctx.stroke();});ctx.globalAlpha=1; }
  ctx.fillStyle="#aeb9d0"; ctx.font="15px system-ui"; ctx.textAlign="center"; ctx.fillText("1/1",mid,mid+5);
  state.pitches.forEach((pitch,index) => { const point=points[index], relation=harmony(index); const active=state.active.has(index); ctx.fillStyle=relation.color; ctx.beginPath(); ctx.arc(point.x,point.y,active?16:10,0,Math.PI*2); ctx.fill(); if(active){ctx.strokeStyle="#fff4cf";ctx.lineWidth=3;ctx.beginPath();ctx.arc(point.x,point.y,22,0,Math.PI*2);ctx.stroke();} ctx.fillStyle="#10131c";ctx.font="bold 10px system-ui";ctx.fillText(String(index+1),point.x,point.y+4);ctx.fillStyle=relation.color;ctx.font="13px system-ui";ctx.fillText(pitch.ratio,mid+Math.cos(point.angle)*(radius+31),point.y+Math.sin(point.angle)*31+4); });
  canvas.onclick = event => { const rect=canvas.getBoundingClientRect(), x=(event.clientX-rect.left)*size/rect.width, y=(event.clientY-rect.top)*size/rect.height; let nearest=-1, distance=Infinity; state.pitches.forEach((pitch,i)=>{const a=pitch.cents/1200*Math.PI*2-Math.PI/2, px=mid+Math.cos(a)*radius, py=mid+Math.sin(a)*radius, d=Math.hypot(px-x,py-y);if(d<distance){distance=d;nearest=i}}); if(distance<28) play(nearest); };
}
function renderGraph(ctx, size) {
  const mid=size/2, radius=size*.36, nodes=state.graph.nodes, points=nodes.map((node,index)=>{const angle=index/nodes.length*Math.PI*2-Math.PI/2;return {x:mid+Math.cos(angle)*radius,y:mid+Math.sin(angle)*radius,node};});
  ctx.clearRect(0,0,size,size); ctx.strokeStyle="#40506d"; ctx.lineWidth=1; state.graph.edges.forEach(edge=>{ctx.beginPath();ctx.moveTo(points[edge.source].x,points[edge.source].y);ctx.lineTo(points[edge.target].x,points[edge.target].y);ctx.stroke();});
  points.forEach((point,index)=>{ctx.fillStyle="#98e7ca";ctx.beginPath();ctx.arc(point.x,point.y,12,0,Math.PI*2);ctx.fill();ctx.fillStyle="#10131c";ctx.font="bold 10px system-ui";ctx.textAlign="center";ctx.fillText(String(index+1),point.x,point.y+4);ctx.fillStyle="#aeb9d0";ctx.font="12px system-ui";ctx.fillText(point.node.ratio,point.x,point.y+28);});
  canvas.onclick=event=>{const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*size/rect.width,y=(event.clientY-rect.top)*size/rect.height;const nearest=points.reduce((best,point,index)=>Math.hypot(point.x-x,point.y-y)<best.distance?{index,distance:Math.hypot(point.x-x,point.y-y)}:best,{index:-1,distance:Infinity});const pitch=state.pitches.findIndex(item=>item.ratio===nodes[nearest.index]?.ratio);if(nearest.distance<28&&pitch>=0)play(pitch);};
}
function monzoText(monzo) { return Object.entries(monzo).map(([p,e])=>`${p}:${e}`).join(" ") || "0"; }
function renderPitches() { el("pitches").innerHTML = state.pitches.map((p,i)=>{const relation=harmony(i);return `<tr><td>${keyboardKeys[i]||"–"}</td><td><span class="relation-dot" style="color:${relation.color}"></span>${p.ratio}</td><td>${p.cents.toFixed(2)}</td><td class="monzo">${monzoText(p.monzo)}</td><td><button data-index="${i}">Play</button></td></tr>`}).join(""); el("pitches").querySelectorAll("button").forEach(button=>button.onclick=()=>play(Number(button.dataset.index))); }
function renderKeyboard() { const box=el("keyboard"); box.innerHTML=""; state.pitches.slice(0,16).forEach((pitch,i)=>{const node=el("key-template").content.cloneNode(true);const button=node.querySelector("button");button.querySelector(".key-name").textContent=keyboardKeys[i];button.querySelector(".ratio").textContent=pitch.ratio;button.onclick=()=>play(i);box.append(node)}); }
function audioContext() { if (!state.context) state.context = new AudioContext(); return state.context; }
function play(index) { const pitch=state.pitches[index]; if(!pitch) return; if(state.recording){state.recorded.push({ratio:pitch.ratio,time:performance.now()});renderTimeline();} stop(index); const context=audioContext(), osc=context.createOscillator(), gain=context.createGain(), now=context.currentTime, attack=Number(el("attack").value)/1000, decay=Number(el("decay").value)/1000, sustain=Number(el("sustain").value)/100; osc.type=el("waveform").value; osc.frequency.value=Number(el("base-frequency").value)*(Number(pitch.ratio.split("/")[0])/Number(pitch.ratio.split("/")[1])); gain.gain.setValueAtTime(.0001,now); gain.gain.exponentialRampToValueAtTime(.24,now+attack); gain.gain.exponentialRampToValueAtTime(Math.max(.001,.24*sustain),now+attack+decay); osc.connect(gain).connect(context.destination); osc.start(); state.active.set(index,{osc,gain}); state.focus=index; render(); }
function renderTimeline(){el("timeline-events").innerHTML=state.recorded.length?state.recorded.map((event,index)=>`<span style="left:${index/Math.max(1,state.recorded.length-1)*88+4}%">${event.ratio}</span>`).join(""):"";}
function stop(index) { const voice=state.active.get(index); if(!voice) return; const now=audioContext().currentTime, release=Number(el("release").value)/1000; voice.gain.gain.cancelScheduledValues(now); voice.gain.gain.setTargetAtTime(.0001,now,release/5); voice.osc.stop(now+release); state.active.delete(index); if(state.focus===index) state.focus=[...state.active.keys()].at(-1) ?? null; render(); }
function stopAll() { [...state.active.keys()].forEach(stop); }
el("generator").onchange=syncGeneratorFields; el("choose").oninput=event=>el("choose-value").textContent=event.target.value; el("generate").onclick=generate; el("stop").onclick=stopAll;
el("base-frequency").oninput=e=>el("base-output").textContent=`${e.target.value} Hz`; ["attack","decay","release"].forEach(id=>el(id).oninput=e=>el(`${id}-output`).textContent=`${e.target.value} ms`); el("sustain").oninput=e=>el("sustain-output").textContent=`${e.target.value}%`;
document.addEventListener("keydown", event=>{if(event.repeat || /INPUT|SELECT/.test(event.target.tagName)) return; const index=keyboardKeys.indexOf(event.key.toUpperCase()); if(index>=0){event.preventDefault();play(index);}}); document.addEventListener("keyup",event=>{const index=keyboardKeys.indexOf(event.key.toUpperCase());if(index>=0)stop(index)});
el("scala").onclick=async()=>{ if(!state.pitches.length)return; const response=await fetch("/api/export/scala",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name:"Pure Intonation Workbench",ratios:state.pitches.map(p=>p.ratio)})}); const link=document.createElement("a");link.href=URL.createObjectURL(await response.blob());link.download="pure-intonation.scl";link.click();URL.revokeObjectURL(link.href); };
el("graph-toggle").onclick=()=>{if(!state.graph)return;state.showGraph=!state.showGraph;el("visual-title").textContent=state.showGraph?"Harmonic graph":"Pitch circle";el("graph-toggle").textContent=state.showGraph?"Circle":"Graph";renderCircle();};
el("record").onclick=()=>{state.recording=!state.recording;if(state.recording)state.recorded=[];el("record").textContent=state.recording?"Stop":"Record";renderTimeline();};
syncGeneratorFields(); generate();
