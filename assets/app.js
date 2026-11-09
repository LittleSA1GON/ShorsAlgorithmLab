/* app.js — animation players, the three labs, and the live experiments. */
(() => {
"use strict";
const C = window.ShorCore;
const $ = s => document.querySelector(s);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const pct = (x, d = 0) => (100 * x).toFixed(d) + "%";
const esc = s => String(s).replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
const tick = () => new Promise(r => setTimeout(r, 0));
const sleep = ms => new Promise(r => setTimeout(r, reduce ? 0 : ms));

/* ================================================================= SVG helpers */
const NS = "http://www.w3.org/2000/svg";
const svg = (w, h) => { const s = document.createElementNS(NS, "svg"); s.setAttribute("viewBox", `0 0 ${w} ${h}`); s.setAttribute("role", "img"); return s; };
const el = (p, tag, a = {}, text) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (text != null) e.textContent = text; p.appendChild(e); return e; };
function niceTicks(max, n = 4) {
  if (max <= 0) return [0, 1];
  const raw = max / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].find(k => k * mag >= raw) * mag;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => +(i * step).toFixed(10));
}
/* frame: {W,H,L,R,T,B, xmin,xmax, ymax, xticks:[[v,label]], yticks:[[v,label]], xlabel, ylabel, logx} */
function frame(f) {
  const s = svg(f.W, f.H);
  const tx = v => f.logx ? Math.log10(v) : v;
  f.sx = v => f.L + (tx(v) - tx(f.xmin)) / (tx(f.xmax) - tx(f.xmin)) * (f.R - f.L);
  f.sy = v => f.B - Math.min(v, f.ymax) / f.ymax * (f.B - f.T);
  const grid = css("--line"), ink = css("--faint");
  for (const [v, lab] of f.yticks) { el(s, "line", { x1: f.L, x2: f.R, y1: f.sy(v), y2: f.sy(v), stroke: grid }); el(s, "text", { x: f.L - 8, y: f.sy(v) + 4, "text-anchor": "end" }, lab); }
  el(s, "line", { x1: f.L, x2: f.R, y1: f.B, y2: f.B, stroke: ink });
  for (const [v, lab] of f.xticks) el(s, "text", { x: f.sx(v), y: f.B + 18, "text-anchor": "middle" }, lab);
  if (f.xlabel) el(s, "text", { x: (f.L + f.R) / 2, y: f.B + 36, "text-anchor": "middle" }, f.xlabel);
  if (f.ylabel) el(s, "text", { x: f.L - 36, y: f.T - 10 }, f.ylabel);
  return s;
}
const mount = (host, s) => { host.innerHTML = ""; host.appendChild(s); };

/* ================================================================= animation players */
const FPS = 24, RATE = 0.45;
document.querySelectorAll(".chapter").forEach(ch => {
  const clip = ch.dataset.clip;
  const segs = ch.dataset.steps.split(",").map(s => s.split("-").map(Number)).map(([a, b]) => [(a - 1) / FPS, (b - 1) / FPS]);
  const items = [...ch.querySelectorAll(".steps li")];
  const player = ch.querySelector(".player");
  player.innerHTML = `
    <div class="stage"><img src="media/${clip}.jpg" alt=""><video muted playsinline preload="auto" aria-label="${esc(ch.querySelector("h3").textContent)}"></video><div class="cap"></div></div>
    <div class="pcontrols">
      <button class="btn primary play" type="button">Play</button>
      <button class="btn prev" type="button" aria-label="Previous step">Back</button>
      <button class="btn next" type="button" aria-label="Next step">Next</button>
      <span class="count num"></span>
      <div class="track"><i></i></div>
    </div>`;
  const v = player.querySelector("video"), img = player.querySelector("img"), cap = player.querySelector(".cap");
  const playBtn = player.querySelector(".play"), countEl = player.querySelector(".count"), bar = player.querySelector(".track i");
  let cur = 0, end = 0, raf = 0, ready = false;

  function show(i) {
    cur = i;
    items.forEach((li, k) => li.classList.toggle("on", k === i));
    const b = items[i].querySelector("b");
    cap.innerHTML = `<b>${i + 1}.</b> ${esc(b ? b.textContent : items[i].textContent)}`;
    countEl.textContent = `Step ${i + 1} of ${items.length}`;
    player.querySelector(".prev").disabled = i === 0;
    player.querySelector(".next").disabled = i === items.length - 1;
  }
  function loop() {
    const dur = v.duration || segs[segs.length - 1][1];
    bar.style.width = (100 * v.currentTime / dur) + "%";
    if (v.currentTime >= end - 0.02) { v.pause(); v.currentTime = end; playBtn.textContent = cur === items.length - 1 ? "Replay all" : "Replay step"; return; }
    raf = requestAnimationFrame(loop);
  }
  function playStep(i) {
    show(i);
    if (!ready) return;
    cancelAnimationFrame(raf);
    const [a, b] = segs[i];
    end = Math.min(b, v.duration - 0.01);
    v.currentTime = a;
    if (reduce) { v.currentTime = end; bar.style.width = (100 * end / v.duration) + "%"; playBtn.textContent = "Replay step"; return; }
    v.playbackRate = RATE;
    v.play().then(() => { playBtn.textContent = "Playing…"; raf = requestAnimationFrame(loop); }).catch(() => {});
  }
  function park(i) { show(i); if (ready) { v.currentTime = Math.min(segs[i][1], v.duration - 0.01); bar.style.width = (100 * v.currentTime / v.duration) + "%"; } }

  playBtn.addEventListener("click", () => playStep(playBtn.textContent === "Replay all" ? 0 : cur));
  player.querySelector(".next").addEventListener("click", () => playStep(Math.min(items.length - 1, cur + 1)));
  player.querySelector(".prev").addEventListener("click", () => playStep(Math.max(0, cur - 1)));
  items.forEach((li, i) => { li.tabIndex = 0; li.addEventListener("click", () => playStep(i)); li.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); playStep(i); } }); });

  v.addEventListener("loadeddata", () => { ready = true; img.hidden = true; park(cur); }, { once: true });
  // Load as a blob so seeking works on every host (blob URLs are always seekable).
  const src = `media/${clip}.mp4`;
  fetch(src).then(r => { if (!r.ok) throw 0; return r.blob(); }).then(b => { v.src = URL.createObjectURL(b); }).catch(() => { v.src = src; });
  show(0);

  // Play step 1 the first time the chapter scrolls into view.
  if (!reduce && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => { if (es[0].isIntersecting && ready) { io.disconnect(); playStep(0); } }, { threshold: 0.6 });
    v.addEventListener("loadeddata", () => io.observe(player), { once: true });
  }
});

