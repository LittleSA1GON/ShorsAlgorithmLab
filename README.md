# Shor's Algorithm Lab

Step-by-step animations of Shor's algorithm plus labs and experiments that run live in the browser.
PHYS 161 Project 2B by Ethan Vu.

**Open it:** enable GitHub Pages for this repo (Settings → Pages → Deploy from branch → `main` / root),
or run it locally:

```bash
python -m http.server 8000      # then open http://localhost:8000
```

## What's on the site

| Section | What you do |
|---|---|
| **Learn** | Six short Blender animations (RSA → the repeating pattern → superposition → interference → measurement → post-quantum). Each one plays one step at a time with a caption. |
| **Lab A** | Find the period of aˣ mod N the slow way and turn it into factors. |
| **Lab B** | Run Shor's circuit: see the readout probabilities, measure, and watch continued fractions recover r. Includes a hardware-noise slider. |
| **Lab C** | Encrypt a message with a tiny RSA key, then break the key with simulated Shor's. |
| **Experiments** | Five questions answered live by running the circuit hundreds of times: readout peaks, counting qubits needed, which bases work, noise tolerance, and how classical brute force scales on your own computer. |

A run only counts as a success when the continued-fraction result itself is the period and yields
a factor. Looser scoring lets random noise "factor" 15 most of the time.

## Files

```
index.html, assets/        the website (no build step, no dependencies)
assets/shor-core.js        the math: exact output distribution, continued fractions, noise model
media/                     rendered animations (MP4 + poster)
lab/                       Python version: numpy simulator, tests, experiments, Qiskit/IBM script
blender/                   scenes.py builds every animation; encode.sh makes the MP4s
```

## Re-running the Python lab

```bash
pip install -r lab/requirements.txt
python lab/test_shor_sim.py            # gate-by-gate simulator == fast simulator
python lab/experiments.py              # writes lab/results + lab/figures
python lab/qiskit_hardware.py --N 15 --a 7 --t 8           # Qiskit, local
python lab/qiskit_hardware.py --ibm --N 21 --a 2 --t 8     # real IBM hardware (needs an account)
```

## Re-rendering the animations

```bash
pip install bpy        # or run inside Blender: blender -b -P blender/scenes.py -- all render/
python blender/scenes.py all render/ --frames 72
bash blender/encode.sh render/ media/
```

## Sources

Shor, *SIAM J. Comput.* 26 (1997) · IBM Quantum, "Shor's algorithm" (Learning and Documentation) ·
Gidney, arXiv:2505.15917 (2025) · Skosana & Tame, *Sci. Rep.* (2021) · arXiv:2512.15330 (2025) ·
NIST FIPS 203, 204, 205 (2024)
