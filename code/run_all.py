"""Run the full benchmark: one JSON per seed in ../results/.

Usage: python3 run_all.py [n_seeds]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

import qkdsim as q
import finite_key as fk
import detectors as D

OUT = Path(__file__).resolve().parent.parent / "results"
OUT.mkdir(exist_ok=True)

ALPHAS = (1e-2, 1e-3, 1e-4)
ALPHA_MAIN = 1e-3
DRIFTS = (0.0, 1.0, 2.0, 4.0)
ATTACK_LEN = 720            # windows (2 h)
PE_BLOCK = 60               # windows per post-processing block (10 min, 6e10 pulses)
TEST_ATTACKS = [("ir", 0.05), ("ir", 0.2), ("pns", 0.0), ("blind_naive", 0.0),
                ("blind_gain", 0.0), ("blind_nodark", 0.0), ("blind_cal", 0.0), ("blind_cal_static", 0.0), ("loss", 1.0), ("loss", 3.0)]
TRAIN_ATTACKS = [("ir", 0.05), ("ir", 0.1), ("ir", 0.25), ("ir", 0.5), ("pns", 0.0),
                 ("blind_naive", 0.0), ("loss", 1.0), ("loss", 3.0), ("loss", 6.0)]


def yields_for(kind, strength, st, cfg):
    if kind == "honest":
        return q.honest_yields(st["eta"], st["y0"], st["ed"], cfg.e0)
    if kind == "blind_cal_static":
        W = len(st["eta"])
        return q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg,
                               eta_eve=np.full(W, cfg.eta_nominal),
                               y0_eve=np.full(W, cfg.y0_nominal), ed_eve=np.full(W, cfg.e_mis))
    return q.attack_yields(kind, st["eta"], st["y0"], st["ed"], cfg, strength)


def stream(cfg, rng, drift, kind="honest", strength=0.0, n_windows=None, t0=None, length=None):
    c = q.Config(**{**cfg.__dict__, "drift": drift,
                    "n_windows": n_windows or cfg.n_windows})
    st = q.channel_state(c, rng)
    base = q.sample(c, rng, st, *yields_for("honest", 0, st, c))
    if kind == "honest":
        return base, st
    att = q.sample(c, rng, st, *yields_for(kind, strength, st, c))
    mask = np.zeros(c.n_windows, bool)
    if t0 is None:
        mask[:] = True
    else:
        mask[t0:t0 + length] = True
    return q.splice(base, att, mask), st


def concat(Ts):
    return q.Telemetry(*(np.concatenate([getattr(T, f) for T in Ts]) for f in
                         ("N", "n", "m", "n1", "known", "label")))


def key_audit(T, mask, cfg):
    """Finite-key length per PE block fully inside `mask`, and the breach test
    ell > nZ - K_E (Eve knows K_E sifted key bits exactly)."""
    idx = np.where(mask)[0]
    out = []
    for b0 in range(idx[0], idx[-1] + 1 - PE_BLOCK + 1, PE_BLOCK):
        sl = slice(b0, b0 + PE_BLOCK)
        nZ, nX = T.n[sl, 0].sum(0), T.n[sl, 1].sum(0)
        mZ, mX = T.m[sl, 0].sum(0), T.m[sl, 1].sum(0)
        r = fk.key_length(nZ, nX, mZ, mX, cfg.mu, cfg.p_mu)
        KE = T.known[sl, 0].sum()
        out.append(dict(ell=float(r["ell"]), nZ=float(r["nZ"]), KE=float(KE),
                        rate=float(r["ell"] / (cfg.n_pulses * PE_BLOCK)),
                        sZ1=float(r["sZ1"]), sZ1_true=float(T.n1[sl, 0].sum()),
                        breach=bool(r["ell"] > r["nZ"] - KE)))
    return out


def run_seed(seed: int):
    t_start = time.time()
    rng = np.random.default_rng(1000 + seed)
    cfg = q.Config()
    res = dict(seed=seed, config={k: v for k, v in cfg.__dict__.items()})

    # --- calibration (benign, no slow drift) -----------------------------------
    T_fit, _ = stream(cfg, rng, 0.0)
    T_thr = concat([stream(cfg, rng, 0.0)[0] for _ in range(3)])
    # control: benign calibration data that already contains slow drift
    T_fit_d = concat([stream(cfg, rng, d)[0] for d in (0.5, 1.0, 2.0)])
    T_thr_d = concat([stream(cfg, rng, d)[0] for d in (0.5, 1.0, 2.0)])

    # --- ML training sets: stationary ("literature style") and drift-randomised --
    def train_set(randomise):
        Ts = []
        dr = (lambda: rng.uniform(0, 2)) if randomise else (lambda: 0.0)
        Ts.append(stream(cfg, rng, dr())[0])
        for kind, s in TRAIN_ATTACKS:
            Ts.append(stream(cfg, rng, dr(), kind, s, n_windows=2160)[0])
        T = concat(Ts)
        return D.features(T), T.label

    Xs, ys = train_set(False)
    Xd, yd = train_set(True)
    ifd = D.IF(seed).fit(T_fit_d); ifd.name = "IsoForest-drift"
    dets = [D.QBERThreshold(), D.DCS(cfg.mu).fit(T_fit), D.IF(seed).fit(T_fit), ifd,
            D.RF("RF-stationary", seed).fit(Xs, ys), D.RF("RF-drift-rand", seed).fit(Xd, yd)]
    # thresholds: 'stat' calibrated on drift-free benign data (the deployable default),
    # 'drift' calibrated on benign data with drift (control with extra benign data)
    thr, thr_d = {}, {}
    for d in dets:
        sc, scd = d.score(T_thr), d.score(T_thr_d)
        thr[d.name] = {str(a): D.threshold(sc, a) for a in ALPHAS}
        thr_d[d.name] = {str(a): D.threshold(scd, a) for a in ALPHAS}
        if d.name == "QBER-11%":
            thr[d.name] = thr_d[d.name] = {str(a): 0.11 for a in ALPHAS}
    res["thresholds"] = thr
    res["thresholds_drift"] = thr_d

    # --- test ------------------------------------------------------------------
    res["test"] = {}
    for drift in DRIFTS:
        rd = {}
        Tb, stb = stream(cfg, rng, drift)
        rd["benign"] = {}
        for d in dets:
            sc = d.score(Tb)
            rd["benign"][d.name] = {
                "fpr": {str(a): float(np.mean(sc > thr[d.name][str(a)])) for a in ALPHAS},
                "fpr_dcal": {str(a): float(np.mean(sc > thr_d[d.name][str(a)])) for a in ALPHAS},
                "first_fa_window": int(np.argmax(sc > thr[d.name][str(ALPHA_MAIN)]))
                if np.any(sc > thr[d.name][str(ALPHA_MAIN)]) else -1}
        rd["benign"]["key"] = key_audit(Tb, np.ones(len(Tb.label), bool), cfg)
        rd["benign"]["loss_db_range"] = [float(stb["loss_db"].min()), float(stb["loss_db"].max())]
        rd["benign"]["ed_range"] = [float(stb["ed"].min()), float(stb["ed"].max())]
        for kind, s in TEST_ATTACKS:
            t0 = int(rng.integers(1440, cfg.n_windows - ATTACK_LEN - 1440))
            T, _ = stream(cfg, rng, drift, kind, s, t0=t0, length=ATTACK_LEN)
            mask = T.label.astype(bool)
            ra = {"t0": t0}
            for d in dets:
                sc = d.score(T)
                th = thr[d.name][str(ALPHA_MAIN)]
                after = np.where(sc[t0:] > th)[0]
                ra[d.name] = {
                    "auc": float(roc_auc_score(mask, sc)),
                    "tpr": {str(a): float(np.mean(sc[mask] > thr[d.name][str(a)])) for a in ALPHAS},
                    "tpr_dcal": {str(a): float(np.mean(sc[mask] > thr_d[d.name][str(a)])) for a in ALPHAS},
                    "fpr_outside_dcal": float(np.mean(sc[~mask] > thr_d[d.name][str(ALPHA_MAIN)])),
                    "fpr_outside": float(np.mean(sc[~mask] > th)),
                    "delay": int(after[0]) if len(after) and after[0] < ATTACK_LEN else -1,
                    "auc_flip": float(roc_auc_score(mask, -sc)),
                }
            ra["key"] = key_audit(T, mask, cfg)
            rd[f"{kind}:{s}"] = ra
        res["test"][str(drift)] = rd
    res["runtime_s"] = time.time() - t_start
    (OUT / f"seed_{seed:02d}.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seeds = [int(a) for a in sys.argv[2:]] or range(n)
    for s in seeds:
        r = run_seed(s)
        print(f"seed {s} done in {r['runtime_s']:.1f}s", flush=True)