/* ================================================================= tabs */
const tabs = [...document.querySelectorAll(".tab")];
function selectTab(tab) {
  tabs.forEach(t => { const on = t === tab; t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1; $("#" + t.getAttribute("aria-controls")).hidden = !on; });
  if (tab.id === "tab-circuit") drawCircuitLab();
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => selectTab(t));
  t.addEventListener("keydown", e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); selectTab(n); } });
});

/* ================================================================= Lab A: find the period */
function renderPeriod() {
  const N = Math.max(4, Math.min(9999, parseInt($("#pN").value) || 15));
  const a = Math.max(2, Math.min(N - 1, parseInt($("#pA").value) || 2));
  const out = $("#pVerdict"), seq = $("#pSeq"), host = $("#pChart");
  const g = C.gcd(a, N);
  if (g !== 1) {
    out.className = "result good";
    out.innerHTML = `${a} and ${N} already share the factor <b>${g}</b>, so N = ${g} × ${N / g}. That was a lucky guess. Usually you need the period.`;
    seq.innerHTML = ""; host.innerHTML = ""; return;
  }
  const r = C.order(a, N), f = C.factorsFromPeriod(a, r, N);
  out.className = "result " + (f.ok ? "good" : "bad");
  out.innerHTML = f.ok
    ? `The sequence returns to 1 after <b>r = ${r}</b> steps. Then ${a}<sup>${r / 2}</sup> mod ${N} = ${f.half}, and gcd(${f.half} − 1, ${N}) and gcd(${f.half} + 1, ${N}) give <b>${N} = ${f.p} × ${f.q}</b>.`
    : `The period is <b>r = ${r}</b>, but ${esc(f.why)}. This base does not work. Pick another a.`;
  const show = Math.min(Math.max(2 * r + 1, 13), 40);
  seq.innerHTML = Array.from({ length: Math.min(show, 24) }, (_, x) => { const y = C.modpow(a, x, N); return `<span class="${y === 1 ? "one" : ""}"><small>x=${x}</small>${y}</span>`; }).join("");
  const yt = niceTicks(N - 1);
  const f2 = { W: 560, H: 230, L: 48, R: 548, T: 28, B: 190, xmin: 0, xmax: show - 1, ymax: yt[yt.length - 1],
    yticks: yt.map(v => [v, v]), xticks: [0, Math.round((show - 1) / 2), show - 1].map(x => [x, x]), xlabel: "x (how many times we multiplied by a)", ylabel: `${a}^x mod ${N}` };
  const s = frame(f2);
  for (let k = r; k < show; k += r) el(s, "line", { x1: f2.sx(k), x2: f2.sx(k), y1: f2.T, y2: f2.B, stroke: css("--quant"), "stroke-dasharray": "3 4", opacity: 0.7 });
  let d = ""; for (let x = 0; x < show; x++) d += (x ? "L" : "M") + f2.sx(x) + "," + f2.sy(C.modpow(a, x, N));
  el(s, "path", { d, fill: "none", stroke: css("--faint") });
  for (let x = 0; x < show; x++) { const y = C.modpow(a, x, N); el(s, "circle", { cx: f2.sx(x), cy: f2.sy(y), r: 3.5, fill: y === 1 ? css("--quant") : css("--class") }); }
  mount(host, s);
}
$("#pN").addEventListener("input", renderPeriod);
$("#pA").addEventListener("input", renderPeriod);

