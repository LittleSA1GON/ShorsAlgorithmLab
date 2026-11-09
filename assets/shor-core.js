/* shor-core.js — the math behind every lab on the site.
   Mirrors lab/shor_sim.py (checked against a gate-by-gate state-vector simulation and Qiskit).
   Pure functions, no DOM: loaded by the page and copied into the experiment Web Worker. */
(function (root) {
  "use strict";

  const gcd = (a, b) => { a = Math.abs(a); b = Math.abs(b); while (b) [a, b] = [b, a % b]; return a; };

  // a^e mod m with BigInt so nothing overflows
  function modpow(b, e, m) {
    let r = 1n, x = BigInt(b) % BigInt(m), E = BigInt(e); const M = BigInt(m);
    while (E > 0n) { if (E & 1n) r = r * x % M; x = x * x % M; E >>= 1n; }
    return Number(r);
  }

  // smallest r > 0 with a^r = 1 (mod N): the classical brute-force walk
  function order(a, N) {
    if (gcd(a, N) !== 1) return null;
    let y = a % N, r = 1;
    while (y !== 1) { y = (y * a) % N; r++; if (r > N) return null; }
    return r;
  }

  const nQubits = N => Math.max(1, Math.ceil(Math.log2(N)));

  function contFrac(num, den) {
    const c = [];
    while (den) { const q = Math.floor(num / den); c.push(q); [num, den] = [den, num - q * den]; }
    return c;
  }
  function convergents(c) {
    const out = []; let h0 = 0, h1 = 1, k0 = 1, k1 = 0;
    for (const a of c) { [h0, h1] = [h1, a * h1 + h0]; [k0, k1] = [k1, a * k1 + k0]; out.push([h1, k1]); }
    return out;
  }

  function factorsFromPeriod(a, r, N) {
    if (r % 2) return { ok: false, why: "the period is odd" };
    const half = modpow(a, r / 2, N);
    if (half === N - 1) return { ok: false, why: "a^(r/2) = −1 (mod N), so the gcds are trivial" };
    for (const f of [gcd(half - 1, N), gcd(half + 1, N)])
      if (f > 1 && f < N) return { ok: true, p: Math.min(f, N / f), q: Math.max(f, N / f), half };
    return { ok: false, why: "the gcds only gave 1 and N" };
  }

  /* Exact probability of measuring y on the t-qubit counting register.
     After the controlled multiplications, x values with the same a^x mod N form classes
     x = x0, x0+r, x0+2r, ...  The inverse QFT turns each class into a Dirichlet kernel,
     so P(y) = sum over classes |sum_k e^(2 pi i k r y / 2^t)|^2 / 4^t.  Only two class sizes occur. */
  function distribution(a, N, t) {
    const M = 2 ** t, r = order(a, N), P = new Float64Array(M);
    const K1 = Math.floor(M / r), K2 = K1 + 1, c2 = M % r, c1 = r - c2;
    for (let y = 0; y < M; y++) {
      const th = ((r * y) % M) / M;
      const f = K => { if (th === 0) return K * K; const s = Math.sin(Math.PI * K * th) / Math.sin(Math.PI * th); return s * s; };
      P[y] = (c1 * f(K1) + (c2 ? c2 * f(K2) : 0)) / (M * M);
    }
    return { P, r, M };
  }

  /* Classical post-processing of one measured y (strict: the convergent denominator itself
     must be a period that yields a factor — no guessing multiples). */
  function analyze(y, t, a, N) {
    const M = 2 ** t;
    if (y === 0) return { y, M, conv: [[0, 1]], cands: [], r: null, ok: false, why: "y = 0 carries no information" };
    const conv = convergents(contFrac(y, M));
    const cands = [];
    for (const [, d] of conv) if (d > 0 && d < N && !cands.includes(d)) cands.push(d);
    for (const d of cands) {
      if (modpow(a, d, N) === 1) {
        const f = factorsFromPeriod(a, d, N);
        if (f.ok) return { y, M, conv, cands, r: d, ok: true, p: f.p, q: f.q };
        return { y, M, conv, cands, r: d, ok: false, why: f.why };
      }
    }
    return { y, M, conv, cands, r: null, ok: false, why: "the fraction gave a divisor of r, not r itself" };
  }

  // two-qubit gate count of a generic (not answer-aware) circuit, same estimate as the Python lab
  const gateEstimate = (N, t) => { const n = nQubits(N); return Math.floor(t * 4 * n * n + t * t / 2); };

  // global depolarizing noise: the ideal state survives each gate with probability 1 - eps
  function noisy(P, t, N, eps) {
    if (!eps) return P;
    const M = P.length, keep = Math.pow(1 - eps, gateEstimate(N, t));
    return P.map(p => keep * p + (1 - keep) / M);
  }

  function successProb(P, t, a, N) {
    let s = 0;
    for (let y = 0; y < P.length; y++) if (P[y] > 1e-12 && analyze(y, t, a, N).ok) s += P[y];
    return s;
  }

  // fast repeated sampling: cumulative table + binary search
  function sampler(P, rnd = Math.random) {
    const C = new Float64Array(P.length); let acc = 0;
    for (let i = 0; i < P.length; i++) { acc += P[i]; C[i] = acc; }
    return () => { const u = rnd() * acc; let lo = 0, hi = C.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (C[m] < u) lo = m + 1; else hi = m; } return lo; };
  }

  const usableBases = N => { const out = []; for (let a = 2; a < N; a++) if (gcd(a, N) === 1) { const r = order(a, N); out.push({ a, r, usable: factorsFromPeriod(a, r, N).ok }); } return out; };

  const api = { gcd, modpow, order, nQubits, contFrac, convergents, factorsFromPeriod, distribution, analyze, gateEstimate, noisy, successProb, sampler, usableBases };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.ShorCore = api;
})(typeof self !== "undefined" ? self : this);
