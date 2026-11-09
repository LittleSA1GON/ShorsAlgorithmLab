"""
experiments.py — the lab experiments behind the web app.

    python experiments.py            # writes results/experiments.json and figures/*.png

E1  Measurement distributions        (N=15,a=7 ; N=21,a=2)
E2  Counting-qubit sweep             how many counting qubits t are enough?
E3  Base sweep                       which bases a are "good" for each N?
E4  Noise sweep                      success vs. two-qubit error rate (global depolarizing model)
E5  Classical brute-force timing     order finding by trying every power
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from math import gcd

import numpy as np

from shor_sim import (order_finding_fast, success_probability, multiplicative_order,
                      factors_from_period, noisy, gate_estimate, n_target_qubits)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)


def e1():
    out = {}
    for a, N, t in [(7, 15, 8), (2, 21, 10)]:
        p = order_finding_fast(a, N, t)
        out[f"{N}_{a}"] = dict(a=a, N=N, t=t, r=multiplicative_order(a, N),
                               probs=[round(float(x), 6) for x in p],
                               success=round(success_probability(p, t, a, N), 4))
    return out


def e2():
    rows = []
    for t in range(3, 12):
        for a, N in [(7, 15), (2, 21)]:
            p = order_finding_fast(a, N, t)
            rows.append(dict(N=N, a=a, t=t, success=round(success_probability(p, t, a, N), 4)))
    return rows


def e3():
    rows = []
    for N in [15, 21, 33, 35, 39, 51, 55, 57, 65, 77, 85, 91]:
        n = n_target_qubits(N)
        t = min(2 * n, 12)
        bases = []
        for a in range(2, N):
            if gcd(a, N) != 1:
                continue
            r = multiplicative_order(a, N)
            useful = factors_from_period(a, r, N) is not None
            s = success_probability(order_finding_fast(a, N, t), t, a, N) if useful else 0.0
            bases.append(dict(a=a, r=r, useful=useful, success=round(s, 3)))
        good = [b for b in bases if b["useful"]]
        rows.append(dict(N=N, t=t, n_coprime=len(bases), n_useful=len(good),
                         frac_useful=round(len(good) / len(bases), 3),
                         mean_success_useful=round(float(np.mean([b["success"] for b in good])), 3),
                         bases=bases))
    return rows


def e4():
    eps_list = [float(x) for x in np.logspace(-5, -1.7, 18)]
    out = []
    for a, N, t in [(7, 15, 8), (2, 21, 10)]:
        ideal = order_finding_fast(a, N, t)
        G = gate_estimate(N, t)
        uni = np.full(2 ** t, 1 / 2 ** t)
        base = success_probability(uni, t, a, N)                       # random guessing, strict
        base_len = success_probability(uni, t, a, N, lenient=True)     # random guessing, lenient
        curve = []
        for eps in eps_list:
            p = noisy(ideal, t, G, eps, readout=0.0)
            curve.append(dict(eps=eps, success=round(success_probability(p, t, a, N), 4)))
        out.append(dict(N=N, a=a, t=t, gates=G, baseline=round(base, 4),
                        baseline_lenient=round(base_len, 4), curve=curve))
    return out


def e5():
    rng = random.Random(7)
    primes = [p for p in range(3, 1 << 14) if all(p % d for d in range(2, int(p ** .5) + 1))]
    rows = []
    for bits in range(8, 27, 2):
        cands = [(p, q) for p in primes for q in primes
                 if p < q and (p * q).bit_length() == bits]
        rng.shuffle(cands)
        times, orders = [], []
        for p, q in cands[:6]:
            N = p * q
            a = rng.randrange(2, N)
            while gcd(a, N) != 1:
                a = rng.randrange(2, N)
            t0 = time.perf_counter()
            r = multiplicative_order(a, N)
            times.append(time.perf_counter() - t0)
            orders.append(r)
        rows.append(dict(bits=bits, median_seconds=float(np.median(times)),
                         median_steps=int(np.median(orders))))
    # fit log2(steps) ~ bits
    b = np.array([r["bits"] for r in rows]); s = np.log2([max(1, r["median_steps"]) for r in rows])
    slope, icpt = np.polyfit(b, s, 1)
    return dict(rows=rows, fit=dict(slope=round(float(slope), 3), intercept=round(float(icpt), 3)))


def figures(data):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing — skipping figures"); return
    plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    ink, acc, acc2 = "#2a3140", "#3b82c4", "#d9822b"
    for key, d in data["e1"].items():
        fig, ax = plt.subplots(figsize=(6.4, 2.6))
        ax.bar(range(len(d["probs"])), d["probs"], width=1.0, color=acc)
        ax.set_title(f"E1 · Counting-register distribution, N={d['N']}, a={d['a']}, t={d['t']}  (r={d['r']})", color=ink)
        ax.set_xlabel("measured y"); ax.set_ylabel("P(y)")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, f"e1_{key}.png")); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    for N, c in [(15, acc), (21, acc2)]:
        rows = [r for r in data["e2"] if r["N"] == N]
        ax.plot([r["t"] for r in rows], [r["success"] for r in rows], "o-", color=c, label=f"N={N}")
    ax.set_title("E2 · One-shot success vs counting qubits t"); ax.set_xlabel("t"); ax.set_ylabel("P(success)")
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(os.path.join(FIG, "e2_t_sweep.png")); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    for d, c in zip(data["e4"], [acc, acc2]):
        ax.semilogx([p["eps"] for p in d["curve"]], [p["success"] for p in d["curve"]], "o-", ms=3, color=c,
                    label=f"N={d['N']} (~{d['gates']} 2q gates)")
        ax.axhline(d["baseline"], color=c, ls=":", lw=1)
    ax.axvline(2.7e-3, color="#888", lw=1); ax.text(2.9e-3, 0.02, "ibm_torino median\n2q error", fontsize=7, color="#666")
    ax.set_title("E4 · Success vs two-qubit error (dotted = random guessing)"); ax.set_xlabel("error per 2-qubit gate")
    ax.set_ylabel("P(success)"); ax.legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e4_noise.png")); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    rows = data["e5"]["rows"]
    ax.semilogy([r["bits"] for r in rows], [r["median_steps"] for r in rows], "o-", color=acc)
    ax.set_title("E5 · Brute-force order finding: steps vs size of N"); ax.set_xlabel("bits in N"); ax.set_ylabel("multiplications")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e5_classical.png")); plt.close(fig)


if __name__ == "__main__":
    t0 = time.time()
    data = dict(e1=e1(), e2=e2(), e3=e3(), e4=e4(), e5=e5())
    with open(os.path.join(OUT, "experiments.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))
    figures(data)
    print(f"done in {time.time()-t0:.1f}s")
    for r in data["e2"]:
        print("E2", r)
    for r in data["e3"]:
        print("E3", r["N"], r["n_useful"], "/", r["n_coprime"], "useful; mean success", r["mean_success_useful"])
    for d in data["e4"]:
        print("E4", d["N"], d["gates"], d["baseline"], [c["success"] for c in d["curve"]])
    print("E5", data["e5"]["fit"], data["e5"]["rows"][-1])