/* ================================================================= Lab B: run the circuit */
const LAB_NS = [15, 21, 33, 35, 39, 51, 55, 57, 65, 77, 85, 91];
const cN = $("#cN"), cA = $("#cA"), cT = $("#cT"), cE = $("#cE");
LAB_NS.forEach(N => cN.add(new Option(N, N)));
let shots = [], cur = null;
function fillBases() {
  const N = +cN.value;
  cA.innerHTML = "";
  for (const b of C.usableBases(N)) cA.add(new Option(`${b.a}${b.usable ? "" : "  (won't work)"}`, b.a));
  const first = C.usableBases(N).find(b => b.usable); if (first) cA.value = first.a;
}
const epsOf = k => k === 0 ? 0 : Math.pow(10, -5 + k / 20);
function drawCircuitLab() {
  const N = +cN.value, a = +cA.value, t = +cT.value, eps = epsOf(+cE.value);
  $("#cTv").textContent = t;
  $("#cEv").textContent = eps ? `${(eps * 100).toPrecision(2)}% per gate` : "none";
  const d = C.distribution(a, N, t), P = C.noisy(d.P, t, N, eps);
  cur = { N, a, t, eps, P, r: d.r, M: d.M, draw: C.sampler(P) };
  $("#cExp").textContent = pct(C.successProb(P, t, a, N));
  const G = C.gateEstimate(N, t);
  $("#cNote").textContent = `${d.M} possible results. Peaks sit near multiples of ${d.M} ÷ ${d.r} (the period r = ${d.r}).` +
    ([...Array(Math.min(t, 5)).keys()].some(j => C.modpow(a, 2 ** j, N) === 1) ? " A ×1 box means that multiplication changes nothing for this N and a." : "") +
    (eps ? ` With noise, ~${G} two-qubit gates each fail ${(eps * 100).toPrecision(2)}% of the time, so only ${pct(Math.pow(1 - eps, G), 1)} of runs stay error-free.` : "");
  drawHist(); drawCircuit();
}
function drawHist() {
  const { P, M } = cur;
  const obs = new Float64Array(M); shots.forEach(s => obs[s.y]++); if (shots.length) obs.forEach((v, i) => obs[i] = v / shots.length);
  const yt = niceTicks(Math.max(...P, ...obs));
  const f = { W: 640, H: 240, L: 48, R: 628, T: 16, B: 200, xmin: 0, xmax: M, ymax: yt[yt.length - 1],
    yticks: yt.map(v => [v, pct(v)]), xticks: [0, M / 4, M / 2, 3 * M / 4, M].map(x => [x, x === M ? M - 1 : x]), xlabel: "measured value y" };
  const s = frame(f), bw = (f.R - f.L) / M, q = css("--quant"), am = css("--class");
  for (let y = 0; y < M; y++) if (P[y] > f.ymax * 0.003) el(s, "rect", { x: f.sx(y), y: f.sy(P[y]), width: Math.max(1, bw - (bw > 3 ? 1 : 0)), height: f.B - f.sy(P[y]), fill: q, opacity: 0.85 });
  if (shots.length) for (let y = 0; y < M; y++) if (obs[y]) el(s, "rect", { x: f.sx(y) + bw * 0.15, y: f.sy(obs[y]) - 2, width: Math.max(3, bw * 0.7), height: 4, rx: 1, fill: am });
  mount($("#cHist"), s);
}
function drawCircuit() {
  const { N, a, t } = cur, n = C.nQubits(N), showT = Math.min(t, 5), more = t > showT;
  const gap = 30, top = 34, rows = showT + (more ? 1 : 0), W = 760, yT = top + rows * gap + 12, H = yT + 34;
  const s = svg(W, H), ink = css("--muted"), line = css("--faint"), q = css("--quant"), bg = css("--raised");
  const yRow = i => top + i * gap;
  const xU0 = 160, du = 70, xQ = xU0 + showT * du + (more ? 40 : 16), xM = xQ + 120;
  el(s, "text", { x: 8, y: 14 }, "1. Hadamards");
  el(s, "text", { x: xU0, y: 14 }, `2. multiply by ${a}^(2^j) mod ${N}`);
  el(s, "text", { x: xQ, y: 14 }, "3. inverse QFT");
  el(s, "text", { x: xM - 4, y: 14 }, "4. measure");
  for (let i = 0; i < showT; i++) { el(s, "text", { x: 8, y: yRow(i) + 4 }, `q${i} |0⟩`); el(s, "line", { x1: 64, x2: W - 10, y1: yRow(i), y2: yRow(i), stroke: line }); }
  if (more) el(s, "text", { x: 8, y: yRow(showT) + 4 }, `+ ${t - showT} more qubits`);
  el(s, "text", { x: 8, y: yT + 4 }, `target |1⟩`);
  el(s, "line", { x1: 84, x2: W - 10, y1: yT - 2, y2: yT - 2, stroke: line }); el(s, "line", { x1: 84, x2: W - 10, y1: yT + 2, y2: yT + 2, stroke: line });
  const box = (x, y, w, h, txt, col) => { el(s, "rect", { x, y, width: w, height: h, rx: 6, fill: bg, stroke: col, "stroke-width": 1.2 }); if (txt) el(s, "text", { x: x + w / 2, y: y + h / 2 + 4, "text-anchor": "middle", style: `fill:${col}` }, txt); };
  for (let i = 0; i < showT; i++) box(96, yRow(i) - 11, 24, 22, "H", ink);
  for (let j = 0; j < showT; j++) {
    const x = xU0 + j * du + du / 2, m = C.modpow(a, 2 ** j, N);
    el(s, "line", { x1: x, x2: x, y1: yRow(j), y2: yT - 13, stroke: q });
    el(s, "circle", { cx: x, cy: yRow(j), r: 4.5, fill: q });
    box(x - 26, yT - 13, 52, 26, `×${m}`, q);
  }
  if (more) el(s, "text", { x: xU0 + showT * du + 6, y: yT + 4 }, "…");
  box(xQ, yRow(0) - 14, 96, yRow(showT - 1) - yRow(0) + 28, "QFT⁻¹", ink);
  for (let i = 0; i < showT; i++) { box(xM, yRow(i) - 11, 30, 22, "", ink); el(s, "path", { d: `M${xM + 6},${yRow(i) + 6} A9,9 0 0 1 ${xM + 24},${yRow(i) + 6}`, fill: "none", stroke: ink }); el(s, "line", { x1: xM + 15, y1: yRow(i) + 6, x2: xM + 22, y2: yRow(i) - 6, stroke: ink }); }
  mount($("#cCircuit"), s);
}
function shotLine(res) {
  const head = `y = ${String(res.y).padStart(4)}   ${res.y}/${res.M}`;
  const c = res.r && res.conv.find(([, k]) => k === res.r);
  return res.ok
    ? `<span class="hl">${head}</span> ≈ ${c ? `${c[0]}/${c[1]}` : ""}  → r = ${res.r}  <span class="ok">✓ ${res.p} × ${res.q}</span>`
    : `${head}  <span class="no">✗ ${esc(res.why)}</span>`;
}
function takeShots(k) {
  const { N, a, t, draw } = cur, lines = [];
  for (let i = 0; i < k; i++) { const y = draw(), res = C.analyze(y, t, a, N); shots.push({ y, ok: res.ok }); if (i < 10) lines.push(shotLine(res)); }
  if (k > 10) lines.push(`… and ${k - 10} more runs`);
  const log = $("#cLog");
  if (shots.length === k) log.innerHTML = "";
  log.innerHTML = lines.join("\n") + (log.innerHTML ? "\n" + log.innerHTML : "");
  const hits = shots.filter(s => s.ok).length;
  $("#cRuns").textContent = shots.length; $("#cHits").textContent = hits; $("#cRate").textContent = pct(hits / shots.length);
  drawHist();
}
function clearShots() { shots = []; $("#cLog").textContent = "Each run prints the measured y, the fraction it simplifies to, and whether that revealed the factors."; $("#cRuns").textContent = 0; $("#cHits").textContent = 0; $("#cRate").textContent = "–"; if (cur) drawHist(); }
cN.addEventListener("change", () => { cT.value = Math.min(12, 2 * C.nQubits(+cN.value)); fillBases(); clearShots(); drawCircuitLab(); });
[cA, cT, cE].forEach(e => e.addEventListener("input", () => { clearShots(); drawCircuitLab(); }));
$("#cShot").addEventListener("click", () => takeShots(1));
$("#cShots").addEventListener("click", () => takeShots(100));
$("#cClear").addEventListener("click", clearShots);
cN.value = 15; fillBases(); cT.value = 8;

