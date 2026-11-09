"""
shor_sim.py — a small, honest state-vector simulator of Shor's order-finding circuit.

Register layout (matches Figure 1 of the proposal):
    counting register : t qubits, starts in |0...0>, gets H^{(x)t}
    target register   : n = ceil(log2 N) qubits, starts in |1>
    controlled-U_a^{2^j} for j = 0..t-1   (U_a|y> = |a*y mod N>, y<N; identity on y>=N)
    inverse QFT on the counting register, then measure it.

Two independent implementations are provided so they can check each other:
  * `order_finding_statevector`  — applies every controlled-U^{2^j} as a permutation
    on the full 2^(t+n) state, then an inverse QFT built from H + controlled-phase + swaps.
  * `order_finding_fast`         — same physics, inverse QFT done with an FFT.

Only numpy is required.
"""
from __future__ import annotations

import math
import random
from fractions import Fraction
from math import gcd

import numpy as np


# ----------------------------------------------------------------------------- classical helpers
def multiplicative_order(a: int, N: int) -> int:
    """Smallest r>0 with a^r = 1 (mod N). Brute force — this is the step Shor speeds up."""
    if gcd(a, N) != 1:
        raise ValueError("a must be coprime to N")
    y, r = a % N, 1
    while y != 1:
        y = (y * a) % N
        r += 1
    return r


def continued_fraction(num: int, den: int) -> list[int]:
    """Coefficients [a0; a1, a2, ...] of num/den."""
    coeffs = []
    while den:
        q = num // den
        coeffs.append(q)
        num, den = den, num - q * den
    return coeffs


def convergents(coeffs: list[int]) -> list[Fraction]:
    out, h0, h1, k0, k1 = [], 0, 1, 1, 0
    for c in coeffs:
        h0, h1 = h1, c * h1 + h0
        k0, k1 = k1, c * k1 + k0
        out.append(Fraction(h1, k1))
    return out


def candidate_period(y: int, t: int, N: int) -> int | None:
    """From a measurement y of a t-qubit register, return the first convergent
    denominator r < N that actually satisfies a^r = 1 is checked by the caller."""
    if y == 0:
        return None
    dens = []
    for f in convergents(continued_fraction(y, 2 ** t)):
        if 0 < f.denominator < N and f.denominator not in dens:
            dens.append(f.denominator)
    return dens or None


