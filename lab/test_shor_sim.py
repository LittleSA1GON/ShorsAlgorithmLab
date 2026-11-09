"""Run: python -m pytest lab/ -q   (or just: python lab/test_shor_sim.py)"""
import numpy as np
from shor_sim import (order_finding_statevector, order_finding_fast, multiplicative_order,
                      continued_fraction, convergents, factors_from_period, shor, success_probability)


def test_gate_level_matches_fft():
    for a, N, t in [(7, 15, 6), (2, 15, 5), (2, 21, 6), (4, 21, 5)]:
        p1 = order_finding_statevector(a, N, t)
        p2 = order_finding_fast(a, N, t)
        assert np.allclose(p1, p2, atol=1e-10), (a, N, t)
        assert abs(p1.sum() - 1) < 1e-10


def test_n15_peaks_exact():
    p = order_finding_fast(7, 15, 8)            # r = 4 divides 256 -> 4 perfect peaks
    peaks = sorted(np.argsort(p)[-4:])
    assert peaks == [0, 64, 128, 192]
    assert np.allclose(p[peaks], 0.25)


def test_classical_pieces():
    assert multiplicative_order(2, 15) == 4
    assert multiplicative_order(2, 21) == 6
    assert continued_fraction(85, 256) == [0, 3, 85]  # 85/256 ≈ 1/3
    assert convergents([0, 3, 85])[1].denominator == 3
    assert factors_from_period(2, 4, 15) == (3, 5)


def test_end_to_end():
    for N in (15, 21, 33, 35):
        f = shor(N, verbose=False)
        assert f and f[0] * f[1] == N and 1 < f[0] < N


def test_success_probability_reasonable():
    assert success_probability(order_finding_fast(7, 15, 8), 8, 7, 15) > 0.45  # strict: phi(4)/4 = 0.5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