/* ================================================================= Lab C: break an RSA key */
const PRIMES = [3, 5, 7, 11, 13, 17];
const rP = $("#rP"), rQ = $("#rQ");
PRIMES.forEach(p => { rP.add(new Option(p, p)); rQ.add(new Option(p, p)); });
rP.value = 5; rQ.value = 11;
const enc = ch => ch === " " ? 28 : ch.charCodeAt(0) - 63; // A=2 … Z=27, space=28
const dec = m => m === 28 ? " " : (m >= 2 && m <= 27 ? String.fromCharCode(m + 63) : "?");
function modinv(e, m) { let [g, x] = [m, 0], [g1, x1] = [e, 1]; while (g1) { const q = Math.floor(g / g1); [g, g1] = [g1, g - q * g1]; [x, x1] = [x1, x - q * x1]; } return ((x % m) + m) % m; }
let key = null;
function makeKey() {
  const p = +rP.value, q = +rQ.value, box = $("#rKey"), btn = $("#rAttack");
  if (p === q || p * q < 33) { box.innerHTML = `<span class="no">Pick two different primes whose product is at least 33.</span>`; btn.disabled = true; key = null; return; }
  const N = p * q, phi = (p - 1) * (q - 1);
  let e = 3; while (C.gcd(e, phi) !== 1) e += 2;
  const d = modinv(e, phi);
  const msg = $("#rMsg").value.toUpperCase().replace(/[^A-Z ]/g, "") || "HI";
  const m = [...msg].map(enc), c = m.map(x => C.modpow(x, e, N));
  key = { N, e, c };
  box.innerHTML = `<span class="am">Secret:</span>  p = ${p}, q = ${q}, d = ${d}\n<span class="q">Public:</span>  N = ${N}, e = ${e}\nLocked message:  ${c.join(" ")}`;
  btn.disabled = false;
}
async function attack() {
  if (!key) return;
  const btn = $("#rAttack"); btn.disabled = true;
  const { N, e, c } = key, log = $("#rLog"), n = C.nQubits(N), t = Math.min(2 * n, 16);
  const lines = [`The attacker knows N = ${N} and e = ${e}.`, `Running Shor's algorithm with ${t} counting qubits…`];
  const show = () => { log.innerHTML = lines.join("\n"); log.scrollTop = log.scrollHeight; };
  show();
  let found = null;
  for (let k = 1; k <= 20 && !found; k++) {
    await sleep(420);
    const a = 2 + Math.floor(Math.random() * (N - 3)), g = C.gcd(a, N);
    if (g > 1) { lines.push(`Run ${k}: picked a = ${a}, which already shares the factor ${g}. <span class="ok">Lucky!</span>`); found = [g, N / g]; show(); break; }
    const { P } = C.distribution(a, N, t), y = C.sampler(P)(), res = C.analyze(y, t, a, N);
    lines.push(`Run ${k}: a = ${a}, measured y = ${y}  ` + (res.ok ? `→ period r = ${res.r} <span class="ok">✓</span>` : `<span class="no">✗ try again</span>`));
    show();
    if (res.ok) found = [res.p, res.q];
  }
  await sleep(420);
  if (!found) { lines.push(`<span class="no">No luck in 20 runs. Press Attack again.</span>`); show(); btn.disabled = false; return; }
  const [p, q] = found.sort((x, y) => x - y), d = modinv(e, (p - 1) * (q - 1));
  lines.push(`<span class="am">Factors found: ${N} = ${p} × ${q}</span>`, `So the secret key is d = ${d}.`, `Unlocked message: <span class="ok">"${esc(c.map(x => dec(C.modpow(x, d, N))).join(""))}"</span>`);
  show(); btn.disabled = false;
}
[rP, rQ].forEach(s => s.addEventListener("change", () => { makeKey(); $("#rLog").textContent = "Waiting for the attack."; }));
$("#rMsg").addEventListener("input", makeKey);
$("#rAttack").addEventListener("click", attack);

