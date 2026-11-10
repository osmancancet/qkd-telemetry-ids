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
C = {"DCS": "#2a78d6", "DCS-CUSUM": "#0b3d91", "DCS-block": "#14b8c4", "DCS-X": "#6b8fd6", "Band-roll": "#b8860b", "Band": "#8a6d3b", "IsoForest": "#eb6834",
     "IsoForest-drift": "#1baf7a", "IsoForest-residuals": "#7c3aed",
     "RF-stationary": "#eda100", "RF-drift-rand": "#e87ba4", "RF-residuals": "#52514e",
     "QBER-11%": "#9a9893"}
MK = {"DCS": "o", "DCS-CUSUM": "P", "DCS-block": "*", "DCS-X": "d", "Band-roll": "p", "Band": "X", "IsoForest": "s", "IsoForest-drift": "D",
      "IsoForest-residuals": "h", "RF-stationary": "^", "RF-drift-rand": "v",
      "RF-residuals": "<", "QBER-11%": "x"}
LAB = {"QBER-11%": "QBER > 11%", "Band": "Band", "DCS": "DCS", "DCS-CUSUM": "CUSUM", "DCS-block": "Block", "DCS-X": "DCS-X", "Band-roll": "Band-roll",
       "IsoForest": "IF-stat", "IsoForest-drift": "IF-drift", "IsoForest-residuals": "IF-res",
       "RF-stationary": "RF-stat", "RF-drift-rand": "RF-DR", "RF-residuals": "RF-res"}
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e4e3df",
                     "grid.linewidth": 0.6, "axes.edgecolor": "#52514e", "legend.frameon": False})


def fig_fpr():
    drifts = [0.0, 0.25, 1.0, 2.0, 4.0]
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    shown = ["DCS", "DCS-CUSUM", "DCS-block", "DCS-X", "Band", "Band-roll", "IsoForest", "IsoForest-drift", "IsoForest-residuals",
             "RF-stationary", "RF-drift-rand", "RF-residuals"]
    off = np.linspace(-0.25, 0.25, len(shown))
    for o, dn in zip(off, shown):
        v = np.array([N["fpr"][f"{d}"][dn] for d in drifts])
        m = np.maximum(v[:, 0], 1e-5)
        lo, hi = np.maximum(v[:, 1], 1e-5), np.maximum(v[:, 2], 1e-5)
        ax.errorbar(np.arange(len(drifts)) + o, m, yerr=[m - lo, hi - m], color=C[dn], marker=MK[dn],
                    ms=4.5, lw=1.3, capsize=2, label=LAB[dn])
    ax.axhline(ALPHA_MAIN, color="#52514e", ls="--", lw=1)
    ax.text(3.5, ALPHA_MAIN * 2.0, r"target $\alpha=10^{-3}$", fontsize=8, ha="center", color="#52514e")
    ax.set_yscale("log"); ax.set_ylim(8e-6, 2.0); ax.set_xlim(-0.4, len(drifts) - 0.6)
    ax.set_xticks(range(len(drifts))); ax.set_xticklabels([f"{d:g}" for d in drifts])
    ax.set_xlabel("Drift scale $d$ (0 = drift-free calibration conditions)")
    ax.set_ylabel("Per-window false-alarm rate")
    ax.legend(ncol=1, fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout(); fig.savefig(FIG / "fpr_vs_drift.pdf"); plt.close(fig)


def fig_auc():
    from make_tables import ATT, ALAB, DETS, SUPERVISED, IN_TRAIN
    d = "1.0"
    M = np.array([[N["auc"][d][a][x][0] for x in DETS] for a in ATT])
    H = np.array([[(N["auc"][d][a][x][2] - N["auc"][d][a][x][1]) / 2 for x in DETS] for a in ATT])
    cmap = LinearSegmentedColormap.from_list("div", ["#c2410c", "#f1efe9", "#1d4ed8"])
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, a in enumerate(ATT):
        for j, x in enumerate(DETS):
            col = "white" if abs(M[i, j] - 0.5) > 0.38 else "#0b0b0b"
            star = "*" if (x in SUPERVISED and a in IN_TRAIN) else ""
            ax.text(j, i - 0.13, f"{M[i, j]:.2f}{star}", ha="center", va="center", fontsize=7, color=col)
            ax.text(j, i + 0.25, f"\u00b1{H[i, j]:.2f}", ha="center", va="center", fontsize=5.2, color=col)
    ax.set_xticks(range(len(DETS))); ax.set_xticklabels([LAB[x] for x in DETS], rotation=30, ha="right")
    ax.set_yticks(range(len(ATT)))
    ax.set_yticklabels([ALAB[a].replace("$f=", "f=").replace("$", "") for a in ATT])
    ax.grid(False)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.set_label("Paired ROC AUC (0.5 = chance)")
    fig.tight_layout(); fig.savefig(FIG / "auc_heatmap_d1.pdf"); plt.close(fig)


def fig_trace():
    """One stream at d = 1 for two attacks; DCS and RF-stat scores against thresholds."""
    rng = np.random.default_rng(777)
    cfg = q.Config()
    T_fit = stream(cfg, rng, 0.0)[0]
    thr_streams = [stream(cfg, rng, 0.0)[0] for _ in range(3)]
    Ts = [stream(cfg, rng, 0.0)[0]]
    for kind, s in TRAIN_ATTACKS:
        Ts.append(stream(cfg, rng, 0.0, kind, s, n_windows=2160)[0])
    dcs = D.DCS().fit(T_fit)
    rf = D.RF("RF-stationary", 777).fit(concat(Ts))
    th = {"DCS": D.threshold(np.concatenate([dcs.score(T) for T in thr_streams]), ALPHA_MAIN)[0],
          "RF": D.threshold(np.concatenate([rf.score(T) for T in thr_streams]), ALPHA_MAIN)[0]}
    fig, axes = plt.subplots(2, 2, figsize=(6.6, 3.8), sharex=True)
    t0 = 4320
    for j, (kind, title) in enumerate([("blind_naive", "Blind-naive"), ("blind_cal", "Blind-cal")]):
        T = stream(cfg, rng, 1.0, kind, 0.0, t0=t0, length=720)[0]
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
