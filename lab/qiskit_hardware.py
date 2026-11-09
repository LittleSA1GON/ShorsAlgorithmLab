"""
qiskit_hardware.py — run the same order-finding circuit with Qiskit, locally or on IBM hardware.

    pip install qiskit qiskit-ibm-runtime
    python qiskit_hardware.py                       # local exact simulation (no account)
    python qiskit_hardware.py --ibm --backend ibm_torino --shots 4096
          (needs QiskitRuntimeService.save_account(...) done once)

The controlled-U_a^{2^j} blocks are generic permutation unitaries (not answer-aware
"compiled" shortcuts), so on hardware the transpiled circuit is deep and noisy — that is
the honest point of the experiment. Compare the hit rate with the random-guess baseline,
as in arXiv:2512.15330.
"""
import argparse
import math
from collections import Counter

import numpy as np

from shor_sim import shot_succeeds, n_target_qubits, success_probability


def build_circuit(a: int, N: int, t: int):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import UnitaryGate, QFTGate

    n = n_target_qubits(N)
    qc = QuantumCircuit(t + n, t)
    qc.x(t)                                   # target register = |1>
    qc.h(range(t))
    D = 2 ** n
    for j in range(t):
        m = pow(a, 2 ** j, N)
        U = np.zeros((D, D))
        for y in range(D):
            U[(y * m) % N if y < N else y, y] = 1
        g = UnitaryGate(U, label=f"U^{2**j}").control(1)
        qc.append(g, [j] + list(range(t, t + n)))
    qc.append(QFTGate(t).inverse(), range(t))
    qc.measure(range(t), range(t))
    return qc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=15)
    ap.add_argument("--a", type=int, default=7)
    ap.add_argument("--t", type=int, default=None)
    ap.add_argument("--shots", type=int, default=2048)
    ap.add_argument("--ibm", action="store_true")
    ap.add_argument("--backend", default=None)
    args = ap.parse_args()
    N, a = args.N, args.a
    t = args.t or 2 * n_target_qubits(N)
    if t + n_target_qubits(N) > 16 and not args.ibm:
        t = 16 - n_target_qubits(N)
    qc = build_circuit(a, N, t)

    if args.ibm:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        svc = QiskitRuntimeService()
        backend = svc.backend(args.backend) if args.backend else svc.least_busy(operational=True, simulator=False)
        isa = generate_preset_pass_manager(optimization_level=3, backend=backend).run(qc)
        print("backend:", backend.name, " depth:", isa.depth(), " 2q gates:", isa.num_nonlocal_gates())
        res = SamplerV2(mode=backend).run([isa], shots=args.shots).result()
        counts = res[0].data.c.get_counts()
    else:
        from qiskit.quantum_info import Statevector
        qc_nm = qc.remove_final_measurements(inplace=False)
        probs = Statevector(qc_nm).probabilities(list(range(t)))
        rng = np.random.default_rng(0)
        ys = rng.choice(len(probs), size=args.shots, p=probs / probs.sum())
        counts = {format(int(y), f"0{t}b"): c for y, c in Counter(ys).items()}

    hits = sum(c for b, c in counts.items() if shot_succeeds(int(b, 2), t, a, N))
    base = success_probability(np.full(2 ** t, 1 / 2 ** t), t, a, N)
    print(f"N={N} a={a} t={t} shots={args.shots}")
    print("top outcomes:", sorted(((int(b, 2), c) for b, c in counts.items()), key=lambda x: -x[1])[:8])
    print(f"hit rate {hits/args.shots:.3f}   vs random-guess baseline {base:.3f}")


if __name__ == "__main__":
    main()
