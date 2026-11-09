"""Figures for the manuscript (PDF, light print palette)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

import qkdsim as q
import detectors as D
from run_all import stream, concat, TRAIN_ATTACKS, ALPHA_MAIN

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "manuscript" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
N = json.load(open(ROOT / "results" / "numbers.json"))

# categorical slots in fixed order (reference palette, light mode)
C = {"DCS": "#2a78d6", "IsoForest": "#eb6834", "IsoForest-drift": "#1baf7a",
     "RF-stationary": "#eda100", "RF-drift-rand": "#e87ba4", "QBER-11%": "#52514e"}
MK = {"DCS": "o", "IsoForest": "s", "IsoForest-drift": "D", "RF-stationary": "^",
      "RF-drift-rand": "v", "QBER-11%": "x"}
LAB = {"QBER-11%": "QBER > 11%", "DCS": "DCS (ours)", "IsoForest": "IF-stat",
       "IsoForest-drift": "IF-drift", "RF-stationary": "RF-stat", "RF-drift-rand": "RF-DR"}
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e4e3df",
                     "grid.linewidth": 0.6, "axes.edgecolor": "#52514e", "legend.frameon": False})


def fig_fpr():
    drifts = [0.0, 1.0, 2.0, 4.0]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    for dn in ["DCS", "IsoForest", "IsoForest-drift", "RF-stationary", "RF-drift-rand"]:
        m = np.array([N["fpr"][f"{d}"][dn][0] for d in drifts])
        c = np.array([N["fpr"][f"{d}"][dn][1] for d in drifts])
        ax.errorbar(drifts, m, yerr=c, color=C[dn], marker=MK[dn], ms=5, lw=1.6,
                    capsize=2, label=LAB[dn])
    ax.axhline(ALPHA_MAIN, color="#52514e", ls="--", lw=1)
    ax.text(3.0, ALPHA_MAIN * 0.62, r"target $\alpha=10^{-3}$", fontsize=8, ha="center", color="#52514e")
    ax.set_yscale("log"); ax.set_ylim(3e-4, 2.0); ax.set_xlim(-0.2, 4.2)
    ax.set_xticks(drifts)
    ax.set_xlabel("Drift scale $d$ (0 = calibration conditions)")
    ax.set_ylabel("Per-window false-alarm rate")
    ax.legend(ncol=2, fontsize=7.5, loc="center right", bbox_to_anchor=(1.0, 0.42))
    fig.tight_layout(); fig.savefig(FIG / "fpr_vs_drift.pdf"); plt.close(fig)


def fig_auc():
    from make_tables import ATT, ALAB, DETS
    d = "1.0"
    M = np.array([[N["auc"][d][a][x][0] for x in DETS] for a in ATT])
    cmap = LinearSegmentedColormap.from_list("div", ["#c2410c", "#f1efe9", "#1d4ed8"])
    fig, ax = plt.subplots(figsize=(5.4, 3.9))
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(M[i, j] - 0.5) > 0.38 else "#0b0b0b")
    ax.set_xticks(range(len(DETS))); ax.set_xticklabels([LAB[x] for x in DETS], rotation=30, ha="right")
    ax.set_yticks(range(len(ATT)))
    ax.set_yticklabels([ALAB[a].replace("$f=", "f=").replace("$", "") for a in ATT])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02); cb.set_label("ROC AUC (0.5 = chance)")
    fig.tight_layout(); fig.savefig(FIG / "auc_heatmap_d1.pdf"); plt.close(fig)


def fig_trace():
    """One stream at d = 1 for two attacks; DCS and RF-stat scores against thresholds."""
    rng = np.random.default_rng(777)
    cfg = q.Config()
    T_fit = stream(cfg, rng, 0.0)[0]
    T_thr = concat([stream(cfg, rng, 0.0)[0] for _ in range(3)])
    Ts = [stream(cfg, rng, 0.0)[0]]
    for kind, s in TRAIN_ATTACKS:
        Ts.append(stream(cfg, rng, 0.0, kind, s, n_windows=2160)[0])
    Ttr = concat(Ts)
    dcs = D.DCS(cfg.mu).fit(T_fit)
    rf = D.RF("RF-stationary", 777).fit(D.features(Ttr), Ttr.label)
    th = {"DCS": D.threshold(dcs.score(T_thr), ALPHA_MAIN), "RF": D.threshold(rf.score(T_thr), ALPHA_MAIN)}
    fig, axes = plt.subplots(2, 2, figsize=(6.6, 3.8), sharex=True)
    t0 = 4320
    for j, (kind, title) in enumerate([("blind_naive", "Blind-naive"), ("blind_cal", "Blind-cal")]):
        T, _ = stream(cfg, rng, 1.0, kind, 0.0, t0=t0, length=720)
        h = np.arange(len(T.label)) * cfg.window_s / 3600
        for i, (name, det) in enumerate([("DCS", dcs), ("RF", rf)]):
            ax = axes[i, j]
            sc = det.score(T)
            ax.axvspan(h[t0], h[t0 + 719], color="#e4e3df", lw=0)
            ax.plot(h, sc, color=C["DCS"] if name == "DCS" else C["RF-stationary"], lw=0.6)
            ax.axhline(th[name], color="#0b0b0b", ls="--", lw=0.9)
            if name == "DCS":
                ax.set_yscale("log")
            ax.set_title(f"{title}: {'DCS' if name == 'DCS' else 'RF-stat'}", fontsize=8.5)
            if j == 0:
                ax.set_ylabel("DCS statistic" if name == "DCS" else "P(attack)")
            if i == 1:
                ax.set_xlabel("Time (h)")
    fig.tight_layout(); fig.savefig(FIG / "trace_d1.pdf"); plt.close(fig)


if __name__ == "__main__":
    fig_fpr(); fig_auc(); fig_trace()
    print("figures written")