/* ================================================================= live experiments */
const EXPS = [
  { id: "e1", q: "What does the quantum circuit actually read out?",
    how: "Runs the circuit 2,000 times for one number and plots how often each result came up.",
    params: () => `<label class="field" for="e1N">Number N<select id="e1N">${[15, 21, 33, 35, 39, 51].map(n => `<option${n === 21 ? " selected" : ""}>${n}</option>`).join("")}</select></label>`,
    run: runE1 },
  { id: "e2", q: "How many counting qubits are enough?",
    how: "Factors N = 21 with 3 up to 11 counting qubits, 400 runs each, and records how often a run finds the factors.",
    params: () => "", run: runE2 },
  { id: "e3", q: "Does the choice of base a matter?",
    how: "Tries every possible base a for one N, 200 runs each.",
    params: () => `<label class="field" for="e3N">Number N<select id="e3N">${[15, 21, 33, 35, 39, 51, 55, 65].map(n => `<option${n === 35 ? " selected" : ""}>${n}</option>`).join("")}</select></label>`,
    run: runE3 },
  { id: "e4", q: "How much hardware noise can it survive?",
    how: "Factors N = 21 at ten noise levels, 400 runs each, and compares the result with random guessing.",
    params: () => "", run: runE4 },
  { id: "e5", q: "How fast does the classical method slow down?",
    how: "Times your own computer finding the period the slow way, for numbers from 10 to 26 bits.",
    params: () => "", run: runE5 },
];
const expHost = $("#exps");
expHost.innerHTML = EXPS.map(x => `
  <article class="exp" id="${x.id}">
    <h3 class="q">${x.q}</h3>
    <p class="how">${x.how}</p>
    <div class="row">${x.params()}<button class="btn primary run" type="button">Run experiment</button></div>
    <div class="bar" aria-hidden="true"><i></i></div>
    <div class="chart"></div>
    <div class="found" aria-live="polite"><span class="label">Result</span>Not run yet.</div>
    <details hidden><summary>Show the numbers</summary><div class="tbl"></div></details>
  </article>`).join("");
