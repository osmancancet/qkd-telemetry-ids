# QKD telemetry intrusion-detection benchmark

Code for "What window telemetry can and cannot reveal about quantum hacking".

## Files
- `qkdsim.py`: decoy-state BB84 window simulator (honest channel, benign drift, attacks)
- `finite_key.py`: finite-key length of Lim et al., PRA 89, 022307 (2014)
- `detectors.py`: QBER rule, DCS, isolation forest, random forest
- `run_all.py`: main benchmark, one JSON per seed in `../results/`
- `sensitivity.py`: one-factor sensitivity of the DCS (seeds 100-104)
- `exploratory.py`: post-hoc DCS+Y0 variant (seeds 200-209)
- `make_tables.py`: `results/numbers.json`, LaTeX tables and `manuscript/numbers.tex`
- `make_figs.py`: figures in `manuscript/figures/`
- `test_sim.py`: unit tests (`python3 -m pytest -q test_sim.py`)

## Run order
```
pip install numpy scipy scikit-learn matplotlib pytest
python3 -m pytest -q test_sim.py
python3 run_all.py 10          # seeds 0-9, about 20 s per seed
python3 sensitivity.py         # 9 settings x 5 seeds
python3 exploratory.py         # 10 seeds
python3 make_tables.py
python3 make_figs.py
cd ../manuscript && pdflatex main && bibtex main && pdflatex main && pdflatex main
```
All randomness is seeded (`numpy.random.default_rng`, `random_state`). Licence: MIT.
