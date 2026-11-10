"""Post-hoc variants that add parameter floors to the DCS.

Defined after the main results exposed the Blind-gain and Blind-nodark blind spots of
the DCS, so they are evaluated on fresh seeds and reported separately.

DCS+P (first attempt, seeds 200-209): one-sided robust z-floors on the fitted log Y0
and on e_d per basis. Its false-alarm rate grew with drift, because benign drift moves
Y0 (temperature, afterpulses that scale with the gain) far beyond the drift-free MAD.

DCS+F (second attempt, defined after DCS+P failed, fresh seeds 300-309): fixed
plausibility floors. A window alarms outright if a fitted e_d falls below half its
drift-free calibration median, or the fitted Y0 below a quarter of its median; otherwise
the score is the DCS statistic. Benign drift raises e_d above its compensated floor and
moves Y0 by tens of percent, so the floors sit far outside benign variation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

import qkdsim as q
import detectors as D
from run_all import stream, ALPHA_MAIN, ATTACK_LEN, DRIFTS, TEST_ATTACKS

OUT = Path(__file__).resolve().parent.parent / "results"


class DCSP:
    name = "DCS+P"

    def fit(self, T):
        self.dcs = D.DCS().fit(T)
        _, y0, ed = D.dcs_fit(T)
        P = np.column_stack([np.log(y0), ed])
        self.loc = np.median(P, 0)
        self.scale = 1.4826 * np.median(np.abs(P - self.loc), 0)
        return self

    def score(self, T):
        _, y0, ed = D.dcs_fit(T)
        z = (np.column_stack([np.log(y0), ed]) - self.loc) / self.scale
        return self.dcs.score(T) + np.sum(np.minimum(z, 0) ** 2, 1)


class DCSF:
    name = "DCS+F"

    def fit(self, T):
        self.dcs = D.DCS().fit(T)
        _, y0, ed = D.dcs_fit(T)
        self.y0m, self.edm = np.median(y0), np.median(ed, 0)
        return self

    def score(self, T):
        _, y0, ed = D.dcs_fit(T)
        bad = (y0 < 0.25 * self.y0m) | np.any(ed < 0.5 * self.edm, 1)
        return self.dcs.score(T) + 1e6 * bad


def run(seed, variant=DCSP):
    rng = np.random.default_rng(seed)
    cfg = q.Config()
    T_fit = stream(cfg, rng, 0.0)[0]
    thr_streams = [stream(cfg, rng, 0.0)[0] for _ in range(3)]
    dets = [D.DCS().fit(T_fit), variant().fit(T_fit)]
    th = {d.name: D.threshold(np.concatenate([d.score(T) for T in thr_streams]), ALPHA_MAIN)
          for d in dets}
    res = {}
    for drift in DRIFTS:
        Tb = stream(cfg, rng, drift)[0]
        rd = {"benign": {d.name: float(np.mean(D.alarm_prob(d.score(Tb), th[d.name])))
                         for d in dets}}
        for kind, s in TEST_ATTACKS:
            t0 = int(rng.integers(1440, cfg.n_windows - ATTACK_LEN - 1440))
            T, B, _ = stream(cfg, rng, drift, kind, s, t0=t0, length=ATTACK_LEN)
            m = T.label.astype(bool)
            yy = np.r_[np.ones(ATTACK_LEN), np.zeros(ATTACK_LEN)]
            rd[f"{kind}:{s}"] = {}
            for d in dets:
                sc, sb = d.score(T), d.score(B)
                rd[f"{kind}:{s}"][d.name] = {
                    "auc": float(roc_auc_score(yy, np.r_[sc[m], sb[m]])),
                    "tpr": float(np.mean(D.alarm_prob(sc[m], th[d.name])))}
        res[str(drift)] = rd
    return res


def stress(seed):
    """Seeds 400-409, d = 1: benign operational changes that cross the DCS+F floors, and
    an attacker who emulates the honest channel with e_d and background just above them."""
    import qkdsim as qq
    rng = np.random.default_rng(seed)
    cfg = q.Config()
    T_fit = stream(cfg, rng, 0.0)[0]
    thr_streams = [stream(cfg, rng, 0.0)[0] for _ in range(3)]
    dets = [D.DCS().fit(T_fit), D.CUSUM().fit(T_fit), D.Block().fit(T_fit),
            D.DCS(xonly=True).fit(T_fit), DCSF().fit(T_fit)]
    th = {d.name: D.threshold(np.concatenate([d.score(T) for T in thr_streams]), ALPHA_MAIN)
          for d in dets}
    out = {}
    W, half = cfg.n_windows, cfg.n_windows // 2
    events = {
        "afterpulse_x0.2_step": lambda st: st["pap"].__setitem__(slice(half, None), 0.2 * st["pap"][half:]),
        "better_compensator": lambda st: st["ed"].__setitem__(slice(None), 0.45 * st["ed"]),
        "loss_step_7dB": lambda st: (st["eta"].__setitem__(slice(half, None), st["eta"][half:] * 10 ** -0.7),
                                     st["loss_db"].__setitem__(slice(half, None), st["loss_db"][half:] + 7)),
        "dark_x5_step": lambda st: st["y0"].__setitem__(slice(half, None), 5 * st["y0"][half:]),
        "efficiency_step_-20pct": lambda st: st["eta"].__setitem__(slice(half, None), 0.8 * st["eta"][half:]),
        "laser_relock_+3pct": lambda st: (st["iscale"].__setitem__(slice(half, None), 1.03 * st["iscale"][half:]),
                                          st["imon"].__setitem__(slice(half, None), 1.03 * st["imon"][half:])),
        "monitor_step_1pct_decoy": lambda st: st["imon"].__setitem__((slice(half, None), 1), 1.01 * st["imon"][half:, 1]),
    }
    c = q.Config(**{**cfg.__dict__, "drift": 1.0})
    for name, ev in events.items():
        st = qq.channel_state(c, rng)
        ev(st)
        Tb = qq.sample(c, rng, st, *qq.honest_yields(st["eta"], st["y0"], st["ed"], c.e0))
        out[name] = {d.name: float(np.mean(D.alarm_prob(d.score(Tb), th[d.name]))) for d in dets}
    t0 = int(rng.integers(1440, W - ATTACK_LEN - 1440))
    T, B, _ = stream(cfg, rng, 1.0, "blind_sub", 0.0, t0=t0, length=ATTACK_LEN)
    m = T.label.astype(bool)
    yy = np.r_[np.ones(ATTACK_LEN), np.zeros(ATTACK_LEN)]
    out["blind_sub"] = {d.name: {"auc": float(roc_auc_score(yy, np.r_[d.score(T)[m], d.score(B)[m]])),
                                 "tpr": float(np.mean(D.alarm_prob(d.score(T)[m], th[d.name])))}
                        for d in dets}
    # margin of benign fitted parameters above the floors at d = 4
    Tb4 = stream(cfg, rng, 4.0)[0]
    _, y0, ed = D.dcs_fit(Tb4)
    f = dets[-1]
    out["margin_d4"] = {"y0_min_over_floor": float(y0.min() / (0.25 * f.y0m)),
                        "ed_min_over_floor": float(np.min(ed / (0.5 * f.edm)))}
    return out


if __name__ == "__main__":
    import sys as _s
    if len(_s.argv) > 1 and _s.argv[1] == "S":
        base = int(_s.argv[2]) if len(_s.argv) > 2 else 400
        R = {s: stress(s) for s in range(base, base + 10)}
        (OUT / "exploratory_stress.json").write_text(json.dumps(R, indent=1))
        for k in R[base]:
            if k == "blind_sub":
                print(k, {n: (round(np.mean([R[s][k][n]["auc"] for s in R]), 3),
                              round(np.mean([R[s][k][n]["tpr"] for s in R]), 3)) for n in R[base][k]})
            elif k == "margin_d4":
                print(k, {n: round(min(R[s][k][n] for s in R), 3) for n in R[base][k]})
            else:
                print(k, {n: round(np.mean([R[s][k][n] for s in R]), 4) for n in R[base][k]})
        _s.exit(0)
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "F"
    var, seeds, name = (DCSP, range(200, 210), "DCS+P") if which == "P" else (DCSF, range(300, 310), "DCS+F")
    if len(sys.argv) > 2:                      # confirmatory run on fresh seeds
        seeds = range(int(sys.argv[2]), int(sys.argv[2]) + 10)
    R = {s: run(s, var) for s in seeds}
    (OUT / f"exploratory_{name.replace('+', '_').lower()}.json").write_text(json.dumps(R, indent=1))
    s0 = seeds[0]
    for d in map(str, DRIFTS):
        print(d, {n: round(np.mean([R[s][d]["benign"][n] for s in R]), 4) for n in ("DCS", name)})
        for a in R[s0][d]:
            if a == "benign":
                continue
            print("  ", a, {n: (round(np.mean([R[s][d][a][n]["auc"] for s in R]), 3),
                               round(np.mean([R[s][d][a][n]["tpr"] for s in R]), 3)) for n in ("DCS", name)})
