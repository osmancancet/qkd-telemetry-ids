"""Run the full benchmark: one JSON per seed in ../results/.

Usage: python3 run_all.py [n_seeds] [seed ...]
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
DRIFTS = (0.0, 0.25, 1.0, 2.0, 4.0)
CAL_DRIFTS = (0.5, 1.0, 2.0)  # benign drift in the drift-aware calibration data
ATTACK_LEN = 720              # windows (2 h)
PE_BLOCK = 60                 # windows per post-processing block (10 min, 6e10 pulses)
TEST_ATTACKS = [("ir", 0.05), ("ir", 0.2), ("pns", 0.0), ("blind_naive", 0.0),
                ("blind_gain", 0.0), ("blind_nodark", 0.0), ("blind_thresh", 0.0), ("blind_cal", 0.0),
                ("blind_cal_static", 0.0), ("blind_track", 0.0), ("blind_lag", 0.0),
                ("blind_sub", 0.0), ("blind_partial", 0.1), ("loss", 1.0), ("loss", 3.0)]
LAG_WINDOWS = 30            # Blind-lag: windows of public data Eve uses before onset
WITHHOLD = ("DCS", "DCS-CUSUM", "DCS-block", "RF-drift-rand", "DCS-X", "Band-roll")
# extra loss is not an attack on the protocol and is left out of the training labels
TRAIN_ATTACKS = [("ir", 0.05), ("ir", 0.1), ("ir", 0.25), ("ir", 0.5), ("pns", 0.0),
                 ("blind_naive", 0.0)]
# detectors whose default threshold comes from drifting benign data
DRIFT_AWARE = ("IsoForest-drift", "RF-drift-rand", "RF-residuals", "Band-roll")
BLINDED = ("blind_naive", "blind_gain", "blind_nodark")   # blinded detectors: no afterpulses


def yields_for(kind, strength, st, cfg):
    if kind == "honest":
        return q.honest_yields(st["eta"], st["y0"], st["ed"], cfg.e0)
    W = len(st["eta"])
    nom_ed = np.tile(np.array(cfg.e_mis, float), (W, 1))
    if kind == "blind_cal_static":      # emulates the nominal link: no drift at all
        return q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg,
                               eta_eve=np.full(W, cfg.eta_nominal),
                               y0_eve=np.full(W, cfg.y0_nominal), ed_eve=nom_ed)
    if kind == "blind_track":           # tracks the fibre, replays nominal detector values
        return q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg,
                               eta_eve=cfg.eta_bob * 10 ** (-st["loss_db"] / 10),
                               y0_eve=np.full(W, cfg.y0_nominal), ed_eve=nom_ed)
    if kind == "blind_sub":             # exact emulation, but e_d and background lowered
        return q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg,
                               eta_eve=st["eta"], y0_eve=0.3 * st["y0"], ed_eve=0.6 * st["ed"])
    if kind == "blind_lag":             # parameters estimated before onset (see stream)
        return q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg,
                               eta_eve=st["lag_eta"], y0_eve=st["lag_y0"], ed_eve=st["lag_ed"])
    if kind == "blind_partial":         # Blind-naive on a fraction `strength` of pulses
        f = strength
        yh, eh, kh = q.honest_yields(st["eta"], st["y0"], st["ed"], cfg.e0)
        ya, ea, ka = q.attack_yields("blind_naive", st["eta"], st["y0"], st["ed"], cfg)
        y = (1 - f) * yh + f * ya
        e = ((1 - f) * yh[:, None] * eh + f * ya[:, None] * ea) / y[:, None]
        k = f * ya * ka / y
        return y, e, k
    return q.attack_yields(kind, st["eta"], st["y0"], st["ed"], cfg, strength)


def afterpulse_for(kind, st, cfg):
    if kind in BLINDED:
        return False
    if kind in ("blind_cal_static", "blind_track"):
        return np.full(len(st["eta"]), cfg.p_ap)
    if kind == "blind_sub":
        return 0.3 * st["pap"]
    if kind == "blind_lag":             # the estimated background already holds afterpulses
        return False
    return True


def stream(cfg, rng, drift, kind="honest", strength=0.0, n_windows=None, t0=None, length=None):
    """Returns (telemetry with the attack spliced in, honest telemetry of the same
    channel realisation, channel state)."""
    c = q.Config(**{**cfg.__dict__, "drift": drift,
                    "n_windows": n_windows or cfg.n_windows})
    st = q.channel_state(c, rng)
    base = q.sample(c, rng, st, *yields_for("honest", 0, st, c))
    if kind == "honest":
        return base, base, st
    if kind == "blind_lag":
        # Eve estimates (eta, Y0 incl. afterpulses, e_d per basis) from the public counts
        # of the LAG_WINDOWS windows before onset, then tracks only the fibre loss, which
        # she can measure herself; detector parameters stay frozen at their estimates.
        a0 = t0 if t0 is not None else LAG_WINDOWS
        pre = q.Telemetry(*(getattr(base, f)[a0 - LAG_WINDOWS:a0] for f in q.FIELDS))
        e_hat, y_hat, ed_hat = D.dcs_fit(pre)
        W = c.n_windows
        st = dict(st)
        st["lag_eta"] = e_hat.mean() * 10 ** (-(st["loss_db"] - st["loss_db"][a0]) / 10)
        st["lag_y0"] = np.full(W, y_hat.mean())
        st["lag_ed"] = np.tile(ed_hat.mean(0), (W, 1))
    att = q.sample(c, rng, st, *yields_for(kind, strength, st, c),
                   afterpulse=afterpulse_for(kind, st, c))
    mask = np.zeros(c.n_windows, bool)
    if t0 is None:
        mask[:] = True
    else:
        mask[t0:t0 + length] = True
    return q.splice(base, att, mask), base, st


def concat(Ts):
    return q.Telemetry(*(np.concatenate([getattr(T, f) for T in Ts]) for f in q.FIELDS))


def breach_threshold(nZ, KE, eps=1e-10):
    """Largest key length compatible with eps-secrecy given K_E known bits: an eps-secret
    key of length ell has H(K|E) >= (1-eps) ell - (1+eps) h(eps/(1+eps)) (Alicki-Fannes-
    Winter), while H(K|E) <= n_Z - K_E. Breach if ell exceeds the returned value."""
    g = (1 + eps) * float(fk.h2(eps / (1 + eps)))
    return (nZ - KE + g) / (1 - eps)


def key_audit(T, mask, cfg, alarms=None, t0=None):
    """Finite-key length per PE block fully inside `mask`, the breach test and the bound
    checks. The bounds take the block mean of the monitored intensities; the
    nominal-intensity result is kept for comparison. `alarms` maps detector names to
    realised alarm arrays. Release policy: a block is withheld by a detector if that
    detector alarmed in any window of the block; release resumes with the next block.
    Applied to the paired honest copy, the same policy gives the cost in withheld honest
    blocks."""
    idx = np.where(mask)[0]
    out = []
    first = -(-idx[0] // PE_BLOCK) * PE_BLOCK          # blocks on a fixed grid of the stream
    for b0 in range(first, idx[-1] + 1 - PE_BLOCK + 1, PE_BLOCK):
        sl = slice(b0, b0 + PE_BLOCK)
        nZ, nX = T.n[sl, 0].sum(0), T.n[sl, 1].sum(0)
        mZ, mX = T.m[sl, 0].sum(0), T.m[sl, 1].sum(0)
        r = fk.key_length(nZ, nX, mZ, mX, tuple(T.mu_mon[sl].mean(0)), cfg.p_mu)
        rn = fk.key_length(nZ, nX, mZ, mX, cfg.mu, cfg.p_mu)
        KE = T.known[sl, 0].sum()
        d = dict(ell=float(r["ell"]), nZ=float(r["nZ"]), KE=float(KE),
                 ell_nom=float(rn["ell"]), sZ1_nom=float(rn["sZ1"]),
                 rate=float(r["ell"] / (cfg.n_pulses * PE_BLOCK)),
                 sZ1=float(r["sZ1"]), sZ1_true=float(T.n1[sl, 0].sum()),
                 sX1=float(r["sX1"]), sX1_true=float(T.n1[sl, 1].sum()),
                 vX1=float(r["vX1"]), vX1_true=float(T.m1[sl, 1].sum()),
                 EZ=float(r["EZ"]), phi=float(r["phi"]),
                 breach=bool(r["ell"] > breach_threshold(r["nZ"], KE)))
        if alarms is not None:
            d["withheld"] = {k: bool(v[sl].any()) for k, v in alarms.items()}
        out.append(d)
    return out


def realised_alarms(sc, thr, rng):
    t, g = thr
    return (sc > t) | ((sc == t) & (rng.random(len(sc)) < g))


def episodes(al):
    """Number of alarm episodes (maximal runs of consecutive alarmed windows)."""
    al = np.asarray(al, bool)
    return int(np.sum(al[1:] & ~al[:-1]) + (al[0] if len(al) else 0))


def run_seed(seed: int):
    t_start = time.time()
    rng = np.random.default_rng(1000 + seed)
    cfg = q.Config()
    res = dict(seed=seed, config={k: v for k, v in cfg.__dict__.items()})

    # --- calibration: drift-free benign data, and a drift-aware control ----------
    T_fit = stream(cfg, rng, 0.0)[0]
    thr_streams = [stream(cfg, rng, 0.0)[0] for _ in range(3)]
    T_fit_d = concat([stream(cfg, rng, d)[0] for d in CAL_DRIFTS])
    thr_streams_d = [stream(cfg, rng, d)[0] for d in CAL_DRIFTS]

    # --- supervised training sets: stationary and drift-randomised ----------------
    def train_set(randomise):
        dr = (lambda: rng.uniform(0, 4)) if randomise else (lambda: 0.0)
        Ts = [stream(cfg, rng, dr())[0] for _ in range(6 if randomise else 1)]
        for kind, s in TRAIN_ATTACKS:
            Ts.append(stream(cfg, rng, dr(), kind, s, n_windows=2160)[0])
        return concat(Ts)

    Tr_s, Tr_d = train_set(False), train_set(True)
    dets = [D.QBERThreshold(), D.Band().fit(T_fit), D.DCS().fit(T_fit), D.CUSUM().fit(T_fit),
            D.Block().fit(T_fit),
            D.IF("IsoForest", seed).fit(T_fit), D.IF("IsoForest-drift", seed).fit(T_fit_d),
            D.IF("IsoForest-residuals", seed, on_residuals=True).fit(T_fit),
            D.RF("RF-stationary", seed).fit(Tr_s),
            D.RF("RF-drift-rand", seed).fit(Tr_d),
            D.RF("RF-residuals", seed, on_residuals=True).fit(Tr_d, T_fit),
            D.DCS(xonly=True).fit(T_fit), D.BandRoll().fit(T_fit_d)]
    names = [d.name for d in dets]
    # thresholds: 'free' from drift-free benign data, 'drift' from drifting benign data;
    # each detector's default is 'drift' if it is drift-aware by design, else 'free'
    thr = {"free": {}, "drift": {}}
    for d in dets:
        sc0 = np.concatenate([d.score(T) for T in thr_streams])
        scd = np.concatenate([d.score(T) for T in thr_streams_d])
        thr["free"][d.name] = {str(a): D.threshold(sc0, a) for a in ALPHAS}
        thr["drift"][d.name] = {str(a): D.threshold(scd, a) for a in ALPHAS}
        if d.name == "QBER-11%":
            thr["free"][d.name] = thr["drift"][d.name] = {str(a): (0.11, 0.0) for a in ALPHAS}
    default = {n: ("drift" if n in DRIFT_AWARE else "free") for n in names}
    other = {n: ("free" if default[n] == "drift" else "drift") for n in names}
    res["thresholds"] = thr
    res["default_cal"] = default
    # per-window latency of the DCS (score only)
    t1 = time.perf_counter(); dets[2].score(T_fit); res["dcs_latency_ms"] = 1e3 * (time.perf_counter() - t1) / len(T_fit.label)

    rng_al = np.random.default_rng(5000 + seed)
    res["test"] = {}
    for drift in DRIFTS:
        rd = {}
        Tb, _, stb = stream(cfg, rng, drift)
        rd["benign"] = {}
        oracle = {}
        for d in dets:
            sc = d.score(Tb)
            # matched-FPR control: threshold at this drift scale's own benign quantile
            oracle[d.name] = D.threshold(sc, ALPHA_MAIN)
            th, tho = thr[default[d.name]][d.name], thr[other[d.name]][d.name]
            al = realised_alarms(sc, th[str(ALPHA_MAIN)], rng_al)
            rd["benign"][d.name] = {
                "fpr": {a: float(np.mean(D.alarm_prob(sc, th[a]))) for a in th},
                "fpr_ctrl": {a: float(np.mean(D.alarm_prob(sc, tho[a]))) for a in tho},
                "alarms": int(al.sum()), "episodes": episodes(al),
                "first_fa_window": int(np.argmax(al)) if al.any() else -1}
        rd["benign"]["key"] = key_audit(Tb, np.ones(len(Tb.label), bool), cfg)
        rd["benign"]["loss_db_range"] = [float(stb["loss_db"].min()), float(stb["loss_db"].max())]
        rd["benign"]["ed_range"] = [float(stb["ed"].min()), float(stb["ed"].max())]
        for kind, s in TEST_ATTACKS:
            t0 = int(rng.integers(1440, cfg.n_windows - ATTACK_LEN - 1440))
            T, B, _ = stream(cfg, rng, drift, kind, s, t0=t0, length=ATTACK_LEN)
            mask = T.label.astype(bool)
            ra = {"t0": t0}
            als, als_b = {}, {}
            for d in dets:
                sc, sb = d.score(T), d.score(B)
                th, tho = thr[default[d.name]][d.name], thr[other[d.name]][d.name]
                al = realised_alarms(sc, th[str(ALPHA_MAIN)], rng_al)
                hit = np.where(al[t0:t0 + ATTACK_LEN])[0]
                if d.name in WITHHOLD:
                    als[d.name] = al
                    als_b[d.name] = realised_alarms(sb, th[str(ALPHA_MAIN)], rng_al)
                yy = np.r_[np.ones(ATTACK_LEN), np.zeros(ATTACK_LEN)]
                ra[d.name] = {
                    # paired: attacked windows vs the same windows of the honest run
                    "auc": float(roc_auc_score(yy, np.r_[sc[mask], sb[mask]])),
                    "auc_stream": float(roc_auc_score(mask, sc)),
                    "tpr": {a: float(np.mean(D.alarm_prob(sc[mask], th[a]))) for a in th},
                    "tpr_ctrl": {a: float(np.mean(D.alarm_prob(sc[mask], tho[a]))) for a in tho},
                    "fpr_paired": {a: float(np.mean(D.alarm_prob(sb[mask], th[a]))) for a in th},
                    "fpr_outside": float(np.mean(D.alarm_prob(sc[~mask], th[str(ALPHA_MAIN)]))),
                    "delay": int(hit[0]) if len(hit) else -1,
                    "tpr_oracle": float(np.mean(D.alarm_prob(sc[mask], oracle[d.name]))),
                }
            ra["key"] = key_audit(T, mask, cfg, als, t0)
            ra["key_paired"] = key_audit(B, mask, cfg, als_b, t0)
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