def factors_from_period(a: int, r: int, N: int) -> tuple[int, int] | None:
    if r % 2:
        return None
    half = pow(a, r // 2, N)
    if half == N - 1:
        return None
    p, q = gcd(half - 1, N), gcd(half + 1, N)
    for f in (p, q):
        if 1 < f < N:
            return (f, N // f)
    return None


def shot_succeeds(y: int, t: int, a: int, N: int, lenient: bool = False) -> bool:
    """Classical post-processing of ONE measurement: continued fractions -> candidate r
    -> verify a^r = 1 (mod N) -> gcd.  Strict by default: only convergent denominators.
    lenient=True also tries small multiples of each denominator (common in practice, but for
    tiny N it lets even random noise "succeed" -- see Smolin et al. 2013)."""
    dens = candidate_period(y, t, N)
    if not dens:
        return False
    for d in dens:
        for m in ((1, 2, 3, 4) if lenient else (1,)):
            r = d * m
            if r < N and pow(a, r, N) == 1 and factors_from_period(a, r, N):
                return True
    return False


# ----------------------------------------------------------------------------- quantum pieces
def n_target_qubits(N: int) -> int:
    return max(1, math.ceil(math.log2(N)))


def _apply_controlled_mult(state: np.ndarray, t: int, n: int, j: int, mult: int, N: int) -> np.ndarray:
    """Controlled-U_mult on counting qubit j (little-endian), acting on the target register."""
    M, D = 2 ** t, 2 ** n
    st = state.reshape(M, D)
    perm = np.arange(D)
    perm[:N] = (np.arange(N) * mult) % N  # |y> -> |mult*y mod N>, identity on y>=N
    ctrl = ((np.arange(M) >> j) & 1).astype(bool)
    new = st.copy()
    moved = np.zeros_like(st[ctrl])
    moved[:, perm] = st[ctrl]          # amplitude at |y> moves to |perm[y]>
    new[ctrl] = moved
    return new.reshape(-1)


def _inverse_qft_gates(state: np.ndarray, t: int, n: int) -> np.ndarray:
    """Textbook inverse QFT on the counting register from H, controlled-phase and swaps."""
    M, D = 2 ** t, 2 ** n
    psi = state.reshape([2] * t + [D])          # axes: q_{t-1} ... q_0 , target
    ax = lambda q: t - 1 - q                     # axis index for counting qubit q
    # swaps first (inverse of the swaps at the end of the QFT)
    for q in range(t // 2):
        psi = np.swapaxes(psi, ax(q), ax(t - 1 - q))
    h = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
    for q in range(t):
        for c in range(q):
            # controlled phase e^{-i pi / 2^{q-c}} between qubits c and q
            phase = np.exp(-1j * math.pi / 2 ** (q - c))
            idx = [slice(None)] * (t + 1)
            idx[ax(q)] = 1
            idx[ax(c)] = 1
            psi[tuple(idx)] *= phase
        psi = np.moveaxis(np.tensordot(h, psi, axes=([1], [ax(q)])), 0, ax(q))
    return psi.reshape(M * D)


def order_finding_statevector(a: int, N: int, t: int) -> np.ndarray:
    """Gate-by-gate simulation. Returns P(y) for y in [0, 2^t)."""
    n = n_target_qubits(N)
    M, D = 2 ** t, 2 ** n
    state = np.zeros(M * D, dtype=complex)
    state[0 * D + 1] = 1.0                                # |0>^t |1>
    state = state.reshape(M, D)
    state = np.repeat(state[:1], M, axis=0) / math.sqrt(M)  # H^{(x)t}
    state = state.reshape(-1)
    for j in range(t):
        state = _apply_controlled_mult(state, t, n, j, pow(a, 2 ** j, N), N)
    state = _inverse_qft_gates(state, t, n)
    return (np.abs(state.reshape(M, D)) ** 2).sum(axis=1)


def order_finding_fast(a: int, N: int, t: int) -> np.ndarray:
    """Same distribution: after the controlled multiplications the joint state is
    (1/sqrt M) sum_x |x>|a^x mod N>; inverse QFT on x per target value via FFT."""
    M = 2 ** t
    x = np.arange(M)
    vals = np.array([pow(a, int(k), N) for k in x])
    probs = np.zeros(M)
    for v in np.unique(vals):
        col = (vals == v).astype(complex) / math.sqrt(M)
        amp = np.fft.fft(col) / math.sqrt(M)         # e^{-2 pi i x y / M}: inverse QFT
        probs += np.abs(amp) ** 2
    return probs


# ----------------------------------------------------------------------------- noise
def noisy(probs: np.ndarray, t: int, two_qubit_gates: int, eps: float, readout: float = 0.0) -> np.ndarray:
    """Global depolarizing model: each 2-qubit gate keeps the ideal state with prob (1-eps),
    otherwise the counting register is randomized. Optional independent readout bit-flips."""
    M = 2 ** t
    keep = (1 - eps) ** two_qubit_gates
    p = keep * probs + (1 - keep) / M
    if readout > 0:
        for b in range(t):
            flipped = p[np.arange(M) ^ (1 << b)]
            p = (1 - readout) * p + readout * flipped
    return p


def gate_estimate(N: int, t: int) -> int:
    """Rough 2-qubit gate count for a generic (non-compiled) circuit: modular
    multiplication ~ 4 n^2 CNOTs each, t of them, plus t^2/2 for the inverse QFT."""
    n = n_target_qubits(N)
    return int(t * 4 * n * n + t * t / 2)


def sample(probs: np.ndarray, shots: int, rng: random.Random | None = None) -> list[int]:
    rng = rng or random.Random(0)
    return rng.choices(range(len(probs)), weights=probs, k=shots)


def success_probability(probs: np.ndarray, t: int, a: int, N: int, lenient: bool = False) -> float:
    return float(sum(p for y, p in enumerate(probs) if p > 1e-12 and shot_succeeds(y, t, a, N, lenient)))


def shor(N: int, t: int | None = None, seed: int = 1, max_tries: int = 20, verbose: bool = True):
    """End-to-end: pick a, quantum order finding (simulated), classical post-processing."""
    rng = random.Random(seed)
    n = n_target_qubits(N)
    t = t or 2 * n
    if N % 2 == 0:
        return 2, N // 2
    for attempt in range(1, max_tries + 1):
        a = rng.randrange(2, N)
        g = gcd(a, N)
        if g > 1:
            if verbose:
                print(f"[{attempt}] lucky: gcd({a},{N}) = {g}")
            return g, N // g
        probs = order_finding_fast(a, N, t)
        y = sample(probs, 1, rng)[0]
        ok = shot_succeeds(y, t, a, N, lenient=True)
        if verbose:
            cf = convergents(continued_fraction(y, 2 ** t)) if y else []
            print(f"[{attempt}] a={a}  measured y={y}/{2**t}  convergents={[str(c) for c in cf[:5]]}  ->",
                  "success" if ok else "retry")
        if ok:
            for d in candidate_period(y, t, N):
                for m in (1, 2, 3, 4):
                    r = d * m
                    if pow(a, r, N) == 1 and (f := factors_from_period(a, r, N)):
                        if verbose:
                            print(f"    r={r}: gcd({a}^{r//2}-1,{N}), gcd({a}^{r//2}+1,{N}) -> {f}")
                        return f
    return None


if __name__ == "__main__":
    print(shor(15))
    print(shor(21))
    print(shor(35))
