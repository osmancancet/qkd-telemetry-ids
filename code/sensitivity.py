"""One-factor sensitivity of the DCS, its CUSUM, the block-level DCS and the
seven-residual ablation DCS-7 (seeds 100-109, 24 h streams).

Each setting changes one factor from the nominal configuration, calibrates on
drift-free benign data and tests at drift scales 1 and 4. Attacks last 2 h whatever
the window length. The nominal setting is run once and shared by all factors.
"""
from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

import qkdsim as q
import detectors as D
from run_all import stream, key_audit, ALPHA_MAIN

OUT = Path(__file__).resolve().parent.parent / "results"
SEEDS = range(int(os.environ.get("SENS_SEED0", 100)), int(os.environ.get("SENS_SEED0", 100)) + 10)
ATTACK_S = 7200
ATTACKS = [("ir", 0.05), ("blind_naive", 0.0), ("blind_gain", 0.0), ("blind_nodark", 0.0),
           ("blind_thresh", 0.0)]
FACTORS = {"window_s": [1.0, 60.0], "int_sd_rel": [0.005, 0.02], "length_km": [25.0, 75.0],
           "p_ap": [0.0, 0.05], "e_mis": [(0.01, 0.01), (0.01, 0.02)],
           "int_drift_sd_rel": [0.005, 0.02], "int_monitor": [False],
           "int_mon_sd_rel": [0.005, 0.01], "int_mon_bias_sd_rel": [0.002, 0.005, 0.01],
           "path_eff_sd_rel": [0.0, 0.01, 0.02], "pdl_sd_rel": [0.0, 0.005],
           "mis_rate_per_h": [0.0025]}


def run(args):
    seed, over = args
    rng = np.random.default_rng(seed)
    base = q.Config()
    cfg = q.Config(**{**base.__dict__, **over})
    cfg.n_windows = int(86400 / cfg.window_s)
    L = int(ATTACK_S / cfg.window_s)
    T_fit = stream(cfg, rng, 0.0)[0]
    L_block = max(2, int(round(600 / cfg.window_s)))      # Block always averages 10 minutes
    dets = [D.DCS().fit(T_fit), D.CUSUM().fit(T_fit), D.Block(L=L_block).fit(T_fit),
            D.DCS(full=True).fit(T_fit), D.DCS(xonly=True).fit(T_fit)]
    thr_streams = [stream(cfg, rng, 0.0)[0] for _ in range(3)]
    th = {d.name: D.threshold(np.concatenate([d.score(T) for T in thr_streams]), ALPHA_MAIN)
          for d in dets}
    out = {}
    for drift in (1.0, 4.0):
        Tb = stream(cfg, rng, drift)[0]
        o = {"fpr": {d.name: float(np.mean(D.alarm_prob(d.score(Tb), th[d.name]))) for d in dets}}
        K = key_audit(Tb, np.ones(len(Tb.label), bool), cfg)
        o["key"] = {"rate": float(np.mean([k["rate"] for k in K])),
                    "viol": int(sum(k["sZ1"] > k["sZ1_true"] for k in K)),
                    "viol_nom": int(sum(k["sZ1_nom"] > k["sZ1_true"] for k in K)),
                    "viol_ph": int(sum(k["vX1"] < k["vX1_true"] for k in K)), "n": len(K)}
        if drift == 1.0:
            for kind, s in ATTACKS:
                t0 = int(rng.integers(L, cfg.n_windows - 2 * L))
                T, B, _ = stream(cfg, rng, drift, kind, s, t0=t0, length=L)
                m = T.label.astype(bool)
                o[f"{kind}:{s}"] = {}
                for d in dets:
                    sc, sb = d.score(T), d.score(B)
                    yy = np.r_[np.ones(L), np.zeros(L)]
                    o[f"{kind}:{s}"][d.name] = {
                        "tpr": float(np.mean(D.alarm_prob(sc[m], th[d.name]))),
                        "auc": float(roc_auc_score(yy, np.r_[sc[m], sb[m]]))}
        out[str(drift)] = o
    return out


if __name__ == "__main__":
    settings = {"nominal": {}}
    for f, vals in FACTORS.items():
        for v in vals:
            settings[f"{f}={v}"] = {f: v}
    jobs = [(s, over) for over in settings.values() for s in SEEDS]
    nproc = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    with Pool(nproc) as p:
        flat = p.map(run, jobs, chunksize=1)
    res, i = {}, 0
    for key in settings:
        res[key] = flat[i:i + len(SEEDS)]
        i += len(SEEDS)
    (OUT / "sensitivity.json").write_text(json.dumps(res, indent=1))
    for key, r in res.items():
        print(key, "fpr d1", {n: round(np.mean([x["1.0"]["fpr"][n] for x in r]), 4) for n in r[0]["1.0"]["fpr"]},
              "d4", round(np.mean([x["4.0"]["fpr"]["DCS"] for x in r]), 4),
              {a: round(np.mean([x["1.0"][a]["DCS"]["tpr"] for x in r]), 3)
               for a in r[0]["1.0"] if a not in ("fpr", "key")}, flush=True)
    (OUT / "sensitivity.json").write_text(json.dumps(res, indent=1))
