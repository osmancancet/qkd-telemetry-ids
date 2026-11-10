# QKD count-telemetry intrusion-detection benchmark

Code for "What count telemetry can and cannot reveal about detector-control attacks on decoy-state QKD".

## Files
- `qkdsim.py`: decoy-state BB84 window simulator with Alice's and Bob's basis choice (sifting), per-basis misalignment, afterpulses, basis-dependent efficiencies (Bob's paths, polarisation-dependent loss), slow intensity drift with an intensity monitor (optional bias), benign drift and attacks
- `finite_key.py`: finite-key length of Lim et al., PRA 89, 022307 (2014)
- `detectors.py`: QBER rule, two-sided Band, Band-roll (rolling reference), DCS (4 residuals), DCS-X (test-basis errors only), DCS-7 (ablation), CUSUM and Block on the DCS residuals, isolation forests and random forests (on features or on DCS residuals), randomised thresholds
- `run_all.py`: main benchmark, one JSON per seed in `../results/`
- `sensitivity.py`: one-factor sensitivity (25 settings; seeds set by `SENS_SEED0`, default 100)
- `exploratory.py`: floor variants DCS+P and DCS+F, and the stress test of benign operational events (`S`)
- `make_tables.py`: `results/numbers.json`, LaTeX tables and `manuscript/numbers.tex` (BCa intervals over seeds)
- `make_figs.py`: figures in `manuscript/figures/`
- `test_sim.py`: unit tests (`python3 -m pytest -q test_sim.py`)

## Seeds
Development used seeds 0-9 (kept in `results/dev/`, not used in the paper). The reported results use
fresh seeds: 10-49 (main), 500-509 (DCS+F), 600-609 (stress), 700-709 (sensitivity); DCS+P is
reported from its development seeds 200-209.

## Run order (reproduces every number, table and figure)
```
pip install -r requirements.txt
python3 -m pytest -q test_sim.py
python3 run_all.py 0 $(seq 10 49)          # about 90 s per seed per core; split over processes if desired
python3 exploratory.py P                   # DCS+P, seeds 200-209
python3 exploratory.py F 500               # DCS+F, seeds 500-509
python3 exploratory.py S 600               # stress test, seeds 600-609
SENS_SEED0=700 python3 sensitivity.py 2    # 25 settings x 10 seeds, 2 processes
python3 make_tables.py
python3 make_figs.py
cd ../manuscript && pdflatex main && bibtex main && pdflatex main && pdflatex main
```
`make_tables.py` reads every `results/seed_*.json`. All randomness is seeded (`numpy.random.default_rng`, `random_state`); random-forest scores can differ in the last digits between machines because of multithreading. In the code and JSON files the attack called Blind-nobg in the paper is named `blind_nodark`. Licence: MIT.
