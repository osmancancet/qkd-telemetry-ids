"""Post-hoc variant DCS+Y0 (adds the background-yield level as a seventh residual).

Defined after the main results exposed the Blind-nodark blind spot of DCS, so it is
evaluated on fresh seeds (200-209) and reported separately from the main benchmark.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

import qkdsim as q
import detectors as D
from run_all import stream, concat, ALPHA_MAIN, ATTACK_LEN, DRIFTS, TEST_ATTACKS

OUT = Path(__file__).resolve().parent.parent / "results"


def run(seed):
    rng = np.random.default_rng(seed)
    cfg = q.Config()
    T_fit = stream(cfg, rng, 0.0)[0]
    T_thr = concat([stream(cfg, rng, 0.0)[0] for _ in range(3)])
    dets = [D.DCS(cfg.mu).fit(T_fit), D.DCS(cfg.mu, with_y0=True).fit(T_fit)]
    th = {d.name: D.threshold(d.score(T_thr), ALPHA_MAIN) for d in dets}
    res = {}
    for drift in DRIFTS:
        rd = {"benign": {d.name: float(np.mean(d.score(stream(cfg, rng, drift)[0]) > th[d.name]))
                         for d in dets}}
        for kind, s in TEST_ATTACKS:
            t0 = int(rng.integers(1440, cfg.n_windows - ATTACK_LEN - 1440))
            T, _ = stream(cfg, rng, drift, kind, s, t0=t0, length=ATTACK_LEN)
            m = T.label.astype(bool)
            rd[f"{kind}:{s}"] = {}
            for d in dets:
                sc = d.score(T)
                rd[f"{kind}:{s}"][d.name] = {"auc": float(roc_auc_score(m, sc)),
                                             "tpr": float(np.mean(sc[m] > th[d.name]))}
        res[str(drift)] = rd
    return res


if __name__ == "__main__":
    R = {s: run(s) for s in range(200, 210)}
    (OUT / "exploratory_dcs_y0.json").write_text(json.dumps(R, indent=1))
    for d in map(str, DRIFTS):
        print(d, {n: round(np.mean([R[s][d]["benign"][n] for s in R]), 4) for n in ("DCS", "DCS+Y0")})
        for a in R[200][d]:
            if a == "benign":
                continue
            print("  ", a, {n: (round(np.mean([R[s][d][a][n]["auc"] for s in R]), 3),
                               round(np.mean([R[s][d][a][n]["tpr"] for s in R]), 3)) for n in ("DCS", "DCS+Y0")})
