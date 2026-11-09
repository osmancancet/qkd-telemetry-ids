"""One-factor sensitivity of the DCS detector (separate seeds 100-104).

Factors: monitoring window length, per-window source-intensity noise, fibre length.
Each setting: calibrate on drift-free benign data, test at nominal drift (1.0).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

import qkdsim as q
import detectors as D
from run_all import stream, concat, ALPHA_MAIN

OUT = Path(__file__).resolve().parent.parent / "results"
SEEDS = range(100, 105)
HOURS = 8
ATTACKS = [("ir", 0.05), ("blind_naive", 0.0), ("blind_gain", 0.0), ("blind_nodark", 0.0)]
FACTORS = {"window_s": [1.0, 10.0, 60.0], "int_sd_rel": [0.005, 0.01, 0.02],
           "length_km": [25.0, 50.0, 75.0]}


def run(seed, **over):
    rng = np.random.default_rng(seed)
    base = q.Config()
    cfg = q.Config(**{**base.__dict__, **over})
    cfg.n_windows = int(HOURS * 3600 / cfg.window_s)
    dcs = D.DCS(cfg.mu).fit(stream(cfg, rng, 0.0)[0])
    th = D.threshold(dcs.score(concat([stream(cfg, rng, 0.0)[0] for _ in range(3)])), ALPHA_MAIN)
    out = {"fpr": float(np.mean(dcs.score(stream(cfg, rng, 1.0)[0]) > th))}
    L = cfg.n_windows // 6
    for kind, s in ATTACKS:
        t0 = int(rng.integers(L, cfg.n_windows - 2 * L))
        T, _ = stream(cfg, rng, 1.0, kind, s, t0=t0, length=L)
        sc = dcs.score(T); m = T.label.astype(bool)
        out[f"{kind}:{s}"] = {"tpr": float(np.mean(sc[m] > th)), "auc": float(roc_auc_score(m, sc))}
    return out


if __name__ == "__main__":
    res = {}
    for f, vals in FACTORS.items():
        for v in vals:
            key = f"{f}={v}"
            res[key] = [run(s, **{f: v}) for s in SEEDS]
            print(key, "fpr", np.mean([r["fpr"] for r in res[key]]),
                  {a: round(np.mean([r[a]["tpr"] for r in res[key]]), 3)
                   for a in res[key][0] if a != "fpr"}, flush=True)
    (OUT / "sensitivity.json").write_text(json.dumps(res, indent=1))