const ui = id => { const r = $("#" + id); return { root: r, bar: r.querySelector(".bar i"), chart: r.querySelector(".chart"), found: r.querySelector(".found"), det: r.querySelector("details"), tbl: r.querySelector(".tbl"), btn: r.querySelector(".run") }; };
const setFound = (u, html) => { u.found.innerHTML = `<span class="label">Result</span>${html}`; };
const table = (u, head, rows) => { u.det.hidden = false; u.tbl.innerHTML = `<table><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`; };
const firstUsable = N => C.usableBases(N).find(b => b.usable).a;
async function runShots(N, a, t, P, k) { const draw = C.sampler(P); let hits = 0; const ys = []; for (let i = 0; i < k; i++) { const y = draw(); ys.push(y); if (C.analyze(y, t, a, N).ok) hits++; } return { hits, ys }; }

function lineChart(u, series, o) {
  const yt = o.yticks || niceTicks(o.ymax);
  const f = { W: 520, H: 256, L: 52, R: 500, T: 44, B: 212, xmin: o.xmin, xmax: o.xmax, ymax: yt[yt.length - 1], logx: o.logx,
    yticks: yt.map(v => [v, o.yfmt ? o.yfmt(v) : v]), xticks: o.xticks.map(x => [x, o.xfmt ? o.xfmt(x) : x]), xlabel: o.xlabel, ylabel: o.ylabel };
  const s = frame(f);
  for (const h of o.hlines || []) { el(s, "line", { x1: f.L, x2: f.R, y1: f.sy(h.v), y2: f.sy(h.v), stroke: h.col, "stroke-dasharray": "4 4" }); el(s, "text", { x: f.R, y: f.sy(h.v) - 6, "text-anchor": "end", style: `fill:${h.col}` }, h.label); }
  for (const sr of series) {
    if (sr.pts.length > 1) el(s, "path", { d: sr.pts.map((p, i) => (i ? "L" : "M") + f.sx(p[0]) + "," + f.sy(p[1])).join(""), fill: "none", stroke: sr.col, "stroke-width": sr.dash ? 1.5 : 2, "stroke-dasharray": sr.dash ? "5 4" : "none" });
    if (!sr.dash) sr.pts.forEach(p => el(s, "circle", { cx: f.sx(p[0]), cy: f.sy(p[1]), r: 3.5, fill: sr.col }));
  }
  const lg = el(s, "g", {}); let lx = f.L;
  for (const sr of series) { el(lg, "line", { x1: lx, x2: lx + 16, y1: 10, y2: 10, stroke: sr.col, "stroke-width": 2, "stroke-dasharray": sr.dash ? "4 3" : "none" }); const t = el(lg, "text", { x: lx + 22, y: 14 }, sr.name); lx += 34 + sr.name.length * 7.2; }
  mount(u.chart, s);
}

async function runE1(u) {
  const N = +$("#e1N").value, a = firstUsable(N), t = Math.min(2 * C.nQubits(N), 10);
  const { P, r, M } = C.distribution(a, N, t), draw = C.sampler(P), counts = new Float64Array(M), K = 2000;
  let hits = 0;
  for (let i = 0; i < K; i++) {
    const y = draw(); counts[y]++; if (C.analyze(y, t, a, N).ok) hits++;
    if (i % 100 === 99) {
      u.bar.style.width = pct((i + 1) / K);
      const yt = niceTicks(Math.max(...P) * 1.1);
      const f = { W: 520, H: 256, L: 52, R: 500, T: 44, B: 212, xmin: 0, xmax: M, ymax: yt[yt.length - 1], yticks: yt.map(v => [v, pct(v)]), xticks: [0, M / 2, M].map(x => [x, x === M ? M - 1 : x]), xlabel: "measured value y", ylabel: "share of runs" };
      const s = frame(f), bw = (f.R - f.L) / M;
      for (let y = 0; y < M; y++) if (counts[y]) el(s, "rect", { x: f.sx(y), y: f.sy(counts[y] / (i + 1)), width: Math.max(1.2, bw), height: f.B - f.sy(counts[y] / (i + 1)), fill: css("--class") });
      for (let y = 0; y < M; y++) if (P[y] > 0.004) el(s, "circle", { cx: f.sx(y) + bw / 2, cy: f.sy(P[y]), r: 2.4, fill: css("--quant") });
      el(s, "text", { x: f.L, y: 12 }, "bars: measured · dots: predicted");
      mount(u.chart, s); await tick();
    }
  }
  const peaks = [...P].map((p, y) => [p, y]).sort((x, y) => y[0] - x[0]).slice(0, r).map(p => p[1]).sort((x, y) => x - y);
  const exp = C.successProb(P, t, a, N);
  setFound(u, `For N = ${N} (base a = ${a}), the results bunched into <b>${r} peaks</b> spaced about ${(M / r).toFixed(1)} apart, because the hidden period is r = ${r}. <b>${pct(hits / K, 1)}</b> of runs revealed the factors (theory: ${pct(exp, 1)}). The rest landed on 0 or on a peak that only gave part of r, so the algorithm simply runs again.`);
  table(u, ["peak y", "predicted", "measured"], peaks.map(y => [y, pct(P[y], 1), pct(counts[y] / K, 1)]));
}
async function runE2(u) {
  const N = 21, a = 2, K = 400, pts = [], th = [], rows = [];
  for (let t = 3; t <= 11; t++) {
    const { P } = C.distribution(a, N, t), { hits } = await runShots(N, a, t, P, K), e = C.successProb(P, t, a, N);
    pts.push([t, hits / K]); th.push([t, e]); rows.push([t, `${hits}/${K}`, pct(hits / K, 1), pct(e, 1)]);
    u.bar.style.width = pct((t - 2) / 9);
    lineChart(u, [{ name: "measured", col: css("--class"), pts }, { name: "theory", col: css("--quant"), pts: th, dash: true }], { xmin: 3, xmax: 11, xticks: [3, 5, 7, 9, 11], ymax: 0.5, yfmt: v => pct(v), xlabel: "counting qubits t", ylabel: "runs that found 3 × 7" });
    await tick();
  }
  const zero = pts.filter(p => p[1] === 0).map(p => p[0]), at10 = pts.find(p => p[0] === 10)[1];
  setFound(u, `${zero.length ? `With ${zero.length > 1 ? `${zero[0]}–${zero[zero.length - 1]}` : zero[0]} counting qubits, <b>no run</b> found the factors: the peaks were too blurry to read r = 6. ` : ""}Success rose with more qubits and leveled off near <b>${pct(at10)}</b> at t = 10, close to 2 × log₂ 21 ≈ 9. Past that, extra qubits barely help, because the remaining failures come from the math (s/r fractions that hide r), not from blur.`);
  table(u, ["t", "successes", "measured", "theory"], rows);
}
async function runE3(u) {
  const N = +$("#e3N").value, bases = C.usableBases(N), t = Math.min(2 * C.nQubits(N), 12), K = 200, res = [];
  for (let i = 0; i < bases.length; i++) {
    const b = bases[i];
    let rate = 0;
    if (b.usable) { const { P } = C.distribution(b.a, N, t); rate = (await runShots(N, b.a, t, P, K)).hits / K; }
    res.push({ ...b, rate }); u.bar.style.width = pct((i + 1) / bases.length);
    const f = { W: 520, H: 256, L: 52, R: 500, T: 44, B: 212, xmin: 0, xmax: bases.length, ymax: 1, yticks: [0, .25, .5, .75, 1].map(v => [v, pct(v)]), xticks: [], xlabel: "base a", ylabel: "runs that found the factors" };
    const s = frame(f), bw = (f.R - f.L) / bases.length;
    res.forEach((x, k) => {
      el(s, "rect", { x: f.sx(k) + bw * 0.15, y: x.usable ? f.sy(x.rate) : f.B - 3, width: bw * 0.7, height: x.usable ? f.B - f.sy(x.rate) : 3, rx: 2, fill: x.usable ? css("--quant") : css("--bad") });
      if (bases.length <= 24 || k % 2 === 0) el(s, "text", { x: f.sx(k) + bw / 2, y: f.B + 16, "text-anchor": "middle" }, x.a);
    });
    el(s, "text", { x: f.L, y: 12 }, "cyan: usable base · red stub: can never work");
    mount(u.chart, s); if (i % 3 === 2) await tick();
  }
  const bad = res.filter(x => !x.usable), good = res.filter(x => x.usable), rates = good.map(x => x.rate);
  setFound(u, `Of the ${res.length} bases that share no factor with ${N}, <b>${bad.length} can never work</b>: their period is odd or a<sup>r/2</sup> ≡ −1, which makes the gcd trick fail. The other ${good.length} found the factors in <b>${pct(Math.min(...rates))}–${pct(Math.max(...rates))}</b> of runs. Shor's algorithm handles this by picking a random a and retrying.`);
  table(u, ["a", "period r", "usable", "success"], res.map(x => [x.a, x.r, x.usable ? "yes" : "no", x.usable ? pct(x.rate) : "–"]));
}
async function runE4(u) {
  const N = 21, a = 2, t = 10, K = 400, ideal = C.distribution(a, N, t).P, G = C.gateEstimate(N, t);
  const uni = new Float64Array(2 ** t).fill(1 / 2 ** t), guess = (await runShots(N, a, t, uni, 2000)).hits / 2000;
  const eps = Array.from({ length: 10 }, (_, i) => Math.pow(10, -5 + i * 3.5 / 9)), pts = [], rows = [];
  for (let i = 0; i < eps.length; i++) {
    const P = C.noisy(ideal, t, N, eps[i]), h = (await runShots(N, a, t, P, K)).hits / K;
    pts.push([eps[i], h]); rows.push([(eps[i] * 100).toPrecision(2) + "%", pct(Math.pow(1 - eps[i], G), 1), pct(h, 1)]);
    u.bar.style.width = pct((i + 1) / eps.length);
    lineChart(u, [{ name: "measured", col: css("--class"), pts }], { logx: true, xmin: 1e-5, xmax: eps[eps.length - 1], xticks: [1e-5, 1e-4, 1e-3, 1e-2], xfmt: x => (x * 100) + "%", ymax: 0.5, yfmt: v => pct(v), xlabel: "error chance per two-qubit gate", ylabel: "runs that found 3 × 7",
      hlines: [{ v: guess, col: css("--bad"), label: "random guessing" }] });
    await tick();
  }
  const today = C.noisy(ideal, t, N, 0.0027), hToday = (await runShots(N, a, t, today, 2000)).hits / 2000;
  setFound(u, `This circuit needs about <b>${G.toLocaleString()} two-qubit gates</b>. With almost no noise it found 3 × 7 in ${pct(pts[0][1])} of runs. At <b>0.27% error per gate</b> (the median on IBM's ibm_torino chip) only ${pct(Math.pow(1 - 0.0027, G), 1)} of runs stay error-free, and the success rate drops to <b>${pct(hToday)}</b>. Random guessing scores ${pct(guess)}. This is why real demonstrations remain tiny.`);
  table(u, ["error / gate", "error-free runs", "success"], rows);
}
async function runE5(u) {
  const rnd = n => Math.floor(Math.random() * n);
  const isPrime = n => { if (n < 2) return false; for (let d = 2; d * d <= n; d++) if (n % d === 0) return false; return true; };
  const randPrime = bits => { for (;;) { const p = (1 << (bits - 1)) + rnd(1 << (bits - 1)); if (isPrime(p)) return p; } };
  const pts = [], rows = [];
  for (let bits = 10; bits <= 26; bits += 2) {
    const steps = [], times = [];
    for (let k = 0; k < 6; k++) {
      let N; do { N = randPrime(bits / 2) * randPrime(bits / 2); } while (Math.log2(N) < bits - 1.2);
      let a; do { a = 2 + rnd(N - 3); } while (C.gcd(a, N) !== 1);
      const t0 = performance.now(); let y = a % N, r = 1;
      while (y !== 1) { y = (y * a) % N; r++; if ((r & 0xfffff) === 0) await tick(); }
      times.push(performance.now() - t0); steps.push(r);
    }
    steps.sort((x, y) => x - y); times.sort((x, y) => x - y);
    const med = (steps[2] + steps[3]) / 2, ms = (times[2] + times[3]) / 2;
    pts.push([bits, Math.log2(med)]); rows.push([bits, Math.round(med).toLocaleString(), ms.toFixed(1) + " ms"]);
    u.bar.style.width = pct((bits - 8) / 18);
    lineChart(u, [{ name: "your computer", col: css("--class"), pts }], { xmin: 10, xmax: 26, xticks: [10, 14, 18, 22, 26], ymax: 26, yticks: [0, 5, 10, 15, 20, 25], yfmt: v => "2^" + v, xlabel: "size of N in bits", ylabel: "multiplications needed (typical)" });
    await tick();
  }
  const n = pts.length, mx = pts.reduce((s, p) => s + p[0], 0) / n, my = pts.reduce((s, p) => s + p[1], 0) / n;
  const slope = pts.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0) / pts.reduce((s, p) => s + (p[0] - mx) ** 2, 0);
  setFound(u, `Every extra bit made the search about <b>${Math.pow(2, slope).toFixed(1)}× slower</b> (log₂ steps ≈ ${slope.toFixed(2)} × bits): the work grows exponentially, close to doubling per bit. A 26-bit N took ${rows[rows.length - 1][1]} multiplications. At that rate a real 2048-bit key would need about 2<sup>${Math.round(slope * 2048 + (my - slope * mx))}</sup>. Shor's algorithm needs only about 2048³ ≈ 2<sup>33</sup> quantum operations.`);
  table(u, ["bits", "median steps", "median time"], rows);
}
async function runExp(x) {
  const u = ui(x.id); u.btn.disabled = true; u.bar.style.width = "0"; setFound(u, "Running…");
  try { await x.run(u); } catch (e) { setFound(u, "Something went wrong running this experiment. Reload the page and try again."); console.error(e); }
  u.bar.style.width = "100%"; u.btn.disabled = false; u.btn.textContent = "Run again";
}
EXPS.forEach(x => ui(x.id).btn.addEventListener("click", () => runExp(x)));
// Results are found live: each experiment runs by itself the first time it scrolls into view.
if ("IntersectionObserver" in window) {
  const started = new Set();
  const io = new IntersectionObserver(es => es.forEach(en => {
    if (!en.isIntersecting || started.has(en.target.id)) return;
    started.add(en.target.id); io.unobserve(en.target);
    const x = EXPS.find(e => e.id === en.target.id);
    queue = queue.then(() => ui(x.id).btn.disabled ? null : runExp(x));
  }), { threshold: 0.35 });
  EXPS.forEach(x => io.observe(ui(x.id).root));
}
let queue = Promise.resolve();
$("#runAll").addEventListener("click", async () => { const b = $("#runAll"); b.disabled = true; for (const x of EXPS) await runExp(x); b.disabled = false; });

/* ================================================================= boot */
renderPeriod(); makeKey(); drawCircuitLab();
const redraw = () => { renderPeriod(); drawCircuitLab(); };
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
})();
